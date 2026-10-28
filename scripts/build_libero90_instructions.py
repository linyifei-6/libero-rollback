#!/usr/bin/env python3
"""Rebuild the LIBERO-90 combined-candidate instructions from verified templates.

The previous artifact (``candidates.json``) built each combined instruction by naively
concatenating the two official task languages with " and ".  The user's requirement is
to rebuild every instruction **from success templates validated in LIBERO-10 /
LIBERO-GOAL / LIBERO-OBJECT**, e.g. two placements into one container must use the
LIBERO-10 "put both the A and the B in the C" template (OBJECT v3: 12/300 = 4.0%)
instead of the naive two-sentence concatenation.

Inputs (read-only):
    runs/libero-90-combos-20261025/candidates.json         N candidates, read-only (never modified)
    .tmp/libero90-combos/inventory.json                    goal_atom_args / objects / init
    .tmp/libero90-combos/official-language-and-benchmark-map.json   official languages

Outputs (only these two are written):
    runs/libero-90-combos-20261025/candidates-instructed.json
        = candidates.json + {instruction, instruction_template, instruction_variants,
                            instruction_evidence, instruction_source, instruction_clauses}
    runs/libero-90-combos-20261025/INSTRUCTION_TEMPLATES.md
        = template table, evidence, per-template examples, hit statistics, ambiguity notes

No simulation, no network; original candidates.json / CASE_LIST.md / README.md /
build_libero90_combos.py are never modified (their sha256 is recorded and re-checked).

Usage (repo root, repo .venv python):
    .venv/bin/python scripts/build_libero90_instructions.py
    .venv/bin/python scripts/build_libero90_instructions.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RUN_DIR = REPO / "runs" / "libero-90-combos-20261025"
CANDIDATES_JSON = RUN_DIR / "candidates.json"
INSTRUCTED_JSON = RUN_DIR / "candidates-instructed.json"
TEMPLATES_MD = RUN_DIR / "INSTRUCTION_TEMPLATES.md"
TMP_DIR = REPO / ".tmp" / "libero90-combos"
INVENTORY_JSON = TMP_DIR / "inventory.json"
OFFICIAL_MAP_JSON = TMP_DIR / "official-language-and-benchmark-map.json"
GEN_SCRIPT = REPO / "scripts" / "build_libero90_combos.py"
CASE_LIST_MD = RUN_DIR / "CASE_LIST.md"
README_MD = RUN_DIR / "README.md"

DEFAULT_LIBERO_ROOT = "/home/tarowang/workspace/roboot/libero-plus/LIBERO-plus/libero/libero"
LIBERO_ROOT = Path(__import__("os").environ.get("LIBERO_ROOT", DEFAULT_LIBERO_ROOT))
L10_TASKS_INFO = LIBERO_ROOT / "bddl_files" / "libero_10" / "tasks_info.txt"

TEMPLATE_IDS = ("T1", "T2", "T3", "T4", "T4b", "T5", "T6", "T7", "T8", "T9", "T10")
TEMPLATE_ORDER = {tid: i for i, tid in enumerate(TEMPLATE_IDS)}
PLACEMENT_KINDS = ("place", "stack")
ARTICULATION_KINDS = ("open", "close")
SWITCH_KINDS = ("turn_on", "turn_off")

# --- evidence constants (quoted from the reference-suite experiment reports) ------
EVIDENCE_OBJECT_V3 = ("LIBERO-OBJECT v3: 100 candidates x 3 seeds = 300 episodes, 12 success "
                      "= 4.0% (6 candidates >=1 success, 5 >=2 seeds, 1 at 3/3; "
                      "runs/libero-object-summary-20261025/SUMMARY.md)")
EVIDENCE_L10_PUT_BOTH = ("LIBERO-10 /04 /05 /06 official: `put both the A and the B in the basket` "
                         "(same template family as OBJECT v3)")
EVIDENCE_L10_STACK = ("LIBERO-10 /03 official: `put both moka pots on the stove`")
EVIDENCE_L10_TWO_PUT = ("LIBERO-10 /07 /08 official: two `put ...` clauses for two different destinations")
EVIDENCE_L10_PLACE_CLOSE = ("LIBERO-10 /01 /02 official: `put ... in ... and close it`")
EVIDENCE_L90_OPEN_PLACE = ("LIBERO-90 /00 official: `open the top drawer of the cabinet and put the bowl in it`")
EVIDENCE_L10_TURN_ON = ("LIBERO-10 /00 official: `turn on the stove and put the moka pot on it`")
EVIDENCE_GOAL_IT = ("LIBERO-GOAL `it`-ellipsis variant: 07_01 4/9 -> 7/9 (+3); "
                    "runs/instruction-variants-20261024/FINAL_VARIANT_RESULTS.md")
EVIDENCE_GOAL_THEN = ("LIBERO-GOAL `then` variant: 06_08 5/9 -> 7/9 (+2), 06_07 2/9 -> 6/9 (+4); "
                      "runs/instruction-variants-20261024/FINAL_VARIANT_RESULTS.md")
EVIDENCE_GOAL_INTEGRATED_NEG = ("LIBERO-GOAL `integrated` variant: 06_01 8/9 -> 0/9 (-8) -> rejected")
EVIDENCE_BOTH_SURFACE_NOTE = ("GOAL `both` on two objects on the same surface showed no gain (0/6); `both` is "
                              "kept only because it is the official LIBERO-10 template for same-destination goals")
EVIDENCE_L90_STACK = ("LIBERO-90 /40 /41 official: `stack the left bowl on the right bowl and place them in the "
                      "tray`")
EVIDENCE_L10_CHAIN = ("LIBERO-10 /09 + LIBERO-90 multi-clause official languages: normalized "
                      "put/stack/open/close/turn two-clause chains")

# Template catalogue: id -> display info / reference evidence / source label used in
# candidates-instructed.json instruction_source.
TEMPLATE_INFO = {
    "T1": {
        "name": "同容器双物体（In+In 同一容器）",
        "pattern": "put both {objA} and {objB} in {container}",
        "renders": "put both ",
        "refs": ["LIBERO-10 /04", "LIBERO-10 /05", "LIBERO-10 /06", "LIBERO-OBJECT v3"],
        "example": "put both the alphabet soup and the cream cheese box in the basket",
        "evidence": [EVIDENCE_L10_PUT_BOTH, EVIDENCE_OBJECT_V3],
        "source": "template:L10-04",
    },
    "T2": {
        "name": "同落点双物体（On+On / 同目标短语）",
        "pattern": "put both {objA} and {objB} {dest_phrase}",
        "renders": "put both ",
        "refs": ["LIBERO-10 /03"],
        "example": "put both moka pots on the stove",
        "evidence": [EVIDENCE_L10_STACK, EVIDENCE_BOTH_SURFACE_NOTE],
        "source": "template:L10-03",
    },
    "T3": {
        "name": "不同落点双物体（放置+放置）",
        "pattern": "put {objA} {destA} and put {objB} {destB}",
        "renders": " and put ",
        "refs": ["LIBERO-10 /07", "LIBERO-10 /08"],
        "example": "put the white mug on the left plate and put the yellow and white mug on the right plate",
        "evidence": [EVIDENCE_L10_TWO_PUT],
        "source": "template:L10-07",
    },
    "T4": {
        "name": "放置+关闭同一容器（单物体）",
        "pattern": "put {obj} {dest} and close it",
        "renders": "and close it",
        "refs": ["LIBERO-10 /01", "LIBERO-10 /02"],
        "example": "put the black bowl in the bottom drawer of the cabinet and close it",
        "evidence": [EVIDENCE_L10_PLACE_CLOSE, EVIDENCE_GOAL_THEN],
        "source": "template:L10-01",
    },
    "T4b": {
        "name": "双物体入同一容器+关闭",
        "pattern": "put both {objA} and {objB} in {container} and close it",
        "renders": "put both ",
        "refs": ["LIBERO-10 /01", "LIBERO-10 /02", "LIBERO-10 /04", "LIBERO-10 /05", "LIBERO-10 /06"],
        "example": "put both the butter at the front and the black bowl in the top drawer of the cabinet and close it",
        "evidence": [EVIDENCE_L10_PLACE_CLOSE, EVIDENCE_L10_PUT_BOTH, EVIDENCE_GOAL_THEN],
        "source": "template:L10-01",
    },
    "T5": {
        "name": "打开+放入同一容器",
        "pattern": "open {container} and put {obj} in it",
        "renders": " in it",
        "refs": ["LIBERO-90 /00", "LIBERO-90 /03"],
        "example": "open the top drawer of the cabinet and put the bowl in it",
        "evidence": [EVIDENCE_L90_OPEN_PLACE],
        "source": "template:L90-00",
    },
    "T6": {
        "name": "放置+打开（不同容器）",
        "pattern": "{put clause} and open {container}",
        "renders": " and open ",
        "refs": ["LIBERO-10 /09", "LIBERO-90 /01 /03"],
        "example": "put the black bowl on top of the cabinet and open the top drawer of the cabinet",
        "evidence": [EVIDENCE_L10_CHAIN],
        "source": "template:L10-09",
    },
    "T7": {
        "name": "放置+Turnon（同一炉体）",
        "pattern": "put {obj} {dest} and turn it on  /  turn on {fixture} and put {obj} on it",
        "renders": "turn it on",
        "refs": ["LIBERO-10 /00"],
        "example": "turn on the stove and put the moka pot on it",
        "evidence": [EVIDENCE_L10_TURN_ON, EVIDENCE_GOAL_IT],
        "source": "template:L10-00",
    },
    "T8": {
        "name": "放置+Turnoff（同一炉体）",
        "pattern": "put {obj} {dest} and turn it off  /  turn off {fixture} and put {obj} on it",
        "renders": "turn it off",
        "refs": ["LIBERO-10 /00", "S1 rescue"],
        "example": "put the left moka pot on the stove and turn it off",
        "evidence": [EVIDENCE_L10_TURN_ON, EVIDENCE_GOAL_IT],
        "source": "template:L10-00",
    },
    "T9": {
        "name": "叠放链（stack_anchor）",
        "pattern": "{base placement clause} and stack {upper} on top of it",
        "renders": "on top of it",
        "refs": ["LIBERO-90 /40", "LIBERO-90 /41", "KITCHEN_SCENE2 stack pairs"],
        "example": "put the black bowl at the back on the plate and stack the middle black bowl on top of it",
        "evidence": [EVIDENCE_L90_STACK, EVIDENCE_GOAL_THEN],
        "source": "template:L90-40",
    },
    "T10": {
        "name": "其余两/三子句链（放置/关节/开关混合）",
        "pattern": "normalized put/stack/open/close/turn-on/turn-off clauses joined by and",
        "renders": " and ",
        "refs": ["LIBERO-10 /09", "LIBERO-90 multi-clause official"],
        "example": "close the bottom drawer of the cabinet and open the top drawer",
        "evidence": [EVIDENCE_L10_CHAIN],
        "source": "template:L10-09",
    },
}

# LIBERO-10 official task languages (filename-derived, verified against tasks_info.txt)
L10_TASKS = [
    ("KITCHEN_SCENE3_turn_on_the_stove_and_put_the_moka_pot_on_it",
     "turn on the stove and put the moka pot on it"),
    ("KITCHEN_SCENE4_put_the_black_bowl_in_the_bottom_drawer_of_the_cabinet_and_close_it",
     "put the black bowl in the bottom drawer of the cabinet and close it"),
    ("KITCHEN_SCENE6_put_the_yellow_and_white_mug_in_the_microwave_and_close_it",
     "put the yellow and white mug in the microwave and close it"),
    ("KITCHEN_SCENE8_put_both_moka_pots_on_the_stove",
     "put both moka pots on the stove"),
    ("LIVING_ROOM_SCENE1_put_both_the_alphabet_soup_and_the_cream_cheese_box_in_the_basket",
     "put both the alphabet soup and the cream cheese box in the basket"),
    ("LIVING_ROOM_SCENE2_put_both_the_alphabet_soup_and_the_tomato_sauce_in_the_basket",
     "put both the alphabet soup and the tomato sauce in the basket"),
    ("LIVING_ROOM_SCENE2_put_both_the_cream_cheese_box_and_the_butter_in_the_basket",
     "put both the cream cheese box and the butter in the basket"),
    ("LIVING_ROOM_SCENE5_put_the_white_mug_on_the_left_plate_and_put_the_yellow_and_white_mug_on_the_right_plate",
     "put the white mug on the left plate and put the yellow and white mug on the right plate"),
    ("LIVING_ROOM_SCENE6_put_the_white_mug_on_the_plate_and_put_the_chocolate_pudding_to_the_right_of_the_plate",
     "put the white mug on the plate and put the chocolate pudding to the right of the plate"),
    ("STUDY_SCENE1_pick_up_the_book_and_place_it_in_the_back_compartment_of_the_caddy",
     "pick up the book and place it in the back compartment of the caddy"),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def split_atom(atom: str):
    body = atom.strip()
    if not (body.startswith("(") and body.endswith(")")):
        raise ValueError("bad goal atom: %r" % (atom,))
    parts = body[1:-1].split()
    return parts[0], parts[1:]


def official_language_from_stem(stem: str) -> str:
    m = re.search(r"_SCENE\d+_", stem)
    if not m:
        raise ValueError("cannot derive official language from stem: %r" % (stem,))
    return " ".join(stem[m.end():].split("_"))
# ---------------------------------------------------------------------------
# Component parser: official language -> atomic pieces aligned with goal atoms
# ---------------------------------------------------------------------------
CLAUSE_SPLIT_RE = re.compile(
    r"\s+and\s+(?=(?:put|place|open|close|turn on|turn off|pick up|stack)\b)")
PLACE_DEST = (r"(?:on top of|on|in|under)\s+(?:the|a)\s+.+"
              r"|to the (?:left|right|front|back) of\s+the\s+.+")
PUT_RE = re.compile(r"^put (the .+?) (" + PLACE_DEST + r")$")
PUT_IT_RE = re.compile(r"^put it (in|on) (the .+)$")
PUT_THING_IT_RE = re.compile(r"^put (the .+?) (in|on) it$")
PICK_UP_RE = re.compile(r"^pick up (the .+)$")
PLACE_IT_RE = re.compile(r"^place it (" + PLACE_DEST + r")$")
OPEN_RE = re.compile(r"^open (the .+)$")
CLOSE_RE = re.compile(r"^close (the .+)$")
CLOSE_IT_RE = re.compile(r"^close it$")
TURN_RE = re.compile(r"^turn (on|off) (the .+)$")
STACK_RE = re.compile(r"^stack (the .+?) (on .+)$")


def parse_clause(text: str) -> dict:
    """Parse one official-language clause into a raw component dict."""
    m = TURN_RE.match(text)
    if m:
        kind = "turn_on" if m.group(1) == "on" else "turn_off"
        return {"kind": kind, "fixture_phrase": m.group(2)}
    m = CLOSE_IT_RE.match(text)
    if m:
        return {"kind": "close", "needs_it": True}
    m = OPEN_RE.match(text)
    if m:
        return {"kind": "open", "target_phrase": m.group(1)}
    m = CLOSE_RE.match(text)
    if m:
        return {"kind": "close", "target_phrase": m.group(1)}
    m = PICK_UP_RE.match(text)
    if m:
        return {"kind": "pick_up", "obj_noun": m.group(1)}
    m = PLACE_IT_RE.match(text)
    if m:
        return {"kind": "place", "obj_noun": None, "dest_phrase": m.group(1)}
    m = PUT_IT_RE.match(text)
    if m:
        return {"kind": "place", "obj_noun": None, "dest_phrase": m.group(1) + " " + m.group(2)}
    m = PUT_THING_IT_RE.match(text)
    if m:
        return {"kind": "place", "obj_noun": m.group(1), "needs_it": m.group(2)}
    m = PUT_RE.match(text)
    if m:
        return {"kind": "place", "obj_noun": m.group(1), "dest_phrase": m.group(2)}
    m = STACK_RE.match(text)
    if m:
        dest = m.group(2)
        return {"kind": "stack", "obj_noun": m.group(1), "dest_phrase": dest,
                "base_phrase": dest[3:]}
    raise ValueError("unsupported clause: %r" % (text,))


def parse_task_language(lang: str):
    """Split an official language into resolved atomic pieces (in clause order)."""
    clause_texts = [part.strip() for part in CLAUSE_SPLIT_RE.split(lang.strip()) if part.strip()]
    raw = [parse_clause(text) for text in clause_texts]
    pieces = []
    last_container = None
    last_fixture = None
    i = 0
    while i < len(raw):
        clause = raw[i]
        kind = clause["kind"]
        if kind == "pick_up":
            if i + 1 >= len(raw):
                raise ValueError("pick up without following place clause: %r" % (lang,))
            nxt = raw[i + 1]
            if nxt["kind"] != "place" or nxt.get("obj_noun") is not None:
                raise ValueError("pick up not followed by `put/place it ...`: %r" % (lang,))
            dest = nxt["dest_phrase"]
            pieces.append({"kind": "place", "obj_noun": clause["obj_noun"], "dest_phrase": dest})
            if dest.startswith("in "):
                last_container = dest[3:]
            i += 2
            continue
        if kind == "place":
            if clause.get("obj_noun") is None:
                raise ValueError("`place it` without preceding pick up: %r" % (lang,))
            if clause.get("needs_it"):
                prep = clause["needs_it"]
                if prep == "in":
                    if last_container is None:
                        raise ValueError("`in it` with no previous container: %r" % (lang,))
                    dest = "in " + last_container
                else:
                    if last_fixture is None:
                        raise ValueError("`on it` with no previous fixture: %r" % (lang,))
                    dest = "on " + last_fixture
            else:
                dest = clause["dest_phrase"]
            pieces.append({"kind": "place", "obj_noun": clause["obj_noun"], "dest_phrase": dest})
            if dest.startswith("in "):
                last_container = dest[3:]
            i += 1
            continue
        if kind == "open":
            pieces.append({"kind": "open", "target_phrase": clause["target_phrase"]})
            last_container = clause["target_phrase"]
            i += 1
            continue
        if kind == "close":
            if clause.get("needs_it"):
                if last_container is None:
                    raise ValueError("`close it` with no previous container: %r" % (lang,))
                target = last_container
            else:
                target = clause["target_phrase"]
            pieces.append({"kind": "close", "target_phrase": target})
            i += 1
            continue
        if kind in SWITCH_KINDS:
            pieces.append({"kind": kind, "fixture_phrase": clause["fixture_phrase"]})
            last_fixture = clause["fixture_phrase"]
            i += 1
            continue
        if kind == "stack":
            pieces.append({"kind": "stack", "obj_noun": clause["obj_noun"],
                           "dest_phrase": clause["dest_phrase"],
                           "base_phrase": clause["base_phrase"]})
            i += 1
            continue
        raise ValueError("unhandled clause kind %r in %r" % (kind, lang))
    return pieces


def _dest_prep(dest_phrase: str) -> str:
    """Preposition part of a destination phrase, for the `... on it` ellipsis."""
    if dest_phrase.startswith("to the "):
        return ""
    return dest_phrase.split(" ", 1)[0] + " "


def align_task_pieces(index: int, goal_atoms, pieces):
    """Attach atom args / relation info to parsed pieces, aligned 1:1 with goal atoms."""
    if len(pieces) != len(goal_atoms):
        raise ValueError("task %s: %d pieces vs %d goal atoms (%r vs %r)"
                         % (index, len(pieces), len(goal_atoms), pieces, goal_atoms))
    aligned = []
    for atom, piece in zip(goal_atoms, pieces):
        pred, args = split_atom(atom)
        item = dict(piece)
        if pred in ("In", "On"):
            if item["kind"] not in PLACEMENT_KINDS:
                raise ValueError("task %s: atom %r but piece kind %r" % (index, atom, item["kind"]))
            if pred == "In":
                dest = item["dest_phrase"]
                if not (dest.startswith("in ") or dest.startswith("on ")
                        or dest.startswith("under ") or dest.startswith("to the ")):
                    raise ValueError("task %s: In atom but dest %r" % (index, dest))
                # Known L90 anomaly: 22/23/81/82/84 are In-region goals phrased as
                # "on/under the cabinet shelf" in the official language. Keep the official
                # surface/destination phrase, but flag it in the template doc.
                item["container_phrase"] = dest[3:] if dest.startswith("in ") else dest
                item["container_region"] = args[1]
                item["surface_phrasing_for_in"] = not dest.startswith("in ")
            else:
                if item["dest_phrase"].startswith("in "):
                    raise ValueError("task %s: On atom but dest %r" % (index, item["dest_phrase"]))
            item["pred"] = pred
            item["obj_arg"] = args[0]
            item["dest_arg"] = args[1]
            if item["kind"] == "stack":
                item["base_arg"] = args[1]
        elif pred in ("Open", "Close"):
            if item["kind"] not in ARTICULATION_KINDS:
                raise ValueError("task %s: atom %r but piece kind %r" % (index, atom, item["kind"]))
            item["pred"] = pred
            item["container_region"] = args[0]
            item["container_phrase"] = item["target_phrase"]
        elif pred in ("Turnon", "Turnoff"):
            if item["kind"] not in SWITCH_KINDS:
                raise ValueError("task %s: atom %r but piece kind %r" % (index, atom, item["kind"]))
            item["pred"] = pred
            item["fixture_arg"] = args[0]
        else:
            raise ValueError("task %s: unsupported goal predicate %r" % (index, pred))
        item["atom"] = atom
        aligned.append(item)
    return aligned


def build_task_piece_cache(inventory, official):
    """Parse all 90 tasks; return (pieces_by_task, parse_errors_by_task)."""
    pieces = {}
    errors = {}
    for task in inventory["tasks"]:
        index = task["index"]
        try:
            raw = parse_task_language(official[index])
            pieces[index] = align_task_pieces(index, task["goal_atoms"], raw)
        except ValueError as exc:
            errors[index] = str(exc)
    return pieces, errors


def parse_promoted_piece(lang: str, atom: str):
    """Parse a promoted (borrowed/synthesized) one-object instruction into one piece."""
    raw = parse_task_language(lang)
    if len(raw) != 1:
        raise ValueError("promoted instruction must be one placement: %r" % (lang,))
    return align_task_pieces("promoted", [atom], raw)[0]


def side_piece_map(side, task_pieces, promoted_cache):
    """atom -> piece for one side of a candidate (official task or promoted target)."""
    if side.get("index") is None:
        language = side["language"]
        atom = side["goal_atoms"][0]
        key = (language, atom)
        if key not in promoted_cache:
            promoted_cache[key] = [parse_promoted_piece(language, atom)]
        return {atom: promoted_cache[key][0]}
    return {piece["atom"]: piece for piece in task_pieces[side["index"]]}


def build_candidate_pieces(candidate, task_pieces, promoted_cache):
    """Ordered piece list for the candidate's merged goal (s1 atoms first, then s2 new)."""
    sides = [candidate["s1_task"], candidate["s2_task"]]
    maps = [side_piece_map(sides[0], task_pieces, promoted_cache),
            side_piece_map(sides[1], task_pieces, promoted_cache)]
    own = [set(sides[0]["goal_atoms"]), set(sides[1]["goal_atoms"])]
    ordered = []
    for atom in candidate["goal_atoms"]:
        if atom in own[0]:
            source = 0
        elif atom in own[1]:
            source = 1
        else:
            raise ValueError("candidate %s: atom %r belongs to no side"
                             % (candidate["candidate_id"], atom))
        if atom not in maps[source]:
            raise ValueError("candidate %s: no piece for atom %r"
                             % (candidate["candidate_id"], atom))
        piece = dict(maps[source][atom])
        piece["source"] = "s1" if source == 0 else "s2"
        ordered.append(piece)
    if len(ordered) != len(candidate["goal_atoms"]):
        raise ValueError("candidate %s: piece count mismatch" % candidate["candidate_id"])
    return ordered
