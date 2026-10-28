# Task-expansion experiment summary (serial GPU queue)

## dependency-pairs: 2/6

| bddl | instruction | success | steps | first_true |
|---|---|---|---|---|
| goal_pair_01_06 | put the bowl on the stove and put the cream cheese in the bowl | False | 600 | {"on akita_black_bowl_1 flat_stove_1_cook_region": 101} |
| goal_pair_01_07 | put the bowl on the stove and turn on the stove | False | 600 | {"on akita_black_bowl_1 flat_stove_1_cook_region": 94} |
| goal_pair_03_06 | open the top drawer and put the bowl inside and put the cream cheese in the bowl | False | 600 | {} |
| goal_pair_04_06 | put the bowl on top of the cabinet and put the cream cheese in the bowl | False | 600 | {"on akita_black_bowl_1 wooden_cabinet_1_top_side": 94} |
| goal_pair_04_07 | put the bowl on top of the cabinet and turn on the stove | True | 397 | {"on akita_black_bowl_1 wooden_cabinet_1_top_side": 95, "turnon flat_stove_1": 406} |
| goal_pair_06_08 | put the cream cheese in the bowl and put the bowl on the plate | True | 278 | {"on cream_cheese_1 akita_black_bowl_1": 135, "on akita_black_bowl_1 plate_1": 287} |

## longbudget: 0/4

| bddl | instruction | success | steps | first_true |
|---|---|---|---|---|
| goal_pair_00_01 | open the middle drawer of the cabinet and put the bowl on the stove | False | 990 | {"open wooden_cabinet_1_middle_region": 136} |
| goal_pair_00_02 | open the middle drawer of the cabinet and put the wine bottle on top of the cabinet | False | 990 | {"open wooden_cabinet_1_middle_region": 139} |
| goal_pair_00_07 | open the middle drawer of the cabinet and turn on the stove | False | 990 | {"open wooden_cabinet_1_middle_region": 124} |
| goal_pair_08_09 | put the bowl on the plate and put the wine bottle on the rack | False | 990 | {"on wine_bottle_1 wine_rack_1_top_region": 124} |

## hint-upfront: 0/4

| bddl | instruction | success | steps | first_true |
|---|---|---|---|---|
| goal_pair_00_01 | open the middle drawer of the cabinet and put the bowl on the stove | False | 600 | {"open wooden_cabinet_1_middle_region": 141, "on akita_black_bowl_1 flat_stove_1_cook_region": null} |
| goal_pair_00_02 | open the middle drawer of the cabinet and put the wine bottle on top of the cabinet | False | 600 | {"open wooden_cabinet_1_middle_region": null, "on wine_bottle_1 wooden_cabinet_1_top_side": 128} |
| goal_pair_00_07 | open the middle drawer of the cabinet and turn on the stove | False | 600 | {"open wooden_cabinet_1_middle_region": 146, "turnon flat_stove_1": null} |
| goal_pair_08_09 | put the bowl on the plate and put the wine bottle on the rack | False | 600 | {"on akita_black_bowl_1 plate_1": null, "on wine_bottle_1 wine_rack_1_top_region": 130} |

## hint-progress: 0/4

| bddl | instruction | success | steps | first_true |
|---|---|---|---|---|
| goal_pair_00_01 | open the middle drawer of the cabinet and put the bowl on the stove | False | 600 | {"open wooden_cabinet_1_middle_region": 137, "on akita_black_bowl_1 flat_stove_1_cook_region": null} |
| goal_pair_00_02 | open the middle drawer of the cabinet and put the wine bottle on top of the cabinet | False | 600 | {"open wooden_cabinet_1_middle_region": 140, "on wine_bottle_1 wooden_cabinet_1_top_side": null} |
| goal_pair_00_07 | open the middle drawer of the cabinet and turn on the stove | False | 600 | {"open wooden_cabinet_1_middle_region": 125, "turnon flat_stove_1": null} |
| goal_pair_08_09 | put the bowl on the plate and put the wine bottle on the rack | False | 600 | {"on akita_black_bowl_1 plate_1": null, "on wine_bottle_1 wine_rack_1_top_region": 125} |

## longbudget2: 0/4

| bddl | instruction | success | steps | first_true |
|---|---|---|---|---|
| goal_pair_00_01 | open the middle drawer of the cabinet and put the bowl on the stove | False | 1600 | {"open wooden_cabinet_1_middle_region": 136} |
| goal_pair_00_02 | open the middle drawer of the cabinet and put the wine bottle on top of the cabinet | False | 1600 | {"open wooden_cabinet_1_middle_region": 139} |
| goal_pair_00_07 | open the middle drawer of the cabinet and turn on the stove | False | 1600 | {"open wooden_cabinet_1_middle_region": 124} |
| goal_pair_08_09 | put the bowl on the plate and put the wine bottle on the rack | False | 1600 | {"on wine_bottle_1 wine_rack_1_top_region": 124} |

