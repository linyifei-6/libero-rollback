"""Repository independence guards.

The benchmark repository must not depend on the precursor research
repositories at runtime, and must not embed machine-specific absolute paths.
These tests are intentionally pure-stdlib so they run in the minimal CI job.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_IMPORTS = ("libero_compose", "libero_runtime")
FORBIDDEN_PATH_PATTERNS = (
    # split so this test file does not match itself
    "/" + "home/",
    "/" + "Users/",
    "wsl." + "localhost",
)
# Files whose job is to *detect* host paths necessarily contain the markers.
PATH_HYGIENE_ALLOWLIST = {
    "validation.py",
    "validate_dataset.py",
    "test_dataset.py",
}

STATIC_LAYER = (
    "matrices.py",
    "schema.py",
    "validation.py",
    "evidence.py",
    "metrics.py",
    "report.py",
)


def _python_sources() -> list[Path]:
    roots = [REPO_ROOT / "src", REPO_ROOT / "scripts", REPO_ROOT / "tests"]
    files: list[Path] = []
    for root in roots:
        if root.is_dir():
            files.extend(path for path in root.rglob("*.py") if path.is_file())
    return files


def test_no_precursor_repo_imports() -> None:
    pattern = re.compile(r"^\s*(?:import|from)\s+(" + "|".join(FORBIDDEN_IMPORTS) + r")\b", re.M)
    offenders = []
    for path in _python_sources():
        text = path.read_text(encoding="utf-8", errors="replace")
        if pattern.search(text):
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert not offenders, f"forbidden precursor imports in: {offenders}"


def test_no_absolute_host_paths_in_sources() -> None:
    offenders = []
    for path in _python_sources():
        if path.name in PATH_HYGIENE_ALLOWLIST:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in FORBIDDEN_PATH_PATTERNS:
            if marker in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {marker}")
    assert not offenders, f"absolute host paths in sources: {offenders}"


def test_static_layer_has_no_simulation_imports() -> None:
    forbidden = ("numpy", "torch", "mujoco", "robosuite", "libero")
    offenders = []
    package = REPO_ROOT / "src" / "libero_rollback"
    for name in STATIC_LAYER:
        path = package / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for module in forbidden:
            if re.search(rf"^\s*(?:import|from)\s+{module}\b", text, re.M):
                offenders.append(f"{name}: {module}")
    assert not offenders, f"static layer imports simulation deps: {offenders}"


def test_dataset_has_no_absolute_paths() -> None:
    dataset = REPO_ROOT / "dataset"
    if not dataset.is_dir():
        return
    offenders = []
    for path in dataset.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".csv", ".yaml", ".yml", ".json", ".jsonl", ".md"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker in FORBIDDEN_PATH_PATTERNS:
            if marker in text:
                offenders.append(f"{path.relative_to(REPO_ROOT)}: {marker}")
    assert not offenders, f"absolute host paths in dataset: {offenders}"
