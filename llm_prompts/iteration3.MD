Refactor FSAE Environment Generator — 2026 Formula SAE Michigan Driverless Tracks & Realism Upgrade
Project Objective

Refactor the existing fsae_env_generator Blender add-on, including its procedural geometry generation system and UI sidebar, to support the 2026 Formula SAE Michigan (FSAE Electric) Driverless dynamic events.

The goal is to create a realistic, configurable, deterministic procedural environment generator capable of producing competition-style autonomous vehicle test environments.

The generator must support:

Driverless Acceleration
Driverless Skidpad
Driverless Autocross
EBS Brake Test (supplementary inspection/testing environment)

In addition to implementing the event-specific track generators, improve the visual quality, geometric realism, material appearance, and overall organization of generated environments.

Important: Inspect the existing add-on architecture before modifying it. Preserve existing functionality wherever possible, reuse existing components when appropriate, and avoid unnecessarily rewriting working systems.

Use the official 2026 Formula SAE Rules and Driverless Supplement as the source of truth for competition-specific requirements. Do not invent official dimensions, cone conventions, or event procedures. Any parameter not explicitly established by the rules should be identified as a configurable simulation assumption.

1. UI Sidebar & Track Configuration

Update the existing FSAE Environment sidebar panel to support event-specific configuration.

1.1 Track Type Selection

Add a dropdown with the following options:

Driverless Acceleration
Driverless Skidpad
Driverless Autocross (Default)
EBS Brake Test

Changing the selected event must dynamically update the available parameters, defaults, descriptions, and generation behavior.

1.2 Global Parameters

Expose the following parameters:

Parameter	Description
Random Seed	Integer controlling deterministic procedural generation
Track Width	Configurable course width
Straight Cone Spacing	Distance between cones along straight sections
Corner Cone Spacing	Distance between cones in curved sections
Cone Jitter	Optional positional variation for simulation difficulty
Terrain Size	Size of the surrounding environment
Environment Density	Density of environmental objects

Use sensible event-specific defaults rather than applying one configuration to every track.

Suggested starting values for simulation:

Track width: 3.0–5.0 m, configurable.
Straight cone spacing: approximately 5.0 m.
Corner cone spacing: approximately 2.0–3.0 m.
Cone jitter: 0.0 m by default.

These are simulation defaults, not automatically official competition specifications.

1.3 Event-Specific Parameters
Acceleration
Course length: 75 m.
Starting area configuration.
Finish area configuration.
Stopping zone length.
Stopping zone width.
Skidpad
Circle geometry.
Inner and outer radii.
Track width.
Crossover configuration.
Entry and exit geometry.
Stopping area configuration.

Use the official 2026 skidpad dimensions and layout where specified.

Autocross
Target centerline length: 200–500 m.
Minimum and maximum track width.
Minimum turn radius.
Maximum turn radius.
Straight section length range.
Hairpin frequency.
Chicane frequency.
Slalom frequency.
S-curve frequency.
Track-width variation.
Course complexity.
Stopping zone length.

The generated centerline must have an actual arc length within the selected 200–500 m range.

EBS Brake Test
Approach lane length.
Acceleration zone length.
Brake-trigger gate position.
Emergency stopping area length.
Stopping area width.

Clearly identify supplementary simulation assumptions separately from official test requirements.

1.4 Environment Toggles

Provide independent checkboxes and density controls for:

Trees
Tents
Spectators
Vans
Trailers
Timing structures
Barriers
Background vehicles
Additional paddock equipment

Environmental objects must never interfere with the generated driving course, cone placement, or stopping areas.

2. Rule-Based Procedural Track Generation

Implement separate, modular geometry builders for each event.

Suggested architecture:

generate_acceleration_track()
generate_skidpad_track()
generate_autocross_track()
generate_ebs_track()

Each generator should use a shared track-generation framework for cone placement, materials, boundaries, terrain, and metadata.

2.1 Cone Conventions

Implement competition-style cone materials and geometry.

Required cone categories:

