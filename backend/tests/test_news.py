"""News enrichment honesty invariants (no network — stubbed RSS)."""

from __future__ import annotations

from datetime import date

from freight_radar.business.news import DISCLAIMER, enrich_news, fetch_for_entity

_RSS = """<?xml version="1.0"?><rss><channel>
 <item><title>Hormuz remains choked off - CNN</title>
   <link>https://news.google.com/rss/articles/abc</link>
   <pubDate>Tue, 02 Jun 2026 10:00:00 GMT</pubDate>
   <source url="https://cnn.com">CNN</source></item>
 <item><title>Missing date item - X</title><link>https://x.com/b</link></item>
 <item><title>Missing link item</title>
   <pubDate>Tue, 02 Jun 2026 10:00:00 GMT</pubDate></item>
</channel></rss>"""


class _FakeResp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _FakeClient:
    def __init__(self, text):
        self._text = text

    def get(self, url, timeout=20):
        return _FakeResp(self._text)


def test_gates_unparseable_items():
    out = fetch_for_entity(_FakeClient(_RSS), "Strait of Hormuz", "2026-05-20", date(2026, 6, 3))
    # only the item with BOTH a url and a parseable date survives the gate
    assert len(out) == 1
    a = out[0]
    assert a["url"] and a["published"] == "2026-06-02"
    assert a["source"] == "CNN"


def test_every_item_has_url_and_date(monkeypatch):
    import httpx
    # patch httpx.Client used inside enrich_news to our context-manager-safe fake
    monkeypatch.setattr(httpx, "Client", lambda *a, **k: _CtxFake(_RSS))
    flags = [{"flag_id": "f1", "entity": "Strait of Hormuz", "as_of": "2026-05-20", "lifecycle": "new"}]
    payload = enrich_news(flags, date(2026, 6, 3))
    blk = payload["items"]["f1"]
    assert blk["relation"] == "possibly_related" and blk["disclaimer"] == DISCLAIMER
    for item in blk["items"]:
        assert item["url"] and item["published"]  # honesty invariant


class _CtxFake(_FakeClient):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False
