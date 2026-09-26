#!/usr/bin/env python3
"""Build the original, texture-free Built-in lighting rig for BOTH arena scenes.

The rig is deliberately separate from the environment prefab: candles belong
with their physical clusters; this asset supplies the stable key, five zones,
stained-glass influence, cheap translucent shafts, and dust emitter anchors.
Run generate_unity_guids.py after generating new assets to create their metas.
"""

import math
from pathlib import Path

from generate_unity_guids import guid_for

ROOT = Path(__file__).resolve().parent.parent
ARENA = ROOT / "Assets"
RIG = ARENA / "Prefabs/Arena/Arena_LightingRig.prefab"


def put(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.read_text(encoding="utf-8") != content:
        path.write_text(content, encoding="utf-8")


def material(name, shader, color, queue):
    path = f"Assets/Materials/Arena/{name}.mat"
    r, g, b, a = color
    put(ROOT / path, f"""%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!21 &2100000
Material:
  serializedVersion: 8
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_Name: {name}
  m_Shader: {{fileID: 4800000, guid: {guid_for('Assets/Art/Shaders/' + shader + '.shader')}, type: 3}}
  m_Parent: {{fileID: 0}}
  m_ModifiedProperties:
  m_ValidKeywords: []
  m_InvalidKeywords: []
  m_LightmapFlags: 4
  m_EnableInstancingVariants: 0
  m_DoubleSidedGI: 0
  m_CustomRenderQueue: {queue}
  stringTagMap:
    RenderType: Transparent
  disabledShaderPasses: []
  m_LockedProperties:
  m_SavedProperties:
    serializedVersion: 3
    m_TexEnvs: []
    m_Ints: []
    m_Floats: []
    m_Colors:
    - _Color: {{r: {r}, g: {g}, b: {b}, a: {a}}}
  m_BuildTextureStacks: []
""")
    return guid_for(path)


# Common unlit shaders, with different material colors for the two-tone room.
MATS = {
    "veil_moon": material("M_Arena_VeilMoon", "ArenaLightVeil", (0.39, 0.53, 0.82, 0.055), 3005),
    "veil_rose": material("M_Arena_VeilRose", "ArenaLightVeil", (0.69, 0.30, 0.43, 0.044), 3005),
    "veil_amber": material("M_Arena_VeilAmber", "ArenaLightVeil", (0.80, 0.52, 0.27, 0.042), 3005),
    "pool_blue": material("M_Arena_PoolBlue", "ArenaStainedLight", (0.34, 0.50, 0.89, 0.14), 3002),
    "pool_rose": material("M_Arena_PoolRose", "ArenaStainedLight", (0.72, 0.27, 0.42, 0.105), 3002),
    "pool_amber": material("M_Arena_PoolAmber", "ArenaStainedLight", (0.87, 0.51, 0.22, 0.11), 3002),
    "mist": material("M_Arena_GroundMist", "ArenaGroundMist", (0.15, 0.19, 0.25, 0.07), 3001),
    "dust": material("M_Arena_DustMote", "ArenaMote", (0.72, 0.81, 0.98, 0.38), 3006),
    "ash": material("M_Arena_AshMote", "ArenaMote", (0.53, 0.79, 0.82, 0.31), 3006),
}

# Four triangles per shaft, two per floor pool. UVs are 0..1 for procedural
# edge falloff in the shaders. Quads are unlit and do not cast shadows.
put(ARENA / "Models/Arena/SM_Arena_LightVeil_450.obj", """# Original two-sheet tapered veil, from window at y=4.1 to floor
# Pivot at the floor below the window; local -Z points inward
# UV x crosses the veil and UV y runs floor to window
o SM_Arena_LightVeil_450
v -2.5 0 -4.5
v 2.5 0 -4.5
v 1.15 4.1 0
v -1.15 4.1 0
v 0 0 -5.8
v 0 0 -3.2
v 0 4.1 0.65
v 0 4.1 -0.65
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vn 0 0 1
vn 1 0 0
f 1/1/1 2/2/1 3/3/1
f 1/1/1 3/3/1 4/4/1
f 5/1/2 6/2/2 7/3/2
f 5/1/2 7/3/2 8/4/2
""")
put(ARENA / "Models/Arena/SM_Arena_GlassPool_500.obj", """# Original 5m ground pool (no collider); UVs drive feather and glass pattern
o SM_Arena_GlassPool_500
v -2.5 0 -2.5
v 2.5 0 -2.5
v 2.5 0 2.5
v -2.5 0 2.5
vt 0 0
vt 1 0
vt 1 1
vt 0 1
vn 0 1 0
f 1/1/1 3/3/1 2/2/1
f 1/1/1 4/4/1 3/3/1
""")


def pp(file_id):
    return f"{{fileID: {file_id}}}"


def quat(euler):
    """The project's Unity transforms use yaw * pitch * roll."""
    x, y, z = (math.radians(v) / 2 for v in euler)
    sx, cx = math.sin(x), math.cos(x)
    sy, cy = math.sin(y), math.cos(y)
    sz, cz = math.sin(z), math.cos(z)
    return (cy*sx*cz + sy*cx*sz,
            sy*cx*cz - cy*sx*sz,
            cy*cx*sz - sy*sx*cz,
            cy*cx*cz + sy*sx*sz)


def aim(origin, target):
    dx, dy, dz = (b - a for a, b in zip(origin, target))
    yaw = math.degrees(math.atan2(dx, dz))
    pitch = -math.degrees(math.atan2(dy, math.hypot(dx, dz)))
    return (pitch, yaw, 0)


def component_header(class_id, file_id, name, go_id):
    return f"""--- !u!{class_id} &{file_id}
{name}:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {pp(go_id)}
"""


def game_object(go_id, name, component_ids):
    return (component_header(1, go_id, "GameObject", go_id).replace(
        f"  m_GameObject: {pp(go_id)}\n", "") +
        "  serializedVersion: 6\n  m_Component:\n" +
        "".join(f"  - component: {pp(i)}\n" for i in component_ids) +
        f"  m_Layer: 0\n  m_Name: {name}\n  m_TagString: Untagged\n"
        "  m_Icon: {fileID: 0}\n  m_NavMeshLayer: 0\n"
        "  m_StaticEditorFlags: 0\n  m_IsActive: 1\n")


def transform(go_id, parent_id, position, rotation, scale, children):
    q = quat(rotation)
    return (component_header(4, go_id + 1, "Transform", go_id) +
            "  serializedVersion: 2\n" +
            f"  m_LocalRotation: {{x: {q[0]:.7f}, y: {q[1]:.7f}, z: {q[2]:.7f}, w: {q[3]:.7f}}}\n" +
            f"  m_LocalPosition: {{x: {position[0]:.4f}, y: {position[1]:.4f}, z: {position[2]:.4f}}}\n" +
            f"  m_LocalScale: {{x: {scale[0]:.4f}, y: {scale[1]:.4f}, z: {scale[2]:.4f}}}\n" +
            "  m_ConstrainProportionsScale: 0\n" +
            ("  m_Children:\n" + "".join(f"  - {pp(c)}\n" for c in children)
             if children else "  m_Children: []\n") +
            f"  m_Father: {pp(parent_id)}\n" +
            f"  m_LocalEulerAnglesHint: {{x: {rotation[0]:.3f}, y: {rotation[1]:.3f}, z: {rotation[2]:.3f}}}\n")


# A maximum of ONE shadow-casting light (soft moon). All colored accents and
# practicals are shadowless. m_RenderMode: 1 = important, 2 = not important.
def light(go_id, light_type, color, intensity, distance, angle=30, shadows=False,
          mask=4294967295, important=False):
    r, g, b = color
    return component_header(108, go_id + 2, "Light", go_id) + f"""  m_Enabled: 1
  serializedVersion: 10
  m_Type: {light_type}
  m_Shape: 0
  m_Color: {{r: {r}, g: {g}, b: {b}, a: 1}}
  m_Intensity: {intensity}
  m_Range: {distance}
  m_SpotAngle: {angle}
  m_InnerSpotAngle: {round(angle * 0.68, 2)}
  m_CookieSize: 10
  m_Shadows:
    m_Type: {2 if shadows else 0}
    m_Resolution: -1
    m_CustomResolution: -1
    m_Strength: {0.68 if shadows else 1}
    m_Bias: 0.04
    m_NormalBias: 0.25
    m_NearPlane: 0.2
  m_Cookie: {{fileID: 0}}
  m_DrawHalo: 0
  m_Flare: {{fileID: 0}}
  m_RenderMode: {1 if important else 2}
  m_CullingMask:
    serializedVersion: 2
    m_Bits: {mask}
  m_RenderingLayerMask: 1
  m_Lightmapping: 4
  m_LightShadowCasterMode: 0
  m_AreaSize: {{x: 1, y: 1}}
  m_BounceIntensity: 1
  m_ColorTemperature: 6570
  m_UseColorTemperature: 0
  m_ShadowRadius: 0
  m_ShadowAngle: 0
"""


def mesh(go_id, model, mat):
    return component_header(33, go_id + 2, "MeshFilter", go_id) + f"""  m_Mesh: {{fileID: 4300000, guid: {guid_for('Assets/Models/Arena/' + model)}, type: 3}}
""" + component_header(23, go_id + 3, "MeshRenderer", go_id) + f"""  m_Enabled: 1
  m_CastShadows: 0
  m_ReceiveShadows: 0
  m_DynamicOccludee: 0
  m_StaticShadowCaster: 0
  m_MotionVectors: 0
  m_LightProbeUsage: 0
  m_ReflectionProbeUsage: 0
  m_RayTracingMode: 2
  m_RayTraceProcedural: 0
  m_RenderingLayerMask: 1
  m_RendererPriority: 0
  m_Materials:
  - {{fileID: 2100000, guid: {MATS[mat]}, type: 2}}
  m_StaticBatchInfo:
    firstSubMesh: 0
    subMeshCount: 0
  m_StaticBatchRoot: {{fileID: 0}}
  m_ProbeAnchor: {{fileID: 0}}
  m_LightmapVolume: {{fileID: 0}}
  m_ScaleInLightmap: 0
  m_ReceiveGI: 0
  m_PreserveUVs: 0
  m_IgnoreNormalsForChartDetection: 0
  m_ImportantGI: 0
  m_StitchLightmapSeams: 0
  m_SelectedEditorRenderState: 3
  m_MinimumChartSize: 4
  m_AutoUVMaxDistance: 0.5
  m_AutoUVMaxAngle: 89
  m_LightmapParameters: {{fileID: 0}}
  m_SortingLayerID: 0
  m_SortingLayer: 0
  m_SortingOrder: 0
  m_AdditionalVertexStreams: {{fileID: 0}}
"""


class LightingRig:
    def __init__(self):
        self.groups = {
            "entrance": (2000, "01_Entrance", (0, 0, -15)),
            "central": (3000, "02_CentralArena", (0, 0, 0)),
            "corners": (4000, "03_Corners_and_Glass", (0, 0, 0)),
            "platform": (5000, "04_ElevatedPlatform", (0, 0, 0)),
            "ritual": (6000, "05_RitualArea", (0, 0, 0)),
        }
        self.children = {key: [] for key in self.groups}
        self.objects = []
        self.next_id = 10000
        self.motes = []
        self.ash = None
        self.key = None
        self.subject = None
        self.central_fill = None
        self.platform_fill = None

    def add(self, group, name, position, rotation=(0, 0, 0), scale=(1, 1, 1),
            component=None, **properties):
        go_id = self.next_id
        self.next_id += 10
        parent = self.groups[group][0] + 1
        self.children[group].append(go_id + 1)
        component_ids = [go_id + 1]
        if component == "light":
            component_ids.append(go_id + 2)
        elif component == "mesh":
            component_ids.extend((go_id + 2, go_id + 3))
        yaml = game_object(go_id, name, component_ids)
        yaml += transform(go_id, parent, position, rotation, scale, [])
        if component == "light":
            yaml += light(go_id, **properties)
        elif component == "mesh":
            yaml += mesh(go_id, properties["model"], properties["mat"])
        self.objects.append(yaml)
        return go_id + 1, go_id + 2

    def build(self):
        zone_guids = [pp(self.groups[k][0] + 1) for k in self.groups]
        root = game_object(1000, "Arena_LightingRig", [1001, 1002, 1003])
        root += transform(1000, 0, (0, 0, 0), (0, 0, 0), (1, 1, 1),
                          [self.groups[k][0] + 1 for k in self.groups])
        root += component_header(114, 1002, "MonoBehaviour", 1000) + f"""  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {guid_for('Assets/Scripts/Arena/ArenaLightingZones.cs')}, type: 3}}
  m_Name:
  m_EditorClassIdentifier:
  entranceZone: {zone_guids[0]}
  centralArenaZone: {zone_guids[1]}
  cornersZone: {zone_guids[2]}
  elevatedPlatformZone: {zone_guids[3]}
  ritualAreaZone: {zone_guids[4]}
  moonKey: {pp(self.key)}
  subjectFill: {pp(self.subject)}
  centralArenaFill: {pp(self.central_fill)}
  elevatedPlatformFill: {pp(self.platform_fill)}
"""
        root += component_header(114, 1003, "MonoBehaviour", 1000) + f"""  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {guid_for('Assets/Scripts/Arena/ArenaAtmosphereParticles.cs')}, type: 3}}
  m_Name:
  m_EditorClassIdentifier:
  moteAnchors:
"""
        root += "".join(f"  - {pp(anchor)}\n" for anchor in self.motes)
        root += f"""  moteMaterial: {{fileID: 2100000, guid: {MATS['dust']}, type: 2}}
  motesPerSecond: 1.15
  ritualAshAnchor: {pp(self.ash)}
  ashMaterial: {{fileID: 2100000, guid: {MATS['ash']}, type: 2}}
  ashPerSecond: 0.55
"""
        groups = "".join(game_object(go, name, [go + 1]) +
                         transform(go, 1001, offset, (0, 0, 0), (1, 1, 1),
                                   self.children[key])
                         for key, (go, name, offset) in self.groups.items())
        return "%YAML 1.1\n%TAG !u! tag:unity3d.com,2011:\n" + root + groups + "".join(self.objects)


rig = LightingRig()

# 01: The south doorway is a warm landmark, but cannot wash out the floor.
for side in (-1, 1):
    rig.add("entrance", f"Warm_sconce_{side:+d}", (2.3 * side, 2.5, -1.2),
        component="light", light_type=2, color=(1.0, 0.57, 0.29),
        intensity=0.56, distance=6.3)

# Stable moon and neutral character-only fill. The latter excludes *all* stone,
# so Player / future Enemy silhouettes survive a shadowed corner without
# flattening the gothic architecture. Enemy layer is only RESERVED here.
rig.key = rig.add("central", "Moon_key_soft_shadows", (0, 12, 0),
    (52, -29, 0), component="light", light_type=1, color=(0.68, 0.76, 0.96),
    intensity=0.86, distance=10, shadows=True, important=True)[1]
rig.subject = rig.add("central", "Subjects_only_Player_Enemy", (0, 9, -5),
    (39, 12, 0), component="light", light_type=1, color=(0.82, 0.85, 0.93),
    intensity=0.34, distance=10, mask=768, important=True)[1]
rig.central_fill = rig.add("central", "Combat_floor_broad_fill", (0, 11, 0),
    (90, 0, 0), component="light", light_type=0, color=(0.64, 0.73, 0.87),
    intensity=0.31, distance=21, angle=105, important=True)[1]

# The four alcoves retain shadow and shape, but never become blind spots.
for n, (x, z) in enumerate(((-12, -12), (-12, 12), (12, 12), (12, -12))):
    rig.add("corners", f"Alcove_{n}_low_fill", (x, 3.4, z),
        (90, 0, 0), component="light", light_type=0, color=(0.45, 0.52, 0.68),
        intensity=0.28, distance=8.5, angle=78)

# Three real colored spots graze the stone; three feathered additive pools
# and fake volumes convey the patterned glass without costly spot cookies.
# 67.5 and 112.5 degrees are the two north windows; 157.5 is the west window.
for label, degrees, tint, veil, pool, strength in (
    ("Blue", 67.5, (0.34, 0.51, 0.86), "veil_moon", "pool_blue", 0.39),
    ("Rose", 112.5, (0.68, 0.28, 0.42), "veil_rose", "pool_rose", 0.27),
    ("Amber", 157.5, (0.74, 0.45, 0.24), "veil_amber", "pool_amber", 0.25),
):
    theta = math.radians(degrees)
    ux, uz = math.cos(theta), math.sin(theta)
    source = (18.1 * ux, 4.6, 18.1 * uz)
    target = (13.4 * ux, 0.52, 13.4 * uz)
    rig.add("corners", f"Glass_{label}_grazing_spot", source,
        aim(source, target), component="light", light_type=0, color=tint,
        intensity=strength, distance=9.5, angle=48, mask=1025)
    rig.add("corners", f"Glass_{label}_soft_veil", (18.1 * ux, 0.5, 18.1 * uz),
        (0, 90 - degrees, 0), component="mesh", model="SM_Arena_LightVeil_450.obj", mat=veil)
    rig.add("corners", f"Glass_{label}_floor_pool", (14.0 * ux, 0.535, 14.0 * uz),
        (0, -degrees, 0), (1.12, 1, 0.95), component="mesh", model="SM_Arena_GlassPool_500.obj", mat=pool)
    if label != "Amber":  # Two small dust fields; no particles across the arena.
        anchor, _ = rig.add("corners", f"Dust_anchor_{label}",
                             (15.1 * ux, 2.2, 15.1 * uz))
        rig.motes.append(anchor)

# The raised dais has a steady, nearly neutral pool for any future subject.
rig.platform_fill = rig.add("platform", "Dais_silhouette_fill", (0, 8.2, 0.8),
    (90, 0, 0), component="light", light_type=0, color=(0.78, 0.84, 0.98),
    intensity=0.38, distance=11, angle=78, important=True)[1]

# Ritual emission remains subordinate to silhouettes and future telegraphs.
# Only Default + Environment receive these two tiny cyan accents.
rig.add("ritual", "Rite_inner_stone", (0, 1.1, 0),
    component="light", light_type=2, color=(0.26, 0.62, 0.67),
    intensity=0.23, distance=4.1, mask=1025)
rig.add("ritual", "Altar_incense_glow", (0, 1.7, 11.6),
    component="light", light_type=2, color=(0.31, 0.60, 0.68),
    intensity=0.25, distance=4.3, mask=1025)
rig.ash, _ = rig.add("ritual", "Ash_anchor_at_altar", (0, 2.1, 11.6))

put(RIG, rig.build())
print(f"Wrote {RIG.relative_to(ROOT)} with 5 zones and {len(rig.objects)} lighting/VFX children")
