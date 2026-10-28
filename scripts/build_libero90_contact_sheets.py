"""Build contact sheets from LIBERO-90 baseline videos (cv2, no ffmpeg needed).

Usage:
    python3 scripts/build_libero90_contact_sheets.py \
        --run-dir runs/<name> --task T64 --seed 0
    python3 scripts/build_libero90_contact_sheets.py --run-dir runs/<name> --all
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

COLS, ROWS = 4, 3


def latest_video_dir(run_dir: Path) -> Path:
    candidates = [p for p in run_dir.iterdir() if p.is_dir() and (p / "videos").is_dir()]
    if not candidates:
        raise SystemExit(f"no videos/ under {run_dir}")
    return max(candidates, key=lambda p: p.stat().st_mtime) / "videos"


def contact_sheet(video: Path, out: Path, n: int = COLS * ROWS) -> None:
    cap = cv2.VideoCapture(str(video))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frames = []
    for i in range(n):
        idx = int(i * max(total - 1, 0) / max(n - 1, 1))
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        frame = cv2.resize(frame, (256, 256))
        frame = cv2.copyMakeBorder(frame, 18, 2, 2, 2, cv2.BORDER_CONSTANT, value=(0, 0, 0))
        cv2.putText(
            frame,
            f"f{idx}/{total}",
            (6, 13),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        frames.append(frame)
    cap.release()
    if not frames:
        print(f"no frames read from {video}")
        return
    while len(frames) < n:
        frames.append(np.zeros_like(frames[0]))
    rows = [np.hstack(frames[r * COLS : (r + 1) * COLS]) for r in range(ROWS)]
    grid = np.vstack(rows)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), grid)
    print(f"{out}  ({grid.shape[1]}x{grid.shape[0]}) from {video.name} ({total} frames)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--task", action="append", default=[], help="e.g. T63")
    ap.add_argument("--seed", type=int, default=None, help="filter by episode seed")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out-dir", type=Path, default=None)
    args = ap.parse_args()

    video_dir = latest_video_dir(args.run_dir)
    out_dir = args.out_dir or video_dir.parent / "frames"
    patterns = ["*"] if args.all or not args.task else [f"LIBERO_90_{t}__*" for t in args.task]

    for pattern in patterns:
        for video in sorted(video_dir.glob(f"{pattern}.mp4")):
            if args.seed is not None and f"seed{args.seed}" not in video.name:
                continue
            tag = video.stem.replace("__baseline", "")
            contact_sheet(video, out_dir / f"{tag}-contact.jpg")


if __name__ == "__main__":
    main()
