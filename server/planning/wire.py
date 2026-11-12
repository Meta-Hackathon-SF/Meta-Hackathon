"""Runtime validators for contract 1.0.0 shapes used at the planning boundary.

TypeScript declarations in contracts/protocol.ts are not validation; these
functions are. Each raises ContractError(path, message) on the first problem
and rejects unknown keys so private or unexpected fields cannot ride along.
Shapes marked PROPOSED are pending ACK in docs/DECISIONS.md (D005).
"""
from __future__ import annotations

import re
from typing import Any, Iterable

from .timeutil import parse_utc

CONTRACT_VERSION = "1.0.0"
MODES = ("live", "fixture", "replay")
_CURRENCY = re.compile(r"^[A-Z]{3}$")


class ContractError(ValueError):
    def __init__(self, path: str, message: str) -> None:
        super().__init__(f"{path}: {message}")
        self.path = path
        self.detail = message


def _obj(v: Any, path: str, required: Iterable[str], optional: Iterable[str] = ()) -> dict:
    if not isinstance(v, dict):
        raise ContractError(path, "expected object")
    req, opt = set(required), set(optional)
    for k in v:
        if k not in req and k not in opt:
            raise ContractError(f"{path}.{k}", "unexpected field")
    for k in req:
        if k not in v:
            raise ContractError(f"{path}.{k}", "missing field")
    return v


def _str(v: Any, path: str, *, max_len: int = 200, min_len: int = 1) -> str:
    if not isinstance(v, str) or not (min_len <= len(v) <= max_len):
        raise ContractError(path, f"expected string of length {min_len}..{max_len}")
    return v


def _id(v: Any, path: str) -> str:
    return _str(v, path, max_len=128)


def _int(v: Any, path: str, *, lo: int = 0, hi: int = 10**9) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or not (lo <= v <= hi):
        raise ContractError(path, f"expected integer in [{lo}, {hi}]")
    return v


def _bool(v: Any, path: str) -> bool:
    if not isinstance(v, bool):
        raise ContractError(path, "expected boolean")
    return v


def _lit(v: Any, path: str, *allowed: Any) -> Any:
    if v not in allowed:
        raise ContractError(path, f"expected one of {list(allowed)}")
    return v


def _time(v: Any, path: str) -> str:
    try:
        parse_utc(v)
    except (ValueError, TypeError):
        raise ContractError(path, "expected RFC3339 UTC timestamp") from None
    return v


def _list(v: Any, path: str, *, max_items: int = 100, min_items: int = 0) -> list:
    if not isinstance(v, list) or not (min_items <= len(v) <= max_items):
        raise ContractError(path, f"expected array of {min_items}..{max_items} items")
    return v


def _currency(v: Any, path: str) -> str:
    if not isinstance(v, str) or not _CURRENCY.match(v):
        raise ContractError(path, "expected ISO 4217 currency code")
    return v


def window(v: Any, path: str = "window") -> dict:
    _obj(v, path, ("start", "end"))
    _time(v["start"], f"{path}.start")
    _time(v["end"], f"{path}.end")
    if parse_utc(v["start"]) >= parse_utc(v["end"]):
        raise ContractError(path, "start must be before end")
    return v


def windows(v: Any, path: str, *, max_items: int = 50, min_items: int = 0) -> list:
    for i, w in enumerate(_list(v, path, max_items=max_items, min_items=min_items)):
        window(w, f"{path}[{i}]")
    return v


def context(v: Any, path: str = "context") -> dict:
    _obj(v, path, ("requestId", "contractVersion", "mode"))
    _id(v["requestId"], f"{path}.requestId")
    _lit(v["contractVersion"], f"{path}.contractVersion", CONTRACT_VERSION)
    _lit(v["mode"], f"{path}.mode", *MODES)
    return v


def model_evidence(v: Any, path: str = "evidence") -> dict:
    _obj(v, path, ("model", "source", "generatedAt", "latencyMs"))
    _str(v["model"], f"{path}.model", max_len=100)
    _lit(v["source"], f"{path}.source", "live", "replay")
    _time(v["generatedAt"], f"{path}.generatedAt")
    _int(v["latencyMs"], f"{path}.latencyMs", hi=10**7)
    return v


