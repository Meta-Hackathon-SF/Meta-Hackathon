"""privacy_registration mounts /me/data and /me/blocks when given the stores.
Runs against Kai's real registry when server.app is importable; skips otherwise."""

from __future__ import annotations

import pytest

from server.privacy.answers import AnswerStore
from server.privacy.moderation import ModerationStore
from server.privacy.registration import privacy_registration

registry = pytest.importorskip("server.app.registry")


def _paths(reg) -> set[tuple[str, str]]:
    return {(m, r.path) for r in reg.router.routes for m in getattr(r, "methods", ())}


def test_minimal_registration_mounts_core_routes_only(service):
    paths = _paths(privacy_registration(service))
    assert ("POST", "/communities/{community_id}/join") in paths
    assert ("PATCH", "/me/consent") in paths
    assert ("DELETE", "/me/data") not in paths and ("POST", "/me/blocks") not in paths


def test_full_registration_mounts_data_and_block_routes(store, service):
    reg = privacy_registration(
        service,
        answers=AnswerStore(store, service),
        moderation=ModerationStore(store, service),
        resolve_handle=lambda actor, room, handle: None,
    )
    assert reg.owner == "privacy"
    paths = _paths(reg)
    assert ("DELETE", "/me/data") in paths and ("POST", "/me/blocks") in paths


def test_blocks_route_needs_both_moderation_and_resolver(store, service):
    reg = privacy_registration(service, moderation=ModerationStore(store, service))
    assert ("POST", "/me/blocks") not in _paths(reg)
