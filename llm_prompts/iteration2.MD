Update our Blender procedural FSAE track generator based on the following spec changes to match real-world Formula Student Driverless environments:

Surface: Replace the narrow road-on-grass mesh with a wide-open asphalt tarmac lot surrounded by distant grass berms and tree lines. Remove the highway centerline. Add procedural weathered asphalt textures, tire skid marks, and realistic 'distractor' painted lines (old parking lines, skidpad arcs) on the tarmac.

cones: Materials: Use Principled BSDF with semi-matte PVC roughness (~0.38 modulated by subtle procedural noise), slight subsurface scattering (~0.1), and Z-height procedural dirt/scuffing near the base. Make white bands slightly glossy/retroreflective and the black band matte.

cones: Placement: Add seed-controlled random Z-rotation (0–360°), minor X/Y position jitter (±5 cm), slight tilt (±1.5°), and dynamic spacing that tightens from 5m on straights down to 2m in high-curvature turns.

Props & Layout: Replace generic buildings with a structured paddock zone containing clusters of peaked pop-up canopy tents, parked vans/trailers, and spectators grouped behind continuous safety barriers/fencing. Add a start/finish timing arch and high-vis track marshals near corners.

Lighting: Add procedural Nishita sky or HDRI lighting controlled by the random seed for realistic sun angles and shadows.