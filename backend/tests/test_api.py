"""Wave 3 — read-only API + schedule construction receipts (no live server)."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from freight_radar.api.app import app


def _seed(pub):
    (pub / "snapshot.json").write_text(json.dumps({"as_of": "2026-05-31", "chokepoints": [1, 2], "ports": [1]}))
    (pub / "flags.json").write_text(json.dumps([{"flag_id": "a"}, {"flag_id": "b"}]))
    (pub / "lanes.json").write_text(json.dumps([{"name": "x"}]))
    (pub / "manifest.json").write_text(json.dumps({"version": 3, "as_of": "2026-05-31", "flag_count": 2}))


def test_api_serves_published_json(tmp_path, monkeypatch):
    monkeypatch.setenv("FREIGHT_RADAR_PUBLISH_DIR", str(tmp_path))
    _seed(tmp_path)
    client = TestClient(app)

    r = client.get("/api/snapshot")
    assert r.status_code == 200 and r.json()["as_of"] == "2026-05-31"
    assert r.headers.get("ETag")  # content-hash ETag present

    assert len(client.get("/api/flags").json()) == 2
    assert client.get("/api/manifest").json()["version"] == 3

    health = client.get("/api/health").json()
    assert health["status"] == "ok"
    assert health["manifest"]["flag_count"] == 2


def test_api_degrades_when_unpublished(tmp_path, monkeypatch):
    monkeypatch.setenv("FREIGHT_RADAR_PUBLISH_DIR", str(tmp_path))  # empty dir
    client = TestClient(app)
    assert client.get("/api/snapshot").status_code == 503
    assert client.get("/api/health").json()["status"] == "no_data"


def test_schedule_constructs():
    # validates the Schedule spec/types build without a live server
    from freight_radar.temporal.schedule import _interval, _schedule

    sched = _schedule()
    assert sched.action is not None
    assert sched.spec.intervals and sched.spec.intervals[0].every == _interval()