# ---------------------------------------------------------------------------
# Instruction assembly: merged pieces -> clause units -> template id
# ---------------------------------------------------------------------------
def render_piece(piece) -> str:
    kind = piece["kind"]
    if kind == "place":
        return "put %s %s" % (piece["obj_noun"], piece["dest_phrase"])
    if kind == "stack":
        return "stack %s %s" % (piece["obj_noun"], piece["dest_phrase"])
    if kind == "open":
        return "open %s" % piece["target_phrase"]
    if kind == "close":
        return "close %s" % piece["target_phrase"]
    if kind == "turn_on":
        return "turn on %s" % piece["fixture_phrase"]
    if kind == "turn_off":
        return "turn off %s" % piece["fixture_phrase"]
    raise ValueError("cannot render piece kind %r" % (kind,))


def _find_stack_chain(pieces):
    """(upper_idx, base_idx) for T9, or (None, None)."""
    for upper, piece in enumerate(pieces):
        if piece["kind"] != "stack":
            continue
        for base, other in enumerate(pieces):
            if base == upper or other["kind"] not in PLACEMENT_KINDS:
                continue
            if other.get("obj_arg") is not None and other["obj_arg"] == piece.get("base_arg"):
                return upper, base
    return None, None


def assemble_instruction(pieces):
    """Group merged atomic pieces into clause units; return template + units."""
    consumed = set()
    groups = []

    def add_group(primary, text, kind, members):
        consumed.update(members)
        groups.append({"primary": primary, "text": text, "kind": kind,
                       "members": list(members)})

    # T9 stack chain: base placement first, then `stack {upper} on top of it`.
    upper, base = _find_stack_chain(pieces)
    if upper is not None:
        base_unit = render_piece(pieces[base])
        upper_unit = "stack %s on top of it" % pieces[upper]["obj_noun"]
        add_group(min(upper, base), base_unit + " and " + upper_unit, "T9", [base, upper])

    # T7/T8 place + turn on/off on the same fixture.
    for idx, piece in enumerate(pieces):
        if idx in consumed or piece["kind"] not in SWITCH_KINDS:
            continue
        matches = [j for j, other in enumerate(pieces)
                   if j not in consumed and other["kind"] == "place"
                   and str(other.get("dest_arg", "")).startswith(piece["fixture_arg"] + "_")]
        if not matches:
            continue
        j = matches[0]
        other = pieces[j]
        if j < idx:
            text = render_piece(other) + (" and turn it on" if piece["kind"] == "turn_on"
                                          else " and turn it off")
        else:
            prep = _dest_prep(other["dest_phrase"])
            verb = "turn on" if piece["kind"] == "turn_on" else "turn off"
            text = "%s %s and put %s %s" % (verb, piece["fixture_phrase"], other["obj_noun"],
                                            prep + "it")
        add_group(min(idx, j), text, "T7" if piece["kind"] == "turn_on" else "T8", [idx, j])

    # T4/T4b place into a container + close the same container ("and close it").
    for idx, piece in enumerate(pieces):
        if idx in consumed or piece["kind"] != "close":
            continue
        ins = [j for j, other in enumerate(pieces)
               if j not in consumed and other["kind"] == "place" and other.get("pred") == "In"
               and other.get("dest_arg") == piece.get("container_region")]
        if not ins:
            continue
        ins = sorted(ins)
        if len(ins) >= 2:
            objs = [pieces[j]["obj_noun"] for j in ins]
            text = "put both %s and %s in %s and close it" % (
                objs[0], objs[1], pieces[ins[0]]["container_phrase"])
            kind = "T4b"
        else:
            j = ins[0]
            text = "put %s %s and close it" % (pieces[j]["obj_noun"], pieces[j]["dest_phrase"])
            kind = "T4"
        add_group(min(ins + [idx]), text, kind, ins + [idx])

    # T5 open a container + put into it ("put ... in it").
    for idx, piece in enumerate(pieces):
        if idx in consumed or piece["kind"] != "open":
            continue
        ins = [j for j, other in enumerate(pieces)
               if j not in consumed and other["kind"] == "place" and other.get("pred") == "In"
               and other.get("dest_arg") == piece.get("container_region")]
        if not ins:
            continue
        ins = sorted(ins)
        if len(ins) >= 2:
            objs = [pieces[j]["obj_noun"] for j in ins]
            text = "open %s and put both %s and %s in it" % (
                piece["target_phrase"], objs[0], objs[1])
        else:
            text = "open %s and put %s in it" % (piece["target_phrase"],
                                                 pieces[ins[0]]["obj_noun"])
        add_group(min(ins + [idx]), text, "T5", ins + [idx])

    # Remaining placements: T1 (same container), T2 (same destination), T3 (different).
    remaining = [i for i, p in enumerate(pieces)
                 if i not in consumed and p["kind"] in PLACEMENT_KINDS]
    if remaining:
        dest_keys = {(pieces[i]["pred"], pieces[i].get("dest_arg")) for i in remaining}
        if len(remaining) == 2 and len(dest_keys) == 1:
            pred = pieces[remaining[0]]["pred"]
            text = "put both %s and %s %s" % (
                pieces[remaining[0]]["obj_noun"], pieces[remaining[1]]["obj_noun"],
                pieces[remaining[0]]["dest_phrase"])
            add_group(min(remaining), text, "T1" if pred == "In" else "T2", remaining)
        else:
            text = " and ".join(render_piece(pieces[i]) for i in remaining)
            add_group(min(remaining), text, "T3", remaining)

    # Any leftover articulation / switch clauses are kept as a two-clause chain.
    for idx, piece in enumerate(pieces):
        if idx in consumed:
            continue
        add_group(idx, render_piece(piece), "articulation", [idx])

    groups.sort(key=lambda group: group["primary"])
    units = [group["text"] for group in groups]
    kinds = [group["kind"] for group in groups]
    if "T9" in kinds:
        template = "T9"
    elif "T7" in kinds:
        template = "T7"
    elif "T8" in kinds:
        template = "T8"
    elif "T4b" in kinds:
        template = "T4b"
    elif "T4" in kinds:
        template = "T4"
    elif "T5" in kinds:
        template = "T5"
    elif "T1" in kinds:
        template = "T1"
    elif "T2" in kinds:
        template = "T2"
    elif kinds == ["T3"]:
        template = "T3"
    else:
        has_open = any(piece["kind"] == "open" for piece in pieces)
        has_close = any(piece["kind"] == "close" for piece in pieces)
        has_switch = any(piece["kind"] in SWITCH_KINDS for piece in pieces)
        has_placement = any(piece["kind"] in PLACEMENT_KINDS for piece in pieces)
        template = "T6" if (has_open and not has_close and not has_switch and has_placement) else "T10"
    return {
        "template": template,
        "units": units,
        "instruction": " and ".join(units),
        "groups": [{"kind": g["kind"], "text": g["text"], "primary": g["primary"]} for g in groups],
    }


