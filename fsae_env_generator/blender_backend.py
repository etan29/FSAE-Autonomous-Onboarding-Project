"""Turn a generated environment into Blender objects.

Meshes and materials are shared. Cones and trees are instances of those meshes.
This module is imported only when `bpy` is available.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

from .assets import MATERIAL_RGBA
from .models import (
    COLLECTION_PATHS,
    INPUT_CURVE_NAME,
    REPORT_TEXT_NAME,
    ROOT_COLLECTION,
    MeshData,
    PlacedObject,
    UniqueMesh,
)
from .pipeline import GeneratedEnvironment
from .validation import ValidationReport, format_report


def _fresh_principled(material: bpy.types.Material) -> bpy.types.Node:
    material.use_nodes = True
    tree = material.node_tree
    tree.nodes.clear()
    output = tree.nodes.new("ShaderNodeOutputMaterial")
    principled = tree.nodes.new("ShaderNodeBsdfPrincipled")
    output.location = (400, 0)
    principled.location = (0, 0)
    tree.links.new(principled.outputs["BSDF"], output.inputs["Surface"])
    return principled


def _set_input(node: bpy.types.Node, names: tuple[str, ...], value) -> None:
    for name in names:
        socket = node.inputs.get(name)
        if socket is not None and not socket.is_linked:
            socket.default_value = value
            return


def _build_flat_shader(material: bpy.types.Material, color: tuple[float, float, float, float], roughness: float) -> None:
    principled = _fresh_principled(material)
    _set_input(principled, ("Base Color",), color)
    _set_input(principled, ("Roughness",), roughness)
    _set_input(principled, ("Specular", "Specular IOR Level"), 0.25)


def _build_cone_shader(material: bpy.types.Material, color: tuple[float, float, float, float], kind: str) -> None:
    """PVC body, glossy white band, or matte black band. Dirt collects near z = 0."""
    principled = _fresh_principled(material)
    tree = material.node_tree
    nodes = tree.nodes
    if kind == "black":
        roughness = 0.92
        specular = 0.02
        subsurface = 0.0
    elif kind == "white":
        roughness = 0.16
        specular = 0.72
        subsurface = 0.08
    else:
        roughness = 0.38
        specular = 0.3
        subsurface = 0.1
    _set_input(principled, ("Base Color",), color)
    _set_input(principled, ("Specular", "Specular IOR Level"), specular)
    _set_input(principled, ("Subsurface", "Subsurface Weight"), subsurface)
    _set_input(principled, ("Subsurface Radius",), (1.0, 0.2, 0.1))

    coordinate = nodes.new("ShaderNodeTexCoord")
    coordinate.location = (-900, 0)
    separate = nodes.new("ShaderNodeSeparateXYZ")
    separate.location = (-700, -80)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.location = (-700, 220)
    noise.noise_dimensions = "3D"
    _set_input(noise, ("Scale",), 22.0)
    _set_input(noise, ("Detail",), 3.0)
    _set_input(noise, ("Roughness",), 0.45)
    rough_map = nodes.new("ShaderNodeMapRange")
    rough_map.location = (-420, 220)
    _set_input(rough_map, ("From Min",), 0.3)
    _set_input(rough_map, ("From Max",), 0.7)
    _set_input(rough_map, ("To Min",), roughness - 0.05)
    _set_input(rough_map, ("To Max",), roughness + 0.05)
    if hasattr(rough_map, "clamp"):
        rough_map.clamp = True
    tree.links.new(coordinate.outputs["Generated"], noise.inputs["Vector"])
    tree.links.new(noise.outputs["Fac"], rough_map.inputs["Value"])
    tree.links.new(rough_map.outputs["Result"], principled.inputs["Roughness"])

    if kind == "black":
        return
    dirt_map = nodes.new("ShaderNodeMapRange")
    dirt_map.location = (-420, -80)
    _set_input(dirt_map, ("From Min",), 0.0)
    _set_input(dirt_map, ("From Max",), 0.22)
    _set_input(dirt_map, ("To Min",), 1.0)
    _set_input(dirt_map, ("To Max",), 0.0)
    if hasattr(dirt_map, "clamp"):
        dirt_map.clamp = True
    dirt_mix = nodes.new("ShaderNodeMath")
    dirt_mix.location = (-200, -40)
    dirt_mix.operation = "MULTIPLY"
    mix = nodes.new("ShaderNodeMixRGB")
    mix.location = (-40, 80)
    mix.inputs["Color1"].default_value = color
    mix.inputs["Color2"].default_value = (0.28, 0.2, 0.1, 1.0)
    tree.links.new(coordinate.outputs["Generated"], separate.inputs["Vector"])
    tree.links.new(separate.outputs["Z"], dirt_map.inputs["Value"])
    tree.links.new(dirt_map.outputs["Result"], dirt_mix.inputs[0])
    tree.links.new(noise.outputs["Fac"], dirt_mix.inputs[1])
    tree.links.new(dirt_mix.outputs["Value"], mix.inputs["Fac"])
    tree.links.new(mix.outputs["Color"], principled.inputs["Base Color"])


def _build_asphalt_shader(material: bpy.types.Material, color: tuple[float, float, float, float]) -> None:
    """Weathered asphalt: large color patches, fine roughness, and a light bump."""
    principled = _fresh_principled(material)
    tree = material.node_tree
    nodes = tree.nodes
    coordinate = nodes.new("ShaderNodeTexCoord")
    coordinate.location = (-1100, 0)
    patch = nodes.new("ShaderNodeTexNoise")
    patch.location = (-860, 180)
    grain = nodes.new("ShaderNodeTexNoise")
    grain.location = (-860, -80)
    for node, scale in ((patch, 3.5), (grain, 28.0)):
        node.noise_dimensions = "3D"
        _set_input(node, ("Scale",), scale)
        _set_input(node, ("Detail",), 6.0)
        tree.links.new(coordinate.outputs["Object"], node.inputs["Vector"])
    color_map = nodes.new("ShaderNodeMapRange")
    color_map.location = (-600, 180)
    _set_input(color_map, ("From Min",), 0.35)
    _set_input(color_map, ("From Max",), 0.7)
    _set_input(color_map, ("To Min",), 0.0)
    _set_input(color_map, ("To Max",), 1.0)
    mix = nodes.new("ShaderNodeMixRGB")
    mix.location = (-320, 160)
    mix.inputs["Color1"].default_value = color
    mix.inputs["Color2"].default_value = (0.08, 0.08, 0.085, 1.0)
    rough_map = nodes.new("ShaderNodeMapRange")
    rough_map.location = (-320, -80)
    _set_input(rough_map, ("From Min",), 0.25)
    _set_input(rough_map, ("From Max",), 0.75)
    _set_input(rough_map, ("To Min",), 0.72)
    _set_input(rough_map, ("To Max",), 0.95)
    bump = nodes.new("ShaderNodeBump")
    bump.location = (-40, -220)
    _set_input(bump, ("Strength",), 0.18)
    _set_input(bump, ("Distance",), 0.015)
    tree.links.new(patch.outputs["Fac"], color_map.inputs["Value"])
    tree.links.new(color_map.outputs["Result"], mix.inputs["Fac"])
    tree.links.new(mix.outputs["Color"], principled.inputs["Base Color"])
    tree.links.new(grain.outputs["Fac"], rough_map.inputs["Value"])
    tree.links.new(rough_map.outputs["Result"], principled.inputs["Roughness"])
    tree.links.new(grain.outputs["Fac"], bump.inputs["Height"])
    normal = principled.inputs.get("Normal")
    if normal is not None:
        tree.links.new(bump.outputs["Normal"], normal)
    _set_input(principled, ("Specular", "Specular IOR Level"), 0.12)


def _material(name: str, color: tuple[float, float, float, float], roughness: float) -> bpy.types.Material:
    material_name = f"FSAE_MAT_{name}"
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(material_name)
    material.diffuse_color = color
    if hasattr(material, "use_backface_culling"):
        material.use_backface_culling = False
    if name == "asphalt":
        _build_asphalt_shader(material, color)
    elif name in {"cone_blue", "cone_yellow", "cone_orange"}:
        _build_cone_shader(material, color, "body")
    elif name == "cone_white":
        _build_cone_shader(material, color, "white")
    elif name == "cone_black":
        _build_cone_shader(material, color, "black")
    else:
        _build_flat_shader(material, color, roughness)
    return material


def _roughness_for(name: str) -> float:
    if name in {"asphalt", "asphalt_dark", "parking", "tire", "skid"}:
        return 0.9
    if name in {"grass", "foliage", "foliage_dark"}:
        return 0.8
    if name in {"cone_blue", "cone_yellow", "cone_orange", "cone_white", "cone_black"}:
        return 0.4
    return 0.55


def _ensure_materials() -> dict[str, bpy.types.Material]:
    return {name: _material(name, color, _roughness_for(name)) for name, color in MATERIAL_RGBA.items()}


def _mesh_from_data(name: str, data: MeshData, materials: dict[str, bpy.types.Material]) -> bpy.types.Mesh:
    mesh = bpy.data.meshes.new(name)
    mesh.from_pydata(list(data.vertices), [], [tuple(face) for face in data.faces])
    for slot in data.material_slots:
        mesh.materials.append(materials[slot])
    for polygon, slot in zip(mesh.polygons, data.face_materials):
        polygon.material_index = slot
    mesh.update()
    return mesh


def _remove_collection_tree(collection: bpy.types.Collection) -> None:
    for child in list(collection.children):
        _remove_collection_tree(child)
    for obj in list(collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(collection)


def _purge_unused(prefix: str = "FSAE_") -> None:
    datablocks = (
        bpy.data.meshes,
        bpy.data.materials,
        bpy.data.curves,
        bpy.data.lights,
        bpy.data.cameras,
    )
    for library in datablocks:
        for block in list(library):
            if block.name.startswith(prefix) and block.users == 0:
                library.remove(block)
    world = bpy.data.worlds.get("FSAE_World")
    if world is not None and world.users == 0:
        bpy.data.worlds.remove(world)


def _remember_world_and_camera(scene: bpy.types.Scene) -> None:
    """Remember the user's world and camera once, ignoring our own stand-ins."""
    if scene.get("fsae_previous_world") is None:
        world_name = scene.world.name if scene.world else ""
        if world_name == "FSAE_World":
            world_name = ""
        scene["fsae_previous_world"] = world_name
    if scene.get("fsae_previous_camera") is None:
        camera_name = scene.camera.name if scene.camera else ""
        if camera_name == "FSAE_Camera":
            camera_name = ""
        scene["fsae_previous_camera"] = camera_name


