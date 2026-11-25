Project: Procedural FSAE Autonomous Racing Environment Generator
1. Project Overview

Develop an automated procedural generation system in Blender using Python.

The system must generate realistic Formula SAE autonomous racing environments using a random seed and configurable parameters.

Generated environments should include:

A procedurally generated race track.
Track boundary cones.
Correctly colored and sized FSAE cones.
Track surface and surrounding terrain.
Random environmental objects, including tents, trees, barriers, spectators, and other paddock elements.
Optional lighting and environmental variations.

The primary objective is to generate diverse, reproducible simulation environments for testing autonomous racing perception and navigation systems.

The project must use a modular architecture, allowing individual components to be generated, modified, and tested independently.

2. Input Parameters

The generator must accept the following inputs.

2.1 Required Parameters
Random seed: Integer controlling all procedural randomness.
Track width: Distance between the left and right track boundaries, measured between the inner edges of the cone bases.
Track centerline: Ordered sequence of 2D or 3D coordinates describing the track path.
Cone spacing: Desired longitudinal distance between consecutive cones along each boundary.
2.2 Optional Parameters
Track length: Target track centerline length.
Track type: Autocross, Trackdrive, or custom.
Track curvature: Minimum and maximum curvature.
Number of corners.
Number of straights.
Minimum straight length.
Maximum straight length.
Terrain dimensions.
Number of trees.
Number of tents.
Number of spectators.
Number of barriers.
Environmental density.
Lighting conditions.
Weather conditions.
Surface appearance.
Cone placement variation.
Background object density.
2.3 Default FSAE Configuration

Use the following defaults as a starting profile based on the 2025 U.S. Formula SAE Driverless Supplement:

Minimum track width: 3.0 m.
Minimum turning diameter: 9.0 m.
Maximum straight length: 80 m.
Target lap length: 200–500 m.
Left boundary cone: Small blue.
Right boundary cone: Small yellow.
Small cone dimensions: 0.228 × 0.228 × 0.325 m.
Entry/exit cones: Small orange.
Start/finish cones: Large orange.

Allow these values to be changed through a configuration file.

Do not assume these values apply to every FSAE or Formula Student competition. Label the selected rule profile and its revision in the generated scene.

3. Track Generation
3.1 Centerline Generation

The generator must be capable of creating a closed-loop racing circuit.

When no centerline is supplied, generate one procedurally.

The track generation algorithm should:

Generate a sequence of connected control points.
Produce smooth transitions between control points.
Support straights, gradual turns, hairpins, chicanes, and S-curves.
Avoid sharp discontinuities in track direction.
Avoid self-intersections unless explicitly enabled.
Maintain a closed-loop connection between the starting and ending points.
Produce a continuous and smooth centerline.

Use a spline-based approach, such as a Bezier or Catmull-Rom spline.

The generated centerline should be sampled at sufficiently small intervals to calculate accurate boundary positions.

3.2 Track Geometry

Generate the track surface using the centerline and specified track width.

Calculate the left and right boundaries using the local tangent and perpendicular normal vectors.

For every sampled centerline position:

Calculate the local direction of travel.
Calculate the perpendicular normal.
Offset the centerline by half the specified track width.
Generate left and right boundary curves.
Connect the resulting curves to create the track surface.

Requirements:

Maintain the specified track width within a configurable tolerance.
Prevent track surface discontinuities.
Avoid self-intersecting geometry.
Support variable curvature.
Generate a continuous surface.
Use real-world Blender units in meters.

The track should be represented by a mesh with appropriate materials.

4. Cone Generation
4.1 Cone Models

Create reusable Blender cone meshes.

Small cones:

Height: 0.325 m.
Base width: 0.228 m.
Blue or yellow depending on boundary.
Optional white or black stripe materials.

Large cones:

Height: 0.505 m.
Base width: 0.285 m.
Orange body.
Two white stripes.

Small orange cones:

Same dimensions as other small cones.
Used for entry and exit lanes.

Use procedural materials to represent the correct cone colors and stripes.

4.2 Boundary Cone Placement

Generate cones along both track boundaries.

Left boundary:

Blue cones.
Small cone dimensions.
Single white stripe.

Right boundary:

Yellow cones.
Small cone dimensions.
Single black stripe.

Cone placement must use distance measured along the boundary curve rather than simply using the number of centerline samples.

Requirements:

Place cones on both sides of the track.
Maintain consistent spacing along straight sections.
Support smaller spacing in corners.
Maintain the configured minimum and maximum spacing tolerances.
Ensure every boundary segment has adequate cone coverage.
Keep cones upright and aligned with the ground.
Avoid cone placement inside the drivable track surface.
Avoid cones overlapping other cones.
Prevent cones from intersecting barriers or other generated objects.

The cone spacing should be configurable.

For a Formula Student 2026 profile, enforce a maximum 5 m spacing, with tighter spacing in corners.

For the U.S. Formula SAE Driverless profile, use configurable spacing rather than incorrectly treating the Formula Student 5 m rule as a universal requirement.

4.3 Cone Collision Prevention

Implement a collision prevention system.

Before placing a cone:

Calculate its proposed world position.
Check the distance to previously placed cones.
Check for overlap with nearby track objects.
Check that the cone is on the intended side of the boundary.
Reject or adjust the position if it violates collision constraints.

Use a spatial hash, grid, or another efficient neighbor-search approach rather than comparing every cone against every other cone.

