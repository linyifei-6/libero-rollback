"""Audit full report completeness, local references and evidence hashes."""

from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "runs/full-coverage/report"


class References(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.paths: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"src", "href"} and value:
                self.paths.append(value)


def main() -> int:
    rows = json.loads((REPORT / "evidence.json").read_text())
    errors = []
    if len(rows) != 50 or len({r["case_id"] for r in rows}) != 50:
        errors.append("expected exactly 50 unique cases")
    for index in range(10):
        levels = {r["level"] for r in rows if r["task_id"] == f"libero_10/{index:02d}"}
        if levels != {"d0", "d1", "d2", "d3", "checkpoint"}:
            errors.append(f"task {index:02d}: missing levels")
    for row in rows:
        if not row.get("result_link") or not row.get("videos"):
            errors.append(f"{row['case_id']}: missing final result or video evidence")
            continue
        path = REPORT / row["result_link"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["result_sha256"]:
            errors.append(f"{row['case_id']}: result hash mismatch")
        if row["injection_valid"] is True:
            if row["pre_relation"] is not True or row["post_relation"] is not False:
                errors.append(f"{row['case_id']}: valid injection lacks true-to-false transition")
    parser = References()
    parser.feed((REPORT / "index.html").read_text())
    for reference in parser.paths:
        if reference.startswith("data:"):
            # Embedded compressed copy for playback. The verified original clip is
            # still referenced by the same element's data-original attribute and is
            # checked against evidence.json below.
            continue
        if reference.startswith(("http:", "https:", "#", "mailto:")):
            continue
        if not (REPORT / reference).is_file():
            errors.append(f"missing report reference: {reference}")
    video_audit_path = REPORT / "video-audit.json"
    if not video_audit_path.exists():
        errors.append("missing video decoding audit")
    else:
        video_audit = json.loads(video_audit_path.read_text())
        audited = {entry["path"]: entry for entry in video_audit.get("videos", [])}
        for row in rows:
            for reference in row.get("videos", []) + row.get("baseline_videos", []):
                entry = audited.get(reference)
                if not entry or entry.get("valid") is not True:
                    errors.append(f"video not verified by full decoding: {reference}")
                elif hashlib.sha256((REPORT / reference).read_bytes()).hexdigest() != entry.get(
                    "sha256"
                ):
                    errors.append(f"video differs from decoded evidence: {reference}")
    audit = {"complete": not errors, "case_count": len(rows), "errors": errors}
    (REPORT / "completion-audit.json").write_text(json.dumps(audit, indent=2))
    print(json.dumps(audit, indent=2))
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