def _restore_world_and_camera(scene: bpy.types.Scene) -> None:
    world_name = scene.get("fsae_previous_world")
    if world_name:
        world = bpy.data.worlds.get(world_name)
        if world is not None:
            scene.world = world
    camera_name = scene.get("fsae_previous_camera")
    if camera_name:
        camera = bpy.data.objects.get(camera_name)
        if camera is not None:
            scene.camera = camera
    # Drop the remembered names so the next generate records the restored scene,
    # not the FSAE world that was active during the previous build.
    if "fsae_previous_world" in scene.keys():
        del scene["fsae_previous_world"]
    if "fsae_previous_camera" in scene.keys():
        del scene["fsae_previous_camera"]


def clear_generated_scene() -> None:
    """Remove the generated hierarchy and its unused datablocks.

    Panel settings and the stored regenerate config are left in place so
    Regenerate can rebuild the same environment after a clear.
    """
    scene = bpy.context.scene
    root = bpy.data.collections.get(ROOT_COLLECTION)
    if root is not None:
        _remove_collection_tree(root)
    text = bpy.data.texts.get(REPORT_TEXT_NAME)
    if text is not None:
        bpy.data.texts.remove(text)
    _restore_world_and_camera(scene)
    _purge_unused()


def _child_collection(parent: bpy.types.Collection, name: str) -> bpy.types.Collection:
    for child in parent.children:
        if child.name == name:
            return child
    collection = bpy.data.collections.new(name)
    parent.children.link(collection)
    return collection


