"""Audit every current binding with an explicitly selected external compiler.

Run in the external evaluator's Python environment. This compiles definitions
without loading a model or stepping the simulator; it is not physical acceptance.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    runtime = args.runtime_root.resolve()
    sys.path[:0] = [str(ROOT / "src"), str(runtime)]
    from libero_runtime.engine.spec import SpecCompiler

    from libero_rollback.runtime import (
        check_runtime_capabilities,
        load_case_for_runtime,
        runtime_binding,
    )

    compiler = SpecCompiler(str(runtime / "configs"))
    manifest = yaml.safe_load((ROOT / "dataset/current/manifest.yaml").read_text())
    rows = []
    with tempfile.TemporaryDirectory() as temporary:
        for entry in manifest["cases"]:
            path = ROOT / entry["path"]
            row = {
                "case_id": entry["case_id"],
                "case_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
            try:
                case = load_case_for_runtime(path)
                check_runtime_capabilities(case, runtime)
                binding = runtime_binding(case)
                row["binding_sha256"] = hashlib.sha256(
                    json.dumps(binding, sort_keys=True).encode()
                ).hexdigest()
                binding_path = Path(temporary) / "binding.yaml"
                binding_path.write_text(yaml.safe_dump(binding))
                specs = compiler.compile_binding(str(binding_path))
                row.update(accepted=True, compiled_specs=len(specs))
            except Exception as exc:
                row.update(accepted=False, error=f"{type(exc).__name__}: {exc}")
            rows.append(row)
    result = {
        "kind": "static_external_compilation",
        "runtime_root": str(runtime),
        "physical_acceptance": False,
        "cases": len(rows),
        "accepted": sum(row["accepted"] for row in rows),
        "rows": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}))
    return 0 if result["accepted"] == result["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
