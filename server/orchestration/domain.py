"""Pure P1 workflow decisions; callers apply them in an authorized transaction.

There are no database effects, model calls, trust decisions or side-channel
messages here. A quorum freezes one revision. Withdrawals/invalidation must use a
dedicated guarded transition rather than silently changing an in-flight quorum.
"""

from server.orchestration.wire import WorkflowError, validate_plan

STATUSES = {
    "forming",
    "proposed",
    "planning",
    "scheduled",
    "revision_pending",
    "completed",
    "cancelled",
}
MATERIAL_FIELDS = (
    "title",
    "activity",
    "collaborationTask",
    "venueId",
    "start",
    "end",
    "timeZone",
    "costPerPersonMinor",
    "currency",
    "minimumSize",
    "maximumSize",
)


def _positive(value: object) -> None:
    if type(value) is not int or value < 1:
        raise WorkflowError("INVALID_INPUT")


def _ids(values: object, *, minimum: int = 0) -> set[str]:
    if (
        not isinstance(values, list)
        or not minimum <= len(values) <= 5
        or any(not isinstance(value, str) or not value.strip() for value in values)
        or len(set(values)) != len(values)
    ):
        raise WorkflowError("INVALID_INPUT")
    return set(values)


def decide_acceptance(
    status: str,
    current_revision: int,
    submitted_revision: int,
    member_ids: list[str],
    accepted_ids: list[str],
    participant_id: str,
    choice: str,
    *,
    declined_ids: list[str] | None = None,
) -> dict:
    """Return a deterministic decision without mutating the supplied collections.

    Identity/consent must already be checked by the service. Declines are sticky
    in one revision. Only the third acceptance enqueues finalization; repeated
    accepted choices never enqueue a second job. Planning/scheduled quorums are
    frozen, so any non-idempotent acceptance command needs a fresh revision.
    """
    _positive(current_revision)
    _positive(submitted_revision)
    members = _ids(member_ids, minimum=3)
    accepted = _ids(accepted_ids)
    declined = _ids(declined_ids if declined_ids is not None else [])
    if (
        not isinstance(status, str)
        or status not in STATUSES
        or not isinstance(choice, str)
        or choice not in {"accept", "decline"}
    ):
        raise WorkflowError("INVALID_INPUT")
    if not accepted <= members or not declined <= members or accepted & declined:
        raise WorkflowError("INVALID_INPUT")
    if not isinstance(participant_id, str) or not participant_id.strip():
        raise WorkflowError("INVALID_INPUT")
    if participant_id not in members:
        raise WorkflowError("FORBIDDEN")
    if submitted_revision != current_revision:
        raise WorkflowError("STALE_REVISION")
    if status not in {"proposed", "planning", "scheduled"}:
        raise WorkflowError("STALE_REVISION")
    if status == "proposed" and len(accepted) >= 3:
        raise WorkflowError("INVALID_INPUT")
    if status in {"planning", "scheduled"} and len(accepted) < 3:
        raise WorkflowError("INVALID_INPUT")

    decision = {
        "status": status,
        "acceptedIds": sorted(accepted),
        "declinedIds": sorted(declined),
        "enqueueFinalization": False,
    }
    if choice == "accept" and participant_id in accepted:
        return decision
    if status in {"planning", "scheduled"}:
        raise WorkflowError("STALE_REVISION")
    if participant_id in declined:
        if choice == "decline":
            return decision
        raise WorkflowError("STALE_REVISION")
    if choice == "decline":
        accepted.discard(participant_id)
        declined.add(participant_id)
    else:
        if len(accepted) >= 5:
            raise WorkflowError("CAPACITY_REACHED")
        accepted.add(participant_id)
    quorum = len(accepted) >= 3
    return {
        "status": "planning" if quorum else "proposed",
        "acceptedIds": sorted(accepted),
        "declinedIds": sorted(declined),
        "enqueueFinalization": quorum,
    }


def requires_reconfirmation(accepted_plan: object, final_plan: object) -> bool:
    """Compare material accepted facts; evidence/opener/identity alone do not vote."""
    accepted = validate_plan(accepted_plan)
    final = validate_plan(final_plan)
    if accepted["proposalId"] != final["proposalId"]:
        raise WorkflowError("INVALID_INPUT")
    if any(accepted[field] != final[field] for field in MATERIAL_FIELDS):
        return True

    def key(member: dict) -> str:
        return member["participantId"]

    return sorted(accepted["memberVersions"], key=key) != sorted(final["memberVersions"], key=key)


def decide_publication(
    accepted_plan: object,
    final_plan: object,
    *,
    current_revision: int,
    accepted_ids: list[str],
    member_ids: list[str],
) -> dict:
    """Resolve an unchanged plan or require a fresh vote on changed details.

    The caller still owns fresh auth/version/feasibility checks and persists any
    new plan revision/lineage atomically. No provider result is authorized here.
    """
    _positive(current_revision)
    members = _ids(member_ids, minimum=3)
    accepted = _ids(accepted_ids, minimum=3)
    old = validate_plan(accepted_plan)
    new = validate_plan(final_plan)
    if not accepted <= members:
        raise WorkflowError("INVALID_INPUT")
    if old["revision"] != current_revision:
        raise WorkflowError("STALE_REVISION")
    if {member["participantId"] for member in old["memberVersions"]} != members:
        raise WorkflowError("INVALID_INPUT")
    if not {member["participantId"] for member in new["memberVersions"]} <= members:
        raise WorkflowError("INVALID_INPUT")
    if new["revision"] not in {current_revision, current_revision + 1}:
        raise WorkflowError("STALE_REVISION")
    if new["revision"] == current_revision + 1 and new["basedOnRevision"] != current_revision:
        raise WorkflowError("STALE_REVISION")
    changed = requires_reconfirmation(old, new) or new["revision"] != current_revision
    return {
        "status": "proposed" if changed else "scheduled",
        "revision": current_revision + 1 if changed else current_revision,
        "requiresReconfirmation": changed,
        "acceptedIds": [] if changed else sorted(accepted),
    }
