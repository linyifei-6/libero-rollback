"""Integrity tests for the migrated ``experiments/`` evidence tree (task-5 / M2-A).

These tests need **no simulation, no GPU and no model weights**.  They check:

1. directory structure (one README + results.json per suite, source copies present);
2. that ``results.json`` parses, keeps numerator/denominator/rate internally
   consistent, and that the headline numbers match the predecessor source docs
   (the expected values below were transcribed from the read-only source repos,
   so a silent edit of the JSON cannot pass);
3. that the suite READMEs / index / ``docs/experiment-report.md`` quote the same
   headline numbers as ``results.json``;
4. that every file recorded in ``experiments/provenance.yaml`` exists with the
   recorded sha256 and that the source provenance is complete;
5. path hygiene: no host-absolute paths and no videos / oversized files;
6. that relative markdown links in the authored docs resolve.

Run with::

    python -m pytest tests/test_experiments.py
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS = REPO_ROOT / "experiments"
REPORT = REPO_ROOT / "docs" / "experiment-report.md"

SUITE_DIRS = {"a": "a-libero", "b": "b-rollback", "c": "c-compose"}

# Task-6 delivers this report directory; it is referenced (not written) by task-5.
ALLOWED_MISSING_LINK_PREFIXES = ("experiments/b-rollback/report-goal-object-20261118",)
# report-goal-object-20261118/ is delivered by task-6 (review report + local-only
# videos that are gitignored); it is out of this task's write scope, so the
# hygiene/size checks below cover only the files migrated by task-5.
OTHER_TASK_REPORT_PREFIX = "experiments/b-rollback/report-goal-object-20261118"

TEXT_SUFFIXES = {".md", ".json", ".jsonl", ".yaml", ".yml", ".txt", ".csv"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}

# Markers are assembled from parts on purpose: this file is itself scanned by
# tests/test_independence.py, which forbids literal host-path markers in Python
# sources (same trick as test_independence.py uses for its own patterns).
HOST_PATH_PATTERNS = [
    re.compile("/" + "home/"),
    re.compile("/" + "Users/"),
    re.compile("wsl." + "localhost", re.IGNORECASE),
    re.compile("taro" + "wang"),
    re.compile(r"[A-Za-z]:\\"),
    re.compile("file" + ":///"),
]

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
FENCE_RE = re.compile(r"```.*?```", re.DOTALL)

EXPECTED_IMPORTS = 9


def owned_files() -> list[Path]:
    """Files under experiments/ migrated by this task (task-6 report dir excluded)."""
    files: list[Path] = []
    for path in EXPERIMENTS.rglob("*"):
        if path.is_file():
            relative = path.relative_to(REPO_ROOT).as_posix()
            if not relative.startswith(OTHER_TASK_REPORT_PREFIX):
                files.append(path)
    return files


def load_suite(suite: str) -> dict:
    with (EXPERIMENTS / SUITE_DIRS[suite] / "results.json").open(encoding="utf-8") as fh:
        return json.load(fh)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def assert_rate(value: float, numerator: int, denominator: int, label: str = "") -> None:
    assert abs(value - numerator / denominator) < 1e-5, (
        f"{label}: {value} != {numerator}/{denominator}"
    )


def iter_rate_dicts(node):
    """Yield every dict that carries numerator/denominator/rate together."""
    if isinstance(node, dict):
        if {"numerator", "denominator", "rate"} <= set(node):
            yield node
        for value in node.values():
            yield from iter_rate_dicts(value)
    elif isinstance(node, list):
        for value in node:
            yield from iter_rate_dicts(value)


# --------------------------------------------------------------------------- #
# 1. structure
# --------------------------------------------------------------------------- #
class TestStructure:
    def test_index_and_report_exist(self):
        assert (EXPERIMENTS / "README.md").is_file()
        assert (EXPERIMENTS / "provenance.yaml").is_file()
        assert REPORT.is_file()

    @pytest.mark.parametrize("suite", sorted(SUITE_DIRS))
    def test_suite_has_readme_and_results(self, suite: str):
        suite_dir = EXPERIMENTS / SUITE_DIRS[suite]
        assert suite_dir.is_dir(), suite_dir
        assert (suite_dir / "README.md").is_file()
        assert (suite_dir / "results.json").is_file()

    def test_source_copies_present(self):
        a_sources = sorted((EXPERIMENTS / "a-libero" / "source").glob("*.md"))
        c_sources = sorted((EXPERIMENTS / "c-compose" / "source").glob("*.md"))
        b_sources = sorted((EXPERIMENTS / "b-rollback" / "legacy" / "source").glob("*"))
        assert len(a_sources) == 4
        assert len(c_sources) == 1
        assert len(b_sources) == 4
        assert (EXPERIMENTS / "b-rollback" / "legacy" / "README.md").is_file()

    def test_no_videos_or_oversized_files(self):
        total = 0
        for path in owned_files():
            if not path.is_file():
                continue
            assert path.suffix.lower() not in VIDEO_SUFFIXES, path
            size = path.stat().st_size
            total += size
            assert size <= 256 * 1024, f"unexpectedly large migrated file: {path} ({size} B)"
        assert total <= 2 * 1024 * 1024, f"experiments/ total size {total} B"


# --------------------------------------------------------------------------- #
# 2. results.json content and internal consistency
# --------------------------------------------------------------------------- #
class TestResultsJson:
    def test_schema_version_and_suite_ids(self):
        for suite in SUITE_DIRS:
            data = load_suite(suite)
            assert data["schema_version"] == "experiments-summary.v1"
            assert data["suite"] == suite
            assert data["suite_dir"] == "experiments/" + SUITE_DIRS[suite]
            assert data["title"]
            assert data["sources"], f"{suite}: sources must not be empty"
            assert data["limitations"], f"{suite}: limitations must not be empty"

    def test_all_rate_dicts_are_arithmetically_consistent(self):
        for suite in SUITE_DIRS:
            data = load_suite(suite)
            for entry in iter_rate_dicts(data):
                num = entry["numerator"]
                den = entry["denominator"]
                if num is None or den in (None, 0):
                    continue
                assert_rate(entry["rate"], num, den, f"{suite}:{entry.get('label', '')}")

    def test_a_headline_numbers(self):
        models = load_suite("a")["models"]
        assert models["pi05"]["tasks_total"] == 130
        assert models["pi05"]["hit"] == 64
        assert models["pi05"]["stable_at_100"] == 58
        assert_rate(models["pi05"]["window_survival"], 58, 64, "pi05 window survival")
        assert models["pi05"]["four_suite"]["hit"] == 37
        assert models["pi05"]["four_suite"]["stable"] == 35
        assert models["pi05"]["l90"]["hit"] == 27
        assert models["smolvla"]["four_suite"]["hit"] == 19
        assert models["smolvla"]["four_suite"]["stable"] == 17
        assert models["openvla"]["four_suite"]["hit"] == 33
        assert models["openvla"]["tasks_total"] == 40
        assert models["openvla"]["l90"] is None

    def test_a_four_suite_is_sum_of_suites(self):
        for name, model in load_suite("a")["models"].items():
            suites = model["suites"]
            assert len(suites) == 4, name
            four = model["four_suite"]
            assert sum(s["tasks"] for s in suites.values()) == four["tasks"] == 40
            assert sum(s["hit"] for s in suites.values()) == four["hit"], name
            assert sum(s["stable"] for s in suites.values()) == four["stable"], name
            assert sum(s["lost"] for s in suites.values()) == four["lost"], name
            assert sum(s["no_hit"] for s in suites.values()) == four["no_hit"], name
            if model["l90"] is not None:
                assert model["hit"] == four["hit"] + model["l90"]["hit"]
                assert model["stable_at_100"] == four["stable"] + model["l90"]["stable"]

    def test_a_lost_cases_match_lost_counts(self):
        models = load_suite("a")["models"]
        assert len(models["pi05"]["lost_cases"]) == models["pi05"]["lost"] == 6
        assert len(models["smolvla"]["lost_cases"]) == models["smolvla"]["lost"] == 2
        assert len(models["openvla"]["lost_cases"]) == models["openvla"]["lost"] == 0
        # window-length curves have one value per K for each of sampled/strict
        for name, model in models.items():
            curve = model["window_length_curve"]
            width = len(curve["k"])
            assert len(curve["sampled"]) == width, name
            assert len(curve["strict"]) == width, name
            assert all(0.0 <= v <= 1.0 for v in curve["sampled"] + curve["strict"])

    def test_b_headline_numbers(self):
        data = load_suite("b")
        assert data["model_coverage"]["pi05"].startswith("covered")
        assert "not" in data["model_coverage"]["smolvla"]
        assert "not" in data["model_coverage"]["openvla_oft"]

        legacy = data["sections"]["v1_legacy_libero_rollback"]["experiments"]
        pre = legacy["d0_mid_pi05_pre_fix"]
        assert pre["reported_model_recovery"] == 18
        assert pre["correction"]["model_self_recovery"] == 0
        assert pre["correction"]["external_restoration"] == 18

        accept = legacy["d0_mid_pi05_post_fix_acceptance"]
        assert accept["model_self_recovered"] == 0
        assert accept["required_self_repair_cases"] == 9
        assert sum(accept["verdicts"].values()) == accept["cases"] == 40

        basic = legacy["basic_single_task_rollback_20261117"]
        assert basic["cases"] == 10
        assert basic["injection_valid"] == 9
        assert basic["recovered"] == 1
        assert basic["trigger_unreachable"] == 1
        details = basic["cases_detail"]
        assert len(details) == 10
        assert sum(1 for c in details if c["injection_valid"]) == 9
        assert sum(1 for c in details if c["recovered"]) == 1
        assert sum(1 for c in details if not c["injection_valid"]) == 1
        # trigger - success arithmetic on the rows that triggered
        for row in details:
            if row["trigger_step"] is None:
                continue
            expected = row["trigger_step"] - row["baseline_success_step"]
            assert row["trigger_minus_success"] == expected

        seed1 = legacy["basic_single_task_rollback_seed1_rerun"]
        assert seed1["task_key"] == "libero_10/03"
        assert seed1["task_count"] == 1 and seed1["completed"] == 1 and seed1["failed"] == 0
        assert seed1["baseline_success"] == 1
        assert seed1["perturbation_total"] == 1
        assert seed1["perturbation_success"] == 0
        assert seed1["perturbation_injection_valid"] == 1

    def test_b_v2_matrix_numbers(self):
        v2 = load_suite("b")["sections"]["v2_b_matrix_pi05_goal_object"]
        assert v2["total_cases"] == 165
        assert v2["triggered"] == 157
        assert_rate(v2["trigger_rate"], 157, 165, "trigger rate")
        assert v2["injection_valid"] == 157
        assert v2["recovery_denominator"] == 137
        assert v2["recovered"] == 23
        assert_rate(v2["recovery_rate"], 23, 137, "recovery")
        assert v2["c0_total"] == 20
        assert v2["c0_success"] == 20
        assert v2["n_a"] == 8
        by_suite = v2["by_suite"]
        assert by_suite["goal"]["recovered"] == 21 and by_suite["goal"]["denominator"] == 68
        assert by_suite["object"]["recovered"] == 2 and by_suite["object"]["denominator"] == 69
        assert sum(s["denominator"] for s in by_suite.values()) == 137
        assert sum(s["denominator"] for s in v2["by_level"].values()) == 137
        assert sum(s["denominator"] for s in v2["by_target"].values()) == 137
        failures = v2["failure_composition"]
        assert failures["trigger_not_reached_all_done_not_in_budget"] == 7
        assert failures["trigger_not_reached_revoked_relation_false_at_all_done"] == 1
        assert failures["valid_but_not_recovered"] == 114
        # recovered + not recovered + C0 + N/A accounts for every case
        assert 23 + 114 + 20 + 8 == 165
        assert v2["source_sha256"] and len(v2["source_sha256"]) == 64

    def test_c_headline_numbers(self):
        models = load_suite("c")["models"]
        pi05 = models["pi05"]["joint_success"]
        assert (pi05["goal_compose"]["numerator"], pi05["goal_compose"]["denominator"]) == (2, 49)
        assert (pi05["object_compose"]["numerator"], pi05["object_compose"]["denominator"]) == (
            12,
            300,
        )
        assert_rate(pi05["l90_novel_dedup"]["rate"], 372, 10000, "pi05 l90 novel")
        assert (models["smolvla"]["joint_success"]["goal_compose_76"]["numerator"]) == 0
        assert models["smolvla"]["pp"] == 0.0

        oft = models["openvla_oft"]

        def pair(node):
            return node["numerator"], node["denominator"]

        assert pair(oft["joint_success"]["total"]) == (0, 176)
        assert pair(oft["pp"]["goal_compose"]) == (58, 76)
        assert pair(oft["pp"]["object_compose"]) == (95, 100)
        assert (oft["first_mentioned"]["object_compose"]["numerator"]) == 95
        assert (oft["second_mentioned"]["object_compose"]["numerator"]) == 0
        ab = oft["ab_ba_natural_experiment"]["object_compose"]
        assert pair(ab["ab_atom0_achieved"]) == (47, 50)
        assert pair(ab["ba_atom1_achieved"]) == (48, 50)
        assert len(oft["per_scene_object"]) == 10
        # the source-report inconsistency must be flagged, not hidden
        four = oft["terminal_four_way"]["goal_compose"]
        assert four["source_inconsistent"] is True
        assert four["reported_sum"] == sum(
            four[k] for k in ("both", "first_mentioned_only", "second_mentioned_only", "neither")
        )
        assert four["reported_sum"] != 76
        assert len(load_suite("c")["failure_ladder"]) == 3

    def test_results_sources_point_to_existing_copies(self):
        for suite in SUITE_DIRS:
            for source in load_suite(suite)["sources"]:
                assert source["source_repo"] in {"libero-rollback", "libero-compose"}
                assert source["source_path"]
                local = source.get("local_path")
                if not local:
                    continue
                path = REPO_ROOT / local
                assert path.is_file(), f"{suite}: missing migrated copy {local}"
                digest = sha256_bytes(path.read_bytes())
                expected = source.get("imported_sha256") or source.get("sha256")
                assert digest == expected, f"{suite}: sha256 mismatch for {local}"


# --------------------------------------------------------------------------- #
# 3. README / index / overall report stay in sync with results.json
# --------------------------------------------------------------------------- #
class TestDocsMatchResults:
    @pytest.mark.parametrize(
        ("doc", "needles"),
        [
            (
                "experiments/a-libero/README.md",
                ["37/40 = 92.5%", "19/40 = 47.5%", "33/40 = 82.5%", "90.6%", "90.5%", "100.0%"],
            ),
            (
                "experiments/b-rollback/README.md",
                ["0/9 = 0%", "23/137 = 16.8%", "21/68 = 30.9%", "2/69 = 2.9%", "20/20", "1/9"],
            ),
            (
                "experiments/c-compose/README.md",
                [
                    "2/49 = 4.1%",
                    "12/300 = 4.0%",
                    "0/76 = 0%",
                    "0/176 = 0%",
                    "58/76 = 76.3%",
                    "95/100 = 95.0%",
                ],
            ),
            (
                "experiments/README.md",
                ["37/40 = 92.5%", "23/137 = 16.8%", "2/49 = 4.1%", "0/176 = 0%"],
            ),
            (
                "docs/experiment-report.md",
                [
                    "37/40 = 92.5%",
                    "58/64 = 90.6%",
                    "0/9 = 0%",
                    "1/9 = 11.1%",
                    "23/137 = 16.8%",
                    "2/49 = 4.1%",
                    "0/76 = 0%",
                    "0/176 = 0%",
                ],
            ),
        ],
    )
    def test_headline_numbers_are_quoted(self, doc: str, needles: list[str]):
        text = read_text(REPO_ROOT / doc)
        missing = [needle for needle in needles if needle not in text]
        assert not missing, f"{doc} is missing {missing} (results.json changed?)"

    def test_report_keeps_the_required_caveats(self):
        text = read_text(REPORT)
        caveats = [
            "B 轴目前只有 π0.5",
            "不是 v2 C 套件",
            "N/A 不是 0%",
            "外部复原",
            "单 seed",
            "v1 与 v2 不混表",
            "18/30 = 60%",
        ]
        for caveat in caveats:
            assert caveat in text, f"docs/experiment-report.md lost caveat: {caveat}"

    def test_index_points_to_every_suite_and_report(self):
        text = read_text(EXPERIMENTS / "README.md")
        for relative in (
            "a-libero/README.md",
            "b-rollback/README.md",
            "c-compose/README.md",
            "../docs/experiment-report.md",
            "provenance.yaml",
        ):
            assert relative in text, relative


# --------------------------------------------------------------------------- #
# 4. provenance
# --------------------------------------------------------------------------- #
class TestProvenance:
    @pytest.fixture(scope="class")
    def provenance(self) -> dict:
        with (EXPERIMENTS / "provenance.yaml").open(encoding="utf-8") as fh:
            return yaml.safe_load(fh)

    def test_header(self, provenance: dict):
        assert provenance["schema_version"] == 1
        assert provenance["migrated_at"] == "2026-11-18"
        repos = {repo["name"] for repo in provenance["repositories"]}
        assert repos == {"libero-rollback", "libero-compose"}
        for repo in provenance["repositories"]:
            assert repo["runtime_import_allowed"] is False

    def test_sanitization_policy_is_documented(self, provenance: dict):
        policy = provenance["conventions"]["host_path_policy"]
        assert "<workspace>/" in policy
        assert "host_path_policy" in provenance["conventions"]

    def test_every_import_exists_with_recorded_sha256(self, provenance: dict):
        imports = provenance["imports"]
        assert len(imports) == EXPECTED_IMPORTS
        seen = set()
        for entry in imports:
            target = entry["target"]
            assert target not in seen, f"duplicate import target {target}"
            seen.add(target)
            path = REPO_ROOT / target
            assert path.is_file(), target
            digest = sha256_bytes(path.read_bytes())
            assert digest == entry["sha256"], f"sha256 mismatch for {target}"
            assert re.fullmatch(r"[0-9a-f]{64}", entry["source_sha256"])
            assert entry["mode"] in {"verbatim", "sanitized"}
            if entry["mode"] == "verbatim":
                assert digest == entry["source_sha256"], f"{target} claims verbatim but differs"
            else:
                assert entry.get("sanitization"), f"{target}: sanitized copy needs a note"
                assert digest != entry["source_sha256"]
            assert entry["evidence_tier"].startswith("E")
            assert entry["migrated_at"] == "2026-11-18"
            assert entry["used_by"]

    def test_aggregates_reference_existing_summaries(self, provenance: dict):
        aggregates = provenance["aggregates"]
        assert len(aggregates) == 4
        for entry in aggregates:
            assert (REPO_ROOT / entry["summary_file"]).is_file(), entry["id"]
            assert entry["computed_from"]
            assert entry["evidence_tier"].startswith("E")

    def test_not_migrated_entries_are_explained(self, provenance: dict):
        assert provenance["referenced_not_migrated"]
        assert provenance["not_migrated_runs"]
        for entry in provenance["referenced_not_migrated"]:
            assert entry["reason"]
        for entry in provenance["not_migrated_runs"]:
            assert entry["reason"]


# --------------------------------------------------------------------------- #
# 5. path hygiene
# --------------------------------------------------------------------------- #
class TestPathHygiene:
    def test_no_host_absolute_paths_or_username(self):
        offenders = []
        targets = [REPO_ROOT / "docs" / "experiment-report.md"]
        targets.extend(owned_files())
        for path in targets:
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern in HOST_PATH_PATTERNS:
                if pattern.search(text):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}: {pattern.pattern}")
        assert not offenders, offenders


# --------------------------------------------------------------------------- #
# 6. relative links in authored docs
# --------------------------------------------------------------------------- #
def _authored_markdown() -> list[Path]:
    docs = [
        EXPERIMENTS / "README.md",
        EXPERIMENTS / "a-libero" / "README.md",
        EXPERIMENTS / "b-rollback" / "README.md",
        EXPERIMENTS / "b-rollback" / "legacy" / "README.md",
        EXPERIMENTS / "c-compose" / "README.md",
        REPORT,
    ]
    return [path for path in docs if path.is_file()]


class TestLinks:
    @pytest.mark.parametrize("path", _authored_markdown(), ids=lambda p: p.name)
    def test_relative_links_resolve(self, path: Path):
        text = FENCE_RE.sub("", read_text(path))
        broken = []
        for match in LINK_RE.finditer(text):
            target = match.group(1).split("#", 1)[0].strip()
            if not target or target.startswith(("http://", "https://", "mailto:", "/")):
                continue
            resolved = (path.parent / target).resolve()
            try:
                relative = resolved.relative_to(REPO_ROOT.resolve()).as_posix()
            except ValueError:
                relative = ""
            if relative.startswith(ALLOWED_MISSING_LINK_PREFIXES):
                continue
            if not resolved.exists():
                broken.append(target)
        assert not broken, f"{path.relative_to(REPO_ROOT)}: broken links {broken}"