def private_intent(v: Any, path: str = "intent") -> dict:
    _obj(v, path, (
        "participantId", "communityId", "intentVersion", "goal", "interests", "areaId",
        "timeZone", "availability", "maxBudgetMinor", "currency", "maxDurationMinutes",
        "groupPreference", "consentVersion", "confirmedAt",
    ))
    _id(v["participantId"], f"{path}.participantId")
    _id(v["communityId"], f"{path}.communityId")
    _int(v["intentVersion"], f"{path}.intentVersion", lo=1)
    _str(v["goal"], f"{path}.goal", max_len=280)
    for i, s in enumerate(_list(v["interests"], f"{path}.interests", max_items=20)):
        _str(s, f"{path}.interests[{i}]", max_len=60)
    _id(v["areaId"], f"{path}.areaId")
    _str(v["timeZone"], f"{path}.timeZone", max_len=64)
    windows(v["availability"], f"{path}.availability")
    _int(v["maxBudgetMinor"], f"{path}.maxBudgetMinor", hi=10**7)
    _currency(v["currency"], f"{path}.currency")
    _int(v["maxDurationMinutes"], f"{path}.maxDurationMinutes", lo=1, hi=24 * 60)
    _lit(v["groupPreference"], f"{path}.groupPreference", "small")
    _int(v["consentVersion"], f"{path}.consentVersion", lo=1)
    _time(v["confirmedAt"], f"{path}.confirmedAt")
    return v


def public_participant(v: Any, path: str = "publicProfile") -> dict:
    _obj(v, path, ("participantId", "displayName", "publicInterests", "isSynthetic"))
    _id(v["participantId"], f"{path}.participantId")
    _str(v["displayName"], f"{path}.displayName", max_len=80)
    for i, s in enumerate(_list(v["publicInterests"], f"{path}.publicInterests", max_items=20)):
        _str(s, f"{path}.publicInterests[{i}]", max_len=60)
    _bool(v["isSynthetic"], f"{path}.isSynthetic")
    return v


def candidate(v: Any, path: str = "candidate") -> dict:
    _obj(v, path, ("intent", "publicProfile"))
    private_intent(v["intent"], f"{path}.intent")
    public_participant(v["publicProfile"], f"{path}.publicProfile")
    if v["intent"]["participantId"] != v["publicProfile"]["participantId"]:
        raise ContractError(path, "intent and publicProfile participantId differ")
    return v


def member_version(v: Any, path: str) -> dict:
    _obj(v, path, ("participantId", "intentVersion", "consentVersion"))
    _id(v["participantId"], f"{path}.participantId")
    _int(v["intentVersion"], f"{path}.intentVersion", lo=1)
    _int(v["consentVersion"], f"{path}.consentVersion", lo=1)
    return v


def member_versions(v: Any, path: str) -> list:
    for i, m in enumerate(_list(v, path, min_items=3, max_items=5)):
        member_version(m, f"{path}[{i}]")
    ids = [m["participantId"] for m in v]
    if len(set(ids)) != len(ids):
        raise ContractError(path, "duplicate participant")
    return v


def group_proposal(v: Any, path: str = "proposal") -> dict:
    _obj(v, path, (
        "proposalId", "communityId", "revision", "memberIds", "memberVersions",
        "feasibleWindows", "sharedInterests", "publicRationale", "evidence",
    ))
    _id(v["proposalId"], f"{path}.proposalId")
    _id(v["communityId"], f"{path}.communityId")
    _int(v["revision"], f"{path}.revision", lo=1)
    ids = _list(v["memberIds"], f"{path}.memberIds", min_items=3, max_items=5)
    for i, m in enumerate(ids):
        _id(m, f"{path}.memberIds[{i}]")
    if len(set(ids)) != len(ids):
        raise ContractError(f"{path}.memberIds", "duplicate participant")
    member_versions(v["memberVersions"], f"{path}.memberVersions")
    if sorted(ids) != sorted(m["participantId"] for m in v["memberVersions"]):
        raise ContractError(f"{path}.memberVersions", "must cover exactly memberIds")
    windows(v["feasibleWindows"], f"{path}.feasibleWindows")
    for i, s in enumerate(_list(v["sharedInterests"], f"{path}.sharedInterests", max_items=20)):
        _str(s, f"{path}.sharedInterests[{i}]", max_len=60)
    _str(v["publicRationale"], f"{path}.publicRationale", max_len=600)
    model_evidence(v["evidence"], f"{path}.evidence")
    return v


def venue(v: Any, path: str = "venue") -> dict:
    _obj(v, path, ("venueId", "name", "areaId", "publicAddress", "isPublic", "openingWindows"))
    _id(v["venueId"], f"{path}.venueId")
    _str(v["name"], f"{path}.name", max_len=120)
    _id(v["areaId"], f"{path}.areaId")
    _str(v["publicAddress"], f"{path}.publicAddress", max_len=200)
    _lit(v["isPublic"], f"{path}.isPublic", True)
    windows(v["openingWindows"], f"{path}.openingWindows", max_items=100)
    return v


