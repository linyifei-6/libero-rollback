"""Decode every report video using PyAV in the external video environment."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import av

REPORT = Path(__file__).resolve().parents[1] / "runs/full-coverage/report"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT)
    report_dir = parser.parse_args().report.resolve()
    evidence = json.loads((report_dir / "evidence.json").read_text())
    if isinstance(evidence, dict):
        evidence = evidence["cases"].values()
    references = {
        item["path"] if isinstance(item, dict) else item: item.get("sha256")
        if isinstance(item, dict)
        else None
        for row in evidence
        for key in ("videos", "baseline_videos")
        for item in row.get(key, [])
    }
    rows = []
    for reference in sorted(references):
        path = report_dir / reference
        row = {"path": reference}
        try:
            row["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            row["hash_matches_evidence"] = references[reference] in (None, row["sha256"])
            with av.open(str(path)) as container:
                stream = container.streams.video[0]
                count = sum(1 for _ in container.decode(video=0))
                row.update(
                    codec=stream.codec_context.name,
                    decoded_frames=count,
                    declared_frames=stream.frames,
                    width=stream.width,
                    height=stream.height,
                    valid=row["hash_matches_evidence"]
                    and stream.codec_context.name == "h264"
                    and count > 0
                    and count == stream.frames,
                )
        except Exception as exc:
            row.update(valid=False, error=str(exc))
        rows.append(row)
    audit = {
        "video_count": len(rows),
        "all_referenced_videos_decode": bool(rows) and all(row["valid"] for row in rows),
        "videos": rows,
    }
    (report_dir / "video-audit.json").write_text(json.dumps(audit, indent=2))
    print(json.dumps({key: value for key, value in audit.items() if key != "videos"}, indent=2))
    return int(not audit["all_referenced_videos_decode"])


if __name__ == "__main__":
    raise SystemExit(main())