def build_variants(units, instruction, template):
    """`and` / `then` / `both` / `it` variants of the templated instruction.

    Compound single-clause templates (T4/T4b/T5/T7/T8/T9) are split at their suffix
    boundary for the `then` variant, e.g. `put ... in ... and close it` ->
    `put ... in ..., then close it`; `open ... and put ... in it` ->
    `open ..., then put ... in it`.
    """
    variants = {"and": instruction}
    then_text = None
    if template in ("T4", "T4b"):
        then_text = instruction.replace(" and close it", ", then close it")
    elif template == "T5":
        then_text = instruction.replace(" and put ", ", then put ", 1)
    elif template in ("T7", "T8"):
        match = re.search(r" and turn it (on|off)$", instruction)
        if match:
            then_text = instruction[:match.start()] + ", then turn it " + match.group(1)
        else:
            then_text = instruction.replace(" and put ", ", then put ", 1)
    elif template == "T9":
        then_text = instruction.replace(" and stack ", ", then stack ", 1)
    elif template == "T3" and len(units) == 1:
        then_text = (instruction.replace(" and put ", ", then put ")
                     .replace(" and stack ", ", then stack "))
    elif len(units) > 1:
        then_text = ", then ".join(units)
    variants["then"] = then_text if (then_text and then_text != instruction) else instruction
    if "put both" in instruction:
        variants["both"] = instruction
    if re.search(r"\bit\b", instruction):
        variants["it"] = instruction
    return variants


