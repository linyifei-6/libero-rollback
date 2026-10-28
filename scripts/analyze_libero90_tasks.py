"""Parse the LIBERO-90 BDDL suite and report per-task instruction + goal structure.

Read-only analysis helper. It does not touch the dataset or run any simulator.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_SUITE = Path.home() / (
    "workspace/roboot/libero-plus/LIBERO-plus/libero/libero/bddl_files/libero_90"
)


def tokenize(text: str) -> list[str]:
    text = re.sub(r";[^\n]*", "", text)
    return re.findall(r"\(|\)|[^\s()]+", text)


def parse_sexp(tokens: list[str], pos: int = 0):
    if tokens[pos] != "(":
        return tokens[pos], pos + 1
    pos += 1
    out = []
    while tokens[pos] != ")":
        node, pos = parse_sexp(tokens, pos)
        out.append(node)
    return out, pos + 1


def find_block(tree, key: str):
    for node in tree:
        if isinstance(node, list) and node and node[0] == key:
            return node
    return None


def flatten_goal(goal_block) -> list[tuple[str, tuple[str, ...]]]:
    if goal_block is None or len(goal_block) < 2:
        return []
    cond = goal_block[1]
    atoms: list[tuple[str, tuple[str, ...]]] = []

    def walk(node):
        if isinstance(node, str):
            return
        if node and node[0] == "And":
            for child in node[1:]:
                walk(child)
        elif node and node[0] == "Not":
            walk(node[1])
        else:
            atoms.append((node[0], tuple(str(a) for a in node[1:])))

    walk(cond)
    return atoms


def scene_of(name: str) -> str:
    m = re.match(r"([A-Z_]+_SCENE\d+)", name)
    return m.group(1) if m else name.split("_")[0]


def describe_atom(atom: tuple[str, tuple[str, ...]]) -> str:
    pred, args = atom
    return f"({pred} {' '.join(args)})"


ARTICULATION_PREDS = {"Close", "Open"}
SWITCH_PREDS = {"Turnon", "Turnoff"}
PLACEMENT_PREDS = {"On", "In"}


def classify(atoms):
    preds = [a[0] for a in atoms]
    return {
        "n_goal_atoms": len(atoms),
        "predicates": preds,
        "n_placement": sum(p in PLACEMENT_PREDS for p in preds),
        "n_articulation": sum(p in ARTICULATION_PREDS for p in preds),
        "n_switch": sum(p in SWITCH_PREDS for p in preds),
        "multi_stage": len(atoms) >= 2,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    ap.add_argument("--json", type=Path, default=None)
    args = ap.parse_args()

    suite: Path = args.suite
    listing = (suite / "tasks_info.txt").read_text().splitlines()
    listed = [ln.strip() for ln in listing if ln.strip()]
    listed_names = [Path(ln).stem for ln in listed]
    dir_names = sorted(p.stem for p in suite.glob("*.bddl"))

    rows = []
    for idx, name in enumerate(listed_names):
        path = suite / f"{name}.bddl"
        tree, _ = parse_sexp(tokenize(path.read_text()))
        lang_block = find_block(tree, ":language")
        goal_block = find_block(tree, ":goal")
        atoms = flatten_goal(goal_block)
        rows.append(
            {
                "index": idx,
                "bddl": path.name,
                "scene": scene_of(name),
                "language": " ".join(lang_block[1:]) if lang_block else None,
                "goal": " ".join(describe_atom(a) for a in atoms),
                "goal_atoms": [describe_atom(a) for a in atoms],
                **classify(atoms),
            }
        )

    payload = {
        "suite": str(suite),
        "n_listed": len(listed),
        "n_bddl_in_dir": len(dir_names),
        "extra_bddl_not_listed": sorted(set(dir_names) - set(listed_names)),
        "missing_bddl": sorted(set(listed_names) - set(dir_names)),
        "tasks": rows,
    }

    multi = [r for r in rows if r["multi_stage"]]
    print(f"listed={len(listed)} bddl_in_dir={len(dir_names)} multi_stage={len(multi)}")
    print(f"extra={payload['extra_bddl_not_listed']}")
    print(f"missing={payload['missing_bddl']}")
    for r in rows:
        flag = "MULTI" if r["multi_stage"] else "     "
        print(f"{r['index']:02d} {flag} [{','.join(r['predicates'])}] {r['language']}")

    if args.json:
        args.json.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {args.json}")


if __name__ == "__main__":
    main()
