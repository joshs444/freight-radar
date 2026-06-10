"""README receipts can't rot (HARDENING-PLAN H0-A).

The adversarial review's root cause #1: hand-maintained receipts drift — the README
claimed "80/80 tests" while CI collected ~280, and "190 facts" while the chat oracle
checked 800+. The fix is structural: receipts are dated or machine-checked, and a stale
receipt fails this test. Three layers of defence, all offline and deterministic:

  1. retired stale literals can never reappear (the exact strings the review caught);
  2. every known point-in-time number in the README carries a YYYY-MM-DD nearby;
  3. where a claim is cheaply checkable against the repo, it is checked against the
     repo (dbt test count, view names, snapshot entity counts, local link targets).

Marker-free on purpose: this runs in the default `-m "not live"` suite on every push.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
README_PATH = REPO / "README.md"
FEATURES_PATH = REPO / "docs" / "FEATURES.md"
README = README_PATH.read_text(encoding="utf-8")
FEATURES = FEATURES_PATH.read_text(encoding="utf-8")
DOCS = {"README.md": README, "docs/FEATURES.md": FEATURES}

DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


# --- 1. retired literals (the exact rot the review caught) stay retired ---------------

RETIRED = [
    "80/80",                  # "80/80 non-live backend tests pass" — was 278 when checked
    "80 deterministic tests", # same stale count in the Run-it block
    "190 facts",              # chat oracle grew to 833 facts
    "13 raw z-detections",    # point-in-time detection example presented as current
]

# Repo docs are product-voiced; career-meta framing stays out (H0-C's bar, kept here).
BANNED_VOICE = ["$200K", "interview gold", "hiring manager"]


def test_retired_stale_literals_do_not_return() -> None:
    for name, text in DOCS.items():
        for lit in RETIRED:
            assert lit not in text, f"{name}: retired stale receipt {lit!r} reappeared"


def test_no_career_meta_language() -> None:
    for name, text in DOCS.items():
        for phrase in BANNED_VOICE:
            assert phrase.lower() not in text.lower(), (
                f"{name}: career-meta phrase {phrase!r} — repo docs are product-voiced"
            )


# --- 2. point-in-time numbers carry their date -----------------------------------------

# Known shapes of point-in-time claims. Each match must have a YYYY-MM-DD within the
# surrounding window — "any number that describes the data right now names its moment."
POINT_IN_TIME = [
    re.compile(r"\d[\d,]*\s+(?:chat\s+)?facts\b"),               # chat-grounding fact counts
    re.compile(r"\d[\d,]*\s+flags\b"),                           # current flag-rail size
    re.compile(r"\d[\d,]*\s+(?:deterministic|non-live)[\w\s-]*tests\b"),  # pytest suite size
    re.compile(r"\d+\.\d\s*/\s*[\"“]"),                     # stress 'NN.N / "label"'
]
WINDOW = 250  # chars each side — generous enough for wrapped lines, tight enough to bind


def test_point_in_time_numbers_are_dated() -> None:
    undated: list[str] = []
    for pattern in POINT_IN_TIME:
        for m in pattern.finditer(README):
            window = README[max(0, m.start() - WINDOW) : m.end() + WINDOW]
            if not DATE_RE.search(window):
                undated.append(m.group(0))
    assert not undated, (
        f"README.md: point-in-time numbers without an as-of date nearby: {undated} — "
        "add the YYYY-MM-DD the number was derived (and re-derive it)"
    )


# --- 3. cheap claims-vs-reality checks --------------------------------------------------


def _dbt_declared_test_count() -> int:
    """Count dbt data tests the way dbt does: yml-declared generics + singular SQL tests."""
    dbt = REPO / "dbt"
    n = len(list((dbt / "tests").glob("*.sql")))

    def tests_in(node: dict) -> int:
        return len(node.get("tests") or []) + len(node.get("data_tests") or [])

    for yml in (dbt / "models").rglob("*.yml"):
        doc = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        for section in ("models", "sources", "seeds", "snapshots"):
            for entry in doc.get(section) or []:
                n += tests_in(entry)
                for col in entry.get("columns") or []:
                    n += tests_in(col)
                for table in entry.get("tables") or []:  # sources nest tables
                    n += tests_in(table)
                    for col in table.get("columns") or []:
                        n += tests_in(col)
    return n


def test_stated_dbt_test_count_matches_project() -> None:
    actual = _dbt_declared_test_count()
    for name, text in DOCS.items():
        for m in re.finditer(r"(\d+)\s+(?:dbt|data)\s+tests\b", text):
            stated = int(m.group(1))
            assert stated == actual, (
                f"{name} states {stated} dbt tests; the dbt/ project declares {actual}"
            )


def test_stated_entity_counts_match_snapshot() -> None:
    snapshot = json.loads(
        (REPO / "frontend" / "public" / "data" / "snapshot.json").read_text(encoding="utf-8")
    )
    ports, chokepoints = len(snapshot["ports"]), len(snapshot["chokepoints"])
    for name, text in DOCS.items():
        for m in re.finditer(r"([\d,]+)\s+ports\b", text):
            stated = int(m.group(1).replace(",", ""))
            assert stated == ports, f"{name} says {stated} ports; snapshot.json has {ports}"
        for m in re.finditer(r"(\d+)\s+(?:maritime\s+)?chokepoints\b", text):
            stated = int(m.group(1))
            assert stated == chokepoints, (
                f"{name} says {stated} chokepoints; snapshot.json has {chokepoints}"
            )


def test_views_claim_matches_frontend() -> None:
    """The 'four views' story is checked against the actual view toggle + type union."""
    toggle = (REPO / "frontend" / "src" / "components" / "ViewToggle.tsx").read_text(encoding="utf-8")
    views = re.findall(r"id:\s*'(\w+)',\s*label:\s*'([^']+)',\s*glyph:\s*'(.+?)'", toggle)
    assert views, "could not parse VIEWS from ViewToggle.tsx — update this test's regex"

    union = re.search(
        r"export type AppView =\s*([^;]+);",
        (REPO / "frontend" / "src" / "types.ts").read_text(encoding="utf-8"),
    )
    assert union, "could not parse the AppView union from types.ts"
    union_ids = set(re.findall(r"'(\w+)'", union.group(1)))
    assert {v[0] for v in views} == union_ids, "ViewToggle VIEWS drifted from the AppView union"

    words = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six"}
    count_word = words.get(len(views), str(len(views)))
    assert f"{count_word} views" in README, (
        f"the app has {len(views)} views; the README must say '{count_word} views'"
    )
    for _id, label, glyph in views:
        assert glyph in README and label in README, (
            f"view '{glyph} {label}' exists in the app but isn't named in the README"
        )


def test_local_readme_links_resolve() -> None:
    """Every relative link in the README points at a real file (link rot = receipt rot)."""
    missing: list[str] = []
    for m in re.finditer(r"\]\((?!https?://|#|mailto:)([^)#]+)(?:#[^)]*)?\)", README):
        target = m.group(1).strip()
        path = REPO / target
        if not (path.is_file() or path.is_dir()):
            missing.append(target)
    assert not missing, f"README.md links to missing files: {missing}"