def instruction_source_for(candidate, template):
    route = candidate["route"]
    if route == "M2":
        source = candidate.get("instruction_source") or "synthesized"
        return source if source.startswith("borrowed:") else "synthesized"
    if route == "S1":
        return "synthesized"
    return TEMPLATE_INFO[template]["source"]


def build_evidence(candidate, template, pieces):
    info = TEMPLATE_INFO[template]
    evidence = {
        "template_id": template,
        "template_name": info["name"],
        "pattern": info["pattern"],
        "references": list(info["refs"]),
        "evidence": list(info["evidence"]),
    }
    if candidate["class"] == "hard":
        evidence = dict(evidence)
        evidence["preferred_variant"] = "then"
        evidence["variant_evidence"] = [EVIDENCE_GOAL_THEN, EVIDENCE_GOAL_INTEGRATED_NEG]
    objects = [p["obj_noun"] for p in pieces if p["kind"] in PLACEMENT_KINDS]
    evidence["objects_used"] = objects
    if candidate["route"] in ("M2", "S1") and candidate.get("promoted_target"):
        evidence["promoted_target"] = candidate["promoted_target"]
        evidence["promoted_wording_source"] = candidate.get("instruction_source")
    return evidence
# ---------------------------------------------------------------------------
# Build instructed payload
# ---------------------------------------------------------------------------
INSTRUCTION_FIELDS = ("instruction", "instruction_template", "instruction_variants",
                      "instruction_evidence", "instruction_source", "instruction_clauses",
                      "instruction_preferred_variant")


def load_inputs():
    if not CANDIDATES_JSON.exists():
        raise SystemExit("missing candidates.json: %s" % CANDIDATES_JSON)
    if not INVENTORY_JSON.exists():
        raise SystemExit("missing inventory.json: %s" % INVENTORY_JSON)
    if not OFFICIAL_MAP_JSON.exists():
        raise SystemExit("missing official-language map: %s" % OFFICIAL_MAP_JSON)
    candidates_payload = read_json(CANDIDATES_JSON)
    inventory = read_json(INVENTORY_JSON)
    official_map = read_json(OFFICIAL_MAP_JSON)
    official = {row["index"]: row["official_language"] for row in official_map["benchmark_order"]}
    candidates = candidates_payload.get("candidates") or []
    n_candidates = len(candidates)
    if n_candidates < 1:
        raise SystemExit("candidates.json contains no candidates")
    summary = candidates_payload.get("summary") or {}
    if summary.get("total") is not None and summary["total"] != n_candidates:
        raise SystemExit("candidates.json summary.total=%r but %d candidates found"
                         % (summary["total"], n_candidates))
    return candidates_payload, inventory, official_map, official


def check_l10_evidence():
    """Cross-check embedded LIBERO-10 template languages against tasks_info-derived ones."""
    derived = []
    source = "embedded"
    if L10_TASKS_INFO.exists():
        stems = [Path(line.strip()).name[:-5]
                 for line in L10_TASKS_INFO.read_text(encoding="utf-8").splitlines()
                 if line.strip()]
        derived = [(stem, official_language_from_stem(stem)) for stem in stems]
        source = str(L10_TASKS_INFO)
    embedded = [(stem, lang) for stem, lang in L10_TASKS]
    if derived and derived != embedded:
        raise SystemExit("embedded LIBERO-10 template languages differ from tasks_info.txt:\n%r\n%r"
                         % (derived, embedded))
    return {"source": source, "n": len(embedded), "crosschecked": bool(derived)}


def instruction_stats(candidates, pieces_by_candidate, l10_check):
    template_counts = Counter()
    route_template = defaultdict(Counter)
    scene_template = defaultdict(Counter)
    route_counts = Counter()
    variant_counts = Counter()
    source_counts = Counter()
    preferred_counts = Counter()
    class_template = defaultdict(Counter)
    for candidate in candidates:
        template = candidate["instruction_template"]
        template_counts[template] += 1
        route_template[candidate["route"]][template] += 1
        scene_template[candidate["scene"]][template] += 1
        route_counts[candidate["route"]] += 1
        class_template[candidate["class"]][template] += 1
        source_counts[candidate["instruction_source"]] += 1
        preferred_counts[candidate["instruction_preferred_variant"]] += 1
        for key in candidate["instruction_variants"]:
            variant_counts[key] += 1
    return {
        "n_candidates": len(candidates),
        "template_counts": {tid: template_counts.get(tid, 0) for tid in TEMPLATE_IDS},
        "route_counts": dict(route_counts),
        "route_template": {route: {tid: route_template[route].get(tid, 0) for tid in TEMPLATE_IDS}
                           for route in sorted(route_template)},
        "class_template": {cls: {tid: class_template[cls].get(tid, 0) for tid in TEMPLATE_IDS}
                           for cls in sorted(class_template)},
        "scene_template": {scene: {tid: scene_template[scene].get(tid, 0) for tid in TEMPLATE_IDS}
                           for scene in sorted(scene_template)},
        "variant_counts": {key: variant_counts.get(key, 0) for key in ("and", "then", "both", "it")},
        "instruction_source_counts": dict(source_counts),
        "preferred_variant_counts": dict(preferred_counts),
        "template_ids": list(TEMPLATE_IDS),
        "l10_evidence": l10_check,
        "n_unique_instructions": len({c["instruction"] for c in candidates}),
    }


def build_instructed(candidates_payload, inventory, official):
    task_pieces, parse_errors = build_task_piece_cache(inventory, official)
    dual7 = set(inventory["rules"]["two_atoms_distinct_target_entity"])
    unexpected_errors = sorted(set(parse_errors) - dual7)
    if unexpected_errors:
        raise SystemExit("cannot parse official language of single-goal-pool tasks: %r"
                         % [(i, parse_errors[i]) for i in unexpected_errors])
    candidates = candidates_payload["candidates"]
    promoted_cache = {}
    pieces_ctx = {}
    instructed = []
    for candidate in candidates:
        pieces = build_candidate_pieces(candidate, task_pieces, promoted_cache)
        assembled = assemble_instruction(pieces)
        instruction = assembled["instruction"]
        template = assembled["template"]
        evidence = build_evidence(candidate, template, pieces)
        if candidate["class"] == "hard":
            evidence["then_variant_evidence"] = [EVIDENCE_GOAL_THEN]
        if candidate["route"] == "M2":
            evidence["promoted_wording_evidence"] = (
                "second-object noun taken from the promoted instruction (%s)"
                % (candidate.get("instruction_source") or "synthesized"))
        if candidate["route"] == "S1":
            evidence["evidence"].append(
                "S1 rescue: `(Turnon flat_stove_1)` dropped (already true in :init); "
                "placement + turn-off synthesized from L90 18 + promoted left moka pot")
            evidence["dropped_goal_atoms"] = candidate.get("dropped_goal_atoms") or []
        record = dict(candidate)
        record["instruction"] = instruction
        record["instruction_template"] = template
        record["instruction_variants"] = build_variants(assembled["units"], instruction, template)
        record["instruction_evidence"] = evidence
        record["instruction_source"] = instruction_source_for(candidate, template)
        record["instruction_clauses"] = assembled["units"]
        record["instruction_preferred_variant"] = (
            "then" if candidate["class"] == "hard" else "and")
        instructed.append(record)
        pieces_ctx[candidate["candidate_id"]] = pieces
    l10_check = check_l10_evidence()
    stats = instruction_stats(instructed, pieces_ctx, l10_check)
    source_summary = candidates_payload.get("summary") or {}
    source_scene_review = candidates_payload.get("scene_review") or {}
    stats["scene_review_version"] = source_summary.get("review_decisions_version")
    stats["pool_bddl"] = source_summary.get("pool_bddl")
    stats["single_pool"] = source_summary.get("single_pool")
    stats["review_excluded_tasks"] = source_summary.get("review_excluded_tasks") or []
    stats["template_zero_hits"] = [tid for tid in TEMPLATE_IDS
                                   if stats["template_counts"][tid] == 0]
    payload = {
        "summary": source_summary,
        "scene_review": source_scene_review,
        "candidates": instructed,
        "extensions": candidates_payload["extensions"],
        "stats": dict(candidates_payload["stats"], instructions=stats),
        "meta": dict(candidates_payload["meta"],
                     instructions_generated_by="scripts/build_libero90_instructions.py",
                     instruction_template_ids=list(TEMPLATE_IDS),
                     instruction_fields=list(INSTRUCTION_FIELDS),
                     source_sha256={},
                     n_candidates=len(instructed),
                     scene_review_version=source_summary.get("review_decisions_version"),
                     template_zero_hits=stats["template_zero_hits"]),
    }
    ctx = {
        "instructed": instructed,
        "pieces": pieces_ctx,
        "task_pieces": task_pieces,
        "parse_errors": parse_errors,
        "source_candidates": candidates_payload,
        "l10_check": l10_check,
        "stats": stats,
        "source_sha256": {},
    }
    return payload, ctx
# ---------------------------------------------------------------------------
# INSTRUCTION_TEMPLATES.md renderer
# ---------------------------------------------------------------------------
def md_cell(value) -> str:
    return str(value).replace("|", "/").replace("\n", " ")


def changed_examples(candidates, limit_per_template=2):
    """Examples where the templated instruction differs from the old naive concat."""
    by_template = defaultdict(list)
    for candidate in sorted(candidates, key=lambda c: c["candidate_id"]):
        if candidate["instruction"] != candidate["language"]:
            by_template[candidate["instruction_template"]].append(candidate)
    return by_template