def quest_plan(v: Any, path: str = "plan") -> dict:
    _obj(v, path, (
        "planId", "proposalId", "revision", "basedOnRevision", "memberVersions", "title",
        "activity", "collaborationTask", "venueId", "start", "end", "timeZone",
        "costPerPersonMinor", "currency", "minimumSize", "maximumSize", "publicRationale",
        "opener", "evidence",
    ))
    _id(v["planId"], f"{path}.planId")
    _id(v["proposalId"], f"{path}.proposalId")
    _int(v["revision"], f"{path}.revision", lo=1)
    if v["basedOnRevision"] is not None:
        _int(v["basedOnRevision"], f"{path}.basedOnRevision", lo=1)
        if v["basedOnRevision"] >= v["revision"]:
            raise ContractError(f"{path}.basedOnRevision", "must precede revision")
    member_versions(v["memberVersions"], f"{path}.memberVersions")
    _str(v["title"], f"{path}.title", max_len=80)
    _str(v["activity"], f"{path}.activity", max_len=400)
    _str(v["collaborationTask"], f"{path}.collaborationTask", max_len=400)
    _id(v["venueId"], f"{path}.venueId")
    _time(v["start"], f"{path}.start")
    _time(v["end"], f"{path}.end")
    if parse_utc(v["start"]) >= parse_utc(v["end"]):
        raise ContractError(path, "start must be before end")
    _str(v["timeZone"], f"{path}.timeZone", max_len=64)
    _int(v["costPerPersonMinor"], f"{path}.costPerPersonMinor", hi=10**7)
    _currency(v["currency"], f"{path}.currency")
    _lit(v["minimumSize"], f"{path}.minimumSize", 3)
    _lit(v["maximumSize"], f"{path}.maximumSize", 5)
    _str(v["publicRationale"], f"{path}.publicRationale", max_len=600)
    _str(v["opener"], f"{path}.opener", max_len=600)
    model_evidence(v["evidence"], f"{path}.evidence")
    return v


def plan_input(v: Any, path: str = "planInput") -> dict:
    _obj(v, path, ("context", "proposal", "participants", "venues"), ("previousPlan", "changeSummary"))
    context(v["context"], f"{path}.context")
    group_proposal(v["proposal"], f"{path}.proposal")
    for i, c in enumerate(_list(v["participants"], f"{path}.participants", min_items=3, max_items=5)):
        candidate(c, f"{path}.participants[{i}]")
    for i, ven in enumerate(_list(v["venues"], f"{path}.venues", max_items=200)):
        venue(ven, f"{path}.venues[{i}]")
    if "previousPlan" in v:
        quest_plan(v["previousPlan"], f"{path}.previousPlan")
    if "changeSummary" in v:
        _str(v["changeSummary"], f"{path}.changeSummary", max_len=400)
    return v


def plan_result(v: Any, path: str = "planResult") -> dict:
    if not isinstance(v, dict):
        raise ContractError(path, "expected object")
    status = v.get("status")
    if status == "proposed":
        _obj(v, path, ("status", "plan"))
        quest_plan(v["plan"], f"{path}.plan")
    elif status == "needs_input":
        _obj(v, path, ("status", "fields", "question"))
        for i, f in enumerate(_list(v["fields"], f"{path}.fields", min_items=1, max_items=10)):
            _str(f, f"{path}.fields[{i}]", max_len=60)
        _str(v["question"], f"{path}.question", max_len=300)
    elif status == "no_feasible_plan":
        _obj(v, path, ("status", "reason"))
        _str(v["reason"], f"{path}.reason", max_len=300)
    else:
        raise ContractError(f"{path}.status", "unknown status")
    return v


def continuation_input(v: Any, path: str = "continuationInput") -> dict:
    _obj(v, path, ("context", "questId", "priorPlan", "feedback", "simulateTimeSkip"))
    context(v["context"], f"{path}.context")
    _id(v["questId"], f"{path}.questId")
    quest_plan(v["priorPlan"], f"{path}.priorPlan")
    seen: set[str] = set()
    for i, f in enumerate(_list(v["feedback"], f"{path}.feedback", max_items=5)):
        p = f"{path}.feedback[{i}]"
        _obj(f, p, ("participantId", "attended", "wantsReturn"))
        _id(f["participantId"], f"{p}.participantId")
        if f["attended"] is not None:
            _bool(f["attended"], f"{p}.attended")
        _bool(f["wantsReturn"], f"{p}.wantsReturn")
        if f["participantId"] in seen:
            raise ContractError(p, "duplicate feedback participant")
        seen.add(f["participantId"])
    _bool(v["simulateTimeSkip"], f"{path}.simulateTimeSkip")
    return v


