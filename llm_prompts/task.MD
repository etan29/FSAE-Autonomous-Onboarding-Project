You are an experienced Python developer specializing in Blender procedural generation, computational geometry, and autonomous vehicle simulation.

I have provided a detailed feature_specification.MD for an FSAE Autonomous Racing Environment Generator.

Your task is to implement the project according to the specification.

IMPORTANT DEVELOPMENT INSTRUCTIONS:

First analyze the entire specification.
Convert it into a clear implementation plan.
Identify dependencies between components.
Create a modular Python project structure.
Implement the core functionality before decorative features.
Use Blender's Python API (bpy) for scene creation and manipulation.
Use a centralized seeded random number generator for reproducibility.
Use meters as the primary unit of measurement.
Follow the selected FSAE rules profile.
Do not silently invent competition requirements.

DEVELOPMENT APPROACH:

Use spec-driven development.

Before implementing each major feature:

Identify its requirements.
Define its inputs and outputs.
Define how it will be tested.
Implement the feature.
Run available tests.
Verify that it satisfies its acceptance criteria.

IMPLEMENTATION ORDER:

Phase 1: Project foundation

Create the project structure.
Implement configuration management.
Implement random seed management.
Set up Blender scene organization.

Phase 2: Track generation

Generate or accept a track centerline.
Smooth the centerline.
Generate track boundaries.
Create the track surface.
Validate track width and geometry.

Phase 3: Cone generation

Create reusable cone meshes.
Create blue, yellow, and orange cone materials.
Generate cones along both boundaries.
Implement distance-based spacing.
Implement collision prevention.
Organize cones into separate collections.

Phase 4: Environment generation

Generate trees.
Generate tents.
Generate spectators.
Generate optional barriers and other event objects.
Ensure deterministic placement.

Phase 5: Validation

Implement automated geometry checks.
Implement cone spacing checks.
Implement collision checks.
Implement seed reproducibility tests.
Produce a validation report.

Phase 6: User interface

Create a simple Blender panel.
Add controls for seed, track width, cone spacing, track type, and environment density.
Add Generate, Regenerate, and Clear buttons.

IMPORTANT: Do not attempt to implement every feature in one enormous script.

Work incrementally and ensure that each phase functions before proceeding to the next.

Use comments and docstrings to explain important geometry calculations.

If a requirement is ambiguous, explain the ambiguity and propose a reasonable configurable solution rather than making an undocumented assumption.

Do not claim a feature is complete unless it has been implemented and tested.

Start by examining the project directory, presenting your implementation plan, and creating the initial project files.