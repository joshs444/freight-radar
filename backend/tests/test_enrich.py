"""Wave 0 — the enricher registry's degradation contract (no DB/network)."""

from __future__ import annotations

import freight_radar.enrich as enrich
from freight_radar.enrich import EnrichCtx, run_enrichers


def _writer(name):
    def run(ctx):
        (ctx.out_dir / f"{name}.json").write_text('{"ok":1}')
        return {"name": name, "sidecar": f"{name}.json"}
    return run


def _boom(ctx):
    raise RuntimeError("kaboom")


def test_one_failure_does_not_abort_the_rest(tmp_path, monkeypatch):
    monkeypatch.setattr(
        enrich, "ENRICHERS",
        [("a", _writer("a"), True), ("b", _boom, True), ("c", _writer("c"), False)],
    )
    ctx = EnrichCtx(db_path=tmp_path / "x.db", out_dir=tmp_path,
                    flags_path=tmp_path / "flags.json", as_of="2026-05-31", today="2026-06-03")
    receipts = run_enrichers(ctx)

    # the failing enricher is reported but swallowed; the others still ran + wrote
    assert "error" in receipts["b"]
    assert receipts["a"]["name"] == "a" and receipts["c"]["name"] == "c"
    assert (tmp_path / "a.json").exists() and (tmp_path / "c.json").exists()
    assert not (tmp_path / "b.json").exists()