def continuation(v: Any, path: str = "continuation") -> dict:
    _obj(v, path, ("questId", "proposedHostId", "invitationText", "nextActivity", "evidence"))
    _id(v["questId"], f"{path}.questId")
    if v["proposedHostId"] is not None:
        _id(v["proposedHostId"], f"{path}.proposedHostId")
    _str(v["invitationText"], f"{path}.invitationText", max_len=600)
    _str(v["nextActivity"], f"{path}.nextActivity", max_len=400)
    model_evidence(v["evidence"], f"{path}.evidence")
    return v


# --- PROPOSED (D005): intent extraction wire shapes -------------------------
INTENT_FIELDS = ("goal", "interests", "areaId", "availability", "maxBudgetMinor", "maxDurationMinutes")


def intent_draft(v: Any, path: str = "draft") -> dict:
    _obj(v, path, (
        "communityId", "goal", "interests", "areaId", "timeZone", "availability",
        "maxBudgetMinor", "currency", "maxDurationMinutes", "groupPreference",
    ))
    _id(v["communityId"], f"{path}.communityId")
    if v["goal"] is not None:
        _str(v["goal"], f"{path}.goal", max_len=280)
    for i, s in enumerate(_list(v["interests"], f"{path}.interests", max_items=8)):
        _str(s, f"{path}.interests[{i}]", max_len=40)
    if v["areaId"] is not None:
        _id(v["areaId"], f"{path}.areaId")
    _str(v["timeZone"], f"{path}.timeZone", max_len=64)
    windows(v["availability"], f"{path}.availability", max_items=6)
    if v["maxBudgetMinor"] is not None:
        _int(v["maxBudgetMinor"], f"{path}.maxBudgetMinor", hi=10**7)
    _currency(v["currency"], f"{path}.currency")
    if v["maxDurationMinutes"] is not None:
        _int(v["maxDurationMinutes"], f"{path}.maxDurationMinutes", lo=1, hi=24 * 60)
    _lit(v["groupPreference"], f"{path}.groupPreference", "small")
    return v


def extraction_result(v: Any, path: str = "extraction") -> dict:
    _obj(v, path, ("status", "draft", "missingFields", "questions", "evidence"))
    _lit(v["status"], f"{path}.status", "draft")
    intent_draft(v["draft"], f"{path}.draft")
    for i, f in enumerate(_list(v["missingFields"], f"{path}.missingFields", max_items=len(INTENT_FIELDS))):
        _lit(f, f"{path}.missingFields[{i}]", *INTENT_FIELDS)
    for i, q in enumerate(_list(v["questions"], f"{path}.questions", max_items=len(INTENT_FIELDS))):
        _obj(q, f"{path}.questions[{i}]", ("field", "question"))
        _lit(q["field"], f"{path}.questions[{i}].field", *INTENT_FIELDS)
        _str(q["question"], f"{path}.questions[{i}].question", max_len=200)
    model_evidence(v["evidence"], f"{path}.evidence")
    return v


# --- PROPOSED (D008, target 1.1.0): preferences, opportunities, negotiation, challenges
ENERGY = ("low", "medium", "high")
SOCIAL_COMFORT = ("quiet", "balanced", "outgoing")
PREFERENCE_FIELDS = ("availability", "maxBudgetMinor", "areaId", "interests", "energy", "socialComfort")
OPPORTUNITY_SOURCES = ("venue_offer", "group_event", "member_idea", "muse_created")
MAX_GROUP = 5
MIN_GROUP = 3


def _nullable(v: Any, check, *args, **kwargs) -> Any:
    return None if v is None else check(v, *args, **kwargs)


def _strings(v: Any, path: str, *, max_items: int, max_len: int) -> list:
    for i, s in enumerate(_list(v, path, max_items=max_items)):
        _str(s, f"{path}[{i}]", max_len=max_len)
    return v


