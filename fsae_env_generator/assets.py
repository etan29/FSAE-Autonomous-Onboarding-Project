"""Low-poly meshes and material colors shared by every instance of that asset.

Cone dimensions come from the active rule profile so a JSON edit changes the
next build. Stripe heights are a visual convention: the specification requires
the stripe colors and counts, not their exact vertical position.
"""

from __future__ import annotations

import math

from .config import RuleProfile
from .models import MeshData

MATERIAL_RGBA: dict[str, tuple[float, float, float, float]] = {
    "cone_blue": (0.02, 0.16, 0.75, 1.0),
    "cone_yellow": (0.95, 0.75, 0.02, 1.0),
    "cone_orange": (0.92, 0.25, 0.02, 1.0),
    "cone_white": (0.95, 0.95, 0.95, 1.0),
    "cone_black": (0.015, 0.015, 0.015, 1.0),
    "asphalt": (0.025, 0.025, 0.028, 1.0),
    "concrete": (0.45, 0.45, 0.46, 1.0),
    "asphalt_dark": (0.012, 0.012, 0.014, 1.0),
    "start_line": (0.92, 0.92, 0.92, 1.0),
    "grass": (0.12, 0.38, 0.1, 1.0),
    "trunk": (0.28, 0.16, 0.07, 1.0),
    "foliage": (0.08, 0.32, 0.08, 1.0),
    "foliage_dark": (0.05, 0.22, 0.08, 1.0),
    "tent_red": (0.7, 0.08, 0.08, 1.0),
    "tent_blue": (0.08, 0.22, 0.65, 1.0),
    "tent_white": (0.9, 0.9, 0.88, 1.0),
    "tent_green": (0.1, 0.4, 0.22, 1.0),
    "tent_yellow": (0.85, 0.7, 0.1, 1.0),
    "pole": (0.15, 0.15, 0.16, 1.0),
    "shirt_red": (0.75, 0.1, 0.1, 1.0),
    "shirt_blue": (0.1, 0.25, 0.7, 1.0),
    "shirt_green": (0.1, 0.45, 0.22, 1.0),
    "shirt_yellow": (0.85, 0.72, 0.12, 1.0),
    "skin": (0.72, 0.54, 0.4, 1.0),
    "pants": (0.12, 0.14, 0.2, 1.0),
    "barrier": (0.85, 0.55, 0.1, 1.0),
    "tire": (0.02, 0.02, 0.02, 1.0),
    "building": (0.55, 0.56, 0.58, 1.0),
    "roof": (0.35, 0.18, 0.14, 1.0),
    "car_body": (0.15, 0.35, 0.55, 1.0),
    "glass": (0.6, 0.75, 0.85, 1.0),
    "flag_cloth": (0.8, 0.1, 0.15, 1.0),
    "table": (0.45, 0.28, 0.14, 1.0),
    "parking": (0.08, 0.08, 0.09, 1.0),
    "equipment": (0.4, 0.4, 0.42, 1.0),
}

TENT_COLORS = ("tent_red", "tent_blue", "tent_white", "tent_green", "tent_yellow")
SHIRT_COLORS = ("shirt_red", "shirt_blue", "shirt_green", "shirt_yellow")

SURFACE_MATERIALS = {
    "asphalt": "asphalt",
    "concrete": "concrete",
    "dark": "asphalt_dark",
}


def mesh_aabb(mesh: MeshData) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    xs = [vertex[0] for vertex in mesh.vertices]
    ys = [vertex[1] for vertex in mesh.vertices]
    zs = [vertex[2] for vertex in mesh.vertices]
    return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))


def _quad(faces: list[tuple[int, ...]], materials: list[int], a: int, b: int, c: int, d: int, slot: int) -> None:
    faces.append((a, b, c, d))
    materials.append(slot)


