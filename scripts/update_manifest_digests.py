"""Recompute manifest.files SHA-256 digests for a dataset release.

The manifest is the integrity contract for a release. This tool only recomputes
digests for paths the manifest already declares; it never adds or drops an entry,
and it refuses to run when a declared path is missing.

Usage:
    python scripts/update_manifest_digests.py --dataset-root dataset/v1.1
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def recompute(dataset_root: Path) -> tuple[int, int, list[str]]:
    manifest_path = dataset_root / "manifest.yaml"
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    repo_root = dataset_root.resolve().parents[1]
    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise SystemExit("manifest.files must be a non-empty list")
    changed = 0
    missing: list[str] = []
    for entry in entries:
        relative = Path(str(entry.get("path", "")))
        if relative.is_absolute() or ".." in relative.parts:
            raise SystemExit(f"unsafe manifest path: {relative}")
        target = repo_root / relative
        if not target.is_file():
            missing.append(str(relative))
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if entry.get("sha256") != digest:
            entry["sha256"] = digest
            changed += 1
    if missing:
        return changed, len(entries), missing
    manifest_path.write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    return changed, len(entries), []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-root", type=Path, default=ROOT / "dataset/v1.1")
    parser.add_argument("--check", action="store_true", help="report without writing")
    args = parser.parse_args()
    dataset_root = args.dataset_root if args.dataset_root.is_absolute() else ROOT / args.dataset_root
    if args.check:
        manifest = yaml.safe_load((dataset_root / "manifest.yaml").read_text(encoding="utf-8"))
        repo_root = dataset_root.resolve().parents[1]
        stale = [
            str(entry["path"])
            for entry in manifest["files"]
            if hashlib.sha256((repo_root / entry["path"]).read_bytes()).hexdigest()
            != entry.get("sha256")
        ]
        print(f"stale digests: {len(stale)}")
        for path in stale[:20]:
            print("  ", path)
        return int(bool(stale))
    changed, total, missing = recompute(dataset_root)
    if missing:
        print(f"REFUSED: {len(missing)} declared paths are missing")
        for path in missing[:20]:
            print("  ", path)
        return 1
    print(f"{dataset_root}/manifest.yaml: {changed}/{total} digests updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