def _collection_for(root: bpy.types.Collection, path: str) -> bpy.types.Collection:
    current = root
    for part in path.split("/"):
        current = _child_collection(current, part)
    return current


def _link_object(obj: bpy.types.Object, collection: bpy.types.Collection) -> None:
    collection.objects.link(obj)


def _apply_tent_color(obj: bpy.types.Object, placed: PlacedObject, materials: dict[str, bpy.types.Material]) -> None:
    color_name = placed.metadata.get("color")
    if not color_name or len(obj.material_slots) < 2:
        return
    slot = obj.material_slots[1]
    slot.link = "OBJECT"
    slot.material = materials[color_name]


def _add_curve(
    name: str,
    points: list,
    closed: bool,
    bevel: float,
    material: bpy.types.Material,
    collection: bpy.types.Collection,
    z: float,
) -> None:
    curve = bpy.data.curves.new(name, type="CURVE")
    curve.dimensions = "3D"
    curve.bevel_depth = bevel
    curve.bevel_resolution = 1
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for index, point in enumerate(points):
        spline.points[index].co = (point.x, point.y, z, 1.0)
    spline.use_cyclic_u = closed
    curve.materials.append(material)
    obj = bpy.data.objects.new(name, curve)
    _link_object(obj, collection)


def _look_at(obj: bpy.types.Object, target: tuple[float, float, float]) -> None:
    direction = Vector(target) - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def _add_sun(lighting: dict, collection: bpy.types.Collection) -> None:
    light_data = bpy.data.lights.new("FSAE_Sun", "SUN")
    light_data.energy = float(lighting["energy"])
    light_data.color = lighting["sun_color"][:3]
    if hasattr(light_data, "angle"):
        light_data.angle = math.radians(0.5)
    obj = bpy.data.objects.new("FSAE_Sun", light_data)
    _link_object(obj, collection)

    elevation = math.radians(float(lighting["elevation"]))
    azimuth = math.radians(float(lighting["azimuth"]))
    # Direction the sunlight travels. Elevation is degrees above the horizon.
    incoming = Vector(
        (
            math.cos(elevation) * math.cos(azimuth),
            math.cos(elevation) * math.sin(azimuth),
            -abs(math.sin(elevation)),
        )
    )
    obj.rotation_euler = incoming.to_track_quat("-Z", "Y").to_euler()