def _box(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    materials: list[int],
    center: tuple[float, float, float],
    size: tuple[float, float, float],
    slot: int,
) -> None:
    """Axis-aligned box centered at `center` with full `size` extents."""
    cx, cy, cz = center
    hx, hy, hz = size[0] * 0.5, size[1] * 0.5, size[2] * 0.5
    base = len(vertices)
    corners = (
        (cx - hx, cy - hy, cz - hz),
        (cx + hx, cy - hy, cz - hz),
        (cx + hx, cy + hy, cz - hz),
        (cx - hx, cy + hy, cz - hz),
        (cx - hx, cy - hy, cz + hz),
        (cx + hx, cy - hy, cz + hz),
        (cx + hx, cy + hy, cz + hz),
        (cx - hx, cy + hy, cz + hz),
    )
    vertices.extend(corners)
    # Outward faces. Bottom points down, top points up.
    _quad(faces, materials, base + 0, base + 3, base + 2, base + 1, slot)
    _quad(faces, materials, base + 4, base + 5, base + 6, base + 7, slot)
    _quad(faces, materials, base + 0, base + 1, base + 5, base + 4, slot)
    _quad(faces, materials, base + 1, base + 2, base + 6, base + 5, slot)
    _quad(faces, materials, base + 2, base + 3, base + 7, base + 6, slot)
    _quad(faces, materials, base + 3, base + 0, base + 4, base + 7, slot)


def _cylinder(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    materials: list[int],
    center_x: float,
    center_y: float,
    z0: float,
    z1: float,
    radius: float,
    sides: int,
    slot: int,
) -> None:
    base = len(vertices)
    for index in range(sides):
        angle = 2.0 * math.pi * index / sides
        vertices.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle), z0))
    for index in range(sides):
        angle = 2.0 * math.pi * index / sides
        vertices.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle), z1))
    for index in range(sides):
        nxt = (index + 1) % sides
        _quad(
            faces,
            materials,
            base + index,
            base + nxt,
            base + sides + nxt,
            base + sides + index,
            slot,
        )
    bottom = len(vertices)
    vertices.append((center_x, center_y, z0))
    top = len(vertices)
    vertices.append((center_x, center_y, z1))
    for index in range(sides):
        nxt = (index + 1) % sides
        faces.append((bottom, base + nxt, base + index))
        materials.append(slot)
        faces.append((top, base + sides + index, base + sides + nxt))
        materials.append(slot)


def _cone(
    vertices: list[tuple[float, float, float]],
    faces: list[tuple[int, ...]],
    materials: list[int],
    center_x: float,
    center_y: float,
    z0: float,
    z1: float,
    radius: float,
    sides: int,
    slot: int,
) -> None:
    base = len(vertices)
    for index in range(sides):
        angle = 2.0 * math.pi * index / sides
        vertices.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle), z0))
    apex = len(vertices)
    vertices.append((center_x, center_y, z1))
    for index in range(sides):
        nxt = (index + 1) % sides
        faces.append((base + index, base + nxt, apex))
        materials.append(slot)


def _finish(vertices: list[tuple[float, float, float]], faces: list[tuple[int, ...]], materials: list[int], slots: list[str]) -> MeshData:
    if len(faces) != len(materials):
        raise RuntimeError("Every face needs a material index.")
    return MeshData(vertices=vertices, faces=faces, material_slots=slots, face_materials=materials)


