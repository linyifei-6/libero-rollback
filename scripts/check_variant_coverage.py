"""Verify the runtime template declares every variant the v1.3 cases need.

The sweep maps each articulation case to a template severity variant; a missing
variant would only surface when that case starts, so check the whole set up front.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml

REPO = Path("/home/tarowang/workspace/roboot/libero-rollback")
RUNTIME = REPO / "runs/full-coverage/runtime"
sys.path.insert(0, str(REPO / "src"))
from libero_rollback.runtime import runtime_binding  # noqa: E402

TEMPLATES = {}
for path in (RUNTIME / "configs/perturbation_templates").rglob("*.yaml"):
    doc = yaml.safe_load(path.read_text())
    template = doc.get("case_template") if isinstance(doc, dict) else None
    if template:
        TEMPLATES[template["id"]] = template

print("templates:", sorted(TEMPLATES))

needed: Counter = Counter()
missing: list[tuple[str, str, str]] = []
for path in sorted((REPO / "dataset/v1.3/cases").glob("*.yaml")):
    case = yaml.safe_load(path.read_text())
    binding = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    template_id = binding["template"]
    variant = binding["severities"][0]
    needed[(template_id, variant)] += 1
    template = TEMPLATES.get(template_id)
    if template is None:
        missing.append((case["case_id"], template_id, "TEMPLATE MISSING"))
    elif variant not in template.get("severity", {}):
        missing.append((case["case_id"], template_id, variant))

print(f"\ndistinct (template, variant) pairs needed: {len(needed)}")
by_template: Counter = Counter(k[0] for k in needed)
for template_id, count in by_template.most_common():
    print(f"  {template_id:<44}{count} variants")

print(f"\nmissing variants: {len(missing)}")
for case_id, template_id, variant in missing[:10]:
    print(f"  {case_id:<58} {template_id} :: {variant}")

# spot-check that declared setbacks match the requested ones
mismatch = []
for path in sorted((REPO / "dataset/v1.3/cases").glob("*.yaml")):
    case = yaml.safe_load(path.read_text())
    if case["severity"] != "articulation":
        continue
    setback = float(case["rollback_target"]["state_change"]["setback"])
    entry = runtime_binding(case)["perturbation_binding"]["enabled_cases"][0]
    declared = TEMPLATES[entry["template"]]["severity"][entry["severities"][0]]["setback"]
    if abs(float(declared) - setback) > 1e-9:
        mismatch.append((case["case_id"], setback, declared))
print(f"\narticulation setback mismatches: {len(mismatch)}")
for case_id, requested, declared in mismatch[:10]:
    print(f"  {case_id}: requested {requested} but variant declares {declared}")