Blue cones: left track boundary.
Yellow cones: right track boundary.
Orange cones: entry/exit and other designated gate markers, according to the applicable rules.
Large orange cones: designated start, finish, or timing markers where required.

Use the official 2026 cone specifications for dimensions, colors, and markings.

Important implementation requirements:

Cone placement must follow the actual generated track boundaries.
Cone spacing must adapt to local curvature.
Cones must be oriented consistently with their intended boundary.
Cones must not overlap or intersect.
Boundary cone positions must remain independent of decorative objects.
Do not use blue or yellow spline meshes as substitutes for cones.

The cones must be the primary visible representation of the track boundaries.

2.2 Driverless Acceleration

Generate a straight 75 m timed course.

Requirements:

Straight, level driving surface.
Blue cones along the left boundary.
Yellow cones along the right boundary.
Correctly configured starting and finishing gates.
Timing-line geometry.
Designated stopping zone beyond the finish.
Appropriate orange gate markers where required.

The stopping area must be geometrically separate from the timed section.

Ensure the generated course supports:

Straight-line vehicle motion.
Cone detection.
Velocity profiling.
Acceleration control.
Controlled stopping.
2.3 Driverless Skidpad

Generate a competition-style figure-eight skidpad.

Requirements:

Two circular driving paths.
One left-hand circle.
One right-hand circle.
Shared central crossover.
Inner and outer cone boundaries.
Entry and exit configuration.
Timing-line placement.
Appropriate stopping area.

Use official 2026 skidpad geometry and dimensions.

IMPORTANT GEOMETRY REQUIREMENT:

Do not approximate the skidpad using two unrelated circles or simply overlapping circular splines.

Construct the layout from a mathematically consistent figure-eight geometry with a defined crossover and correct driving direction.

Cone colors must be determined from the direction of travel and the local left/right boundary of the drivable path.

Validate:

Circle dimensions.
Track width.
Crossover connectivity.
Boundary continuity.
Cone placement.
Start and finish configuration.

The resulting geometry must represent a physically drivable figure-eight.

2.4 Driverless Autocross — Highest Priority

Generate a single-lap technical handling course.

Target centerline length:

Minimum: 200 m.
Maximum: 500 m.

The course should be procedurally assembled from configurable track elements:

Long straights.
Short straights.
Constant-radius corners.
Increasing-radius corners.
Decreasing-radius corners.
Hairpins.
Slaloms.
Chicanes.
S-curves.
Alternating left/right turns.
Variable-width sections.

The random seed must control:

Track element selection.
Element ordering.
Turn direction.
Turn radius.
Straight length.
Track width.
Cone spacing.
Overall course complexity.
Geometry Requirements

Generate a continuous, smooth, physically drivable centerline.

Avoid:

Self-intersections.
Sharp, physically impossible curvature changes.
Disconnected track segments.
Sudden width discontinuities.
Overlapping boundaries.
Cones placed inside the drivable region.

The generator must construct left and right boundaries using the local normal of the centerline.

For a centerline position and tangent, calculate the local normal and offset each boundary by half the track width.

Use curvature-aware cone spacing, with denser cone placement in tighter turns.

Length Validation

Calculate the actual centerline arc length after all geometry transformations.

If the generated length falls outside the requested range, regenerate or adjust the geometry.

Do not rely on bounding-box dimensions or approximate segment lengths.

The final course must include:

Start gate.
Finish gate.
Continuous left/right boundaries.
Cone-defined driving corridor.
Designated stopping area after the finish.

Generate multiple substantially different layouts from different seeds.

2.5 EBS Brake Test

Generate a straight autonomous braking test environment.

Include:

Straight approach lane.
Acceleration section.
Clearly marked brake-trigger gate.
Emergency braking region.
Cone-defined stopping corridor.
Final stopping area.

The geometry should support simulation of:

Brake-trigger activation.
Emergency braking.
Vehicle deceleration.
Stopping distance.
Final vehicle position.

Treat this as a supplementary testing environment, not a fourth scored dynamic competition event.