def traffic_cone(base_width: float, height: float, bands: list[tuple[float, float, str]]) -> MeshData:
    """Truncated square pyramid. `base_width` is the full side length at z = 0.

    `bands` are `(z_start_fraction, z_end_fraction, material)` from the ground
    to the tip. The square's flat faces are parallel to X and Y so a yaw of
    `atan2(tangent)` puts a face toward the track.
    """
    half = base_width * 0.5
    top_half = half * 0.12
    fractions = [0.0]
    for start, end, _material in bands:
        if abs(fractions[-1] - start) > 1e-6:
            fractions.append(start)
        fractions.append(end)
    if fractions[-1] < 1.0 - 1e-6:
        fractions.append(1.0)

    def half_at(fraction: float) -> float:
        return half + (top_half - half) * fraction

    vertices: list[tuple[float, float, float]] = []
    ring_at: dict[float, int] = {}
    for fraction in fractions:
        ring_at[round(fraction, 5)] = len(vertices)
        width = half_at(fraction)
        z = height * fraction
        vertices.extend(
            (
                (width, -width, z),
                (width, width, z),
                (-width, width, z),
                (-width, -width, z),
            )
        )

    slot_names: list[str] = []
    for _start, _end, material in bands:
        if material not in slot_names:
            slot_names.append(material)

    faces: list[tuple[int, ...]] = []
    face_materials: list[int] = []
    for start, end, material in bands:
        lower = ring_at[round(start, 5)]
        upper = ring_at[round(end, 5)]
        slot = slot_names.index(material)
        for side in range(4):
            nxt = (side + 1) % 4
            _quad(faces, face_materials, lower + side, lower + nxt, upper + nxt, upper + side, slot)
    # Tip cap uses the top band's material.
    top = ring_at[round(fractions[-1], 5)]
    cap_slot = slot_names.index(bands[-1][2])
    faces.append((top, top + 1, top + 2, top + 3))
    face_materials.append(cap_slot)
    return _finish(vertices, faces, face_materials, slot_names)


def _small_cone(base: float, height: float, body: str, stripe: str) -> MeshData:
    # One stripe in the upper-middle of the cone.
    return traffic_cone(
        base,
        height,
        (
            (0.0, 0.42, body),
            (0.42, 0.62, stripe),
            (0.62, 1.0, body),
        ),
    )


def _large_cone(base: float, height: float) -> MeshData:
    # Two white stripes on an orange body.
    return traffic_cone(
        base,
        height,
        (
            (0.0, 0.26, "cone_orange"),
            (0.26, 0.40, "cone_white"),
            (0.40, 0.56, "cone_orange"),
            (0.56, 0.70, "cone_white"),
            (0.70, 1.0, "cone_orange"),
        ),
    )


def build_cone_library(profile: RuleProfile) -> dict[str, MeshData]:
    small_base = profile.small_cone_base_m
    small_height = profile.small_cone_height_m
    large_base = profile.large_cone_base_m
    large_height = profile.large_cone_height_m
    left_stripe = "cone_white" if profile.left_stripe == "white" else "cone_black"
    right_stripe = "cone_black" if profile.right_stripe == "black" else "cone_white"
    return {
        "blue_small": _small_cone(small_base, small_height, "cone_blue", left_stripe),
        "yellow_small": _small_cone(small_base, small_height, "cone_yellow", right_stripe),
        "orange_small": _small_cone(small_base, small_height, "cone_orange", "cone_white"),
        "orange_large": _large_cone(large_base, large_height),
    }


def _tree(foliage: str, kind: str) -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    slots = ["trunk", foliage]
    _cylinder(vertices, faces, materials, 0.0, 0.0, 0.0, 1.6, 0.12, 6, 0)
    if kind == "pine":
        _cone(vertices, faces, materials, 0.0, 0.0, 1.1, 6.5, 1.15, 8, 1)
    elif kind == "round":
        _cone(vertices, faces, materials, 0.0, 0.0, 1.3, 4.2, 1.35, 8, 1)
        _cone(vertices, faces, materials, 0.0, 0.0, 2.6, 5.4, 0.95, 8, 1)
    else:
        _cone(vertices, faces, materials, 0.0, 0.0, 1.4, 3.6, 1.7, 8, 1)
        _cone(vertices, faces, materials, 0.0, 0.0, 2.8, 4.8, 1.2, 8, 1)
    return _finish(vertices, faces, materials, slots)


