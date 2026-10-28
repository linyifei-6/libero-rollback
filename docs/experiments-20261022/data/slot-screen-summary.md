# Slot-substitution candidate screening (pi05, seed 0, 600 steps / replan 10)

**2/45 candidates solved**

## By scene

| scene | episodes | success |
|---|---|---|
| KITCHEN_SCENE3 | 2 | 0 |
| KITCHEN_SCENE4 | 3 | 0 |
| KITCHEN_SCENE6 | 2 | 0 |
| KITCHEN_SCENE8 | 2 | 1 |
| LIVING_ROOM_SCENE1 | 5 | 0 |
| LIVING_ROOM_SCENE2 | 19 | 1 |
| LIVING_ROOM_SCENE5 | 5 | 0 |
| LIVING_ROOM_SCENE6 | 3 | 0 |
| STUDY_SCENE1 | 4 | 0 |

## By risk

| risk | episodes | success |
|---|---|---|
| medium | 5 | 0 |
| high | 4 | 0 |
| low | 36 | 2 |

## Per candidate

| candidate | scene | risk | success | steps | language |
|---|---|---|---|---|---|
| k3_frypan_on_stove | KITCHEN_SCENE3 | medium | False | 600 | turn on the stove and put the frying pan on it |
| k3_moka_and_frypan_on_stove | KITCHEN_SCENE3 | high | False | 600 | turn on the stove and put the moka pot and the frying pan on it |
| k4_bowl_middle_close | KITCHEN_SCENE4 | medium | False | 600 | put the black bowl in the middle drawer of the cabinet and close it |
| k4_wine_bottle_bottom_close | KITCHEN_SCENE4 | high | False | 600 | put the wine bottle in the bottom drawer of the cabinet and close it |
| k4_wine_bottle_middle_close | KITCHEN_SCENE4 | high | False | 600 | put the wine bottle in the middle drawer of the cabinet and close it |
| k6_both_mugs_microwave_close | KITCHEN_SCENE6 | high | False | 600 | put the white mug and the yellow and white mug in the microwave and close it |
| k6_porcelain_mug_microwave_close | KITCHEN_SCENE6 | low | False | 600 | put the white mug in the microwave and close it |
| k8_left_pot_on_stove | KITCHEN_SCENE8 | low | True | 168 | put the left moka pot on the stove and turn it on |
| k8_right_pot_on_stove | KITCHEN_SCENE8 | low | False | 600 | put the right moka pot on the stove and turn it on |
| lr1_cheese_ketchup | LIVING_ROOM_SCENE1 | low | False | 600 | put both the cream cheese box and the ketchup in the basket |
| lr1_cheese_tomato | LIVING_ROOM_SCENE1 | low | False | 600 | put both the cream cheese box and the tomato sauce in the basket |
| lr1_soup_ketchup | LIVING_ROOM_SCENE1 | low | False | 600 | put both the alphabet soup and the ketchup in the basket |
| lr1_soup_tomato | LIVING_ROOM_SCENE1 | low | False | 600 | put both the alphabet soup and the tomato sauce in the basket |
| lr1_tomato_ketchup | LIVING_ROOM_SCENE1 | low | False | 600 | put both the tomato sauce and the ketchup in the basket |
| lr2_cheese_juice | LIVING_ROOM_SCENE2 | low | False | 600 | put both the cream cheese box and the orange juice in the basket |
| lr2_cheese_ketchup | LIVING_ROOM_SCENE2 | low | False | 600 | put both the cream cheese box and the ketchup in the basket |
| lr2_cheese_milk | LIVING_ROOM_SCENE2 | low | False | 600 | put both the cream cheese box and the milk in the basket |
| lr2_cheese_tomato | LIVING_ROOM_SCENE2 | low | False | 600 | put both the cream cheese box and the tomato sauce in the basket |
| lr2_juice_butter | LIVING_ROOM_SCENE2 | low | False | 600 | put both the orange juice and the butter in the basket |
| lr2_juice_milk | LIVING_ROOM_SCENE2 | low | False | 600 | put both the orange juice and the milk in the basket |
| lr2_ketchup_butter | LIVING_ROOM_SCENE2 | low | False | 600 | put both the ketchup and the butter in the basket |
| lr2_ketchup_juice | LIVING_ROOM_SCENE2 | low | False | 600 | put both the ketchup and the orange juice in the basket |
| lr2_ketchup_milk | LIVING_ROOM_SCENE2 | low | False | 600 | put both the ketchup and the milk in the basket |
| lr2_milk_butter | LIVING_ROOM_SCENE2 | low | False | 600 | put both the milk and the butter in the basket |
| lr2_soup_butter | LIVING_ROOM_SCENE2 | low | False | 600 | put both the alphabet soup and the butter in the basket |
| lr2_soup_cheese | LIVING_ROOM_SCENE2 | low | False | 600 | put both the alphabet soup and the cream cheese box in the basket |
| lr2_soup_juice | LIVING_ROOM_SCENE2 | low | False | 600 | put both the alphabet soup and the orange juice in the basket |
| lr2_soup_ketchup | LIVING_ROOM_SCENE2 | low | False | 600 | put both the alphabet soup and the ketchup in the basket |
| lr2_soup_milk | LIVING_ROOM_SCENE2 | low | False | 600 | put both the alphabet soup and the milk in the basket |
| lr2_tomato_butter | LIVING_ROOM_SCENE2 | low | True | 388 | put both the tomato sauce and the butter in the basket |
| lr2_tomato_juice | LIVING_ROOM_SCENE2 | low | False | 600 | put both the tomato sauce and the orange juice in the basket |
| lr2_tomato_ketchup | LIVING_ROOM_SCENE2 | low | False | 600 | put both the tomato sauce and the ketchup in the basket |
| lr2_tomato_milk | LIVING_ROOM_SCENE2 | low | False | 600 | put both the tomato sauce and the milk in the basket |
| lr5_porcelain_left_red_right | LIVING_ROOM_SCENE5 | low | False | 600 | put the white mug on the left plate and put the red coffee mug on the right plate |
| lr5_red_left_porcelain_right | LIVING_ROOM_SCENE5 | low | False | 600 | put the red coffee mug on the left plate and put the white mug on the right plate |
| lr5_red_left_yellow_white_right | LIVING_ROOM_SCENE5 | low | False | 600 | put the red coffee mug on the left plate and put the yellow and white mug on the right plate |
| lr5_yellow_white_left_porcelain_right | LIVING_ROOM_SCENE5 | low | False | 600 | put the yellow and white mug on the left plate and put the white mug on the right plate |
| lr5_yellow_white_left_red_right | LIVING_ROOM_SCENE5 | low | False | 600 | put the yellow and white mug on the left plate and put the red coffee mug on the right plate |
| lr6_red_plate_pudding_right | LIVING_ROOM_SCENE6 | low | False | 600 | put the red coffee mug on the plate and put the chocolate pudding to the right of the plate |
| lr6_red_plate_white_right | LIVING_ROOM_SCENE6 | low | False | 600 | put the red coffee mug on the plate and put the white mug to the right of the plate |
| lr6_white_plate_red_right | LIVING_ROOM_SCENE6 | low | False | 600 | put the white mug on the plate and put the red coffee mug to the right of the plate |
| study_book_back_mug_right_comp | STUDY_SCENE1 | medium | False | 600 | pick up the book and place it in the back compartment of the caddy and put the yellow and white mug in the right compartment of the caddy |
| study_book_back_mug_table_right | STUDY_SCENE1 | low | False | 600 | pick up the book and place it in the back compartment of the caddy and put the yellow and white mug to the right of the caddy |
| study_book_front_mug_left_comp | STUDY_SCENE1 | medium | False | 600 | pick up the book and place it in the front compartment of the caddy and put the yellow and white mug in the left compartment of the caddy |
| study_book_front_mug_right_comp | STUDY_SCENE1 | medium | False | 600 | pick up the book and place it in the front compartment of the caddy and put the yellow and white mug in the right compartment of the caddy |