3. Ground Truth & Autonomous Simulation Data

This is an important addition: the generator must produce structured ground-truth data alongside the Blender geometry.

The generated track should not just look correct. It must also be usable for autonomous vehicle simulation, perception, localization, and path planning.

For every generated environment, generate and retain:

Track Geometry
Centerline coordinates.
Left boundary coordinates.
Right boundary coordinates.
Track width profile.
Centerline curvature.
Centerline tangent and normal.
Total track length.
Cone Data

For every cone:

Unique ID.
World-space XYZ position.
Cone category/color.
Boundary classification (left/right/gate).
Cone dimensions.
Orientation.
Optional visibility/occlusion metadata.
Event Metadata
Event type.
Random seed.
Generation parameters.
Start line coordinates.
Finish line coordinates.
Stopping zone boundaries.
Course direction.
Official dimensions versus simulation assumptions.
Export Support

Provide an option to export ground-truth data as JSON or CSV.

Organize the exported data consistently so it can be consumed by external autonomous driving software.

Keep Blender object names and metadata organized using collections, for example:

FSAE_Track
FSAE_Left_Cones
FSAE_Right_Cones
FSAE_Gate_Cones
FSAE_Start_Finish
FSAE_Stopping_Zone
FSAE_Terrain
FSAE_Environment

Do not require the autonomous simulation system to infer ground truth from rendered geometry.

4. Visual & Geometric Realism Improvements
4.1 Remove Artificial Track Guide Splines

Completely remove the blue and yellow boundary lines/tubes currently running beneath the cones.

The cones must define the visible track boundaries.

Keep only subtle, weathered asphalt markings where appropriate.

Examples:

Faded white dashed markings.
Old parking-space lines.
Subtle skidpad surface markings.
Faded directional markings.
Weathered tire marks.

These markings must look painted onto the asphalt rather than floating above it.

Implement them using:

Procedural material textures.
Shader-based masks.
Decals where appropriate.
Procedural noise and wear.

Do not add artificial markings that could be mistaken for official track boundaries.

4.2 Asphalt and Terrain Blending

Replace the existing sharp rectangular asphalt slab and flat green terrain box.

Create a larger continuous environment mesh.

The ground should transition naturally through:

Asphalt.
Gravel or dirt shoulder.
Grass.
Gently rolling terrain.

Use:

Vertex colors.
Procedural distance masks.
Noise-based material blending.
Terrain displacement.
Subtle elevation variation.

Avoid visible rectangular slab edges, floating terrain, and abrupt material transitions.

Maintain a sufficiently flat and predictable driving surface inside the competition course.

4.3 Cone Realism

Improve cone geometry and materials.

Requirements:

Proper cone proportions.
Slightly beveled edges.
Smooth shading.
Correct color assignments.
Realistic orange, blue, and yellow materials.
Correct double-striped markings where applicable.
Proper ground contact.

Do not make cones excessively glossy or cartoon-like.

4.4 Environmental Object Improvements

Upgrade existing props.

Vans and Trailers

Add:

Windshields.
Side windows.
Wheels.
Wheel arches.
Headlights.
Side trim.
Doors.
Realistic proportions.
Tents

Add:

Slender support legs.
Peaked fabric roofs.
Fabric materials.
Structural supports.
Trees

Add:

Multiple tree variations.
Different heights and canopy sizes.
Organic foliage shapes.
Natural clustering.
Randomized rotation and scale.
Barriers

Add:

Realistic barrier dimensions.
Rounded/beveled edges.
Appropriate materials.
Consistent placement outside the driving corridor.

All environmental assets should have realistic proportions and should not obstruct the track.

4.5 Mesh Quality and Shading

Improve generated meshes using:

Bevel modifiers.
Smooth shading.
Weighted normal modifiers where appropriate.
Clean topology.
Consistent normals.
Proper material assignment.

Do not blindly apply modifiers to every object. Use appropriate settings for the object type.