def _add_camera(camera: dict, collection: bpy.types.Collection, scene: bpy.types.Scene) -> None:
    camera_data = bpy.data.cameras.new("FSAE_Camera")
    camera_data.lens = 35.0
    camera_data.clip_end = 5000.0
    obj = bpy.data.objects.new("FSAE_Camera", camera_data)
    obj.location = (camera["x"], camera["y"], camera["z"])
    _look_at(obj, (camera["target_x"], camera["target_y"], camera["target_z"]))
    _link_object(obj, collection)
    scene.camera = obj


def _add_world(scene: bpy.types.Scene, lighting: dict) -> None:
    """Nishita sky driven by the same sun angles as the lamp."""
    world = bpy.data.worlds.get("FSAE_World")
    if world is None:
        world = bpy.data.worlds.new("FSAE_World")
    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()
    output = nodes.new("ShaderNodeOutputWorld")
    background = nodes.new("ShaderNodeBackground")
    sky = nodes.new("ShaderNodeTexSky")
    output.location = (400, 0)
    background.location = (160, 0)
    sky.location = (-200, 0)
    if hasattr(sky, "sky_type"):
        sky.sky_type = "NISHITA"
    sky.sun_elevation = math.radians(float(lighting["elevation"]))
    sky.sun_rotation = math.radians(float(lighting["azimuth"]))
    if hasattr(sky, "sun_disc"):
        sky.sun_disc = True
    if hasattr(sky, "sun_intensity"):
        sky.sun_intensity = float(lighting.get("sun_intensity", 0.3))
    if hasattr(sky, "air_density"):
        sky.air_density = float(lighting.get("air_density", 1.0))
    if hasattr(sky, "dust_density"):
        sky.dust_density = float(lighting.get("dust_density", 1.0))
    if hasattr(sky, "ozone_density"):
        sky.ozone_density = float(lighting.get("ozone_density", 1.0))
    links.new(sky.outputs["Color"], background.inputs["Color"])
    background.inputs["Strength"].default_value = float(lighting["world_energy"])
    links.new(background.outputs["Background"], output.inputs["Surface"])
    scene.world = world


