"""Blender add-on entry point for the FSAE environment generator.

Importing this package does not import bpy. The add-on loader calls register().
"""

from __future__ import annotations

bl_info = {
    "name": "FSAE Autonomous Environment Generator",
    "author": "FSAE Autonomous Onboarding",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "View3D > Sidebar > FSAE",
    "description": "Procedural Formula SAE autonomous racing environments",
    "category": "Add Mesh",
}


def register() -> None:
    from . import ui

    ui.register()


def unregister() -> None:
    from . import ui

    ui.unregister()