def preference_profile(v: Any, path: str = "profile") -> dict:
    _obj(v, path, (
        "communityId", "availability", "timeZone", "maxBudgetMinor", "currency", "areaId",
        "interests", "avoid", "energy", "socialComfort", "openToNew",
    ))
    _id(v["communityId"], f"{path}.communityId")
    windows(v["availability"], f"{path}.availability", max_items=6)
    _str(v["timeZone"], f"{path}.timeZone", max_len=64)
    _nullable(v["maxBudgetMinor"], _int, f"{path}.maxBudgetMinor", hi=10**7)
    _currency(v["currency"], f"{path}.currency")
    _nullable(v["areaId"], _id, f"{path}.areaId")
    _strings(v["interests"], f"{path}.interests", max_items=8, max_len=40)
    _strings(v["avoid"], f"{path}.avoid", max_items=5, max_len=40)
    if v["energy"] is not None:
        _lit(v["energy"], f"{path}.energy", *ENERGY)
    if v["socialComfort"] is not None:
        _lit(v["socialComfort"], f"{path}.socialComfort", *SOCIAL_COMFORT)
    _nullable(v["openToNew"], _bool, f"{path}.openToNew")
    return v


def preference_extraction_request(v: Any, path: str = "request") -> dict:
    _obj(v, path, ("communityId", "transcript"), ("followUp",))
    _id(v["communityId"], f"{path}.communityId")
    _str(v["transcript"], f"{path}.transcript", max_len=2000)
    if "followUp" in v:
        f = _obj(v["followUp"], f"{path}.followUp", ("field", "answer", "previous"))
        _lit(f["field"], f"{path}.followUp.field", *PREFERENCE_FIELDS)
        _str(f["answer"], f"{path}.followUp.answer", max_len=500)
        preference_profile(f["previous"], f"{path}.followUp.previous")
        if f["previous"]["communityId"] != v["communityId"]:
            raise ContractError(f"{path}.followUp.previous.communityId", "must match communityId")
    return v


def preference_extraction_result(v: Any, path: str = "extraction") -> dict:
    _obj(v, path, ("status", "profile", "missingFields", "followUp", "evidence"))
    _lit(v["status"], f"{path}.status", "needs_follow_up", "ready_to_confirm")
    preference_profile(v["profile"], f"{path}.profile")
    missing = _list(v["missingFields"], f"{path}.missingFields", max_items=len(PREFERENCE_FIELDS))
    for i, f in enumerate(missing):
        _lit(f, f"{path}.missingFields[{i}]", *PREFERENCE_FIELDS)
    if v["followUp"] is None:
        if v["status"] == "needs_follow_up":
            raise ContractError(f"{path}.followUp", "required when status is needs_follow_up")
    else:
        if v["status"] != "needs_follow_up":
            raise ContractError(f"{path}.followUp", "only allowed when status is needs_follow_up")
        _obj(v["followUp"], f"{path}.followUp", ("field", "question"))
        _lit(v["followUp"]["field"], f"{path}.followUp.field", *missing)
        _str(v["followUp"]["question"], f"{path}.followUp.question", max_len=200)
    model_evidence(v["evidence"], f"{path}.evidence")
    return v


def preference_traits(v: Any, path: str = "preferences") -> dict:
    _obj(v, path, ("energy", "socialComfort", "avoid", "openToNew"))
    if v["energy"] is not None:
        _lit(v["energy"], f"{path}.energy", *ENERGY)
    if v["socialComfort"] is not None:
        _lit(v["socialComfort"], f"{path}.socialComfort", *SOCIAL_COMFORT)
    _strings(v["avoid"], f"{path}.avoid", max_items=5, max_len=40)
    _nullable(v["openToNew"], _bool, f"{path}.openToNew")
    return v


def candidate_v11(v: Any, path: str = "candidate") -> dict:
    """Candidate 1.1: the 1.0 snapshot plus optional non-public PreferenceTraits."""
    _obj(v, path, ("intent", "publicProfile"), ("preferences",))
    candidate({k: v[k] for k in ("intent", "publicProfile")}, path)
    if "preferences" in v:
        preference_traits(v["preferences"], f"{path}.preferences")
    return v


def _size(v: Any, path: str) -> int:
    return _int(v, path, lo=MIN_GROUP, hi=MAX_GROUP)


