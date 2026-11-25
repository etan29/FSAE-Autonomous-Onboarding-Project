"""Generator settings and competition rule profiles.

Rule numbers live in `profiles/*.json` so they can be edited without changing
Python. A null profile field means that competition file does not define the
limit. The resolver then uses an explicit config override, or the built-in
generator default, and records which source was used.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Built-in generator defaults. These match the project specification's U.S.
# Formula SAE starting profile, but they are not silently attached to every
# competition. `resolve_limits` records the source of each value.
BUILTIN_MIN_TRACK_WIDTH = 3.0
BUILTIN_MIN_TURNING_DIAMETER = 9.0
BUILTIN_MAX_STRAIGHT = 80.0
BUILTIN_LAP_LENGTH = (200.0, 500.0)

PROFILE_DIR = Path(__file__).resolve().parent / "profiles"


@dataclass
class RuleProfile:
    """One labeled competition profile and the limits it actually defines."""

    id: str
    name: str
    revision: str
    source_note: str
    min_track_width_m: float | None
    min_turning_diameter_m: float | None
    max_straight_length_m: float | None
    target_lap_length_m: tuple[float, float] | None
    left_cone: str
    right_cone: str
    entry_exit_cone: str
    start_finish_cone: str
    small_cone_base_m: float
    small_cone_height_m: float
    large_cone_base_m: float
    large_cone_height_m: float
    left_stripe: str
    right_stripe: str
    max_cone_spacing_m: float | None
    enforce_corner_spacing: bool

    def cone_size(self, kind: str) -> tuple[float, float]:
        """Return `(base_width, height)` in meters for a cone asset name."""
        if kind == "orange_large":
            return (self.large_cone_base_m, self.large_cone_height_m)
        return (self.small_cone_base_m, self.small_cone_height_m)


def _optional_float(value: object) -> float | None:
    if value is None:
        return None
    return float(value)


def _load_profile(path: Path) -> RuleProfile:
    data = json.loads(path.read_text(encoding="utf-8"))
    lap = data.get("target_lap_length_m")
    lap_range = None if lap is None else (float(lap[0]), float(lap[1]))
    return RuleProfile(
        id=str(data["id"]),
        name=str(data["name"]),
        revision=str(data["revision"]),
        source_note=str(data.get("source_note", "")),
        min_track_width_m=_optional_float(data.get("min_track_width_m")),
        min_turning_diameter_m=_optional_float(data.get("min_turning_diameter_m")),
        max_straight_length_m=_optional_float(data.get("max_straight_length_m")),
        target_lap_length_m=lap_range,
        left_cone=str(data["left_cone"]),
        right_cone=str(data["right_cone"]),
        entry_exit_cone=str(data["entry_exit_cone"]),
        start_finish_cone=str(data["start_finish_cone"]),
        small_cone_base_m=float(data["small_cone_base_m"]),
        small_cone_height_m=float(data["small_cone_height_m"]),
        large_cone_base_m=float(data["large_cone_base_m"]),
        large_cone_height_m=float(data["large_cone_height_m"]),
        left_stripe=str(data.get("left_stripe", "white")),
        right_stripe=str(data.get("right_stripe", "black")),
        max_cone_spacing_m=_optional_float(data.get("max_cone_spacing_m")),
        enforce_corner_spacing=bool(data.get("enforce_corner_spacing", False)),
    )


def load_profiles(directory: Path | None = None) -> dict[str, RuleProfile]:
    folder = directory or PROFILE_DIR
    profiles: dict[str, RuleProfile] = {}
    for path in sorted(folder.glob("*.json")):
        profile = _load_profile(path)
        profiles[profile.id] = profile
    if not profiles:
        raise FileNotFoundError(f"No rule profiles found in {folder}")
    return profiles


PROFILES = load_profiles()


@dataclass
class GeneratorConfig:
    """All user-facing inputs. Lengths are meters."""

    seed: int = 1
    track_width: float = 3.5
    cone_spacing: float = 5.0
    track_type: str = "trackdrive"
    rules_profile: str = "us_fsae_driverless_2025"
    centerline: list[list[float]] | None = None
    # None selects a closed loop for procedural tracks. Custom curves can override it.
    closed_loop: bool | None = None
    smooth_centerline: bool = True
    allow_self_intersection: bool = False
    target_length_min: float | None = None
    target_length_max: float | None = None
    min_turning_diameter: float | None = None
    max_straight_length: float | None = None
    min_straight_length: float = 10.0
    num_corners: int | None = None
    num_straights: int | None = None
    track_width_tolerance: float = 0.05
    min_radius_tolerance: float = 0.2
    straight_length_tolerance: float = 1.0
    length_tolerance: float = 1.0
    # Curvature gentler than this radius (meters) is treated as a straight.
    straight_curvature_radius: float = 50.0
    sample_spacing: float = 0.5
    cone_spacing_min: float = 2.0
    cone_spacing_max: float | None = None
    cone_spacing_tolerance: float = 0.25
    corner_spacing_factor: float = 0.65
    corner_radius_threshold: float = 18.0
    cone_placement_variation: float = 0.0
    terrain_margin: float = 42.0
    terrain_width: float | None = None
    terrain_depth: float | None = None
    env_density: float = 1.0
    background_density: float = 1.0
    num_trees: int | None = None
    num_tents: int | None = None
    num_spectators: int | None = None
    num_barriers: int | None = None
    enable_trees: bool = True
    enable_tents: bool = True
    enable_spectators: bool = True
    enable_barriers: bool = True
    enable_buildings: bool = True
    enable_extra_props: bool = True
    enable_entry_exit: bool | None = None
    enable_start_finish: bool = True
    enable_track_limits: bool = True
    lighting: str = "noon"
    weather: str = "clear"
    surface_appearance: str = "asphalt"
    tree_clearance: float = 2.0
    tent_clearance: float = 3.0
    spectator_clearance: float = 4.0
    barrier_clearance: float = 1.5
    prop_clearance: float = 2.0
    warnings: list[str] = field(default_factory=list)

    def profile(self) -> RuleProfile:
        try:
            return PROFILES[self.rules_profile]
        except KeyError as exc:
            known = ", ".join(sorted(PROFILES))
            raise ValueError(f"Unknown rules profile '{self.rules_profile}'. Known profiles: {known}") from exc

    def wants_closed_loop(self) -> bool:
        if self.closed_loop is None:
            return True
        return bool(self.closed_loop)

    def wants_entry_exit(self) -> bool:
        """Autocross draws entry and exit lanes unless the user turns them off.

        Trackdrive and custom tracks do not, unless `enable_entry_exit` is set.
        The lanes are a short orange-coned corridor beside the start straight,
        not a second copy of the racing line. See docs/assumptions.md.
        """
        if self.enable_entry_exit is not None:
            return bool(self.enable_entry_exit)
        return self.track_type == "autocross"


@dataclass
class ResolvedLimits:
    """Concrete numbers used for generation and validation, with sources."""

    min_track_width: float
    min_track_width_source: str
    min_turning_diameter: float
    min_turning_diameter_source: str
    max_straight: float
    max_straight_source: str
    length_min: float
    length_max: float
    length_source: str
    nominal_cone_spacing: float
    min_cone_spacing: float
    max_cone_spacing: float
    cone_spacing_source: str
    tighten_corners: bool
    corner_spacing_factor: float
    warnings: list[str]


def _pick(override: float | None, profile_value: float | None, builtin: float, label: str, profile_name: str) -> tuple[float, str]:
    if override is not None:
        return float(override), f"config override ({label})"
    if profile_value is not None:
        return float(profile_value), f"{profile_name} ({label})"
    return float(builtin), f"generator default ({label}); not claimed as a rule of the selected profile"


def resolve_limits(config: GeneratorConfig) -> ResolvedLimits:
    """Merge the profile, explicit overrides, and generator defaults."""
    profile = config.profile()
    warnings: list[str] = []
    if config.track_type not in {"autocross", "trackdrive", "custom"}:
        raise ValueError(
            f"Unknown track type '{config.track_type}'. Use autocross, trackdrive, or custom."
        )
    if config.track_width <= 0.0 or config.cone_spacing <= 0.0:
        raise ValueError("Track width and cone spacing must be positive.")

    min_width, width_source = _pick(
        None,
        profile.min_track_width_m,
        BUILTIN_MIN_TRACK_WIDTH,
        "minimum track width",
        profile.name,
    )
    if config.track_width + 1e-6 < min_width and profile.min_track_width_m is not None:
        warnings.append(
            f"Requested track width {config.track_width:.2f} m is below the "
            f"{profile.name} minimum of {min_width:.2f} m. The track is still generated "
            "at the requested width and the profile check will fail."
        )

    min_diameter, diameter_source = _pick(
        config.min_turning_diameter,
        profile.min_turning_diameter_m,
        BUILTIN_MIN_TURNING_DIAMETER,
        "minimum turning diameter",
        profile.name,
    )
    max_straight, straight_source = _pick(
        config.max_straight_length,
        profile.max_straight_length_m,
        BUILTIN_MAX_STRAIGHT,
        "maximum straight length",
        profile.name,
    )
    if config.target_length_min is not None or config.target_length_max is not None:
        length_min = float(config.target_length_min if config.target_length_min is not None else BUILTIN_LAP_LENGTH[0])
        length_max = float(config.target_length_max if config.target_length_max is not None else BUILTIN_LAP_LENGTH[1])
        length_source = "config override (target lap length)"
    elif profile.target_lap_length_m is not None:
        length_min, length_max = profile.target_lap_length_m
        length_source = f"{profile.name} (target lap length)"
    else:
        length_min, length_max = BUILTIN_LAP_LENGTH
        length_source = "generator default (target lap length); not claimed as a rule of the selected profile"
    if length_max < length_min:
        raise ValueError("Target length minimum is greater than the maximum.")

    nominal = float(config.cone_spacing)
    min_spacing = min(float(config.cone_spacing_min), nominal)
    if config.cone_spacing_max is not None:
        max_spacing = float(config.cone_spacing_max)
        spacing_source = "config cone_spacing_max"
    else:
        max_spacing = nominal
        spacing_source = "configured cone spacing"
    if profile.max_cone_spacing_m is not None:
        cap = float(profile.max_cone_spacing_m)
        if nominal > cap + 1e-6:
            warnings.append(
                f"{profile.name} caps cone spacing at {cap:.2f} m. "
                f"Requested spacing {nominal:.2f} m was reduced to that cap."
            )
            nominal = cap
        max_spacing = min(max_spacing, cap)
        spacing_source = f"{profile.name} maximum cone spacing"
        min_spacing = min(min_spacing, nominal)
    if max_spacing < min_spacing:
        min_spacing = max_spacing

    # The general cone spec asks for tighter spacing in corners on every profile.
    # The Formula Student profile additionally records that this is required.
    tighten = True
    factor = min(max(float(config.corner_spacing_factor), 0.3), 1.0)
    if not tighten:
        factor = 1.0

    return ResolvedLimits(
        min_track_width=min_width,
        min_track_width_source=width_source,
        min_turning_diameter=min_diameter,
        min_turning_diameter_source=diameter_source,
        max_straight=max_straight,
        max_straight_source=straight_source,
        length_min=length_min,
        length_max=length_max,
        length_source=length_source,
        nominal_cone_spacing=nominal,
        min_cone_spacing=min_spacing,
        max_cone_spacing=max_spacing,
        cone_spacing_source=spacing_source,
        tighten_corners=tighten or profile.enforce_corner_spacing,
        corner_spacing_factor=factor,
        warnings=warnings,
    )


def config_to_dict(config: GeneratorConfig) -> dict:
    return asdict(config)


def config_from_dict(data: dict) -> GeneratorConfig:
    known = {item.name for item in GeneratorConfig.__dataclass_fields__.values()}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ValueError(f"Unknown config keys: {unknown}")
    return GeneratorConfig(**data)


def config_to_json(config: GeneratorConfig) -> str:
    return json.dumps(config_to_dict(config))


def config_from_json(text: str) -> GeneratorConfig:
    return config_from_dict(json.loads(text))