def _add_label(text: str, location: tuple[float, float, float], collection: bpy.types.Collection, material: bpy.types.Material) -> None:
    curve = bpy.data.curves.new("FSAE_Rules_Label_Curve", "FONT")
    curve.body = text
    curve.size = 0.7
    curve.align_x = "LEFT"
    curve.materials.append(material)
    obj = bpy.data.objects.new("FSAE_Rules_Label", curve)
    obj.location = location
    _link_object(obj, collection)


def _write_report(report: ValidationReport) -> None:
    existing = bpy.data.texts.get(REPORT_TEXT_NAME)
    if existing is not None:
        bpy.data.texts.remove(existing)
    text = bpy.data.texts.new(REPORT_TEXT_NAME)
    text.write(format_report(report))


def _configure_units(scene: bpy.types.Scene) -> None:
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"


def _is_project_root(path: Path) -> bool:
    return (path / "run_generator.py").is_file() and (path / "fsae_env_generator" / "__init__.py").is_file()


def project_root() -> Path:
    """Folder that contains this project, whether Blender loaded it from source or as an add-on."""
    starts: list[Path] = [Path(__file__).resolve().parent, Path.cwd()]
    for entry in sys.path:
        if entry:
            starts.append(Path(entry))
    if bpy.data.filepath:
        starts.append(Path(bpy.data.filepath).resolve().parent)
    home = Path.home()
    project_name = "FSAE-Autonomous-Onboarding-Project"
    for base in (
        home / "OneDrive" / "Desktop",
        home / "Desktop",
        home / "OneDrive",
        home / "Documents",
    ):
        starts.append(base / project_name)

    seen: set[Path] = set()
    for start in starts:
        try:
            resolved = start.resolve()
        except OSError:
            continue
        for candidate in (resolved, *resolved.parents):
            if candidate in seen:
                break
            seen.add(candidate)
            if _is_project_root(candidate):
                return candidate
    raise FileNotFoundError(
        "Could not find FSAE-Autonomous-Onboarding-Project (the folder that contains run_generator.py)."
    )


def generated_tracks_directory() -> Path:
    """Default directory for every generated track. Created on first use."""
    directory = project_root() / "generated_tracks"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def generated_track_filepath(seed: int) -> Path:
    return generated_tracks_directory() / f"FSAE_Track_Seed_{int(seed)}.blend"


def save_generated_blend(seed: int) -> Path:
    """Overwrite ``generated_tracks/FSAE_Track_Seed_<seed>.blend`` with the current scene.

    Uses ``bpy.ops.wm.save_as_mainfile`` so the file is a normal .blend that opens on its own.
    Numbered ``.blend1`` backups are suppressed for this write so the same seed does not
    leave extra copies beside the file.
    """
    path = generated_track_filepath(seed)
    path.parent.mkdir(parents=True, exist_ok=True)
    preferences = bpy.context.preferences.filepaths
    previous_backups = preferences.save_version
    preferences.save_version = 0
    try:
        result = bpy.ops.wm.save_as_mainfile(
            "EXEC_DEFAULT",
            filepath=str(path),
            check_existing=False,
            compress=False,
            relative_remap=False,
        )
    finally:
        preferences.save_version = previous_backups
    if "FINISHED" not in set(result):
        raise RuntimeError(f"Could not save {path}. Blender returned {result}.")
    print(f"Saved FSAE track: {path}")
    return path


