"""The architecture document must describe the system that exists.

Two documents are read by judges and by anyone joining the project, and a rule
format that has drifted from the schema is worse than no example at all. The
example in ARCHITECTURE §5.1 is parsed here and validated against the real
schema, so documentation that claims to show a valid rule is a valid rule.
"""

import re
from pathlib import Path

import pytest
import yaml

from bayyina.registry.schema import Rule, RuleLogic

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
ARCHITECTURE = DOCS / "ARCHITECTURE.md"


def _first_yaml_block(markdown: str) -> str:
    match = re.search(r"```yaml\n(.*?)```", markdown, re.DOTALL)
    assert match, "ARCHITECTURE.md has no YAML block"
    return match.group(1)


@pytest.fixture(scope="module")
def architecture() -> str:
    return ARCHITECTURE.read_text(encoding="utf-8")


def test_the_documented_rule_format_is_a_valid_rule(architecture):
    """§5.1 shows a rule. It must be one."""
    rule = Rule.model_validate(yaml.safe_load(_first_yaml_block(architecture)))
    assert rule.logic is RuleLogic.BANDED_PERCENTAGE
    assert len(rule.bands) == 5
    assert rule.source.clause == "Article 1"


def test_the_documented_format_declares_the_derived_input(architecture):
    """The example must show the distinction G5 depends on."""
    rule = Rule.model_validate(yaml.safe_load(_first_yaml_block(architecture)))
    assert rule.requires_market_evidence()
    assert rule.inputs["market_average_rent"].derived
    assert not rule.inputs["current_annual_rent"].derived


def test_retrieval_is_only_ever_mentioned_as_declined(architecture):
    """Citations come from each signed rule's verbatim clause. There is no RAG.

    Canvas box J declines retrieval, so the architecture must not quietly claim
    it. The two documents are read together, and a judge who spots the
    contradiction is right to.

    Word boundaries matter here: an earlier version of this test matched
    "storage", "average" and "coverage".
    """
    mentions = [
        line
        for line in architecture.splitlines()
        if re.search(r"\bRAG\b|\bvector database\b|\bembeddings?\b", line, re.IGNORECASE)
    ]
    for line in mentions:
        assert "Declined" in line or "carries its own" in line, (
            f"ARCHITECTURE.md appears to claim retrieval: {line!r}"
        )


def test_every_documented_script_exists():
    """A command in the docs that does not run is worse than no command.

    ARCHITECTURE once documented `python -m bayyina.registry.verify`, a module
    that was never written, while CI ran `scripts/verify_corpus.py`. A judge
    following the document would have hit ModuleNotFoundError.
    """
    backend = Path(__file__).resolve().parents[1]
    root = backend.parent
    documents = [DOCS / "ARCHITECTURE.md", root / "README.md", root / "plan.md"]

    missing: list[str] = []
    for document in documents:
        for script in re.findall(r"python (scripts/[\w./-]+\.py)", document.read_text("utf-8")):
            if not (backend / script).exists():
                missing.append(f"{document.name} -> {script}")

    assert not missing, f"documented scripts that do not exist: {missing}"


def test_the_docs_do_not_reference_a_bayyina_module_that_is_missing():
    """`python -m bayyina.x` must name a module that imports."""
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    for document in (DOCS / "ARCHITECTURE.md", root / "README.md"):
        for module in re.findall(r"python -m (bayyina[\w.]*)", document.read_text("utf-8")):
            assert importlib.util.find_spec(module), f"{document.name} names missing {module}"


# --- The submission canvas ---------------------------------------------------

CANVAS = DOCS / "CANVAS.md"

# Word limits from the official ElevenLabs Idea Canvas template. A box over its
# limit is a submission failure, and the counts were maintained by hand until
# this test existed.
BOX_LIMITS = {"B": 25, "C": 120, "E": 60, "G": 50, "J": 60, "O": 60}


def _box_word_counts() -> dict[str, int]:
    """Count the quoted submission text in each lettered box."""
    counts: dict[str, int] = {}
    for section in re.split(r"\n## ", CANVAS.read_text(encoding="utf-8")):
        letter = section[:1]
        if letter not in BOX_LIMITS:
            continue
        quoted = "\n".join(line for line in section.split("\n") if line.strip().startswith(">"))
        stripped = re.sub(r"\*\*|\*|`|>", " ", quoted)
        counts[letter] = len([word for word in stripped.split() if word])
    return counts


@pytest.mark.parametrize(("box", "limit"), sorted(BOX_LIMITS.items()))
def test_canvas_boxes_are_within_their_word_limits(box, limit):
    counts = _box_word_counts()
    assert box in counts, f"box {box} has no quoted submission text in CANVAS.md"
    assert counts[box] <= limit, f"box {box} is {counts[box]} words, limit {limit}"