4.4 Special Track Markings

Support the generation of:

Start line.
Finish line.
Entry lanes.
Exit lanes.
Timing gates.
Large orange start/finish cones.
Optional track limit markings.

Organize these elements separately from ordinary boundary cones.

5. Environmental Generation

Generate randomized surroundings to create more realistic autonomous racing environments.

All environmental randomness must be controlled by the input seed.

5.1 Tents

Generate paddock and event tents around the track.

Features:

Multiple tent sizes.
Different tent colors.
Randomized orientation.
Configurable quantity.
Placement outside the drivable track area.
Optional tables and equipment.
5.2 Trees

Generate trees around the terrain.

Features:

Different tree heights.
Randomized trunk sizes.
Different foliage shapes.
Randomized rotation.
Configurable density.
Prevent trees from overlapping the track.
5.3 Spectators and People

Generate simple low-poly human models or reusable spectator assets.

Features:

Different body colors.
Different poses.
Randomized positions.
Randomized orientation.
Groups of spectators.
Placement in designated spectator areas.

Avoid placing people on the driving surface or in restricted areas.

5.4 Additional Environmental Objects

Optional generated objects include:

Safety barriers.
Tire walls.
Paddock equipment.
Flags.
Traffic cones outside the racing boundaries.
Event signage.
Buildings.
Parking areas.
Marshall stations.

All objects should be positioned using predefined placement zones.

6. Random Seed and Reproducibility

The random seed must control every randomized operation.

Requirements:

Identical inputs and identical seeds must produce identical environments.
Changing the seed must produce a different environment.
All random operations must use a centralized random number generator.
Do not use uncontrolled random calls throughout the code.
Avoid dependence on object creation order where possible.
Ensure generation is deterministic across repeated executions in the same supported Blender/Python environment.

The random seed should be stored as scene metadata.

Include a function that regenerates the complete environment using the stored seed.

7. Blender Organization

All generated objects must be organized into clearly named collections.

Recommended hierarchy:

FSAE_Environment

Track
Track_Surface
Track_Centerline
Track_Boundaries
Cones
Blue_Cones
Yellow_Cones
Orange_Cones
Large_Orange_Cones
Environment
Trees
Tents
Spectators
Barriers
Buildings
Lighting
Cameras

Use linked mesh data or object instancing where appropriate to reduce memory consumption.

Do not create unnecessary unique meshes for identical cones or environmental assets.

8. Configuration and User Interface

Create a simple Blender interface using a Python panel or operator.

The user should be able to:

Enter a random seed.
Specify track width.
Specify cone spacing.
Choose a track type.
Choose a competition rules profile.
Set environmental object density.
Enable or disable individual environmental elements.
Generate a new environment.
Regenerate using the same seed.
Clear the generated environment.

Provide sensible default values.

9. Validation System

The generator must automatically validate its output.

Track Validation
Track is continuous.
Track is closed when closed-loop mode is selected.
Track has no unintended self-intersections.
Track width meets the selected profile.
Minimum turning diameter is respected.
Straight sections respect configured maximum lengths.
Track length is within the selected target range.
Cone Validation
Every track segment has cones on both boundaries.
Left boundary cones are blue.
Right boundary cones are yellow.
Cone dimensions are correct.
Cone spacing is within the configured tolerance.
Cones do not overlap.
Cones are located on the correct boundary.
Special orange cones are correctly identified.
Environment Validation
Environmental objects do not obstruct the track.
Objects are within the designated terrain boundaries.
Spectators are outside restricted areas.
Trees and tents do not intersect the drivable surface.
Reproducibility Validation
Generate an environment with a specific seed.
Generate it again with identical inputs.
Compare the resulting geometry and object positions.
Confirm that the output is identical within a defined numerical tolerance.

Generate a validation report containing:

Track length.
Track width measurements.
Number of cones per boundary.
Average cone spacing.
Minimum and maximum cone spacing.
Number of collision violations.
Selected random seed.
Selected rules profile.
Validation pass/fail status.
10. Performance Requirements

The generator should:

Generate a complete environment within a reasonable time.
Reuse meshes and materials.
Avoid unnecessarily high polygon counts.
Support increasing environmental complexity.
Use efficient collision checking.
Keep the code modular and maintainable.
11. Acceptance Criteria

The project is complete when:

A track can be generated from a supplied centerline.
A track can also be generated procedurally without a supplied centerline.
Track width is maintained within the selected tolerance.
Blue cones appear on the left boundary.
Yellow cones appear on the right boundary.
Special orange cones can be generated.
Cone spacing respects the selected configuration.
Cones do not overlap.
The same seed produces identical geometry and object positions.
Different seeds produce different environments.
Tents, trees, and spectators can be generated independently.
Every generated object is organized into the correct Blender collection.
The generator produces a validation report.
The system can be run again without accumulating duplicate objects.
The project includes setup and execution documentation.
12. Development Priorities

Implement features in this order:

Priority 1:

Centerline generation.
Track surface generation.
Boundary generation.
Blue and yellow cone placement.
Random seed reproducibility.

Priority 2:

Cone collision detection.
Special orange cones.
Track validation.
Blender collection organization.

Priority 3:

Tents.
Trees.
Spectators.
Barriers and other environmental objects.

Priority 4:

Blender user interface.
Configuration profiles.
Validation report.
Performance improvements.
Documentation.

Focus on delivering a functional core generator before implementing decorative environmental features.