def render_templates_md(payload, ctx) -> str:
    stats = payload["stats"]["instructions"]
    candidates = payload["candidates"]
    pieces = ctx["pieces"]
    lines = []
    lines.append("# LIBERO-90 组合候选：模板化合并指令说明（INSTRUCTION_TEMPLATES）")
    lines.append("")
    lines.append("> 自动生成：`scripts/build_libero90_instructions.py`（**请勿手改**；`--check` 会校验全部断言）。")
    lines.append("> 目的：**全部 %d 条候选的合并指令不再由两条官方句子直接用 `and` 拼接**，而是按 "
                 "LIBERO-10 / LIBERO-GOAL / LIBERO-OBJECT 中**验证过的成功任务模板**重建。"
                 % len(candidates))
    lines.append("> **scene_review v%s 之后**：候选 %d 条（KITCHEN_SCENE1 任务 00 已按用户逐场景复核移出组合池，"
                 "330 -> %d）；模板 `T5`（open+place）当前命中 0 条，模板定义保留并标注。"
                 % ((payload["summary"].get("review_decisions_version")),
                    len(candidates), len(candidates)))
    lines.append("")
    lines.append("## 1. 输入、产物与审计")
    lines.append("")
    lines.append("| 类型 | 路径 |")
    lines.append("| --- | --- |")
    lines.append("| 输入（只读） | `runs/libero-90-combos-20261025/candidates.json`（%d 条，**原文件不变**；"
                 "scene_review v%s：剔除任务 %s，组合池 %d 条） |"
                 % (len(candidates), payload["summary"].get("review_decisions_version"),
                    payload["summary"].get("review_excluded_tasks"),
                    payload["summary"].get("single_pool")))
    lines.append("| 输入（只读） | `.tmp/libero90-combos/inventory.json`、`official-language-and-benchmark-map.json` |")
    lines.append("| 证据（只读） | `runs/instruction-variants-20261024/FINAL_VARIANT_RESULTS.md`、"
                 "`runs/libero-object-summary-20261025/SUMMARY.md`、LIBERO-10 `tasks_info.txt` |")
    lines.append("| 产物 | `candidates-instructed.json`（%d 条，原字段 + 指令字段） |" % len(candidates))
    lines.append("| 产物 | 本文件 `INSTRUCTION_TEMPLATES.md` |")
    lines.append("")
    for path, digest in sorted((payload["meta"].get("source_sha256") or {}).items()):
        lines.append("- 源文件 sha256（审计用，未修改）：`%s` = `%s`" % (path, digest))
    lines.append("")
    lines.append("新增字段（其余原字段逐字节保留）：")
    lines.append("")
    lines.append("| 字段 | 含义 |")
    lines.append("| --- | --- |")
    lines.append("| `instruction` | 模板化主指令（小写、单行、无句号） |")
    lines.append("| `instruction_template` | 模板 id（T1–T10 之一） |")
    lines.append("| `instruction_variants` | 变体：`and`/`then`/`both`/`it`（按适用性生成） |")
    lines.append("| `instruction_evidence` | 模板 id、参考任务、证据数字、objects_used；hard 附 then 证据 |")
    lines.append("| `instruction_source` | `template:L10-xx` / `template:L90-xx` / `borrowed:nn` / `synthesized` |")
    lines.append("| `instruction_clauses` | 指令的子句列表（`then` 变体与 staged 切分用） |")
    lines.append("| `instruction_preferred_variant` | `then`（hard/P2，依赖类推荐）或 `and` |")
    lines.append("")
    lines.append("## 2. 参考证据总表")
    lines.append("")
    lines.append("| 证据 | 数字 / 结论 |")
    lines.append("| --- | --- |")
    evidence_rows = [
        ("LIBERO-OBJECT v3 模板 `put both the A and the B in the basket`",
         "100 候选 x 3 seeds = 300 episodes，**12/300 = 4.0%**（6 候选 >=1 次、5 候选 >=2 seeds、1 候选 3/3）"),
        ("LIBERO-10 官方 10 条双目标任务",
         "04/05/06 = put both … in the basket；03 = put both moka pots on the stove；07/08 = 两条 put 子句；"
         "01/02 = put … and close it；00 = turn on … and put … on it；09 = pick up … and place it …"),
        ("LIBERO-GOAL `it` 指代变体", "07_01：4/9 -> **7/9（+3）**，是最强正信号"),
        ("LIBERO-GOAL `then` 变体", "06_08：5/9 -> **7/9（+2）**；06_07：2/9 -> **6/9（+4）**（容器依赖类正收益）"),
        ("LIBERO-GOAL `integrated` 变体", "06_01：8/9 -> 0/9（-8），**灾难负收益，已排除**"),
        ("GOAL `both` 对同表面双物体", "0/6 无提升；本清单只在**同容器/同落点**使用 `both`（L10 官方模板），"
         "同表面 `both` 的收益仍需动态验证"),
    ]
    for name, value in evidence_rows:
        lines.append("| %s | %s |" % (md_cell(name), md_cell(value)))
    lines.append("")
    lines.append("## 3. 模板总表（命中统计）")
    lines.append("")
    lines.append("| 模板 | 名称 | 模板句式 | 参考任务 | 命中（全部 / M1 / M2 / S1） | `instruction_source` |")
    lines.append("| --- | --- | --- | --- | ---: | --- |")
    for tid in TEMPLATE_IDS:
        info = TEMPLATE_INFO[tid]
        total = stats["template_counts"][tid]
        m1 = stats["route_template"].get("M1", {}).get(tid, 0)
        m2 = stats["route_template"].get("M2", {}).get(tid, 0)
        s1 = stats["route_template"].get("S1", {}).get(tid, 0)
        lines.append("| `%s` | %s | `%s` | %s | %d / %d / %d / %d | `%s` |" % (
            tid, md_cell(info["name"]), md_cell(info["pattern"]),
            ", ".join(info["refs"]), total, m1, m2, s1, info["source"]))
    lines.append("| **合计** | — | — | — | **%d / %d / %d / %d** | — |" % (
        sum(stats["template_counts"].values()),
        sum(stats["route_template"].get("M1", {}).values()),
        sum(stats["route_template"].get("M2", {}).values()),
        sum(stats["route_template"].get("S1", {}).values())))
    lines.append("")
    zero_hits = stats.get("template_zero_hits") or []
    if zero_hits:
        lines.append("> **当前候选集 0 命中的模板**：%s。"
                     % ", ".join("`%s`" % tid for tid in zero_hits))
        if "T5" in zero_hits:
            lines.append("> `T5`（open + place 同一容器）原有的 **8 条全部来自 KITCHEN_SCENE1 含任务 00 的组合**；"
                         "任务 00 已按用户逐场景复核 v1 移出组合池（330 -> %d），因此当前 0 命中。"
                         "**模板定义保留**：其他场景未来出现 open+place 组合时仍可复用（见 §4 的 T5 段落）。"
                         % len(candidates))
        lines.append("")
    lines.append("### 3.1 五个关键变换示例（旧拼接 -> 模板化）")
    lines.append("")
    lines.append("| candidate_id | 旧指令（两条官方拼接） | 新指令（模板化） |")
    lines.append("| --- | --- | --- |")
    highlight_ids = [
        "L90_LR1_31_32_ab", "L90_KS3_06_08_ab", "L90_KS4_12_14_ab",
        "L90_KS9_20_21_ab", "L90_KS2_53_58_ab", "L90_KS8_18_moka_pot_2_ab",
    ]
    by_id = {candidate["candidate_id"]: candidate for candidate in candidates}
    for candidate_id in highlight_ids:
        candidate = by_id[candidate_id]
        lines.append("| `%s` | %s | **%s** |" % (
            candidate_id, md_cell(candidate["language"]), md_cell(candidate["instruction"])))
    lines.append("")
    lines.append("## 4. 逐模板说明与变换示例")
    lines.append("")
    lines.append("> 若某行“旧指令 = 新指令”，说明两条官方语言本身已经是规范的 `put/close/open` 句式（T3/T6/T10 的 "
                 "normalized 两子句），模板化只统一动词与结构、不强行改写措辞；这类相等见 §9 的统计。")
    lines.append("")
    changed = changed_examples(candidates)
    for tid in TEMPLATE_IDS:
        info = TEMPLATE_INFO[tid]
        lines.append("### `%s` %s（%d 条）" % (tid, info["name"], stats["template_counts"][tid]))
        lines.append("")
        if stats["template_counts"][tid] == 0:
            lines.append("> 当前候选集 **0 条**（原 8 条均来自 KITCHEN_SCENE1 含任务 00 的组合；"
                         "00 已按用户逐场景复核 v1 移出组合池）。模板定义保留，本次无候选命中。")
            lines.append("")
        lines.append("- 模板：`%s`" % info["pattern"])
        lines.append("- 参考：%s" % ", ".join(info["refs"]))
        lines.append("- 证据：%s" % "；".join(info["evidence"]))
        lines.append("")
        examples = [c for c in sorted(candidates, key=lambda x: x["candidate_id"])
                    if c["instruction_template"] == tid][:3]
        if examples:
            lines.append("| candidate_id | 旧指令（两条官方拼接） | 新指令（模板化） |")
            lines.append("| --- | --- | --- |")
            for candidate in examples:
                lines.append("| `%s` | %s | **%s** |" % (
                    candidate["candidate_id"], md_cell(candidate["language"]),
                    md_cell(candidate["instruction"])))
            lines.append("")
        if changed.get(tid):
            diff_examples = changed[tid][:2]
            if diff_examples and examples and diff_examples[0]["candidate_id"] not in {
                    e["candidate_id"] for e in examples}:
                lines.append("更多变换示例：")
                lines.append("")
                for candidate in diff_examples:
                    lines.append("- `%s`：`%s` -> **`%s`**" % (
                        candidate["candidate_id"], candidate["language"], candidate["instruction"]))
                lines.append("")
    lines.append("## 5. 指令变体（`instruction_variants`）")
    lines.append("")
    lines.append("| 变体 | 生成规则 | 覆盖候选数 |")
    lines.append("| --- | --- | ---: |")
    variant_rules = {
        "and": "主指令，dependencies 无关时默认连接词",
        "then": "`..., then ...` 连接各子句（GOAL 06_08 +2 / 06_07 +4；hard 类优先）",
        "both": "仅 T1/T2/T4b（同容器/同落点双物体）与主指令相同，即 `put both A and B`",
        "it": "仅 T4/T4b/T5/T7/T8（`... and close it` / `... in it` / `turn it on/off`）",
    }
    for key in ("and", "then", "both", "it"):
        lines.append("| `%s` | %s | %d |" % (key, variant_rules[key], stats["variant_counts"][key]))
    lines.append("")
    lines.append("> T12（hard 的 then 变体偏好）不是独立模板 id：hard 类仍按结构归入 T4/T4b/T9/T3 等，"
                 "但 `instruction_preferred_variant = then`，并在 `instruction_evidence.then_variant_evidence` 里引用 "
                 "GOAL 06_08 +2 / 06_07 +4 的证据。")
    lines.append("")
    lines.append("每条候选的 `instruction_preferred_variant`：`then` %d 条（hard/P2，依赖类推荐），"
                 "`and` %d 条（其余）。"
                 % (stats["preferred_variant_counts"].get("then", 0),
                    stats["preferred_variant_counts"].get("and", 0)))
    lines.append("")
    lines.append("## 6. M2 / S1 特殊候选")
    lines.append("")
    lines.append("| candidate_id | 模板 | 提升目标 | instruction | 指令来源 |")
    lines.append("| --- | --- | --- | --- | --- |")
    for candidate in [c for c in candidates if c["route"] in ("M2", "S1")]:
        promoted = candidate.get("promoted_target") or {}
        lines.append("| `%s` | `%s` | `%s` %s | %s | `%s` |" % (
            candidate["candidate_id"], candidate["instruction_template"],
            promoted.get("object", ""), md_cell(promoted.get("goal_atom", "")),
            md_cell(candidate["instruction"]), candidate["instruction_source"]))
    lines.append("")
    lines.append("> ⚠ M2 的提升目标名词来自**借用指令**（`borrowed:<task>`），S1 的提升目标名词为**合成**"
                 "（`synthesized`）；这些措辞不是本场景官方原文，进入动态验证前必须人工确认。")
    lines.append("")
    lines.append("## 7. 语言组件解析规则")
    lines.append("")
    lines.append("每条官方 language 先被拆成原子组件，再与 goal 原子一一对齐（错位即 fail-fast）：")
    lines.append("")
    lines.append("| 组件 | 解析规则 |")
    lines.append("| --- | --- |")
    parser_rows = [
        ("clause 切分", "只在 ` and ` 后接动词（put/place/open/close/turn on/turn off/pick up/stack）处切分，"
                        "因此 `the yellow and white mug` 内部的 `and` 不会被误切"),
        ("`obj_noun`", "保留官方限定词：`the black bowl at the back/front`、`the middle black bowl`、"
                       "`the left/right bowl`、`the book on the left/in the middle`、`the yellow and white mug` 等；"
                       "KITCHEN_SCENE2 的三只黑碗靠这些限定词区分，不退化成 `the bowl`"),
        ("`dest_phrase`", "介词短语整体保留：`in the bottom drawer of the cabinet`、`on top of the cabinet`、"
                          "`to the right of the plate`、`under the cabinet shelf`、`on the left/right plate`"),
        ("`container_phrase`", "In 目标去掉 `in `：`the basket` / `the top drawer of the cabinet` / "
                               "`the left compartment of the caddy`"),
        ("`relation`", "由 goal 原子谓词决定：In/On（放置）、Open/Close（关节）、Turnon/Turnoff（开关）；"
                       "`stack` 用于 On-到-物体"),
        ("`has_close_suffix`", "任务 26/27/28 的 `... and close it` 解析为同一容器的关闭后缀；渲染时合并成 "
                               "`put ... in ... and close it`，不会出现两条 `close`"),
        ("`it` 指代", "`put X in it` 回指最近的 Open/In 容器；`put X on it` 回指最近的 Turn on 炉体；"
                      "`close it` 回指最近的 In 容器"),
        ("place / open / switch", "关节与开关子句保留 `open/close/turn on/turn off {phrase}`，"
                          "放置类统一规范为 `put {obj} {dest}`（或 stack）"),
    ]
    for name, rule in parser_rows:
        lines.append("| %s | %s |" % (md_cell(name), md_cell(rule)))
    lines.append("")
    lines.append("## 8. 命中统计细表")
    lines.append("")
    lines.append("### 8.1 按 route")
    lines.append("")
    lines.append("| route | " + " | ".join("`%s`" % tid for tid in TEMPLATE_IDS) + " | 合计 |")
    lines.append("| --- | " + " | ".join("---:" for _ in TEMPLATE_IDS) + " | ---: |")
    for route in ("M1", "M2", "S1"):
        row = stats["route_template"].get(route, {})
        lines.append("| %s | %s | %d |" % (
            route, " | ".join(str(row.get(tid, 0)) for tid in TEMPLATE_IDS),
            sum(row.get(tid, 0) for tid in TEMPLATE_IDS)))
    lines.append("")
    lines.append("### 8.2 按 class")
    lines.append("")
    lines.append("| class | " + " | ".join("`%s`" % tid for tid in TEMPLATE_IDS) + " | 合计 |")
    lines.append("| --- | " + " | ".join("---:" for _ in TEMPLATE_IDS) + " | ---: |")
    for cls in ("compatible", "hard", "conflict", "degenerate"):
        row = stats["class_template"].get(cls, {})
        lines.append("| %s | %s | %d |" % (
            cls, " | ".join(str(row.get(tid, 0)) for tid in TEMPLATE_IDS),
            sum(row.get(tid, 0) for tid in TEMPLATE_IDS)))
    lines.append("")
    lines.append("### 8.3 按场景")
    lines.append("")
    lines.append("| 场景 | " + " | ".join("`%s`" % tid for tid in TEMPLATE_IDS) + " | 合计 |")
    lines.append("| --- | " + " | ".join("---:" for _ in TEMPLATE_IDS) + " | ---: |")
    for scene in sorted(stats["scene_template"]):
        row = stats["scene_template"][scene]
        lines.append("| `%s` | %s | %d |" % (
            scene, " | ".join(str(row.get(tid, 0)) for tid in TEMPLATE_IDS),
            sum(row.get(tid, 0) for tid in TEMPLATE_IDS)))
    lines.append("")
    comparisons = Counter()
    for candidate in candidates:
        comparisons["changed"] += int(candidate["instruction"] != candidate["language"])
        comparisons["same"] += int(candidate["instruction"] == candidate["language"])
    lines.append("## 9. 与旧指令（官方语言直接拼接）的差异")
    lines.append("")
    lines.append("- %d 条中 **%d 条指令被模板化改写**，%d 条与旧拼接相同（同为目标已是 "
                 "`put/close/open` 规范句式的 T3/T6/T10 或独立放置类）。"
                 % (len(candidates), comparisons["changed"], comparisons["same"]))
    lines.append("- 参考套件 v1 旧措辞（`pick up A ... and pick up B ...`）在 OBJECT 上 0 成功的历史批次"
                 "因 init 语义错误作废；v3 的 L10 模板在正确 init 下 12/300 = 4.0%。"
                 "本清单据此把所有 `pick up ... and put it ...` 系列改写为 `put`/`put both` 模板句。")
    lines.append("")
    lines.append("## 10. 每条候选的模板命中（附录）")
    lines.append("")
    lines.append("| candidate_id | route | scene | class | template | instruction |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for candidate in sorted(candidates, key=lambda c: c["candidate_id"]):
        lines.append("| `%s` | %s | `%s` | %s | `%s` | %s |" % (
            candidate["candidate_id"], candidate["route"], candidate["scene"],
            candidate["class"], candidate["instruction_template"],
            md_cell(candidate["instruction"])))
    lines.append("")
    lines.append("## 11. `--check` 断言与复现")
    lines.append("")
    lines.append("`--check` 断言包括：%d 条齐全且原字段不变、模板 id 合法、模板/变体/来源统计与 summary 一致、"
                 "同容器双目标含 `put both`、place+close 含 `and close it`、place+Turnon/Turnoff 用 `it`、"
                 "stack_anchor 用 stack 模板、非独立/非关节类指令不与旧拼接同义、M2/S1 提升名词标注、"
                 "变体一致性、证据完整性、源文件 sha256 未变、磁盘 round-trip 等（详见脚本）。"
                 % len(candidates))
    lines.append("")
    lines.append("```bash")
    lines.append(".venv/bin/python scripts/build_libero90_instructions.py --check")
    lines.append("```")
    lines.append("")
    lines.append("## 12. 遗留歧义（需人工/动态验证）")
    lines.append("")
    lines.append("1. **三只黑碗的指代**（KITCHEN_SCENE2 53/54/55/58/59）：名词用官方限定词 "
                 "`at the back` / `at the front` / `the middle black bowl` / `on the black bowl in the middle` "
                 "区分，但三者视觉上高度相似，组合句 `put both the black bowl at the back and the black bowl "
                 "at the front on the plate` 是否可被策略正确 grounding 未知。")
    lines.append("2. **名词内部含 `and`**：`the yellow and white mug` 放进 `put both A and B` 后变成 "
                 "`put both the yellow and white mug and the red mug ...`，存在句法歧义（46_48 / 71 系列）。")
    lines.append("3. **conflict 类（P3, valid=false）**：同一物体两个互斥落点的指令必然重复同一名词"
                 "（如 `put the red mug on the left plate and put the red mug on the right plate`），"
                 "只作负例对照，不用于执行。")
    lines.append("4. **degenerate 类（P3）**：合并目标等价于单任务，模板化指令与官方原句相同"
                 "（如 03+00 -> `open the top drawer of the cabinet and put the bowl in it`），无新增信息。")
    lines.append("5. **`both` 对同表面的收益证据弱**（0/6）：T2 按 L10/03 官方模板保留，但优先级/动态可解性"
                 "需在验证漏斗中确认。")
    lines.append("6. **T10 混合类可能 3 子句**（如 open+place+额外 open），指令长度超过参考套件任一官方任务，"
                 "策略对长指令的鲁棒性未知。")
    lines.append("7. **M2/S1 措辞非官方**：提升目标名词借自其他任务/合成，需逐条人工确认（见 §6 警示）。")
    lines.append("8. **依赖修正导致同 pair 两个方向指令相同**：T4（place-then-close）、T9（base-first）、T5（open-first）"
                 "按依赖修正执行顺序，故 `ab`/`ba` 可能得到同一句指令（`unique_instructions = %d / %d`）；"
                 "方向差异保留在候选的 `s1_task`/`s2_task`、`order_caveat` 与 rollback 语义中，执行指令必须按依赖顺序。"
                 % (stats["n_unique_instructions"], len(candidates)))
    lines.append("9. **L90 已知 instruction-vs-goal 不一致**：任务 22/23/81/82/84 的 goal 是 `In` 区域，但官方语言写作 "
                 "`on/under the cabinet shelf`；本解析保留官方 dest 短语（T1/T3 会输出 `on/under ... shelf` 的措辞），"
                 "与 goal 的 In 语义存在已知偏差，需人工确认。")
    lines.append("")
    return "\n".join(lines)
# ---------------------------------------------------------------------------
# --check validation
# ---------------------------------------------------------------------------
CLAUSE_VERBS = ("put ", "stack ", "open ", "close ", "turn on ", "turn off ")


def count_clauses(instruction: str) -> int:
    return sum(instruction.count(verb) for verb in CLAUSE_VERBS)


def structural_flags(pieces):
    flags = {}
    ins = [p for p in pieces if p["kind"] == "place" and p.get("pred") == "In"]
    closes = [p for p in pieces if p["kind"] == "close"]
    opens = [p for p in pieces if p["kind"] == "open"]
    turns = [p for p in pieces if p["kind"] in SWITCH_KINDS]
    places = [p for p in pieces if p["kind"] in PLACEMENT_KINDS]
    flags["n_pieces"] = len(pieces)
    flags["ins"] = ins
    flags["places"] = places
    flags["has_close"] = bool(closes)
    flags["has_open"] = bool(opens)
    flags["has_switch"] = bool(turns)
    flags["same_container_two_in"] = (
        len(ins) >= 2 and len({p.get("dest_arg") for p in ins}) == 1)
    flags["close_matches_in"] = any(
        close.get("container_region") == piece.get("dest_arg") for close in closes for piece in ins)
    flags["open_matches_in"] = any(
        opened.get("container_region") == piece.get("dest_arg") for opened in opens for piece in ins)
    flags["switch_matches_place"] = any(
        str(piece.get("dest_arg", "")).startswith(turn["fixture_arg"] + "_")
        for turn in turns for piece in places if piece["kind"] == "place")
    flags["only_place_switch"] = (
        len(pieces) == 2 and len(places) == 1 and len(turns) == 1)
    flags["has_articulation_switch"] = flags["has_close"] or flags["has_open"] or flags["has_switch"]
    return flags


def validate(payload, ctx):
    errors = []
    checks = [0]

    def check(condition, name, detail=""):
        checks[0] += 1
        if condition:
            print("[check] PASS %s%s" % (name, (": " + detail) if detail else ""))
        else:
            print("[check] FAIL %s%s" % (name, (": " + detail) if detail else ""))
            errors.append(name)

    candidates = payload["candidates"]
    source_candidates = ctx["source_candidates"]
    pieces = ctx["pieces"]
    stats = payload["stats"]["instructions"]
    source_by_id = {c["candidate_id"]: c for c in source_candidates["candidates"]}
    instructed_by_id = {c["candidate_id"]: c for c in candidates}
    ids = [c["candidate_id"] for c in candidates]
    n_candidates = len(source_candidates["candidates"])

    # --- source files untouched ---------------------------------------------
    for path_text, digest in sorted(ctx["source_sha256"].items()):
        path = Path(path_text)
        check(path.exists() and sha256_file(path) == digest,
              "source file unchanged: %s" % path.name)
    check(payload["summary"] == source_candidates["summary"], "summary identical to candidates.json")
    if source_candidates.get("scene_review") is not None:
        check(payload.get("scene_review") == source_candidates.get("scene_review"),
              "scene_review block carried over from candidates.json")
        check(payload["meta"].get("scene_review_version") ==
              payload["summary"].get("review_decisions_version"),
              "meta.scene_review_version == summary.review_decisions_version")
        check(payload["summary"].get("total") in (None, n_candidates),
              "instructed count == summary.total", "%d" % n_candidates)

    # --- record identity / preserved fields ---------------------------------
    check(len(candidates) == n_candidates,
          "candidate count == candidates.json (from JSON, not hard-coded)",
          "%d" % n_candidates)
    check(ids == [c["candidate_id"] for c in source_candidates["candidates"]],
          "candidate order/ids identical to candidates.json")
    check(len(set(ids)) == len(ids), "candidate_id uniqueness")
    preserved_bad = []
    for candidate in candidates:
        source = source_by_id[candidate["candidate_id"]]
        if any(candidate.get(key) != value for key, value in source.items()):
            preserved_bad.append(candidate["candidate_id"])
    check(not preserved_bad, "original candidate fields preserved byte-for-byte (all keys)",
          "%d bad" % len(preserved_bad))
    missing_fields = [(c["candidate_id"], field) for c in candidates
                      for field in INSTRUCTION_FIELDS if field not in c]
    check(not missing_fields, "instruction fields present on all candidates",
          "%d missing" % len(missing_fields))
    check(all(c["instruction"] and c["instruction_template"] and c["instruction_variants"]
              and c["instruction_evidence"] and c["instruction_source"] for c in candidates),
          "instruction fields non-empty")

    # --- instruction style ---------------------------------------------------
    style_bad = []
    for candidate in candidates:
        text = candidate["instruction"]
        if (text != text.strip() or not text or "\n" in text or "  " in text
                or text != text.lower() or text.endswith(".") or " ," in text
                or " and and " in text or "the the " in text):
            style_bad.append(candidate["candidate_id"])
    check(not style_bad, "instruction style: lowercase/single-line/clean/no trailing period",
          "%d bad" % len(style_bad))
    check(all("pick up" not in c["instruction"] for c in candidates),
          "no legacy `pick up ...` wording remains (normalized to put/stack)")

    # --- template id / counts ----------------------------------------------
    bad_templates = [c["candidate_id"] for c in candidates
                     if c["instruction_template"] not in TEMPLATE_IDS]
    check(not bad_templates, "instruction_template in defined template set (%s)"
          % ", ".join(TEMPLATE_IDS), "%d bad" % len(bad_templates))
    template_counter = Counter(c["instruction_template"] for c in candidates)
    check(sum(stats["template_counts"].values()) == n_candidates
          and sum(template_counter.values()) == n_candidates,
          "template hit counts sum to candidate count", "%d" % n_candidates)
    check(all(stats["template_counts"][tid] == template_counter.get(tid, 0) for tid in TEMPLATE_IDS),
          "stats.instructions.template_counts == recomputed")

    # --- template-specific textual invariants ------------------------------
    by_template = defaultdict(list)
    for candidate in candidates:
        by_template[candidate["instruction_template"]].append(candidate)
    check(stats["template_counts"]["T5"] == 0 and len(by_template["T5"]) == 0,
          "T5 zero hits in current candidate set (definition kept for future scenes)")
    open_place_left = [c["candidate_id"] for c in candidates
                       if structural_flags(pieces[c["candidate_id"]])["open_matches_in"]]
    check(not open_place_left,
          "no open+place same-container candidate remains after scene review",
          "%d bad" % len(open_place_left))
    check(stats.get("template_zero_hits") == [tid for tid in TEMPLATE_IDS
                                              if stats["template_counts"][tid] == 0],
          "stats.instructions.template_zero_hits == recomputed")
    check(all("put both " in c["instruction"] for tid in ("T1", "T2", "T4b")
              for c in by_template[tid]),
          "T1/T2/T4b contain `put both `")
    check(all("and close it" in c["instruction"] for c in by_template["T4"] + by_template["T4b"]),
          "T4/T4b contain `and close it`", "%d records" % len(by_template["T4"] + by_template["T4b"]))
    check(all(" in it" in c["instruction"] for c in by_template["T5"]),
          "T5 contains ` in it`", "%d records" % len(by_template["T5"]))
    check(all(re.search(r"\bturn it on\b", c["instruction"]) or " on it" in c["instruction"]
              for c in by_template["T7"]),
          "T7 place+turn-on uses `it` ellipsis", "%d records" % len(by_template["T7"]))
    check(all(re.search(r"\bturn it off\b", c["instruction"]) or " on it" in c["instruction"]
              for c in by_template["T8"]),
          "T8 place+turn-off uses `it` ellipsis", "%d records" % len(by_template["T8"]))
    check(all("stack " in c["instruction"] and "on top of it" in c["instruction"]
              for c in by_template["T9"]),
          "T9 uses stack template + `on top of it`", "%d records" % len(by_template["T9"]))
    check(all(count_clauses(c["instruction"]) >= 2 for c in by_template["T3"]),
          "T3 has two placement clauses", "%d records" % len(by_template["T3"]))
    check(all(count_clauses(c["instruction"]) >= 2 for c in by_template["T10"] + by_template["T6"]),
          "T6/T10 have at least two normalized clauses")

    # --- structural consistency: same structure -> same template ------------
    structural_bad = []
    for candidate in candidates:
        flags = structural_flags(pieces[candidate["candidate_id"]])
        template = candidate["instruction_template"]
        if flags["same_container_two_in"]:
            expected = "T4b" if flags["close_matches_in"] else (
                "T5" if flags["open_matches_in"] else "T1")
            if template != expected and not (expected == "T1" and template in ("T4b", "T5")):
                structural_bad.append((candidate["candidate_id"], expected, template))
        if "stack_anchor" in (candidate.get("dependency") or []) and template != "T9":
            structural_bad.append((candidate["candidate_id"], "T9", template))
        if flags["only_place_switch"] and flags["switch_matches_place"]:
            expected = "T7" if any(p["kind"] == "turn_on" for p in pieces[candidate["candidate_id"]]) else "T8"
            if template != expected:
                structural_bad.append((candidate["candidate_id"], expected, template))
    check(not structural_bad, "same goal structure -> same template (structural sampling)",
          "%d bad" % len(structural_bad))

    # --- naive concatenation replaced --------------------------------------
    same_concat = [c for c in candidates if c["instruction"] == c["language"]]
    changed = [c for c in candidates if c["instruction"] != c["language"]]
    required_different_bad = []
    t5_side_bad = []
    same_allowed_bad = []
    for candidate in candidates:
        flags = structural_flags(pieces[candidate["candidate_id"]])
        template = candidate["instruction_template"]
        side_langs = [candidate["s1_task"].get("language", ""),
                      candidate["s2_task"].get("language", "")]
        same = candidate["instruction"] == candidate["language"]
        # T5 is literally the LIBERO-90 /00 official sentence; when a side *is* task 00 the
        # template output may legitimately coincide with that official language.
        t5_side_realized = template == "T5" and any(lang and lang in candidate["instruction"]
                                                    for lang in side_langs)
        both_canonical = all(("pick up" not in lang and "place it" not in lang)
                             for lang in side_langs)
        allowed_same = ("independent" in (candidate.get("dependency") or [])
                        or flags["has_articulation_switch"]
                        or candidate["class"] in ("conflict", "degenerate")
                        or both_canonical)
        if template in ("T1", "T2", "T4", "T4b", "T7", "T8", "T9") and same:
            required_different_bad.append(candidate["candidate_id"])
        if template == "T5" and same and not t5_side_realized:
            t5_side_bad.append(candidate["candidate_id"])
        if template in ("T3", "T5", "T6", "T10") and same and not allowed_same:
            same_allowed_bad.append(candidate["candidate_id"])
    check(not required_different_bad,
          "T1/T2/T4/T4b/T7/T8/T9 instructions differ from naive official concat",
          "%d bad" % len(required_different_bad))
    check(not t5_side_bad,
          "T5 instructions differ from naive concat unless the template is already one side's official language",
          "%d bad" % len(t5_side_bad))
    check(not same_allowed_bad,
          "naive-concat equality only for independent/articulation/canonical/conflict/degenerate",
          "%d bad" % len(same_allowed_bad))
    print("[check] NOTE templated instructions changed vs naive concat: %d / %d (%d unchanged, "
          "allowed categories)." % (len(changed), n_candidates, len(same_concat)))

    # --- variants ------------------------------------------------------------
    variant_bad = []
    for candidate in candidates:
        variants = candidate["instruction_variants"]
        clauses = candidate["instruction_clauses"]
        if variants.get("and") != candidate["instruction"]:
            variant_bad.append((candidate["candidate_id"], "and"))
        if len(clauses) > 1:
            if ", then " not in variants.get("then", ""):
                variant_bad.append((candidate["candidate_id"], "then"))
        if candidate["class"] == "hard" and variants.get("then") == candidate["instruction"]:
            variant_bad.append((candidate["candidate_id"], "then-hard"))
        if variants.get("then") != candidate["instruction"] and ", then " not in variants["then"]:
            variant_bad.append((candidate["candidate_id"], "then-format"))
        if ("put both" in candidate["instruction"]) != ("both" in variants):
            variant_bad.append((candidate["candidate_id"], "both"))
        if bool(re.search(r"\bit\b", candidate["instruction"])) != ("it" in variants):
            variant_bad.append((candidate["candidate_id"], "it"))
    check(not variant_bad, "instruction_variants consistent (and/then/both/it)", "%d bad" % len(variant_bad))
    check(all(c["instruction_preferred_variant"] == ("then" if c["class"] == "hard" else "and")
              for c in candidates),
          "preferred variant: then for hard, and otherwise")

    # --- evidence / source ---------------------------------------------------
    evidence_bad = []
    for candidate in candidates:
        evidence = candidate["instruction_evidence"]
        if not isinstance(evidence, dict):
            evidence_bad.append(candidate["candidate_id"])
            continue
        if evidence.get("template_id") != candidate["instruction_template"]:
            evidence_bad.append(candidate["candidate_id"])
        if not evidence.get("references") or not evidence.get("evidence"):
            evidence_bad.append(candidate["candidate_id"])
    check(not evidence_bad, "instruction_evidence complete and template-consistent",
          "%d bad" % len(evidence_bad))
    duplicate_evidence = [c["candidate_id"] for c in candidates
                          if len(c["instruction_evidence"].get("evidence") or []) != len(
                              set(c["instruction_evidence"].get("evidence") or []))]
    check(not duplicate_evidence, "instruction_evidence has no duplicated entries",
          "%d bad" % len(duplicate_evidence))
    source_pattern = re.compile(r"^(?:template:L(?:10|90)-\d{2}|borrowed:\d{2}|synthesized)$")
    source_bad = [c["candidate_id"] for c in candidates
                  if not source_pattern.match(c["instruction_source"])]
    check(not source_bad, "instruction_source matches template:/borrowed:/synthesized",
          "%d bad" % len(source_bad))
    check(all(c["instruction_source"].startswith("template:") for c in candidates
              if c["route"] == "M1"),
          "M1 instruction_source is template:<ref>")
    check(all(c["instruction_source"].startswith("borrowed:")
              for c in candidates if c["route"] == "M2"),
          "M2 instruction_source is borrowed:<task>")
    check(all(c["instruction_source"] == "synthesized"
              for c in candidates if c["route"] == "S1"),
          "S1 instruction_source is synthesized")

    # --- M2 / S1 promoted nouns ---------------------------------------------
    promoted_bad = []
    for candidate in candidates:
        if candidate["route"] not in ("M2", "S1"):
            continue
        promoted = candidate.get("promoted_target") or {}
        promoted_piece = None
        for piece in pieces[candidate["candidate_id"]]:
            if piece["source"] in ("s1", "s2") and piece["kind"] in PLACEMENT_KINDS:
                if piece.get("obj_arg") == promoted.get("object"):
                    promoted_piece = piece
                    break
        if promoted_piece is None or promoted_piece["obj_noun"] not in candidate["instruction"]:
            promoted_bad.append(candidate["candidate_id"])
    check(not promoted_bad, "M2/S1 promoted object noun appears in instruction and is annotated",
          "%d bad" % len(promoted_bad))
    s1_ab = [c for c in candidates if c["route"] == "S1" and c["order"] == "ab"]
    s1_ba = [c for c in candidates if c["route"] == "S1" and c["order"] == "ba"]
    check(len(s1_ab) == 1 and len(s1_ba) == 1
          and "turn it off" in s1_ab[0]["instruction"]
          and "turn off the stove" in s1_ba[0]["instruction"]
          and "on it" in s1_ba[0]["instruction"],
          "S1 ab uses `turn it off`, ba uses `turn off ... and put ... on it`")

    # --- stats consistency ---------------------------------------------------
    recomputed_variants = Counter()
    recomputed_sources = Counter()
    scene_counter = Counter()
    for candidate in candidates:
        for key in candidate["instruction_variants"]:
            recomputed_variants[key] += 1
        recomputed_sources[candidate["instruction_source"]] += 1
        scene_counter[candidate["scene"]] += 1
    check(all(stats["variant_counts"][key] == recomputed_variants.get(key, 0)
              for key in ("and", "then", "both", "it")),
          "variant counts match recomputation")
    check(dict(stats["instruction_source_counts"]) == dict(recomputed_sources),
          "instruction_source counts match recomputation")
    check(sum(sum(row.values()) for row in stats["scene_template"].values()) == n_candidates,
          "per-scene template matrix sums to candidate count")
    check(stats["n_unique_instructions"] == len({c["instruction"] for c in candidates}),
          "unique instruction count matches recomputation",
          "%d" % stats["n_unique_instructions"])

    # --- parse cache / L10 evidence -----------------------------------------
    dual7 = set(ctx["source_candidates"] and {5, 9, 17, 19, 25, 40, 41})
    check(set(ctx["parse_errors"]) <= dual7,
          "official-language parse only fails on dual-goal (non-pool) tasks",
          "errors=%r" % sorted(ctx["parse_errors"]))
    check(ctx["l10_check"]["n"] == 10,
          "LIBERO-10 evidence templates crosschecked (%d)" % ctx["l10_check"]["n"])

    # --- on-disk round-trip --------------------------------------------------
    if INSTRUCTED_JSON.exists():
        check(read_json(INSTRUCTED_JSON) == payload, "candidates-instructed.json round-trip")
    if TEMPLATES_MD.exists():
        text = TEMPLATES_MD.read_text(encoding="utf-8")
        check(len(text) > 5000 and all("`%s`" % tid in text for tid in TEMPLATE_IDS),
              "INSTRUCTION_TEMPLATES.md written with all templates",
              "%d chars" % len(text))
        appendix = text.split("## 10. 每条候选的模板命中（附录）")[-1]
        appendix_rows = sum(1 for line in appendix.splitlines() if line.startswith("| `L90_"))
        check(appendix_rows == n_candidates,
              "INSTRUCTION_TEMPLATES.md appendix lists all candidates",
              "%d rows" % appendix_rows)
        check("当前候选集 **0 条**" in text and "`T5` |" in text,
              "INSTRUCTION_TEMPLATES.md keeps T5 definition with 0-hit annotation")
    if errors:
        print("[check] FAILED %d of %d checks" % (len(errors), checks[0]))
        return False
    print("[check] OK -- %d checks passed" % checks[0])
    return True


# ---------------------------------------------------------------------------
# Orchestration / CLI
# ---------------------------------------------------------------------------
def write_outputs(payload, ctx):
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    INSTRUCTED_JSON.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n",
                               encoding="utf-8")
    TEMPLATES_MD.write_text(render_templates_md(payload, ctx) + "\n", encoding="utf-8")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Rebuild LIBERO-90 combined-candidate instructions from verified templates.")
    parser.add_argument("--check", action="store_true",
                        help="write outputs then assert all instruction invariants")
    args = parser.parse_args(argv)
    source_paths = [CANDIDATES_JSON, CASE_LIST_MD, README_MD, GEN_SCRIPT]
    source_sha256 = {str(path): sha256_file(path) for path in source_paths if path.exists()}
    candidates_payload, inventory, official_map, official = load_inputs()
    payload, ctx = build_instructed(candidates_payload, inventory, official)
    payload["meta"]["source_sha256"] = source_sha256
    stats = payload["stats"]["instructions"]
    payload["meta"]["instruction_stats_digest"] = hashlib.sha256(
        json.dumps(stats["template_counts"], sort_keys=True).encode("utf-8")).hexdigest()
    ctx["source_sha256"] = source_sha256
    write_outputs(payload, ctx)
    print("[build] wrote %s" % INSTRUCTED_JSON)
    print("[build] wrote %s" % TEMPLATES_MD)
    print("[build] template counts: %s" % stats["template_counts"])
    n_candidates = len(payload["candidates"])
    print("[build] candidates: %d | scene_review v%s: pool_bddl=%s pairing_pool=%s excluded=%s "
          "| template_zero_hits: %s"
          % (n_candidates, payload["summary"].get("review_decisions_version"),
             payload["summary"].get("pool_bddl"), payload["summary"].get("single_pool"),
             payload["summary"].get("review_excluded_tasks"),
             stats.get("template_zero_hits")))
    print("[build] variants: %s | sources: %s | changed-vs-concat: %d/%d"
          % (stats["variant_counts"], stats["instruction_source_counts"],
             sum(1 for c in payload["candidates"] if c["instruction"] != c["language"]),
             n_candidates))
    if not args.check:
        return 0
    ok = validate(payload, ctx)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())