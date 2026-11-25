# FSAE Procedural Racing Environment Generator — Setup and Execution

This guide is for the project in this folder. It uses the files, commands, and Blender controls that are actually in the project. You do not need prior experience with Blender add-ons or Python environments.

The generator builds a closed racing loop, blue and yellow cones, orange start cones, and optional paddock objects (trees, tents, spectators, barriers). Lengths are meters. A seed number makes the same settings rebuild the same scene.

---

## 1. Software requirements

### Blender

The add-on declares that it needs **Blender 3.6.0 or newer** (`bl_info` in `fsae_env_generator/__init__.py`).

It was run and checked on **Blender 4.5.4 LTS**, installed at:

`C:\Program Files\Blender Foundation\Blender 4.5\blender.exe`

Use that version if you have it. A newer 4.x release should also work. The sidebar layout described below matches Blender 4.5.

Check the version you have:

1. Open Blender.
2. Click **Help → About Blender** and read the version at the top.

Or, in PowerShell:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --version
```

If Blender is installed somewhere else, use that path instead. You can also find `blender.exe`, hold Shift, right-click it, and choose **Copy as path**.

### Python

Blender brings its own Python. You do not install Python inside Blender, and you do not point Blender at a Python you installed yourself.

Blender 4.5.4 uses **Python 3.11.11**. Confirm it with:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --background --python-expr "import sys; print(sys.version)"
```

You should see a line that starts with `3.11.11`.

The automated tests do not use Blender. They use the `python` command on your PATH. Python 3.11 is what this project was tested with. Check it with:

```powershell
python --version
```

