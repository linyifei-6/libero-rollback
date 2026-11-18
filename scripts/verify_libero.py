#!/usr/bin/env python3
"""Verify the pinned upstream LIBERO checkout (layer 3 of the asset pin).

Run this before any evaluation episode. It hard-fails on drift instead of
silently running against modified assets:

    export LIBERO_HOME=/path/to/LIBERO
    uv run python scripts/verify_libero.py --libero-home "$LIBERO_HOME"

Checks, in order:

1. the ``libero/libero`` package and its ``bddl_files`` / ``init_files`` /
   ``assets`` directories exist;
2. the git commit equals ``f78abd68ee283de9f9be3c8f7e2a9ad60246e95c``
   (``docs/SPEC.md`` §2.1);
3. the worktree is clean (``--allow-dirty`` downgrades this to a warning for
   development checkouts; never use it for a leaderboard run);
4. the bddl / pruned-init file counts match ``assets/libero.lock.yaml``
   (130 / 130 total, per-suite counts included);
5. if ``assets/manifest.yaml`` carries a non-empty ``files:`` list, every
   recorded sha256 matches the checkout.

``--print-sha256`` prints ``<sha256>  <path relative to LIBERO_HOME>`` lines for
the bddl + pruned-init files, so the content pin can be frozen honestly from a
clean checkout (see assets/manifest.yaml). It does not write anything.

Exit codes: 0 = all checks pass (warnings allowed); 1 = at least one failure.
Dependencies: Python stdlib + PyYAML.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ASSETS_MANIFEST = REPO_ROOT / "assets" / "manifest.yaml"
DEFAULT_ASSETS_LOCK = REPO_ROOT / "assets" / "libero.lock.yaml"
LIBERO_HOME_ENV = "LIBERO_HOME"

#: From docs/SPEC.md §2.1 / assets/libero.lock.yaml.
PINNED_COMMIT = "f78abd68ee283de9f9be3c8f7e2a9ad60246e95c"

#: Expected upstream file counts (assets/libero.lock.yaml).
EXPECTED_COUNTS = {"bddl_files": 130, "pruned_init_files": 130}

#: Per-suite (bddl, pruned_init) counts; libero_90 exists upstream but is unused.
EXPECTED_SUITE_COUNTS: dict[str, tuple[int, int]] = {
    "libero_goal": (10, 10),
    "libero_object": (10, 10),
    "libero_spatial": (10, 10),
    "libero_10": (10, 10),
    "libero_90": (90, 90),
}

_OK = "ok"
_WARN = "warn"
_FAIL = "fail"


class VerifyError(RuntimeError):
    """Raised when the checkout cannot be inspected at all."""


@dataclass
class Check:
    name: str
    status: str
    detail: str


@dataclass
class Report:
    libero_home: str
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str) -> None:
        self.checks.append(Check(name=name, status=status, detail=detail))

    @property
    def failures(self) -> list[Check]:
        return [check for check in self.checks if check.status == _FAIL]

    @property
    def warnings(self) -> list[Check]:
        return [check for check in self.checks if check.status == _WARN]

    def to_json(self) -> dict[str, Any]:
        return {
            "libero_home": self.libero_home,
            "pinned_commit": PINNED_COMMIT,
            "passed": not self.failures,
            "checks": [
                {"name": check.name, "status": check.status, "detail": check.detail}
                for check in self.checks
            ],
        }


def _yaml():
    try:
        import yaml  # noqa: PLC0415 - lazy import for a clear error message
    except ImportError as error:  # pragma: no cover - project dependency
        raise VerifyError(
            "PyYAML is required (install the project with `uv sync`): " + str(error)
        ) from error
    return yaml


def resolve_libero_home(cli_value: str | None) -> Path:
    raw = cli_value or _env(LIBERO_HOME_ENV)
    if not raw:
        raise VerifyError(
            f"{LIBERO_HOME_ENV} is not set; pass --libero-home /path/to/LIBERO "
            "or export it (see .env.example)"
        )
    path = Path(raw).expanduser()
    if not path.is_dir():
        raise VerifyError(f"LIBERO_HOME is not a directory: {path}")
    return path


def _env(name: str) -> str | None:
    import os  # noqa: PLC0415 - keep the import local to the helper

    return os.environ.get(name)


def find_package_dir(libero_home: Path) -> Path:
    for candidate in (
        libero_home / "libero" / "libero",
        libero_home,
        libero_home / "libero",
    ):
        if (candidate / "__init__.py").is_file():
            return candidate
    raise VerifyError(
        f"cannot locate the LIBERO package under {libero_home}: expected "
        "`<LIBERO_HOME>/libero/libero/__init__.py` (is this the upstream LIBERO repo?)"
    )


def _run_git(libero_home: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["git", "-C", str(libero_home), *args],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None


def check_git(report: Report, libero_home: Path, *, allow_dirty: bool, skip_git: bool) -> None:
    if skip_git:
        report.add("git", _WARN, "--skip-git: commit/worktree checks skipped")
        return
    head = _run_git(libero_home, "rev-parse", "HEAD")
    if head is None or head.returncode != 0:
        detail = "not a git checkout (use --skip-git for a source archive)"
        reason = head.stderr.strip() if head else "git unavailable"
        report.add("git.commit", _FAIL, f"{detail}: {reason}")
    else:
        observed = head.stdout.strip()
        if observed == PINNED_COMMIT:
            report.add("git.commit", _OK, observed)
        else:
            report.add(
                "git.commit",
                _FAIL,
                f"{observed} != pinned {PINNED_COMMIT}",
            )

    status = _run_git(libero_home, "status", "--porcelain")
    if status is None or status.returncode != 0:
        report.add("git.clean", _WARN, "cannot read worktree status")
        return
    changes = [line for line in status.stdout.splitlines() if line.strip()]
    if not changes:
        report.add("git.clean", _OK, "worktree clean")
    elif allow_dirty:
        report.add(
            "git.clean",
            _WARN,
            f"worktree dirty ({len(changes)} entries); --allow-dirty is for development "
            "checkouts only — a leaderboard run needs a clean checkout",
        )
    else:
        report.add(
            "git.clean",
            _FAIL,
            f"worktree dirty ({len(changes)} entries); re-run with --allow-dirty only for "
            "development checkouts",
        )


def _count(directory: Path, pattern: str) -> int:
    return sum(1 for path in directory.rglob(pattern) if path.is_file())


def check_layout(report: Report, package_dir: Path) -> None:
    for name in ("bddl_files", "init_files", "assets"):
        directory = package_dir / name
        if directory.is_dir():
            report.add(f"layout.{name}", _OK, str(directory))
        else:
            report.add(f"layout.{name}", _FAIL, f"missing {directory}")
    assets = package_dir / "assets"
    if assets.is_dir():
        entries = sum(1 for _ in assets.iterdir())
        if entries == 0:
            report.add("layout.assets_nonempty", _FAIL, f"assets directory is empty: {assets}")
        else:
            report.add("layout.assets_nonempty", _OK, f"{entries} top-level entries")


def check_counts(report: Report, package_dir: Path) -> None:
    expected = dict(EXPECTED_COUNTS)
    lock_path = DEFAULT_ASSETS_LOCK
    if lock_path.is_file():
        try:
            lock = _yaml().safe_load(lock_path.read_text(encoding="utf-8")) or {}
        except Exception as error:  # noqa: BLE001 - YAML errors are opaque
            report.add("lock", _WARN, f"cannot parse {lock_path}: {error}")
            lock = {}
        counts = lock.get("counts") if isinstance(lock, dict) else None
        if isinstance(counts, dict):
            for key in ("bddl_files", "pruned_init_files"):
                if isinstance(counts.get(key), int):
                    expected[key] = int(counts[key])

    bddl_root = package_dir / "bddl_files"
    init_root = package_dir / "init_files"
    observed = {
        "bddl_files": _count(bddl_root, "*.bddl") if bddl_root.is_dir() else 0,
        "pruned_init_files": _count(init_root, "*.pruned_init") if init_root.is_dir() else 0,
    }
    for key, count in observed.items():
        wanted = expected[key]
        if count == wanted:
            report.add(f"counts.{key}", _OK, f"{count} == {wanted}")
        else:
            report.add(f"counts.{key}", _FAIL, f"{count} != expected {wanted}")

    suites = lock.get("suites") if isinstance(lock, dict) else None
    suites = suites if isinstance(suites, dict) else {}
    for suite, (want_bddl, want_init) in EXPECTED_SUITE_COUNTS.items():
        suite_expectation = suites.get(suite)
        if isinstance(suite_expectation, dict):
            want_bddl = int(suite_expectation.get("bddl", want_bddl))
            want_init = int(suite_expectation.get("pruned_init", want_init))
        got_bddl = _count(bddl_root / suite, "*.bddl") if (bddl_root / suite).is_dir() else 0
        got_init = _count(init_root / suite, "*.pruned_init") if (init_root / suite).is_dir() else 0
        if (got_bddl, got_init) == (want_bddl, want_init):
            report.add(f"counts.{suite}", _OK, f"bddl={got_bddl} pruned_init={got_init}")
        else:
            report.add(
                f"counts.{suite}",
                _FAIL,
                f"bddl={got_bddl} pruned_init={got_init} != expected "
                f"bddl={want_bddl} pruned_init={want_init}",
            )


def _sha256_file(path: Path, chunk_size: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            chunk = stream.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def check_sha256(
    report: Report,
    libero_home: Path,
    manifest_path: Path,
    *,
    require_hashes: bool,
) -> None:
    if not manifest_path.is_file():
        status = _FAIL if require_hashes else _WARN
        report.add("sha256", status, f"{manifest_path} not found")
        return
    try:
        manifest = _yaml().safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception as error:  # noqa: BLE001 - YAML errors are opaque
        report.add("sha256", _FAIL, f"cannot parse {manifest_path}: {error}")
        return
    files = manifest.get("files") if isinstance(manifest, dict) else None
    entries = files if isinstance(files, list) else []
    if not entries:
        status = _FAIL if require_hashes else _WARN
        report.add(
            "sha256",
            status,
            "content pin is empty (sha256_frozen: false); freeze it from a clean "
            "checkout — see assets/manifest.yaml",
        )
        return
    failures: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            failures.append(f"malformed manifest entry: {entry!r}")
            continue
        relative = str(entry.get("path") or "")
        wanted = str(entry.get("sha256") or "")
        if not relative or len(wanted) != 64:
            failures.append(f"malformed manifest entry: {entry!r}")
            continue
        path = libero_home / relative
        if not path.is_file():
            failures.append(f"missing file: {relative}")
            continue
        observed = _sha256_file(path)
        if observed != wanted.lower():
            failures.append(f"{relative}: {observed} != {wanted}")
    if failures:
        preview = "; ".join(failures[:5])
        suffix = f" (+{len(failures) - 5} more)" if len(failures) > 5 else ""
        report.add("sha256", _FAIL, f"{preview}{suffix}")
    else:
        report.add("sha256", _OK, f"{len(entries)} files match assets/manifest.yaml")


def print_sha256(package_dir: Path, libero_home: Path) -> int:
    patterns = (("bddl_files", "*.bddl"), ("init_files", "*.pruned_init"))
    lines: list[tuple[str, str]] = []
    for directory_name, pattern in patterns:
        root = package_dir / directory_name
        if not root.is_dir():
            continue
        for path in sorted(root.rglob(pattern)):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(libero_home)
            except ValueError:
                relative = path
            lines.append((_sha256_file(path), str(relative).replace("\\", "/")))
    for digest, relative in sorted(lines, key=lambda item: item[1]):
        print(f"{digest}  {relative}")
    print(f"# {len(lines)} files", file=sys.stderr)
    return 0


def render(report: Report) -> None:
    width = max((len(check.name) for check in report.checks), default=0)
    for check in report.checks:
        label = {_OK: "[ok]  ", _WARN: "[warn]", _FAIL: "[FAIL]"}[check.status]
        print(f"{label} {check.name:<{width}}  {check.detail}")
    print("")
    if report.failures:
        print(
            f"verify_libero: FAIL — {len(report.failures)} failure(s), "
            f"{len(report.warnings)} warning(s); LIBERO_HOME={report.libero_home}"
        )
    else:
        print(
            f"verify_libero: PASS — {len(report.checks)} checks, "
            f"{len(report.warnings)} warning(s); LIBERO_HOME={report.libero_home}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Verify a pinned upstream LIBERO checkout: commit, clean worktree, "
            "bddl/init counts and optional per-file sha256."
        ),
        epilog=(
            "example: export LIBERO_HOME=/path/to/LIBERO && "
            "python scripts/verify_libero.py --allow-dirty"
        ),
    )
    parser.add_argument(
        "--libero-home",
        default=None,
        help="upstream LIBERO checkout; defaults to $LIBERO_HOME",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="downgrade the clean-worktree failure to a warning (development only; "
        "never for a leaderboard run)",
    )
    parser.add_argument(
        "--skip-git",
        action="store_true",
        help="skip commit/worktree checks (e.g. for a source archive)",
    )
    parser.add_argument(
        "--assets-manifest",
        default=str(DEFAULT_ASSETS_MANIFEST),
        help="content-pin manifest with per-file sha256 (default: assets/manifest.yaml)",
    )
    parser.add_argument(
        "--require-hashes",
        action="store_true",
        help="fail when assets/manifest.yaml has no frozen sha256 entries "
        "(used by release CI; Phase 2 until the content pin is frozen)",
    )
    parser.add_argument(
        "--print-sha256",
        action="store_true",
        help="print `<sha256>  <path>` lines for bddl/init files and exit; "
        "does not write the manifest",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the report as JSON on stdout (human-readable by default)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.print_sha256 and args.json:
        print("--print-sha256 and --json are mutually exclusive", file=sys.stderr)
        return 2
    try:
        libero_home = resolve_libero_home(args.libero_home)
        package_dir = find_package_dir(libero_home)
    except VerifyError as error:
        print(f"verify_libero: FAIL — {error}", file=sys.stderr)
        return 1

    if args.print_sha256:
        return print_sha256(package_dir, libero_home)

    report = Report(libero_home=str(libero_home))
    check_layout(report, package_dir)
    check_git(
        report,
        libero_home,
        allow_dirty=args.allow_dirty,
        skip_git=args.skip_git,
    )
    check_counts(report, package_dir)
    check_sha256(
        report,
        libero_home,
        Path(args.assets_manifest).expanduser(),
        require_hashes=args.require_hashes,
    )

    if args.json:
        print(json.dumps(report.to_json(), indent=2, ensure_ascii=False))
    else:
        render(report)
    return 1 if report.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