def _tent(width: float, depth: float, height: float, cloth: str) -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    slots = ["pole", cloth]
    hx = width * 0.5
    hy = depth * 0.5
    pole_h = height * 0.72
    for x, y in ((-hx, -hy), (hx, -hy), (hx, hy), (-hx, hy)):
        _cylinder(vertices, faces, materials, x * 0.92, y * 0.92, 0.0, pole_h, 0.04, 5, 0)
    # Canopy sits on the poles. A box roof is enough at this detail level.
    _box(vertices, faces, materials, (0.0, 0.0, pole_h + 0.18), (width, depth, 0.36), 1)
    # A raised ridge makes the tent read as a tent rather than a crate.
    ridge_z = pole_h + 0.55
    base = len(vertices)
    vertices.extend(
        (
            (-hx, -hy, pole_h + 0.36),
            (hx, -hy, pole_h + 0.36),
            (hx, hy, pole_h + 0.36),
            (-hx, hy, pole_h + 0.36),
            (0.0, -hy, ridge_z),
            (0.0, hy, ridge_z),
        )
    )
    faces.append((base + 0, base + 1, base + 4))
    materials.append(1)
    faces.append((base + 3, base + 5, base + 2))
    materials.append(1)
    _quad(faces, materials, base + 0, base + 4, base + 5, base + 3, 1)
    _quad(faces, materials, base + 1, base + 2, base + 5, base + 4, 1)
    return _finish(vertices, faces, materials, slots)


def _spectator(shirt: str, arms_up: bool) -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    slots = ["pants", shirt, "skin"]
    _box(vertices, faces, materials, (0.0, 0.0, 0.45), (0.28, 0.16, 0.9), 0)
    _box(vertices, faces, materials, (0.0, 0.0, 1.15), (0.38, 0.2, 0.55), 1)
    _box(vertices, faces, materials, (0.0, 0.0, 1.62), (0.18, 0.18, 0.22), 2)
    arm_z = 1.35 if arms_up else 1.15
    arm_h = 0.34 if arms_up else 0.4
    _box(vertices, faces, materials, (-0.28, 0.0, arm_z), (0.1, 0.1, arm_h), 1)
    _box(vertices, faces, materials, (0.28, 0.0, arm_z), (0.1, 0.1, arm_h), 1)
    return _finish(vertices, faces, materials, slots)


def _barrier() -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    _box(vertices, faces, materials, (0.0, 0.0, 0.4), (2.0, 0.4, 0.8), 0)
    return _finish(vertices, faces, materials, ["barrier"])


def _tire_stack() -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    _cylinder(vertices, faces, materials, 0.0, 0.0, 0.0, 0.22, 0.34, 8, 0)
    _cylinder(vertices, faces, materials, 0.0, 0.0, 0.22, 0.44, 0.34, 8, 0)
    _cylinder(vertices, faces, materials, 0.0, 0.0, 0.44, 0.66, 0.34, 8, 0)
    return _finish(vertices, faces, materials, ["tire"])


def _building() -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    _box(vertices, faces, materials, (0.0, 0.0, 2.2), (12.0, 8.0, 4.4), 0)
    _box(vertices, faces, materials, (0.0, 0.0, 4.55), (12.6, 8.6, 0.3), 1)
    return _finish(vertices, faces, materials, ["building", "roof"])


def _car() -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    _box(vertices, faces, materials, (0.0, 0.0, 0.45), (4.2, 1.8, 0.7), 0)
    _box(vertices, faces, materials, (0.2, 0.0, 1.05), (2.2, 1.6, 0.55), 1)
    return _finish(vertices, faces, materials, ["car_body", "glass"])


def _flag() -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    _cylinder(vertices, faces, materials, 0.0, 0.0, 0.0, 3.0, 0.03, 5, 0)
    _box(vertices, faces, materials, (0.45, 0.0, 2.7), (0.9, 0.04, 0.5), 1)
    return _finish(vertices, faces, materials, ["pole", "flag_cloth"])


