"""Group-agent <-> simulated-venue negotiation (PROPOSED D008, supporting feature).

Information boundary:
  - The venue persona receives a VenueBrief (activity, group size, window, the
    group's TOTAL budget, currency) plus the group agent's latest counter. Never
    member ids, names or individual budgets.
  - totalBudgetMinor = groupSize x the LOWEST member ceiling, so any total within
    it splits equally under every member's ceiling.
Code, not Muse, enforces:
  - the group agent can only accept an offer within the limit, and can only
    counter downward and within the limit;
  - the simulated venue cannot price below its persona floor;
  - a final per-person check against EVERY member ceiling before a Deal exists;
  - a Deal is only ``awaiting_approval``. Nothing is booked or paid here; Kai's
    workflow collects each member's explicit approval.
Venue businesses are simulated and every offer and deal says so.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable, Mapping

from server.providers.errors import ProviderError
from server.providers.port import GenerateRequest, MusePort

from . import public_text, wire
from .catalog import SYNTHETIC_VENUE_PERSONAS, VenuePersona
from .errors import PlanningError
from .prompts_v11 import NEGOTIATE_PROMPT_VERSION, VENUE_PERSONA_PROMPT_VERSION

Telemetry = Callable[[dict[str, Any]], None]


def per_person(total: int, size: int) -> int:
    return -(-total // size)


def group_limit(participants: list[dict]) -> tuple[int, int]:
    """(groupSize, totalBudgetMinor): size x lowest ceiling."""
    size = len(participants)
    return size, size * min(p["intent"]["maxBudgetMinor"] for p in participants)


class Negotiator:
    def __init__(self, muse: MusePort, *, personas: Mapping[str, VenuePersona] = SYNTHETIC_VENUE_PERSONAS,
                 new_id: Callable[[], str] | None = None, semantic_attempts: int = 2,
                 telemetry: Telemetry | None = None) -> None:
        self._muse = muse
        self._personas = personas
        self._new_id = new_id or (lambda: "deal_" + uuid.uuid4().hex)
        self._attempts = max(1, min(semantic_attempts, 3))
        self._telemetry = telemetry or (lambda _r: None)

    async def negotiate(self, inp: dict) -> dict:
        try:
            wire.negotiation_input(inp)
        except wire.ContractError as exc:
            raise PlanningError("INVALID_INPUT", f"invalid NegotiationInput at {exc.path}") from None
        opp, parts = inp["opportunity"], inp["participants"]
        if any(p["intent"]["communityId"] != opp["communityId"] for p in parts):
            raise PlanningError("INVALID_INPUT", "participant outside opportunity community")
        if any(p["intent"]["currency"] != opp["currency"] for p in parts):
            raise PlanningError("INVALID_INPUT", "participant currency differs from opportunity")
        persona = self._personas.get(opp["venueId"])
        if persona is None:
            raise PlanningError("INVALID_INPUT", "venue has no simulated business assistant")

        size, limit = group_limit(parts)
        brief = wire.venue_brief({
            "negotiationId": inp["negotiationId"], "venueId": opp["venueId"], "activity": opp["activity"],
            "groupSize": size, "window": dict(opp["window"]), "totalBudgetMinor": limit,
            "currency": opp["currency"],
        })
        rid, max_rounds = inp["context"]["requestId"], inp["maxRounds"]
        turns: list[dict] = []
        counter: dict | None = None
        history: list[int] = []

        def done(result: dict) -> dict:
            self._telemetry({"requestId": rid, "task": "negotiate", "rounds": len(history) + 1,
                             "outcome": result["status"], "reason": result.get("reason")})
            return wire.negotiation_result(result)

        for rnd in range(1, max_rounds + 1):
            offer = await self._venue_turn(brief, persona, rnd, max_rounds, counter, rid)
            turns.append({"by": "venue", "offer": offer})
            if offer["action"] == "decline":
                return done({"status": "no_deal", "reason": "venue_declined", "turns": turns})
            counter = await self._agent_turn(brief, offer, rnd, max_rounds, history, rid)
            turns.append({"by": "group_agent", "counter": counter})
            if counter["action"] == "accept":
                return done({"status": "deal", "deal": self._deal(brief, opp, offer, counter, parts, rnd), "turns": turns})
            if counter["action"] == "walk_away":
                return done({"status": "no_deal", "reason": "over_budget", "turns": turns})
            history.append(offer["totalPriceMinor"])
        return done({"status": "no_deal", "reason": "rounds_exhausted", "turns": turns})

    # ---------------------------------------------------------------- turns
    async def _venue_turn(self, brief: dict, persona: VenuePersona, rnd: int, max_rounds: int,
                          counter: dict | None, rid: str) -> dict:
        size = brief["groupSize"]
        floor_total = persona.floor_price_per_person_minor * size
        payload = {
            "persona": {"venueId": brief["venueId"], "style": persona.style, "simulated": True,
                        "listPricePerPersonMinor": persona.list_price_per_person_minor,
                        "floorPricePerPersonMinor": persona.floor_price_per_person_minor},
            "request": {k: brief[k] for k in ("activity", "groupSize", "window", "totalBudgetMinor", "currency")},
            "round": rnd, "maxRounds": max_rounds,
            "groupCounter": None if counter is None else {"totalPriceMinor": counter["totalPriceMinor"],
                                                          "message": counter["message"]},
        }

        def check(out: dict) -> list[str]:
            errors = []
            if out["action"] != "decline" and out["totalPriceMinor"] < floor_total:
                errors.append("price: totalPriceMinor is below floorPricePerPersonMinor x groupSize")
            bad = public_text.violations(out["terms"])
            if bad:
                errors.append(f"public_text: terms contains disallowed content ({', '.join(bad)})")
            return errors

        out, evidence = await self._ask("venue_persona", VENUE_PERSONA_PROMPT_VERSION, payload, check, rid)
        return wire.venue_offer({
            "negotiationId": brief["negotiationId"], "round": rnd, "venueId": brief["venueId"],
            "action": out["action"], "window": dict(brief["window"]), "groupSize": size,
            "totalPriceMinor": out["totalPriceMinor"], "currency": brief["currency"],
            "terms": out["terms"].strip(), "isSimulated": True, "evidence": dict(evidence),
        })

    async def _agent_turn(self, brief: dict, offer: dict, rnd: int, max_rounds: int,
                          history: list[int], rid: str) -> dict:
        limit, asked = brief["totalBudgetMinor"], offer["totalPriceMinor"]
        payload = {
            "brief": {k: brief[k] for k in ("activity", "groupSize", "window", "totalBudgetMinor", "currency")},
            "round": rnd, "maxRounds": max_rounds,
            "venueOffer": {"action": offer["action"], "totalPriceMinor": asked, "terms": offer["terms"]},
            "history": history,
        }

        def check(out: dict) -> list[str]:
            errors = []
            if out["action"] == "accept":
                if asked > limit:
                    errors.append("accept: venueOffer.totalPriceMinor exceeds brief.totalBudgetMinor; counter or walk_away")
                elif out["totalPriceMinor"] != asked:
                    errors.append("accept: totalPriceMinor must equal venueOffer.totalPriceMinor")
            elif out["action"] == "counter":
                if out["totalPriceMinor"] > limit:
                    errors.append("counter: totalPriceMinor exceeds brief.totalBudgetMinor")
                if out["totalPriceMinor"] >= asked:
                    errors.append("counter: totalPriceMinor must be below venueOffer.totalPriceMinor")
            bad = public_text.violations(out["message"])
            if bad:
                errors.append(f"public_text: message contains disallowed content ({', '.join(bad)})")
            return errors

        out, evidence = await self._ask("negotiate", NEGOTIATE_PROMPT_VERSION, payload, check, rid)
        price = asked if out["action"] == "accept" else out["totalPriceMinor"]
        return wire.counteroffer({
            "negotiationId": brief["negotiationId"], "round": rnd, "action": out["action"],
            "totalPriceMinor": price, "currency": brief["currency"], "window": dict(brief["window"]),
            "message": out["message"].strip(), "evidence": dict(evidence),
        })

    async def _ask(self, task: str, version: str, payload: dict, check: Callable[[dict], list[str]],
                   rid: str) -> tuple[dict, dict]:
        correction: str | None = None
        for _ in range(self._attempts):
            try:
                gen = await self._muse.generate(GenerateRequest(
                    task=task, request_id=rid, prompt_version=version, payload=payload, correction=correction,  # type: ignore[arg-type]
                ))
            except ProviderError as exc:
                raise PlanningError.from_provider(exc) from None
            errors = check(gen.output)
            if not errors:
                return gen.output, gen.evidence
            correction = "; ".join(errors)[:580]
        raise PlanningError("PROVIDER_UNAVAILABLE", f"model did not produce a valid {task} turn", retryable=True)

    # ----------------------------------------------------------------- deal
    def _deal(self, brief: dict, opp: dict, offer: dict, counter: dict, parts: list[dict], rnd: int) -> dict:
        total, size = offer["totalPriceMinor"], brief["groupSize"]
        each = per_person(total, size)
        # Defense in depth: re-check EVERY member, independent of the brief arithmetic.
        if total > brief["totalBudgetMinor"] or any(each > p["intent"]["maxBudgetMinor"] for p in parts):
            raise PlanningError("PROVIDER_UNAVAILABLE", "agreed price exceeds a member ceiling", retryable=False)
        return wire.deal({
            "dealId": self._new_id(), "negotiationId": brief["negotiationId"],
            "opportunityId": opp["opportunityId"], "venueId": brief["venueId"],
            "window": dict(brief["window"]), "groupSize": size,
            "totalPriceMinor": total, "perPersonMinor": each, "currency": brief["currency"],
            "terms": offer["terms"], "rounds": rnd, "status": "awaiting_approval",
            "isSimulated": True, "evidence": dict(counter["evidence"]),
        })


__all__ = ["Negotiator", "group_limit", "per_person"]