def test_the_canvas_status_table_reports_the_real_counts():
    """A status table that drifts from the text is worse than no status table."""
    canvas = CANVAS.read_text(encoding="utf-8")
    counts = _box_word_counts()

    for box, limit in BOX_LIMITS.items():
        row = re.search(rf"^\|\s*\*?\*?{box}\b[^|]*\|[^|]*\|([^|]*)\|", canvas, re.MULTILINE)
        if not row:
            continue
        claimed = re.search(r"\*\*(\d+)\*\*", row.group(1))
        if claimed:
            assert int(claimed.group(1)) == counts[box], (
                f"box {box}: status table says {claimed.group(1)}, text is {counts[box]}"
            )
            assert counts[box] <= limit


def test_no_template_placeholder_survives():
    """T0.1's definition of done."""
    assert "from template" not in CANVAS.read_text(encoding="utf-8")


def test_no_deferral_marker_names_a_task_that_is_already_done():
    """A `NOT YET CONSUMED - T2.1` marker outlives the task it names.

    T2.1 shipped and two markers still pointed at it — one on
    `market_snapshot_max_age_days`, one on the `/healthz` deferral — so both read
    as "this is coming in the work we just finished". A reader has no way to tell
    a genuine deferral from a stale one, which is how the deferral list stops
    being trustworthy. The plan's own tick is the source of truth.
    """
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    completed = {
        task
        for task, tail in re.findall(r"^##\s+(T\d+\.\d+)\s+—([^\n]*)$", plan, re.MULTILINE)
        if "✅" in tail
    }
    assert completed, "no completed tasks found in plan.md — has its heading format changed?"

    stale: list[str] = []
    for path in sorted((ROOT / "backend" / "src").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for task in re.findall(r"NOT YET CONSUMED\s*[-–—]\s*(T\d+\.\d+)", text):
            if task in completed:
                stale.append(f"{path.relative_to(ROOT)} defers to {task}, which is complete")

    assert not stale, "stale deferral markers:\n  " + "\n  ".join(stale)


def test_every_deferral_marker_names_a_real_task():
    """A deferral pointing at a task number that does not exist is worse than
    none: it looks planned and is not."""
    plan = (ROOT / "plan.md").read_text(encoding="utf-8")
    known = set(re.findall(r"^##\s+(T\d+\.\d+)\s+—", plan, re.MULTILINE))

    unknown: list[str] = []
    for path in sorted((ROOT / "backend" / "src").rglob("*.py")):
        for task in re.findall(
            r"NOT YET CONSUMED\s*[-–—]\s*(T\d+\.\d+)", path.read_text(encoding="utf-8")
        ):
            if task not in known:
                unknown.append(
                    f"{path.relative_to(ROOT)} defers to {task}, which is not in plan.md"
                )

    assert not unknown, "deferral markers naming unknown tasks:\n  " + "\n  ".join(unknown)


def test_the_documented_database_filenames_are_the_ones_we_write():
    """ARCHITECTURE once said `data/rent_contracts.duckdb`; the code wrote
    `data/market.duckdb`.

    Nothing caught it, because a filename is neither a module nor a script. An
    operator following the document would have looked for a file that is never
    created — and, worse, might have created it.

    There are two now, and the distinction matters: the build database is 359 MB
    of contract rows and is never shipped, while the serving database is 1.3 MB
    and is what the image carries. A document that confuses them would send
    someone to deploy the wrong one.
    """
    script = (ROOT / "backend" / "scripts" / "ingest_market.py").read_text(encoding="utf-8")
    written = set(re.findall(r'default=Path\("data/([^"]+\.duckdb)"\)', script))
    assert len(written) == 2, f"expected a build and a serving database, found {written}"

    app_source = (ROOT / "backend" / "src" / "bayyina" / "api" / "app.py").read_text("utf-8")
    served = re.search(r'Path\(settings\.data_dir\)\s*/\s*"([^"]+\.duckdb)"', app_source)
    assert served, "the app no longer names a default comparables database"
    assert served.group(1) in written, (
        f"the service reads {served.group(1)}, which the ingest never writes"
    )

    for document in (ARCHITECTURE, ROOT / "README.md"):
        mentioned = {
            Path(name).name
            for name in re.findall(r"[\w./-]*\.duckdb", document.read_text(encoding="utf-8"))
        }
        unknown = mentioned - written
        assert not unknown, (
            f"{document.name} names {sorted(unknown)}, which the code never writes. "
            f"It writes {sorted(written)}"
        )