def _table() -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    _box(vertices, faces, materials, (0.0, 0.0, 0.75), (1.2, 0.7, 0.08), 0)
    for x, y in ((-0.5, -0.25), (0.5, -0.25), (0.5, 0.25), (-0.5, 0.25)):
        _box(vertices, faces, materials, (x, y, 0.36), (0.06, 0.06, 0.72), 0)
    return _finish(vertices, faces, materials, ["table"])


def _equipment() -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    _box(vertices, faces, materials, (0.0, 0.0, 0.35), (0.8, 0.5, 0.7), 0)
    return _finish(vertices, faces, materials, ["equipment"])


def _marshall() -> MeshData:
    vertices: list[tuple[float, float, float]] = []
    faces: list[tuple[int, ...]] = []
    materials: list[int] = []
    _cylinder(vertices, faces, materials, 0.0, 0.0, 0.0, 2.2, 0.04, 5, 0)
    _cone(vertices, faces, materials, 0.0, 0.0, 2.0, 2.7, 1.1, 8, 1)
    _box(vertices, faces, materials, (0.9, 0.0, 0.75), (1.2, 0.6, 0.08), 2)
    return _finish(vertices, faces, materials, ["pole", "tent_yellow", "table"])


def quad_mesh(width: float, depth: float, material: str, z: float = 0.0) -> MeshData:
    """A single ground quad on z = `z`, centered on the origin. Width is along X."""
    hx = width * 0.5
    hy = depth * 0.5
    vertices = (
        (-hx, -hy, z),
        (hx, -hy, z),
        (hx, hy, z),
        (-hx, hy, z),
    )
    return MeshData(vertices=list(vertices), faces=[(0, 1, 2, 3)], material_slots=[material], face_materials=[0])


def build_asset_library(profile: RuleProfile) -> dict[str, MeshData]:
    """Every mesh that will be instanced. Cones use the profile's dimensions."""
    library = build_cone_library(profile)
    library["tree_pine"] = _tree("foliage_dark", "pine")
    library["tree_round"] = _tree("foliage", "round")
    library["tree_broad"] = _tree("foliage", "broad")
    library["tent_small"] = _tent(3.0, 3.0, 2.5, "tent_white")
    library["tent_medium"] = _tent(6.0, 4.0, 3.0, "tent_white")
    library["tent_large"] = _tent(10.0, 5.0, 3.4, "tent_white")
    for shirt in SHIRT_COLORS:
        library[f"spectator_{shirt}"] = _spectator(shirt, arms_up=False)
        library[f"spectator_{shirt}_up"] = _spectator(shirt, arms_up=True)
    library["barrier"] = _barrier()
    library["tire_stack"] = _tire_stack()
    library["building"] = _building()
    library["car"] = _car()
    library["flag"] = _flag()
    library["table"] = _table()
    library["equipment"] = _equipment()
    library["marshall"] = _marshall()
    return library


# Half-diagonal (or equivalent) of each asset's ground footprint, in meters,
# before instance scale is applied. Used to keep objects off the asphalt.
ASSET_FOOTPRINT: dict[str, float] = {
    "tree_pine": 1.3,
    "tree_round": 1.5,
    "tree_broad": 1.8,
    "tent_small": 2.2,
    "tent_medium": 3.7,
    "tent_large": 5.6,
    "barrier": 1.05,
    "tire_stack": 0.4,
    "building": 7.3,
    "car": 2.3,
    "flag": 0.5,
    "table": 0.7,
    "equipment": 0.5,
    "marshall": 1.3,
    "blue_small": 0.162,
    "yellow_small": 0.162,
    "orange_small": 0.162,
    "orange_large": 0.202,
}

for _shirt in SHIRT_COLORS:
    ASSET_FOOTPRINT[f"spectator_{_shirt}"] = 0.45
    ASSET_FOOTPRINT[f"spectator_{_shirt}_up"] = 0.45


def footprint_of(asset: str) -> float:
    if asset in ASSET_FOOTPRINT:
        return ASSET_FOOTPRINT[asset]
    if asset.startswith("spectator_"):
        return 0.45
    raise KeyError(f"No footprint for asset '{asset}'")
