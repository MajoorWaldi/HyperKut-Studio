import hashlib
import io
import json

import pytest

from backend.artifact_contract import ArtifactRef, ProjectSnapshot
from backend.artifact_store import LocalArtifactStore
from backend.project_snapshot import materialize_snapshot


def test_invalid_manifest_is_rejected_before_snapshot_materialization(tmp_path):
    manifest = {
        "schema_version": "1.0.0",
        "project_id": "p_12345678",
        "project_revision": 1,
        "source": {
            "uri": "sources/source.mp4",
            "fingerprint": "fixture",
            "width": 64,
            "height": 64,
            "fps_num": 24,
            "fps_den": 0,
            "timing_mode": "CFR",
            "frame_count": 24,
            "duration_seconds": 1.0,
            "has_audio": False,
        },
        "detection": {"mode": "manual", "sensitivity": 0.5, "min_shot_frames": 1, "cache_key": "fixture"},
        "shots": [],
    }
    encoded = json.dumps(manifest, separators=(",", ":")).encode()
    ref = ArtifactRef(hashlib.sha256(encoded).hexdigest(), len(encoded))
    store = LocalArtifactStore(tmp_path / "cache")
    store.put(io.BytesIO(encoded), ref)
    snapshot = ProjectSnapshot("p_12345678", 1, ref, ())
    workspace = tmp_path / "worker"

    with pytest.raises(ValueError, match="fps_den"):
        with materialize_snapshot(store, snapshot, workspace):
            pytest.fail("Invalid manifest reached materialization")
    assert not workspace.exists()
