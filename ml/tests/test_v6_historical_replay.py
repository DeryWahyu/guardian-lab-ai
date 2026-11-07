"""New exposure does not erase old parity evidence or permit alteration of old data."""

import importlib
import sys

import pytest

from guardian_ml.paths import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
replay = importlib.import_module("v6_historical_replay")
sys.path.pop(0)


def test_historical_replay_accepts_appended_exposure():
    assert replay.verify_append_only_inventory(
        {"old": "hash-a"}, {"old": "hash-a", "new": "hash-b"}
    ) == ["new"]


@pytest.mark.parametrize("current", [{}, {"old": "tampered", "new": "hash-b"}])
def test_historical_replay_rejects_missing_or_modified_exposure(current):
    with pytest.raises(ValueError, match="removed_or_modified"):
        replay.verify_append_only_inventory({"old": "hash-a"}, current)