def opportunity(v: Any, path: str = "opportunity") -> dict:
    _obj(v, path, (
        "opportunityId", "communityId", "source", "title", "activity", "collaborationTask",
        "venueId", "window", "timeZone", "costPerPersonMinor", "currency", "minimumSize",
        "maximumSize", "publicRationale", "isSimulated", "evidence",
    ))
    _id(v["opportunityId"], f"{path}.opportunityId")
    _id(v["communityId"], f"{path}.communityId")
    _lit(v["source"], f"{path}.source", *OPPORTUNITY_SOURCES)
    _str(v["title"], f"{path}.title", max_len=80)
    _str(v["activity"], f"{path}.activity", max_len=400)
    _str(v["collaborationTask"], f"{path}.collaborationTask", max_len=400)
    _id(v["venueId"], f"{path}.venueId")
    window(v["window"], f"{path}.window")
    _str(v["timeZone"], f"{path}.timeZone", max_len=64)
    _int(v["costPerPersonMinor"], f"{path}.costPerPersonMinor", hi=10**7)
    _currency(v["currency"], f"{path}.currency")
    _lit(v["minimumSize"], f"{path}.minimumSize", 3)
    _lit(v["maximumSize"], f"{path}.maximumSize", 5)
    _str(v["publicRationale"], f"{path}.publicRationale", max_len=600)
    _bool(v["isSimulated"], f"{path}.isSimulated")
    if v["evidence"] is None:
        if v["source"] == "muse_created":
            raise ContractError(f"{path}.evidence", "required for muse_created")
    else:
        model_evidence(v["evidence"], f"{path}.evidence")
    return v


def create_event_input(v: Any, path: str = "createEventInput") -> dict:
    _obj(v, path, ("context", "communityId", "candidates", "venues"))
    context(v["context"], f"{path}.context")
    _id(v["communityId"], f"{path}.communityId")
    cands = _list(v["candidates"], f"{path}.candidates", min_items=MIN_GROUP, max_items=50)
    for i, c in enumerate(cands):
        candidate_v11(c, f"{path}.candidates[{i}]")
        if c["intent"]["communityId"] != v["communityId"]:
            raise ContractError(f"{path}.candidates[{i}]", "candidate outside community")
    ids = [c["intent"]["participantId"] for c in cands]
    if len(set(ids)) != len(ids):
        raise ContractError(f"{path}.candidates", "duplicate participant")
    for i, ven in enumerate(_list(v["venues"], f"{path}.venues", max_items=200)):
        venue(ven, f"{path}.venues[{i}]")
    return v


def create_event_result(v: Any, path: str = "createEventResult") -> dict:
    if not isinstance(v, dict):
        raise ContractError(path, "expected object")
    if v.get("status") == "created":
        _obj(v, path, ("status", "opportunity", "eligibleMemberCount"))
        opportunity(v["opportunity"], f"{path}.opportunity")
        if v["opportunity"]["source"] != "muse_created":
            raise ContractError(f"{path}.opportunity.source", "expected muse_created")
        _int(v["eligibleMemberCount"], f"{path}.eligibleMemberCount", lo=MIN_GROUP, hi=50)
    elif v.get("status") == "no_fit":
        _obj(v, path, ("status", "reason"))
        _lit(v["reason"], f"{path}.reason", "too_few_overlap", "no_open_venue", "budget")
    else:
        raise ContractError(f"{path}.status", "unknown status")
    return v


def venue_brief(v: Any, path: str = "venueBrief") -> dict:
    _obj(v, path, ("negotiationId", "venueId", "activity", "groupSize", "window", "totalBudgetMinor", "currency"))
    _id(v["negotiationId"], f"{path}.negotiationId")
    _id(v["venueId"], f"{path}.venueId")
    _str(v["activity"], f"{path}.activity", max_len=400)
    _size(v["groupSize"], f"{path}.groupSize")
    window(v["window"], f"{path}.window")
    _int(v["totalBudgetMinor"], f"{path}.totalBudgetMinor", hi=10**7)
    _currency(v["currency"], f"{path}.currency")
    return v


def venue_offer(v: Any, path: str = "offer") -> dict:
    _obj(v, path, (
        "negotiationId", "round", "venueId", "action", "window", "groupSize",
        "totalPriceMinor", "currency", "terms", "isSimulated", "evidence",
    ))
    _id(v["negotiationId"], f"{path}.negotiationId")
    _int(v["round"], f"{path}.round", lo=1, hi=8)
    _id(v["venueId"], f"{path}.venueId")
    _lit(v["action"], f"{path}.action", "offer", "final_offer", "decline")
    window(v["window"], f"{path}.window")
    _size(v["groupSize"], f"{path}.groupSize")
    _int(v["totalPriceMinor"], f"{path}.totalPriceMinor", hi=10**7)
    _currency(v["currency"], f"{path}.currency")
    _str(v["terms"], f"{path}.terms", max_len=300)
    _lit(v["isSimulated"], f"{path}.isSimulated", True)
    model_evidence(v["evidence"], f"{path}.evidence")
    return v


