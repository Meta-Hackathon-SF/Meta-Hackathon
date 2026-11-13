"""Weekly formation invariants, independent of provider calls or persistence."""

from server.app.errors import ServiceError


def validate_partition(constellations, eligible_ids, blocked_pairs):
    eligible = set(eligible_ids)
    placed = []
    for constellation in constellations:
        members = constellation.memberIds
        if not 3 <= len(members) <= 5 or len(set(members)) != len(members):
            raise ServiceError("INVALID_INPUT")
        if any(a in members and b in members for a, b in blocked_pairs):
            raise ServiceError("FORBIDDEN")
        placed.extend(members)
    if len(placed) != len(set(placed)) or set(placed) != eligible:
        raise ServiceError("STALE_REVISION")
