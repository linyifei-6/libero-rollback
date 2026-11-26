#!/usr/bin/env python3
"""Write ``provenance.json`` for one run directory (thin CLI wrapper).

The implementation lives in :mod:`libero_rollback.provenance`; the runner calls
it automatically, so this script is only needed for runs produced before that
integration (or to regenerate a record).

Usage::

    python scripts/write_provenance.py --run runs/smolvla-smoke \
        --checkpoint work/ckpt/smolvla_local --libero-home work/assets/LIBERO
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from libero_rollback.provenance import build_provenance  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--run", type=Path, required=True, help="run directory")
    parser.add_argument("--checkpoint", type=Path, default=None, help="model checkpoint")
    parser.add_argument("--libero-home", type=Path, default=None, help="upstream LIBERO checkout")
    parser.add_argument("--out", type=Path, default=None, help="default: <run>/provenance.json")
    args = parser.parse_args(argv)
    if not args.run.is_dir():
        print(f"error: run directory not found: {args.run}", file=sys.stderr)
        return 2
    import json

    payload = build_provenance(args.run, checkpoint=args.checkpoint, libero_home=args.libero_home)
    out = args.out or args.run / "provenance.json"
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"provenance written: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
