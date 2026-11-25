# Iteration 3: 2026 Formula SAE driverless events

The add-on now builds the four courses used for 2026 Formula SAE Michigan driverless work. Official numbers come from Formula SAE Rules 2026 v1.0 (10 September 2025) and the Driverless Cup Supplement 2026. A number that is not in those documents is labeled an assumption in the ground-truth file and in the validation report.

## What changed

- **Acceleration.** Timed straight is 75 m (D.9.1.1). Default width is 4.9 m between the inner edges of the cone bases (D.9.1.2). Cones are about 6 m apart (D.9.1.3). The exit lane continues another 75 m, which is the maximum stop distance in DD.4.2.4. Large orange cones mark the start and the finish.
- **Skidpad.** One figure eight. Circle centers are 18.25 m apart. Inner diameter 15.25 m, outer diameter 21.25 m, driving path 3.0 m (D.10.1.1). The centerline enters from the south, drives the right circle clockwise, the left circle counter-clockwise, and leaves to the north. The real crossover is the shared point at the origin. Each circle has 17 inner pylons and 13 outer pylons (DD.4.3.1, D.10.1.2). Entry and exit cones are small orange. The drawn curve is one lap of each circle. The lap sequence in the ground truth is right, right, left, left, because D.10.2.3 times the second lap on each circle and those laps retrace the same curve. Timed length is those two laps.
- **Autocross.** Closed lap. The reported length is the centerline arc length and stays between 200 and 500 m (DD.4.4.1). Minimum width 3 m, minimum turning diameter 9 m, straights no longer than 80 m. The car stops on the track within 30 m of the finish (DD.4.4.4). This is not the combustion autocross in D.11.
- **EBS.** A straight inspection course, not a scored event (DI.2). The acceleration zone defaults to the 20 m maximum and the emergency stop defaults to the 8.5 m maximum (DI.2.2.2). The approach before that zone, the exact trigger coordinate, the width, and the rest corridor after 8.5 m are assumptions. The report says so.
- **Cones are the boundaries.** Blue and yellow guide curves are no longer created. Cone yaw follows the boundary. Jitter defaults to 0 m. Corner spacing is a separate control and defaults to 2 m.
- **Ground.** One mesh fades from flat asphalt to gravel to grass. The driving surface stays at z = 0. Tire marks and distractor paint sit a few millimeters above it. They are not course boundaries.
- **Ground truth.** A passing Generate writes `generated_tracks/FSAE_Track_Seed_<seed>_ground_truth.json`, plus centerline and cone CSV files. The same JSON is stored in the text block `FSAE_Ground_Truth`. Export Ground Truth writes those files again. The blend file is still saved only when validation passes.

Trackdrive and custom centerlines still work. Collections stay `Cones/Blue_Cones`, `Cones/Yellow_Cones`, `Cones/Orange_Cones`, and `Cones/Large_Orange_Cones`.

## Install

1. Rebuild is already done if you are using the `fsae_env_generator.zip` next to this project. If you change the source, zip the `fsae_env_generator` folder again and reinstall. Editing the source does not update an add-on that was installed from the zip.
2. Blender 4.5: Edit → Preferences → Add-ons → Install from Disk, choose `fsae_env_generator.zip`, then enable **FSAE Environment Generator**.
3. Open the 3D Viewport sidebar (N) and choose the **FSAE** tab.

You can also load the project without installing:

```text
blender --background --factory-startup --python run_generator.py -- --track-type acceleration --seed 1
```

## Use

1. Pick the event. The width, cone spacing, and stopping-zone fields update to that event's defaults. Autocross is the default.
2. Set the seed. The same seed and the same settings rebuild the same course. A different seed builds a different autocross.
3. Generate. The console prints the blend path and the ground-truth path when validation passes. Clear does not save.
4. Regenerate rebuilds the last stored settings. Edits you have not generated yet are not used.
5. Export Ground Truth writes the JSON and CSV again from the text block.

Event fields that are rules, not guesses:

| Event | Fixed by the 2026 rules |
| --- | --- |
| Acceleration | 75 m timed distance, 4.9 m minimum width, about 6 m cone spacing, stop within 75 m |
| Skidpad | 18.25 m centers, 15.25 m and 21.25 m diameters, 3.0 m path, 17 inner and 13 outer cones, 15 m staging, 25 m exit |
| Autocross | 200–500 m arc length, 3 m minimum width, 9 m minimum turning diameter, 80 m maximum straight, stop within 30 m on the track |
| EBS | Reach 40 km/h within 20 m, then stop within 8.5 m. Not a scored event |

Cone colors follow DD.1.1: blue on the left of travel, yellow on the right, small orange at entry and exit, large orange at timing lines. On the skidpad the right circle is clockwise, so its inner cones are yellow. The left circle is counter-clockwise, so its inner cones are blue.

## Check

From the project folder, with Python 3.11:

```text
python -m unittest discover -s tests -v
```

In Blender:

```text
blender --background --factory-startup --python run_generator.py -- --self-check
```
