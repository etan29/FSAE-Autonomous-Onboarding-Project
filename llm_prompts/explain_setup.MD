I now need you to explain exactly how to set up, install, and run the FSAE Procedural Racing Environment Generator you have developed.

Assume I am relatively new to Blender Python development.

Do not assume I know how Blender scripting, Python environments, or Blender add-ons work.

Create a complete step-by-step setup and execution guide.

Cover the following:

1. Software Requirements
Which Blender version is required?
Which Python version is used by Blender?
Are any external Python libraries required?
How do I check that the dependencies are installed?
2. Project Setup
Explain how to open the project in Cursor.
Explain where every Python file should be located.
Explain the purpose of each file.
Explain how the project files interact with each other.
3. Blender Setup
Explain how to open Blender.
Explain how to access the scripting workspace.
Explain how to execute the generator script.
Explain whether the project needs to be installed as a Blender add-on.
If an add-on is provided, explain how to install and enable it.
4. Running the Generator

Provide exact instructions for:

Generating the first track.
Setting a random seed.
Changing track width.
Changing cone spacing.
Generating a new environment.
Regenerating the same environment using the same seed.
Generating a different environment using a new seed.
Enabling and disabling tents, trees, and spectators.
Clearing the previous generated scene.

Include the exact commands or Blender interface actions needed.

5. Expected Output

Explain what I should see in Blender when generation is successful.

Explain the collection hierarchy and where the track, cones, and environmental objects are stored.

6. Troubleshooting

Explain how to resolve:

Missing Python modules.
Blender Python errors.
Missing materials.
Cones appearing on the wrong side.
Cones overlapping.
Incorrect track width.
Objects appearing below the ground.
The generator creating duplicate objects.
Random seeds producing inconsistent output.

For each problem, provide likely causes and practical solutions.

7. Testing

Show me how to:

Run the automated tests.
Verify cone spacing.
Verify track width.
Verify cone colors.
Verify that identical seeds produce identical environments.
Generate a validation report.
8. Final Quick Start

Finish with a short checklist that lets me go from opening the project in Cursor to generating a complete FSAE racing environment in Blender.

IMPORTANT: Use the actual files, functions, dependencies, and commands in this project.

Do not provide generic instructions that do not match the implementation.

If something has not been implemented, explicitly identify it rather than pretending it exists.

Make the guide detailed enough that someone with limited Blender experience can follow it independently.