def build_blender_scene(environment: GeneratedEnvironment, report: ValidationReport) -> None:
    """Replace any previous FSAE hierarchy with this environment."""
    scene = bpy.context.scene
    _remember_world_and_camera(scene)
    clear_generated_scene()
    # clear restores the previous world and forgets it. Remember again so a
    # later clear still returns to the user's original world, not FSAE_World.
    _remember_world_and_camera(scene)
    _configure_units(scene)

    root = bpy.data.collections.new(ROOT_COLLECTION)
    scene.collection.children.link(root)
    collections = {path: _collection_for(root, path) for path in COLLECTION_PATHS}
    materials = _ensure_materials()

    shared: dict[str, bpy.types.Mesh] = {}
    for asset_name, mesh_data in environment.assets.items():
        shared[asset_name] = _mesh_from_data(f"FSAE_MESH_{asset_name}", mesh_data, materials)

    for placed in environment.objects:
        obj = bpy.data.objects.new(placed.name, shared[placed.asset])
        obj.location = (placed.x, placed.y, placed.z)
        obj.rotation_mode = "ZYX"
        obj.rotation_euler = (placed.pitch, placed.roll, placed.yaw)
        obj.scale = placed.scale
        _link_object(obj, collections[placed.collection])
        _apply_tent_color(obj, placed, materials)

    for unique in environment.unique_meshes:
        mesh = _mesh_from_data(unique.name, unique.mesh, materials)
        obj = bpy.data.objects.new(unique.name, mesh)
        obj.location = (unique.x, unique.y, unique.z)
        _link_object(obj, collections[unique.collection])

    show_limits = bool(environment.config.get("enable_track_limits", True))
    # The highway centerline is not drawn. The path stays in the track data for cones and checks.
    if show_limits:
        boundary_collection = collections["Track/Track_Boundaries"]
        _add_curve(
            "FSAE_Left_Boundary",
            environment.track.left_boundary,
            environment.track.closed,
            0.012,
            materials["cone_blue"],
            boundary_collection,
            0.045,
        )
        _add_curve(
            "FSAE_Right_Boundary",
            environment.track.right_boundary,
            environment.track.closed,
            0.012,
            materials["cone_yellow"],
            boundary_collection,
            0.045,
        )

    _add_label(environment.label_text, environment.label_position, root, materials["start_line"])
    _add_sun(environment.lighting, collections["Lighting"])
    _add_camera(environment.camera, collections["Cameras"], scene)
    _add_world(scene, environment.lighting)
    _write_report(report)

    root["fsae_seed"] = environment.seed
    root["fsae_rules_profile"] = environment.profile_id
    root["fsae_rules_revision"] = environment.profile_revision
    root["fsae_rules_note"] = environment.profile_note
    root["fsae_validation_passed"] = bool(report.passed)
    scene["fsae_seed"] = environment.seed
    scene["fsae_rules_profile"] = environment.profile_id
    scene["fsae_rules_revision"] = environment.profile_revision
    scene["fsae_config"] = json.dumps(environment.config)
    scene["fsae_validation_passed"] = bool(report.passed)
    if bpy.context.view_layer is not None:
        bpy.context.view_layer.update()


def read_input_centerline(object_name: str = INPUT_CURVE_NAME) -> tuple[list[list[float]], bool | None]:
    """Read a user curve. Returns points in world space and whether the spline is cyclic.

    The second value is None when no usable curve exists.
    """
    obj = bpy.data.objects.get(object_name)
    if obj is None or obj.type != "CURVE":
        return [], None
    points: list[list[float]] = []
    cyclic = False
    for spline in obj.data.splines:
        cyclic = cyclic or bool(spline.use_cyclic_u)
        if spline.type == "BEZIER":
            for point in spline.bezier_points:
                world = obj.matrix_world @ point.co
                points.append([float(world.x), float(world.y), float(world.z)])
        else:
            for point in spline.points:
                world = obj.matrix_world @ Vector((point.co.x, point.co.y, point.co.z))
                points.append([float(world.x), float(world.y), float(world.z)])
    return points, cyclic