def counteroffer(v: Any, path: str = "counter") -> dict:
    _obj(v, path, ("negotiationId", "round", "action", "totalPriceMinor", "currency", "window", "message", "evidence"))
    _id(v["negotiationId"], f"{path}.negotiationId")
    _int(v["round"], f"{path}.round", lo=1, hi=8)
    _lit(v["action"], f"{path}.action", "counter", "accept", "walk_away")
    _int(v["totalPriceMinor"], f"{path}.totalPriceMinor", hi=10**7)
    _currency(v["currency"], f"{path}.currency")
    window(v["window"], f"{path}.window")
    _str(v["message"], f"{path}.message", max_len=300)
    model_evidence(v["evidence"], f"{path}.evidence")
    return v


def negotiation_turn(v: Any, path: str) -> dict:
    if not isinstance(v, dict):
        raise ContractError(path, "expected object")
    if v.get("by") == "venue":
        _obj(v, path, ("by", "offer"))
        venue_offer(v["offer"], f"{path}.offer")
    elif v.get("by") == "group_agent":
        _obj(v, path, ("by", "counter"))
        counteroffer(v["counter"], f"{path}.counter")
    else:
        raise ContractError(f"{path}.by", "expected venue or group_agent")
    return v


def deal(v: Any, path: str = "deal") -> dict:
    _obj(v, path, (
        "dealId", "negotiationId", "opportunityId", "venueId", "window", "groupSize",
        "totalPriceMinor", "perPersonMinor", "currency", "terms", "rounds", "status",
        "isSimulated", "evidence",
    ))
    for k in ("dealId", "negotiationId", "opportunityId", "venueId"):
        _id(v[k], f"{path}.{k}")
    window(v["window"], f"{path}.window")
    size = _size(v["groupSize"], f"{path}.groupSize")
    total = _int(v["totalPriceMinor"], f"{path}.totalPriceMinor", hi=10**7)
    per = _int(v["perPersonMinor"], f"{path}.perPersonMinor", hi=10**7)
    if per != -(-total // size):
        raise ContractError(f"{path}.perPersonMinor", "must equal ceil(totalPriceMinor / groupSize)")
    _currency(v["currency"], f"{path}.currency")
    _str(v["terms"], f"{path}.terms", max_len=300)
    _int(v["rounds"], f"{path}.rounds", lo=1, hi=8)
    _lit(v["status"], f"{path}.status", "awaiting_approval")
    _lit(v["isSimulated"], f"{path}.isSimulated", True)
    model_evidence(v["evidence"], f"{path}.evidence")
    return v


def negotiation_input(v: Any, path: str = "negotiationInput") -> dict:
    _obj(v, path, ("context", "negotiationId", "opportunity", "participants", "maxRounds"))
    context(v["context"], f"{path}.context")
    _id(v["negotiationId"], f"{path}.negotiationId")
    opportunity(v["opportunity"], f"{path}.opportunity")
    parts = _list(v["participants"], f"{path}.participants", min_items=MIN_GROUP, max_items=MAX_GROUP)
    for i, c in enumerate(parts):
        candidate_v11(c, f"{path}.participants[{i}]")
    ids = [c["intent"]["participantId"] for c in parts]
    if len(set(ids)) != len(ids):
        raise ContractError(f"{path}.participants", "duplicate participant")
    _int(v["maxRounds"], f"{path}.maxRounds", lo=1, hi=4)
    return v


def negotiation_result(v: Any, path: str = "negotiationResult") -> dict:
    if not isinstance(v, dict):
        raise ContractError(path, "expected object")
    if v.get("status") == "deal":
        _obj(v, path, ("status", "deal", "turns"))
        deal(v["deal"], f"{path}.deal")
    elif v.get("status") == "no_deal":
        _obj(v, path, ("status", "reason", "turns"))
        _lit(v["reason"], f"{path}.reason", "over_budget", "venue_declined", "rounds_exhausted")
    else:
        raise ContractError(f"{path}.status", "unknown status")
    for i, t in enumerate(_list(v["turns"], f"{path}.turns", max_items=16)):
        negotiation_turn(t, f"{path}.turns[{i}]")
    return v


def _reward_common(v: Any, path: str) -> None:
    _str(v["label"], f"{path}.label", max_len=120)
    _lit(v["sponsor"], f"{path}.sponsor", "venue", "group_quests")
    _nullable(v["venueId"], _id, f"{path}.venueId")
    if (v["sponsor"] == "venue") != (v["venueId"] is not None):
        raise ContractError(f"{path}.venueId", "required exactly when sponsor is venue")
    _lit(v["isSimulated"], f"{path}.isSimulated", True)


def reward_option(v: Any, path: str = "rewardOption") -> dict:
    _obj(v, path, ("rewardOptionId", "label", "sponsor", "venueId", "isSimulated"))
    _id(v["rewardOptionId"], f"{path}.rewardOptionId")
    _reward_common(v, path)
    return v


def reward(v: Any, path: str = "reward") -> dict:
    _obj(v, path, ("rewardId", "rewardOptionId", "label", "sponsor", "venueId", "isSimulated"))
    _id(v["rewardId"], f"{path}.rewardId")
    _id(v["rewardOptionId"], f"{path}.rewardOptionId")
    _reward_common(v, path)
    return v


def event_record(v: Any, path: str = "event") -> dict:
    _obj(v, path, (
        "eventId", "questId", "planId", "revision", "status", "title", "venueId",
        "start", "end", "acceptedMemberIds", "conversationId",
    ))
    for k in ("eventId", "questId", "planId", "venueId", "conversationId"):
        _id(v[k], f"{path}.{k}")
    _int(v["revision"], f"{path}.revision", lo=1)
    _lit(v["status"], f"{path}.status", "scheduled", "cancelled", "completed")
    _str(v["title"], f"{path}.title", max_len=80)
    window({"start": v["start"], "end": v["end"]}, path)
    for i, m in enumerate(_list(v["acceptedMemberIds"], f"{path}.acceptedMemberIds", max_items=MAX_GROUP)):
        _id(m, f"{path}.acceptedMemberIds[{i}]")
    return v


def challenge_input(v: Any, path: str = "challengeInput") -> dict:
    _obj(v, path, ("context", "questId", "event", "priorPlan", "feedback", "rewardOptions", "simulateTimeSkip"))
    context(v["context"], f"{path}.context")
    _id(v["questId"], f"{path}.questId")
    event_record(v["event"], f"{path}.event")
    if v["event"]["questId"] != v["questId"]:
        raise ContractError(f"{path}.event.questId", "must match questId")
    quest_plan(v["priorPlan"], f"{path}.priorPlan")
    seen: set[str] = set()
    for i, f in enumerate(_list(v["feedback"], f"{path}.feedback", max_items=MAX_GROUP)):
        p = f"{path}.feedback[{i}]"
        _obj(f, p, ("participantId", "attended", "wantsReturn"))
        _id(f["participantId"], f"{p}.participantId")
        _nullable(f["attended"], _bool, f"{p}.attended")
        _bool(f["wantsReturn"], f"{p}.wantsReturn")
        if f["participantId"] in seen:
            raise ContractError(p, "duplicate feedback participant")
        seen.add(f["participantId"])
    for i, r in enumerate(_list(v["rewardOptions"], f"{path}.rewardOptions", max_items=20)):
        reward_option(r, f"{path}.rewardOptions[{i}]")
    _bool(v["simulateTimeSkip"], f"{path}.simulateTimeSkip")
    return v


def challenge(v: Any, path: str = "challenge") -> dict:
    _obj(v, path, (
        "challengeId", "questId", "basedOnEventId", "title", "description", "goal",
        "dueBy", "progress", "reward", "evidence",
    ))
    for k in ("challengeId", "questId", "basedOnEventId"):
        _id(v[k], f"{path}.{k}")
    _str(v["title"], f"{path}.title", max_len=80)
    _str(v["description"], f"{path}.description", max_len=400)
    _obj(v["goal"], f"{path}.goal", ("metric", "target"))
    _lit(v["goal"]["metric"], f"{path}.goal.metric", "sessions_together")
    target = _int(v["goal"]["target"], f"{path}.goal.target", lo=2, hi=6)
    _time(v["dueBy"], f"{path}.dueBy")
    _obj(v["progress"], f"{path}.progress", ("completed", "target"))
    _int(v["progress"]["completed"], f"{path}.progress.completed", hi=target)
    if v["progress"]["target"] != target:
        raise ContractError(f"{path}.progress.target", "must equal goal.target")
    if v["reward"] is not None:
        reward(v["reward"], f"{path}.reward")
    model_evidence(v["evidence"], f"{path}.evidence")
    return v