Ensure generated objects do not contain unnecessary geometry or excessive polygon counts.

5. Procedural Generation Reliability

The generator must be deterministic.

For the same:

Event type.
Random seed.
Parameter configuration.

The generated geometry and ground-truth data should be identical.

Use an isolated random-number generator rather than relying on Blender's global random state.

Implement geometry validation before finalizing the environment.

Validation should check:

Valid centerline.
Valid track length.
Continuous boundaries.
Correct boundary ordering.
No unintended self-intersections.
No overlapping cones.
No cones inside the drivable corridor.
Correct event-specific geometry.
Correct materials.
Correct collection organization.
Valid stopping-zone placement.

If generation fails validation, provide a meaningful error message and attempt a controlled regeneration where appropriate.

Avoid silently generating invalid tracks.

6. Performance and Code Architecture

Keep the add-on modular and maintainable.

Requirements:

Separate event-specific generators from shared geometry utilities.
Reuse cone-generation and material-generation functions.
Avoid duplicating geometry-generation logic.
Avoid unnecessary Blender mesh creation and deletion.
Use efficient mesh construction for large cone collections.
Use instancing or linked mesh data where appropriate.
Preserve existing add-on registration and unregistration behavior.
Ensure the UI remains responsive during generation.
Cleanly remove or replace previously generated track collections when regenerating.

Do not introduce unnecessary dependencies.

Maintain compatibility with the Blender version currently targeted by the existing add-on.

7. Testing and Validation

Rebuild and package the complete add-on as fsae_env_generator.zip.

Before packaging, perform a complete validation pass.

Event Generation Tests

Test all four event types:

Driverless Acceleration.
Driverless Skidpad.
Driverless Autocross.
EBS Brake Test.
Autocross Tests

Generate multiple layouts using different random seeds.

Verify:

Centerline length is always between 200 and 500 m.
Geometry is continuous.
Track boundaries are valid.
No unintended self-intersections occur.
Cones are correctly classified.
Cone spacing adapts to curvature.
Start and finish gates exist.
Stopping area is correctly positioned.
Skidpad Tests

Verify:

Correct figure-eight configuration.
Correct circle dimensions.
Correct crossover geometry.
Correct boundary placement.
Correct cone colors.
Continuous driving path.
Acceleration Tests

Verify:

Exactly 75 m of timed course.
Correct straight-line geometry.
Correct boundary cones.
Correct start and finish positions.
Valid stopping zone.
EBS Tests

Verify:

Approach lane.
Brake-trigger gate.
Emergency stopping corridor.
Valid stopping area.
General Tests

Verify:

Deterministic seed behavior.
Correct materials.
No floating cones.
No duplicate object generation.
Correct collection organization.
Successful JSON/CSV export.
Successful add-on registration.
Successful add-on unregistration.

Run the tests inside Blender where possible. Do not claim that tests passed if they were not actually executed.

8. Final Deliverables

Provide:

Updated fsae_env_generator source code.
Updated Blender sidebar UI.
All four event-specific procedural generators.
Improved terrain, asphalt, cones, and environment assets.
Ground-truth JSON/CSV export functionality.
Automated validation and test scripts.
Rebuilt fsae_env_generator.zip.
A concise changelog describing the modifications.
Installation and usage instructions.
Final Acceptance Criteria

The project is complete only when:

All four event generators work.
Autocross produces valid 200–500 m courses.
Acceleration produces a 75 m timed course.
Skidpad produces valid figure-eight geometry.
EBS produces a valid braking test environment.
Cone boundaries are visually represented by cones rather than colored guide tubes.
Ground-truth data can be exported.
Different seeds produce different valid environments.
Identical seeds and parameters reproduce identical environments.
The add-on installs and runs successfully in Blender.
The final ZIP package contains the complete working add-on.

Implementation priority: First ensure rule-accurate track geometry and reliable ground-truth generation. Then implement UI improvements, visual realism, environmental props, and final packaging.

Do not sacrifice geometric accuracy or autonomous simulation usability for visual appearance.