If that command is not found, install Python 3.11 from [python.org](https://www.python.org/downloads/) and tick **Add python.exe to PATH** during setup. The tests only need the standard library. They do not need Blender's Python.

### External libraries

None. There is no `requirements.txt` and nothing to `pip install`.

The generator uses only:

- the Python standard library (`json`, `math`, `random`, `pathlib`, `dataclasses`, `hashlib`, `unittest`, and so on)
- `bpy` and `mathutils`, which are already inside Blender

`bpy` cannot be installed with pip for this project. If a command says Blender is not available, you ran the script with system Python. That is fine for a text report. It will not build a 3D scene. Building the scene requires Blender.

### How to check that you are ready

| Check | Command or action | What you want |
| --- | --- | --- |
| Blender exists | Help → About, or `blender.exe --version` | 3.6.0 or newer. 4.5.4 LTS is the tested version. |
| Blender's Python | the `--python-expr` command above | 3.11.x on Blender 4.5 |
| System Python for tests | `python --version` | 3.11.x |
| Third-party packages | none | Do not install `bpy`, `mathutils`, or a requirements file. |

---

## 2. Project setup

### Open the project in Cursor

1. Start Cursor.
2. **File → Open Folder**.
3. Choose:

`C:\Users\monac\OneDrive\Desktop\FSAE-Autonomous-Onboarding-Project`

4. Click **Select Folder**.

You should see `fsae_env_generator`, `tests`, `run_generator.py`, `docs`, and `llm_prompts` in the sidebar. Leave the files where they are. The import statements expect this layout.

### Where every Python file lives

```text
FSAE-Autonomous-Onboarding-Project/
  run_generator.py                          entry script for Blender and the terminal
  fsae_env_generator/
    __init__.py                             add-on entry: register() / unregister()
    ui.py                                   sidebar panel and Generate / Regenerate / Clear
    blender_backend.py                      creates and deletes Blender objects
    pipeline.py                             builds one full environment from settings
    config.py                               settings, rule profiles, JSON save/load
    profiles/
      us_fsae_driverless_2025.json
      formula_student_2026.json
    track.py                                centerline, boundaries, asphalt
    cones.py                                cone positions
    environment.py                          trees, tents, spectators, barriers, props
    assets.py                               meshes and colors
    validation.py                           checks and the text report
    models.py                               shared records and collection names
    math2d.py                               2D geometry
    splines.py                              curve smoothing
    spatial.py                              overlap checks
    rng.py                                  seeded random numbers
  tests/
    test_math.py
    test_track.py
    test_scene.py
  docs/
    assumptions.md                          choices the specification left open
```

There are no other Python modules. Do not move `fsae_env_generator` out of the project folder unless you are installing a zip copy into Blender (section 3).

### What each file does

- `run_generator.py` — Starts a generation. Inside Blender it builds the scene. Outside Blender it prints a validation report and does not create objects. `--self-check` loads the add-on, presses Generate, checks the scene, clears it, and regenerates it.
- `fsae_env_generator/__init__.py` — Tells Blender the add-on name, the minimum Blender version, and where the panel lives (`View3D > Sidebar > FSAE`). Importing this file does not load Blender. Blender calls `register()` when you enable the add-on.
- `ui.py` — The **FSAE Environment** panel: Seed, Track Width, Cone Spacing, Track Type, Rules Profile, Environment Density, and the Trees / Tents / Spectators / Barriers checkboxes. The buttons call operators `fsae.generate`, `fsae.regenerate`, and `fsae.clear`.
- `blender_backend.py` — The only place, besides the panel, that creates Blender data. It makes collections, shared meshes, materials named `FSAE_MAT_...`, the sun, the camera, and the report text. `clear_generated_scene()` deletes that generated data.
- `pipeline.py` — `generate_environment(config)` runs the track, cones, and surroundings, then validates the result. It builds the scene twice in memory and compares them so the report can say whether the seed repeated.
- `config.py` — `GeneratorConfig` holds every setting. `resolve_limits()` turns a profile plus your numbers into the limits that validation uses. Profiles are loaded from the `profiles` folder.
- `track.py` — Builds the closed centerline, offsets the left and right boundaries by half the track width, and builds the asphalt mesh.
- `cones.py` — Walks each boundary and places cones. Blue on the left of the direction of travel, yellow on the right. Large orange cones mark the start. Autocross adds an orange lane beside the start straight.
- `environment.py` — Places trees, tents, spectators, barriers, and other paddock objects outside the asphalt. Density `0` skips trees, tents, spectators, and scattered props. Boundary cones are still placed.
- `assets.py` — Cone, tree, tent, person, and prop meshes, plus the color table `MATERIAL_RGBA`. One mesh is shared by every copy of that object.
- `validation.py` — Measures width, spacing, colors, sides, overlaps, and whether a second build matched the first. `format_report()` is the text you see in Blender.
- `models.py` — Names used everywhere else: root collection `FSAE_Environment`, report text `FSAE_Validation_Report`, custom curve `FSAE_Input_Centerline`.
- `math2d.py`, `splines.py`, `spatial.py`, `rng.py` — Geometry, smoothing, a grid that finds nearby objects, and the single random-number source. Nothing in these four files talks to Blender.
- `tests/` — Unit tests. They import `fsae_env_generator` and never start Blender.
- `docs/assumptions.md` — Explains width (inner edge of the cone bases), which rules each profile actually enforces, and what “the same seed” means.

### How the files call each other

```text
Sidebar (ui.py) or run_generator.py
        |
        v
pipeline.generate_environment(config)
        |
        +-- config.py          load the rules profile and resolve limits
        +-- rng.py             one seeded random stream, then named child streams
        +-- track.py           centerline, boundaries, asphalt
        +-- cones.py           blue, yellow, and orange cones
        +-- environment.py     trees, tents, spectators, barriers, props
        +-- assets.py          meshes and colors
        +-- validation.py      checks and the report
        |
        v
blender_backend.build_blender_scene(...)     only when Blender is running
```

`bpy` is imported only when Blender is actually running the add-on or `blender_backend.py`. That is why `python -m unittest` works without Blender.

---

## 3. Blender setup

### Open Blender

Start **Blender 4.5** from the Start menu, or double-click:

`C:\Program Files\Blender Foundation\Blender 4.5\blender.exe`

The splash screen can be closed with a click outside it. You will see a gray cube in the 3D Viewport. You can leave the cube. Generate does not delete your own objects. It only replaces a previous `FSAE_Environment` collection.

### Two ways to run this project

You need the add-on if you want the sidebar. Running `run_generator.py` once builds a scene immediately and does not leave the panel behind.

| Goal | What to do |
| --- | --- |
| Click Generate in the sidebar and change seed, width, and spacing | Install and enable the add-on (section 3.1). |
| Build one scene from a saved script, or from PowerShell | Run `run_generator.py` (section 3.2). |
| Check that Blender itself can build, clear, and regenerate | `--self-check` (section 7). |

Use one of these. If the add-on is enabled and you also call `fsae_env_generator.register()` from a script, Blender will report that the classes are already registered.

### 3.1 Install and enable the add-on

The add-on is the folder `fsae_env_generator`, not the whole project. Blender looks for `bl_info` in that folder's `__init__.py`.

**Make the zip**

1. Open PowerShell.
2. Run:

```powershell
Compress-Archive -Path "C:\Users\monac\OneDrive\Desktop\FSAE-Autonomous-Onboarding-Project\fsae_env_generator" -DestinationPath "C:\Users\monac\OneDrive\Desktop\FSAE-Autonomous-Onboarding-Project\fsae_env_generator.zip" -Force
```

The zip must contain a folder named `fsae_env_generator` with `__init__.py` inside it. Do not zip only the `.py` files, and do not zip the whole project folder.

**Install it in Blender 4.5**

1. In Blender, **Edit → Preferences**.
2. Click **Add-ons** on the left.
3. Click the small down-arrow at the top right of the add-on list.
4. Click **Install from Disk...**.
5. Select `fsae_env_generator.zip` in the project folder.
6. The list should jump to **FSAE Autonomous Environment Generator**. Turn its checkbox on.

If you do not see it, type `FSAE` in the search box at the top of the Add-ons page. The add-on category is **Add Mesh**. The location line reads `View3D > Sidebar > FSAE`.

Close Preferences.

**Open the panel**

1. Click the **Layout** workspace tab at the very top (the default 3D view).
2. Click inside the big 3D view so it is the active area.
3. Press **N**.

A sidebar opens on the right of the 3D view. Along its edge are tabs such as Item, Tool, and View. Click the tab named **FSAE**.

You should see the panel **FSAE Environment** with Seed, Track Width, Cone Spacing, Track Type, Rules Profile, Environment Density, four checkboxes, and the buttons **Generate**, **Regenerate**, and **Clear**.

If the N sidebar is open and there is no FSAE tab, the add-on is not enabled. Go back to Preferences → Add-ons and enable it.

**Edits in Cursor do not change an installed add-on.** Blender copied the folder into its own add-ons directory. After you change Python files, make the zip again, use **Install from Disk** again, and enable the checkbox again. Restart Blender if the old panel is still in memory.

While you are editing code, you can skip the zip and load the project folder directly. In the Scripting workspace (section 3.2), create a new text, paste this, and press **Run Script**:

```python
import sys
path = r"C:\Users\monac\OneDrive\Desktop\FSAE-Autonomous-Onboarding-Project"
if path not in sys.path:
    sys.path.insert(0, path)
import fsae_env_generator
fsae_env_generator.register()
```

Then press **N** in the 3D view and open the **FSAE** tab. Do this only when the add-on is not already enabled in Preferences. After you change code, restart Blender and run that script again. Reloading a package that is already in memory is unreliable.

### 3.2 Scripting workspace and `run_generator.py`

Use this when you want one generation without the panel, or when you want a `.blend` file from the command line.

**Inside Blender**

1. Click the **Scripting** tab at the top of the window.
2. In the text editor (the large middle area), click **Open** and choose:

`C:\Users\monac\OneDrive\Desktop\FSAE-Autonomous-Onboarding-Project\run_generator.py`

3. Leave the file saved on disk. Do not paste it into an unsaved text block. The script uses its own file path to find `fsae_env_generator`.
4. Click **Run Script** (the play button in the text editor header).

With no extra arguments, this builds seed `1`, track width `3.5` m, cone spacing `4.0` m, track type `trackdrive`, profile `us_fsae_driverless_2025`, and density `1.0`. Switch back to the **Layout** tab and press **N** if you want to orbit the result. This run does not add the FSAE sidebar. The Info bar at the bottom of the window will not show the panel status line. The scene and the report text are still created.

**From PowerShell**

Open a terminal whose current directory is the project folder:

```powershell
cd "C:\Users\monac\OneDrive\Desktop\FSAE-Autonomous-Onboarding-Project"
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --python run_generator.py -- --seed 1
```

The `--` is required. Arguments before it belong to Blender. Arguments after it belong to this script.

Add `--background` if you do not want the Blender window:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --background --python run_generator.py -- --seed 1 --save "C:\Users\monac\OneDrive\Desktop\FSAE-Autonomous-Onboarding-Project\fsae_seed1.blend"
```

Then open `fsae_seed1.blend` in Blender with **File → Open**.

**Without Blender**, from the same folder:

```powershell
python run_generator.py --seed 1
```

This prints the validation report and the line `Blender is not available, so no scene was created.`

---

## 4. Running the generator

These steps use the **FSAE** sidebar from section 3.1. Press **N** in the 3D Viewport, then click the **FSAE** tab.

The status line under the buttons updates after each action. A good first run looks like:

`PASS  seed 1  117/124 cones`

The left number is blue cones. The right number is yellow cones. Those counts change when the seed, width, or spacing changes. A short straight has fewer cones than a long one, so the two sides are not required to match.

Blender also prints a line in the top bar, for example `FSAE environment PASS for seed 1.`

### Generate the first track

1. Leave the defaults:
   - Seed `1`
   - Track Width `3.5 m`
   - Cone Spacing `4 m`
   - Track Type **Trackdrive**
   - Rules Profile **U.S. Formula SAE Driverless**
   - Environment Density `1.0`
   - Trees, Tents, Spectators, and Barriers all checked
2. Click **Generate**.
3. In the 3D view, press **Numpad .** (period) or **View → Frame Selected** after selecting the `FSAE_Environment` collection in the Outliner. The track is tens of meters wide. The default camera view is too close to see all of it. Scroll the mouse wheel to zoom out, and hold the middle mouse button to orbit.

Track width on the panel is the distance between the **inner edges** of the cone bases, not the distance between cone centers.

### Set a random seed

The seed is a whole number, not a Blender random button.

1. Click the **Seed** field.
2. Type an integer, for example `7`.
3. Click **Generate**.

Seed `0` is allowed. Generate uses the number in the field at the moment you click. Changing the seed and clicking **Regenerate** does not use the new number. See below.

### Change track width

1. Set **Track Width**. The slider starts at `3.5 m`. The U.S. profile expects at least `3.0 m`. The panel allows smaller values so you can see a failed validation; a width under `3.0 m` still builds, and the report fails the width check.
2. Click **Generate**.

The scene unit system is switched to meters when you generate. The number next to Track Width is meters.

### Change cone spacing

1. Set **Cone Spacing**. The default is `4 m`. This is the gap along straights. Corners are tighter (about 0.65 times that gap once the corner radius is under 18 m). The smallest gap the generator will use is 2 m unless you asked for an even smaller nominal spacing.
2. Click **Generate**.

With **U.S. Formula SAE Driverless**, a spacing of 6 m is kept. With **Formula Student 2026**, a request above 5 m is reduced to 5 m, and the report includes a warning that says the profile caps spacing at 5.00 m. The Formula Student profile does not add a minimum track width. The report says so when that profile is selected.

### Generate a new environment

Click **Generate** any time you change the sidebar. Generate deletes the previous `FSAE_Environment` collection and builds a new one. Your other objects, including the default cube, stay.

**Track Type**

- **Trackdrive** — closed loop and a large-orange start gate. No extra lane.
- **Autocross** — the same kind of loop, plus a straight row of small orange cones beside the start, outside the right boundary.
- **Custom** — uses a curve object that you must name exactly `FSAE_Input_Centerline`. It needs at least 4 points. Generate reads that curve again. If the curve is missing, the status line says `Custom curve missing` and nothing is built.

To make a custom curve: **Add → Curve → Bezier** (or Circle), rename the object to `FSAE_Input_Centerline` in the Outliner, edit its points, set Track Type to Custom, and click Generate.

### Regenerate the same environment

**Regenerate** ignores the sidebar. It rebuilds the settings stored on the scene from the last successful Generate (`scene["fsae_config"]`).

1. Generate once, for example seed `1`.
2. Change the Seed field to `99` and do not click Generate.
3. Click **Regenerate**.

The scene comes back as seed `1`. The status line says `PASS  regenerated seed 1`. Clear does not erase that stored config, so Regenerate still works after Clear.

If you click Regenerate before any Generate, there is nothing stored. The operator warns `No stored environment yet. Using the current sidebar settings.` and builds those settings instead.

### Generate a different environment

1. Type a different **Seed**, for example `2`.
2. Click **Generate**, not Regenerate.

Same seed plus the same width, spacing, track type, profile, density, and checkboxes produces the same layout in this Blender version. A different seed produces a different layout. Changing width or spacing with the same seed also produces a different layout.

### Enable and disable tents, trees, and spectators

The panel has a checkbox for each:

- **Trees**
- **Tents**
- **Spectators**
- **Barriers**

Uncheck the ones you do not want, then click **Generate**.

**Environment Density** scales how many of those objects are placed. `1.0` is the normal amount. `0` places no trees, tents, spectators, or scattered props. Boundary cones, the track, lighting, and the camera are still created. `3.0` is the maximum on the slider.

The same four switches exist on the command line as `--no-trees`, `--no-tents`, `--no-spectators`, and `--no-barriers`, and density is `--density`:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --python run_generator.py -- --seed 1 --track-width 3.5 --cone-spacing 4 --density 0 --no-tents
```

`--density 0` already skips tents. `--no-tents` is how you skip tents while keeping trees and spectators at a density above zero.

Other command-line flags: `--track-type trackdrive|autocross|custom`, `--profile us_fsae_driverless_2025` or `--profile formula_student_2026`, `--report some\path\report.txt`, `--save some\path\scene.blend`.

### Clear the previous scene

Click **Clear**.

This deletes the `FSAE_Environment` collection, its objects, and the text block `FSAE_Validation_Report`. It puts back the world and camera that were active before generation. It keeps the sidebar values and the stored config, so **Regenerate** can build the last environment again.

It does not delete the default cube or objects you made yourself, unless you put them inside `FSAE_Environment`.

---

## 5. Expected output

After a successful Generate you should see:

- A dark closed asphalt ribbon lying on a grass ground, with the cone bases sitting on the ground (`z = 0`). Cone meshes are built with the base at `z = 0`, not buried under it.
- Small blue cones along one boundary and small yellow cones along the other. Blue is on the **left of the direction the car would drive**. Yellow is on the right. If you look at the track from the other direction, the colors will look swapped on screen. That is still correct.
- Two large orange cones at the start of the longest straight, one on each side, with two white bands. Small blue cones have one white band. Small yellow cones have one black band.
- A white start-line marking across the track at that gate.
- Trees, colored tents, simple spectator figures, and barriers around the outside of the asphalt when density is above 0 and the checkboxes are on. They should not sit on the racing surface.
- A text object, `FSAE_Rules_Label`, near the scene, naming the rules profile.
- A sun lamp and a camera aimed at the track. The 3D view does not automatically look through that camera. Press **Numpad 0** to see the camera view, and **Numpad 0** again to leave it. If you have no numpad, use **View → Cameras → Active Camera**.
- The status line on the panel showing `PASS`.

Open the **Outliner** (top right in the Layout workspace). Expand **Scene Collection**. You should see:

```text
FSAE_Environment
  Track
    Track_Surface          asphalt mesh
    Track_Centerline       curve
    Track_Boundaries       left and right curves
    Markings               start line and the rules label
  Cones
    Blue_Cones
    Yellow_Cones
    Orange_Cones           small orange cones (autocross lanes, and any extra orange cones)
    Large_Orange_Cones     the start/finish pair
  Environment
    Trees
    Tents
    Spectators
    Barriers
    Buildings
    Terrain                grass ground
    Props                  tables, cars, tires, flags, and similar objects
  Lighting                 sun
  Cameras                  FSAE_Camera
```

Object names look like `FSAE_blue_small_0001` and `FSAE_tree_0003`. Shared meshes are named `FSAE_MESH_blue_small`, `FSAE_MESH_yellow_small`, and so on. Materials are named `FSAE_MAT_cone_blue`, `FSAE_MAT_cone_yellow`, `FSAE_MAT_cone_orange`, `FSAE_MAT_cone_white`, `FSAE_MAT_cone_black`, `FSAE_MAT_asphalt`, `FSAE_MAT_grass`, and the same pattern for the other colors in `assets.py`.

In Solid shading, Blender paints objects with a random viewport color, so cones can look gray or pastel even when the material is correct. For the real colors, click the shading spheres at the top right of the 3D view and choose **Material Preview** (the second sphere) or **Rendered** (the third).

### Read the validation report

1. Open the **Scripting** workspace.
2. In the text editor header, open the text-block dropdown (it may say `run_generator.py` or `Text`).
3. Choose **FSAE_Validation_Report**.

The first lines look like this:

```text
FSAE Environment Validation Report
==================================
Seed: 1
Rules profile: us_fsae_driverless_2025
...
Track length: ...
Track width mean / min / max: 3.500 / 3.500 / 3.500 m
...
Cones
  left: ... cones, spacing avg/min/max ...
  right: ... cones, spacing avg/min/max ...
Collision violations: 0
...
Overall: PASS
```

Each check is marked `[PASS]` or `[FAIL]`. Overall PASS means every check passed. Warnings can appear above the checks without failing the run. A Formula Student spacing clamp is a warning of that kind.

The same text is printed in the system console when you use `run_generator.py`. On Windows, **Window → Toggle System Console** shows that console while the Blender window is open.

Scene properties used later by Regenerate:

- `fsae_config` — JSON of the settings that were generated
- `fsae_validation_passed` — true when the report passed

They are on the Scene. You do not need to edit them.

---

## 6. Troubleshooting

### Missing Python modules

**Symptom:** `ModuleNotFoundError: No module named 'fsae_env_generator'`.

**Cause:** Python looked in the wrong folder. This happens if `run_generator.py` was pasted into an unsaved Blender text block, so it has no file path, or if you started Blender from a different working directory and imported the package yourself.

**Fix:**

- Use **Text → Open** on the real `run_generator.py`, then Run Script.
- Or install the add-on zip from section 3.1.
- Or start the command from the project folder, as in section 3.2.

**Symptom:** `Blender is not available, so no scene was created.`

**Cause:** You ran `python run_generator.py` with system Python. That path is supported. It only prints the report.

**Fix:** Run the same script with `blender.exe --python`, or click Generate in the sidebar.

**Symptom:** `No module named 'bpy'` while running tests, or a suggestion to pip-install bpy.

**Cause:** Something imported `ui.py` or `blender_backend.py` outside Blender. The tests do not do that. `python -m unittest discover -s tests -v` should not import `bpy`.

**Fix:** Do not `pip install bpy`. Run scene creation through Blender. Run tests with the command in section 7.

### Blender Python errors

**Symptom:** Status line `Custom curve missing`, and the top bar says the custom track needs a curve named `FSAE_Input_Centerline`.

**Cause:** Track Type is Custom and that object is missing or has fewer than 4 points.

**Fix:** Add a curve, set its name to exactly `FSAE_Input_Centerline`, give it at least 4 control points, and click Generate again. Or switch Track Type back to Trackdrive.

**Symptom:** Status line `Error: ...` and the button reports an error.

**Cause:** The generator raised an exception. The message after `Error:` is the reason.

**Fix:** Open **Window → Toggle System Console** and read the traceback. Typical causes are a broken profile JSON in `fsae_env_generator/profiles/`, or a custom centerline that cannot be offset. Restore the JSON file from git if you edited it, or switch back to a procedural track type.

**Symptom:** `register_class(...): already registered`.

**Cause:** The add-on is enabled in Preferences and a script called `fsae_env_generator.register()` again.

**Fix:** Use only one of those. Disable the add-on, or stop running the register script.

### Missing materials

**Symptom:** Cones and the track look gray, or all one color.

**Cause:** The viewport is in Solid shading. Materials exist, but Solid mode does not show them. Generation creates every material itself. There are no external material files to forget.

**Fix:** Set the 3D view to **Material Preview** or **Rendered**. In the Material properties, a cone should use a material named `FSAE_MAT_cone_blue`, `FSAE_MAT_cone_yellow`, or `FSAE_MAT_cone_orange`, plus a stripe material. If those slots are empty, the object was not built by this generator. Click Generate again.

Tent cloth colors are applied on the object after it is linked into the collection. If you copy a tent mesh onto a new object by hand, that cloth color is not copied automatically.

### Cones appearing on the wrong side

**Cause:** Left and right follow the centerline direction, not the camera. Blue is left when you face along the loop. Standing on the other side of the track makes blue appear on your right.

**Fix:** Select the object `FSAE_Track_Centerline` and look at the curve's direction, or read the report checks `Left boundary cones are blue` and `Right boundary cones are yellow`. If those checks PASS, the placement matches the profile. A custom curve drawn in the opposite direction will put blue on the other side of the ribbon. Reverse the curve in Edit Mode (**Curve → Reverse**) and click Generate if you want the colors swapped.

The U.S. and Formula Student profiles in this project both use blue on the left and yellow on the right. There is no switch that swaps them.

### Cones overlapping

**Cause:** A finished generation rejects placements that would intersect, and the report's `Collision violations` count includes cone and prop overlaps. A PASS report with `Collision violations: 0` means the generator did not leave an overlap.

What usually looks like an overlap:

- Zoomed-out viewport, so neighboring cones merge into one blob. Zoom in.
- The orange autocross lane sitting near the yellow cones. That lane is offset outside the right boundary by the track width plus 2.5 m. It is a second row, not a double placement on the boundary.
- Corner spacing, which is intentionally tighter than the straight spacing.

**Fix:** Open `FSAE_Validation_Report`. If a collision check FAILs, click Generate again with the same settings. A second build of the same seed should match the first. If it still fails, the report detail line names the check. Raise cone spacing or track width and Generate again. Do not duplicate cones by hand and then expect Clear to understand them as generator output unless they live under `FSAE_Environment`.

### Incorrect track width

**Cause:** Width is the gap between the inner faces of the cone bases. Measuring center to center adds about one cone base (0.228 m for a small cone) and looks too wide. Measuring the dark asphalt by eye is also easy to get wrong.

The U.S. profile's minimum is 3.0 m. Asking for 2.2 m still builds the track, and the check `Track width meets the selected profile` FAILs. That is the report doing its job. The Formula Student profile does not define a minimum width. Its width check explains that, and a narrow Formula Student track is not failed for a rule this profile does not contain.

**Fix:**

1. Confirm the scene is in meters: **Properties editor → Scene → Units**. System should be Metric, Length should be Meters, Unit Scale `1.0`. Generate sets this.
2. Read `Track width mean / min / max` in the report. For a normal request of 3.5 m those three numbers are 3.500.
3. Set Track Width and click **Generate**. Regenerate will rebuild the old width if you only changed the slider.

### Objects appearing below the ground

**Cause:** Generated meshes sit on `z = 0`. The grass terrain is the ground. Objects look buried when the view is in Solid mode with a large clip distance, when you are looking through the camera from under the ground, or when an object was moved by hand.

**Fix:**

- Select a cone and look at its **Location** in the sidebar Item tab (press **N**, then Item). Z should be `0`.
- Press **Numpad 7** for the top view, or **View → Viewpoint → Top**.
- Frame the scene with **Numpad .** after selecting `FSAE_Environment`.
- Click Generate again if you moved objects. Generate replaces the whole hierarchy.

The generator does not build a second ground under zero, and it does not use the default cube as the floor.

### The generator creating duplicate objects

**Cause:** Generate is supposed to delete `FSAE_Environment` before it creates a new one. Duplicates show up when a previous collection was renamed, for example `FSAE_Environment.001`, because Clear and Generate only remove the exact name `FSAE_Environment`. That rename happens if something duplicated the collection, or if a collection with that name already existed and Blender made the new one `.001` during a failed partial run.

**Fix:**

1. In the Outliner, delete every collection whose name starts with `FSAE_Environment`, including `.001` names. Right-click the collection → **Delete Hierarchy**.
2. Click **Generate** once.
3. Click **Generate** again. The cone count in the status line should stay the same. It should not double.

`--self-check` checks this. It generates twice and fails if the blue-cone count changes.

Copying the collection yourself, or appending the scene into the same file, is a second copy the generator will not treat as its current output.

### Random seeds producing inconsistent output

**Cause:** Regenerate does not read the Seed field. It uses the stored config. Or a setting other than the seed changed: width, spacing, track type, profile, density, a checkbox, or the custom curve. Or you compared two Blender versions. The seed is stable inside one Python version. This project does not promise bit-identical coordinates between Blender 3.6 and Blender 4.5, because Python's `random.Random` is only guaranteed inside one runtime.

**Fix:**

1. Set the seed.
2. Set every other field you care about.
3. Click **Generate**.
4. To repeat it, click **Regenerate** without expecting sidebar edits to apply. Or set the same numbers again and click **Generate**.
5. Compare runs in the same Blender version.

A reliable comparison that does not need the 3D view:

```powershell
python run_generator.py --seed 1 --report reports\a.txt
python run_generator.py --seed 1 --report reports\b.txt
python run_generator.py --seed 2 --report reports\c.txt
```

`a.txt` and `b.txt` should match. `c.txt` should not. Each command also writes a `.json` file next to the text file.

---

## 7. Testing

Run these from:

`C:\Users\monac\OneDrive\Desktop\FSAE-Autonomous-Onboarding-Project`

### Automated tests

```powershell
python -m unittest discover -s tests -v
```

You want `Ran 22 tests` and `OK`. No Blender window opens. The tests cover geometry, a closed rounded rectangle, procedural tracks against the U.S. profile, cone size and stripe materials, left/right colors, Formula Student spacing capped at 5 m, U.S. spacing left at 6 m when you ask for 6 m, a track that is too narrow failing validation, autocross lanes, density 0, and two builds with one seed matching.

If Python is not found, install Python 3.11 and enable **Add python.exe to PATH**, then open a new terminal.

### Verify cone spacing

Generate, then open `FSAE_Validation_Report`. The cone lines give average, minimum, and maximum spacing for the left and right boundaries. On straights the maximum should be your Cone Spacing (or 5 m if Formula Student reduced it). The minimum is lower because corners are tighter. The checks under category spacing should read `[PASS]`.

From the terminal, spacing is in the printed report:

```powershell
python run_generator.py --seed 1 --cone-spacing 4
```

### Verify track width

In the same report, read:

`Track width mean / min / max`

For Track Width `3.5` those values are `3.500 / 3.500 / 3.500 m`. The check `Track width matches the request` should PASS.

To see a failure on purpose, set Track Width to `2.2` with the U.S. profile and click Generate. The scene is still created. The status line says `FAIL`, and `Track width meets the selected profile` fails because 2.2 m is under the profile minimum of 3.0 m. Set the width back to `3.5` and Generate again.

### Verify cone colors

1. Switch the 3D view to **Material Preview**.
2. Blue cones are in `Cones / Blue_Cones` and use `FSAE_MAT_cone_blue` plus a white stripe.
3. Yellow cones are in `Cones / Yellow_Cones` and use `FSAE_MAT_cone_yellow` plus a black stripe.
4. Large orange cones are in `Cones / Large_Orange_Cones`, orange with two white bands.

The report checks include `Left boundary cones are blue` and `Right boundary cones are yellow`. Both should PASS.

The unit test `test_cone_meshes_have_the_specified_size_and_stripes` checks the mesh dimensions (small cones 0.228 m by 0.228 m by 0.325 m, large orange cones 0.285 m by 0.285 m by 0.505 m) and that the stripe materials are on those meshes.

### Verify that identical seeds match

In Blender:

1. Generate with seed `1`.
2. Note the status line cone counts.
3. Change the seed to `5` and click **Generate**. The layout should change.
4. Set the seed back to `1`, set the other fields back to the same values, and click **Generate**. The cone counts should match step 2.
5. Click **Regenerate**. The status line should say regenerated seed `1`, and the scene should match.

From PowerShell, the two reports for seed 1 in the troubleshooting section should be identical, and seed 2 should differ.

`--self-check` also generates twice inside Blender and fails if the second pass adds objects:

```powershell
& "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --background --python run_generator.py -- --self-check
```

The last line should be `SELF_CHECK_OK`.

### Generate a validation report

Any Generate writes the text block `FSAE_Validation_Report` inside the open `.blend` file. Open it from the Scripting workspace text dropdown, as in section 5.

To write files you can keep:

```powershell
python run_generator.py --seed 1 --track-width 3.5 --cone-spacing 4 --profile us_fsae_driverless_2025 --report reports\seed1.txt
```

That creates `reports\seed1.txt` and `reports\seed1.json`. The folder is created for you. `reports/` is listed in `.gitignore`.

The same `--report` flag works at the end of a Blender command, after `--`.

---

## 8. Final quick start

1. Install Blender 4.5 (3.6 or newer can load the add-on; 4.5.4 is the version this project was run in). You do not pip-install anything.
2. In Cursor, **File → Open Folder** and choose `C:\Users\monac\OneDrive\Desktop\FSAE-Autonomous-Onboarding-Project`.
3. In PowerShell, from that folder, zip the add-on:

```powershell
Compress-Archive -Path ".\fsae_env_generator" -DestinationPath ".\fsae_env_generator.zip" -Force
```

4. Open Blender. **Edit → Preferences → Add-ons → down-arrow → Install from Disk**, choose `fsae_env_generator.zip`, and enable **FSAE Autonomous Environment Generator**.
5. In the 3D view, press **N** and click the **FSAE** tab.
6. Leave Seed `1`, Track Width `3.5 m`, Cone Spacing `4 m`, Track Type Trackdrive, and the environment checkboxes on. Click **Generate**.
7. Zoom out (scroll wheel) and switch the viewport shading to **Material Preview**. You should see the asphalt loop, blue cones on the left of travel, yellow cones on the right, and large orange cones at the start.
8. Open the **Scripting** workspace and select the text block **FSAE_Validation_Report**. The last line should be `Overall: PASS`.
9. Change Seed to `2` and click **Generate** for a different layout. Click **Regenerate** to rebuild seed `2` even if you then edit the sidebar. Click **Clear** to remove the generated collection without forgetting that seed.
