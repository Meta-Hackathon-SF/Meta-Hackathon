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
