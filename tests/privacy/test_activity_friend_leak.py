"""Audit P1: client-asserted friend ids and profile id are never stored."""

import inspect

from server.privacy import activity


def test_put_never_persists_client_friend_ids_or_profile_id():
    src = inspect.getsource(activity.ActivityStore.put)
    assert "req.friend_ids" not in src and "req.profile_id" not in src
