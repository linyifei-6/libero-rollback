#!/usr/bin/env python3
"""Write the repo-local LIBERO ``config.yaml`` (never ``~/.libero``).

Upstream LIBERO locates its assets through ``$LIBERO_CONFIG_PATH/config.yaml``.
If that file is missing, importing ``libero`` asks an interactive question and
CI / runner subprocesses hang. This script writes the file non-interactively
from an explicit checkout path, after checking the asset layout.

It is the first of the three asset-pin layers:

    scripts/bootstrap_libero.py   generate the local config (this script)
    scripts/verify_libero.py      hard-fail on commit/worktree/count/digest drift
    assets/libero.lock.yaml       committed code pin + expected counts

Usage::

    export LIBERO_HOME=/path/to/LIBERO
    uv run python scripts/bootstrap_libero.py --libero-home "$LIBERO_HOME" \\
        --out .cache/libero

    # Validate only, never write:
    uv run python scripts/bootstrap_libero.py --check

The generated ``config.yaml`` lives under a gitignored directory and therefore
contains local paths; committed configuration never does. The repository-
committed pin is ``assets/libero.lock.yaml``.

Dependencies: Python stdlib + PyYAML (the project's only runtime dependency).
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = REPO_ROOT / ".cache" / "libero"
LIBERO_HOME_ENV = "LIBERO_HOME"
CONFIG_KEYS = ("benchmark_root", "bddl_files", "init_states", "datasets", "assets")

#: Directory names that must exist under the ``libero/libero`` package.
REQUIRED_PACKAGE_DIRS = ("bddl_files", "init_files", "assets")


class BootstrapError(RuntimeError):
    """Raised when the asset layout cannot be bootstrapped."""


def _yaml():
    try:
        import yaml  # noqa: PLC0415 - lazy import for a clear error message
    except ImportError as error:  # pragma: no cover - project dependency
        raise BootstrapError(
            "PyYAML is required (install the project with `uv sync`): " + str(error)
        ) from error
    return yaml


def resolve_libero_home(cli_value: str | None) -> Path:
    """Resolve ``--libero-home`` with ``$LIBERO_HOME`` as the fallback."""

    raw = cli_value or os.environ.get(LIBERO_HOME_ENV)
    if not raw:
        raise BootstrapError(
            "LIBERO_HOME is not set; pass --libero-home /path/to/LIBERO or export "
            f"{LIBERO_HOME_ENV} (see .env.example)"
        )
    path = Path(raw).expanduser()
    if not path.exists():
        raise BootstrapError(f"LIBERO_HOME does not exist: {path}")
    if not path.is_dir():
        raise BootstrapError(f"LIBERO_HOME is not a directory: {path}")
    return path


def find_package_dir(libero_home: Path) -> Path:
    """Return the ``libero/libero`` package directory that owns the assets."""

    candidates = (
        libero_home / "libero" / "libero",
        libero_home,
        libero_home / "libero",
    )
    for candidate in candidates:
        if (candidate / "__init__.py").is_file() and (candidate / "bddl_files").is_dir():
            return candidate
    raise BootstrapError(
        f"cannot locate the LIBERO package under {libero_home}: expected "
        "`<LIBERO_HOME>/libero/libero/__init__.py` plus bddl_files/init_files/assets "
        "(did you clone the upstream LIBERO repository, not a derived dataset?)"
    )


def count_files(directory: Path, pattern: str) -> int:
    return sum(1 for path in directory.rglob(pattern) if path.is_file())


def check_layout(libero_home: Path, *, require_datasets: bool) -> tuple[Path, list[str]]:
    """Check the asset layout and return ``(package_dir, warnings)``."""

    package_dir = find_package_dir(libero_home)
    warnings: list[str] = []
    for name in REQUIRED_PACKAGE_DIRS:
        directory = package_dir / name
        if not directory.is_dir():
            raise BootstrapError(f"incomplete LIBERO checkout: missing {directory}")
    if not any((package_dir / "bddl_files").rglob("*.bddl")):
        raise BootstrapError(f"no .bddl files under {package_dir / 'bddl_files'}")
    if not any((package_dir / "init_files").rglob("*.pruned_init")):
        raise BootstrapError(f"no .pruned_init files under {package_dir / 'init_files'}")
    if not any((package_dir / "assets").iterdir()):
        raise BootstrapError(f"assets directory is empty: {package_dir / 'assets'}")

    datasets_dir = libero_home / "datasets"
    if not datasets_dir.is_dir():
        message = (
            f"datasets directory not found: {datasets_dir} "
            "(only needed for training data; the config key still points there)"
        )
        if require_datasets:
            raise BootstrapError(message)
        warnings.append(message)
    return package_dir, warnings


def build_config(libero_home: Path, package_dir: Path) -> dict[str, str]:
    """Build the five-key ``config.yaml`` payload (paths are local, gitignored)."""

    return {
        "benchmark_root": str(package_dir),
        "bddl_files": str(package_dir / "bddl_files"),
        "init_states": str(package_dir / "init_files"),
        "datasets": str(libero_home / "datasets"),
        "assets": str(package_dir / "assets"),
    }


def resolve_out(cli_value: str | None) -> Path:
    raw = cli_value or os.environ.get("LIBERO_CONFIG_PATH") or str(DEFAULT_OUT)
    return Path(raw).expanduser()


def guard_out(out: Path, libero_home: Path) -> None:
    """Refuse to write into the global ``~/.libero`` or into the checkout."""

    absolute = out.absolute()
    home_default = Path.home() / ".libero"
    if absolute == home_default.absolute():
        raise BootstrapError(
            "refusing to write ~/.libero: it is shared with other LIBERO variants "
            "and pollutes them. Use the repo-local .cache/libero instead."
        )
    if absolute == libero_home.absolute() or libero_home.absolute() in absolute.parents:
        raise BootstrapError(f"refusing to write inside the read-only LIBERO checkout: {out}")


def load_existing(config_path: Path) -> dict[str, Any] | None:
    if not config_path.is_file():
        return None
    payload = _yaml().safe_load(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BootstrapError(f"{config_path}: config.yaml is not a YAML mapping")
    return payload


def compare(existing: dict[str, Any], expected: dict[str, str]) -> list[str]:
    issues: list[str] = []
    for key in CONFIG_KEYS:
        if key not in existing:
            issues.append(f"missing key {key!r}")
        elif Path(str(existing[key])).expanduser() != Path(expected[key]).expanduser():
            issues.append(f"{key}: {existing[key]!r} != expected {expected[key]!r}")
    extra = sorted(set(existing) - set(CONFIG_KEYS))
    if extra:
        issues.append(f"unexpected keys: {extra}")
    return issues


def write_config(out: Path, config: dict[str, str]) -> Path:
    yaml = _yaml()
    out.mkdir(parents=True, exist_ok=True)
    config_path = out / "config.yaml"
    text = yaml.safe_dump(config, sort_keys=False, allow_unicode=True)
    config_path.write_text(text, encoding="utf-8", newline="\n")
    return config_path


def print_exports(libero_home: Path, out: Path) -> None:
    print("")
    print("Add these to your shell (or .env) before importing LIBERO:")
    print(f'  export {LIBERO_HOME_ENV}="{libero_home}"')
    print(f'  export LIBERO_CONFIG_PATH="{out}"')


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the repo-local LIBERO config.yaml from an upstream checkout. "
            "Never writes ~/.libero and never prompts."
        ),
        epilog=(
            "example: export LIBERO_HOME=/path/to/LIBERO && "
            'python scripts/bootstrap_libero.py --libero-home "$LIBERO_HOME" --out .cache/libero'
        ),
    )
    parser.add_argument(
        "--libero-home",
        default=None,
        help="upstream LIBERO checkout; defaults to $LIBERO_HOME",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="config directory (config.yaml is written there); "
        "defaults to $LIBERO_CONFIG_PATH or <repo>/.cache/libero",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the asset layout and any existing config.yaml, but never write",
    )
    parser.add_argument(
        "--require-datasets",
        action="store_true",
        help="treat a missing <LIBERO_HOME>/datasets directory as an error "
        "(default: warning; demonstrations are not needed for evaluation)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="only print errors and the export lines",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        libero_home = resolve_libero_home(args.libero_home)
        out = resolve_out(args.out)
        guard_out(out, libero_home)
        package_dir, warnings = check_layout(libero_home, require_datasets=args.require_datasets)
        config = build_config(libero_home, package_dir)
    except BootstrapError as error:
        print(f"[bootstrap_libero] FAIL: {error}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"[bootstrap_libero] LIBERO_HOME   : {libero_home}")
        print(f"[bootstrap_libero] package dir    : {package_dir}")
        print(
            "[bootstrap_libero] bddl/init files : "
            f"{count_files(package_dir / 'bddl_files', '*.bddl')} .bddl / "
            f"{count_files(package_dir / 'init_files', '*.pruned_init')} .pruned_init "
            "(expected 130 / 130)"
        )
        print(f"[bootstrap_libero] config target  : {out / 'config.yaml'}")
        for warning in warnings:
            print(f"[bootstrap_libero] warning: {warning}")

    config_path = out / "config.yaml"
    if args.check:
        existing = load_existing(config_path)
        if existing is None:
            print(
                f"[bootstrap_libero] CHECK: layout OK; {config_path} does not exist yet "
                "(run without --check to write it)"
            )
            print_exports(libero_home, out)
            return 0
        issues = compare(existing, config)
        if issues:
            print(
                f"[bootstrap_libero] CHECK: FAIL — {config_path} does not match the "
                "current checkout:",
                file=sys.stderr,
            )
            for issue in issues:
                print(f"  - {issue}", file=sys.stderr)
            print(
                "[bootstrap_libero] re-run without --check to rewrite the config",
                file=sys.stderr,
            )
            return 1
        print(f"[bootstrap_libero] CHECK: OK — {config_path} matches the checkout")
        print_exports(libero_home, out)
        return 0

    try:
        write_config(out, config)
    except OSError as error:
        print(f"[bootstrap_libero] FAIL: cannot write {config_path}: {error}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(f"[bootstrap_libero] wrote {config_path} ({len(config)} keys)")
    print_exports(libero_home, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
