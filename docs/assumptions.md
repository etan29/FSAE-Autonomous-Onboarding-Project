# Assumptions and configurable choices

The feature specification leaves a few points open. Each one below is a choice the generator makes, and the related setting that changes it. These are not extra competition rules.

## Rule profiles

`us_fsae_driverless_2025` uses the numbers the specification lists for the 2025 U.S. Formula SAE Driverless Supplement: 3.0 m minimum width, 9.0 m minimum turning diameter, 80 m maximum straight, 200–500 m lap length, and the stated cone colors and sizes. Cone spacing is whatever you set. This profile does not apply the Formula Student 5 m spacing cap.

`formula_student_2026` only adds what the specification states for that profile: cones no more than 5 m apart, with tighter spacing in corners. It does not define track width, turning diameter, straight length, lap length, or different cone dimensions. Those stay at the generator settings, and the validation report says so. If you ask for more than 5 m spacing, the generator reduces it to 5 m and records a warning.

Edit the JSON files in `fsae_env_generator/profiles/` to change a profile. Do not treat either file as a complete rulebook.

## Track width and cone position

Track width is the distance between the inner edges of the cone bases. The boundary polylines are those inner edges, offset from the centerline by half the width. Each cone's center is moved outward by half its base width, so the inner face of the base sits on the boundary and the cone body is outside the asphalt.

## Events

The sidebar builds four 2026 courses: Acceleration, Skidpad, Autocross, and the EBS brake test. Official dimensions are cited in the ground-truth file. Lengths the rulebooks do not publish (EBS approach, the Remote Stop coordinate, and any corridor past 8.5 m) are labeled assumptions there. See `docs/iteration3.md`.

Autocross and trackdrive are closed loops. The stopping zone is the first part of the lap after the finish, on the same centerline. A separate orange entry/exit corridor is drawn only when `enable_entry_exit` is set. The start/finish gate is placed at the beginning of the longest straight.

A custom track reads coordinates, or in Blender the curve object `FSAE_Input_Centerline`. Generate reads that curve again. Regenerate rebuilds the stored result, including the curve points saved with it.

## Corners, straights, S-curves, chicanes

The procedural centerline starts from a rounded loop or, when it still meets the limits, a convex polygon with one sharpened corner. An S-curve and a chicane are then added on straights when they do not break the width, the turning radius, the maximum straight, or the lap length. A Catmull-Rom spline resamples the result when that spline still passes the same checks. Otherwise the arc-and-line path is kept.

"Straight" means curvature gentler than a 50 m radius (`straight_curvature_radius`). The official turning radius is measured over a 2 m window so the join between a straight and a fillet is not reported as a tighter corner than the fillet itself. If `num_corners` and `num_straights` disagree, the corner count is used, because a single closed loop has one straight per corner. The count is increased when that is the only way to stay under the maximum straight length. A requested minimum straight can be missed when lap length and the maximum straight cannot both be satisfied; that case is a warning, not a silent change of the maximum.

## Cone spacing

Straight spacing is `cone_spacing`. In corners the gap shrinks toward `corner_cone_spacing` (default 2 m) once the local radius drops below `corner_radius_threshold` (default 18 m). The Formula Student profile additionally refuses a gap above 5 m.

## Stripes

Small blue cones have one white stripe, small yellow cones have one black stripe, small orange cones have one white stripe, and large orange cones have two white stripes. The stripe heights are a visual convention. The specification requires the colors and the counts, not the exact band positions.

## Weather and lighting

`clear`, `overcast`, `sunset`, and `night` change the sun and the world background. `rain` and `fog` only dim that lighting. The generator does not create rain particles or volumetric fog.

## Reproducibility

Every random choice goes through `SeededRNG` or a named child stream. The same seed and the same settings rebuild the same positions in one Python/Blender version. Bit-identical results across different Python or Blender versions are not guaranteed, because `random.Random` is only stable inside one runtime.

## Setup guide

`llm_prompts/explain_setup.MD` is the step-by-step install and run guide.
