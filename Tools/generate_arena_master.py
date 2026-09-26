#!/usr/bin/env python3
"""
Generate master arena prefab Arena_RitualChamber_MeshKit using the new mesh kit.
Assembles floor, walls, pillars, arches, windows, stairs, platform, statues, chains, wood, candles, ritual, debris, doors, deco.
"""

import os, uuid, math, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PREFAB = os.path.join(ROOT, "Assets/Prefabs/Arena/Arena_RitualChamber_MeshKit.prefab")

NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "vespershade://unity-project")
def guid_for(rel):
    return uuid.uuid5(NAMESPACE, rel.replace(os.sep, "/")).hex

def parse_obj_mats(obj_path):
    mats=[]
    with open(obj_path,'r') as f:
        for line in f:
            if line.startswith("usemtl "):
                m=line.strip().split()[1]
                if m not in mats:
                    mats.append(m)
    return mats

MAT_NAME_TO_PATH = {
    "M_Arena_StoneFloor": "Assets/Materials/Arena/M_Arena_StoneFloor.mat",
    "M_Arena_StoneFloor_Ritual": "Assets/Materials/Arena/M_Arena_StoneFloor_Ritual.mat",
    "M_Arena_StoneWall": "Assets/Materials/Arena/M_Arena_StoneWall.mat",
    "M_Arena_StonePillar": "Assets/Materials/Arena/M_Arena_StonePillar.mat",
    "M_Arena_Metal_Chain": "Assets/Materials/Arena/M_Arena_Metal_Chain.mat",
    "M_Arena_Wood_Rotted": "Assets/Materials/Arena/M_Arena_Wood_Rotted.mat",
    "M_Arena_Statue_Eroded": "Assets/Materials/Arena/M_Arena_Statue_Eroded.mat",
    "M_Arena_Candle_Wax": "Assets/Materials/Arena/M_Arena_Candle_Wax.mat",
    "M_Arena_Candle_Flame": "Assets/Materials/Arena/M_Arena_Candle_Flame.mat",
    "M_Arena_RitualMarking": "Assets/Materials/Arena/M_Arena_RitualMarking.mat",
    "M_Arena_Fog_Plane": "Assets/Materials/Arena/M_Arena_Fog_Plane.mat",
    "M_Arena_Brazier_Metal": "Assets/Materials/Arena/M_Arena_Brazier_Metal.mat",
    "M_Arena_Glass_Blue": "Assets/Materials/Arena/M_Arena_Glass_Blue.mat",
    "M_Arena_Glass_Red": "Assets/Materials/Arena/M_Arena_Glass_Red.mat",
    "M_Arena_Glass_Amber": "Assets/Materials/Arena/M_Arena_Glass_Amber.mat",
}
MAT_GUIDS = {k: guid_for(v) for k,v in MAT_NAME_TO_PATH.items()}

# Script GUIDs
GUID_ArenaBounds = guid_for("Assets/Scripts/Arena/ArenaBounds.cs")
GUID_ArenaFog = guid_for("Assets/Scripts/Arena/ArenaFogController.cs")
GUID_ArenaLighting = guid_for("Assets/Scripts/Arena/ArenaLightingController.cs")

# Model GUIDs cache
MODEL_GUIDS = {}
def get_model_guid(fname):
    if fname not in MODEL_GUIDS:
        MODEL_GUIDS[fname] = guid_for(f"Assets/Models/Arena/{fname}")
    return MODEL_GUIDS[fname]

# Helper to create prefab YAML
class PrefabBuilder:
    def __init__(self):
        self.objects = []  # list of yaml strings
        self.next_id = 1000
        self.root_children = []  # list of transform fileIDs
        self.root_go = 1000
        self.root_tr = 1001

    def alloc_id(self, count=1):
        nid = self.next_id
        self.next_id += count*10  # step
        # Ensure we don't clash with root ids 1000-1004
        if self.next_id < 2000:
            self.next_id = 2000
        return nid

    def add_root(self):
        # build_file writes the root after all IDs / child references are known.
        self.objects.append("")  # preserve the existing child fileIDs
        self.next_id = 2000
        self.fog_ids = []
        self.candle_ids = []
        self.shaft_ids = []
        self.ritual_ids = []

    def add_mesh_object(self, name, model_file, position, rotation_euler, scale, has_collider, layer, collider_size=None, is_static=False):
        """
        position (x,y,z), rotation_euler (x,y,z) in degrees, scale (x,y,z)
        """
        go_id = self.alloc_id()
        tr_id = go_id+1
        mf_id = go_id+2
        mr_id = go_id+3
        col_id = go_id+4 if has_collider else None

        # Compute rotation quaternion from euler (Unity order ZXY? We'll approximate: use euler to quat conversion)
        # Simple conversion: we need quaternion for Y rotation primarily. For general, we will compute using python.
        # We'll implement euler to quat: Unity uses ZXY? Actually Transform's m_LocalRotation is quaternion, but we can provide euler hint and let Unity compute? The yaml stores both quaternion and euler hint. We should compute quaternion correctly for Y rotation.
        # For simplicity, if rotation is only Y, we can compute quat.
        # For more complex, we will compute using standard XYZ order (pitch X, yaw Y, roll Z) with Unity's convention: quaternion = qy * qx * qz? Let's use typical: Unity's Euler order is ZXY. We'll approximate with yaw only for most objects.
        # We'll compute quaternion for given euler in degrees: 
        # We'll use function to convert euler to quat in Unity's ZXY order.
        def euler_to_quat(euler_deg):
            # euler_deg = (x,y,z) in degrees
            # Convert to radians
            x = math.radians(euler_deg[0])
            y = math.radians(euler_deg[1])
            z = math.radians(euler_deg[2])
            # Unity's order: Z * X * Y? Let's check: typical conversion for ZXY:
            # We'll use standard: qx = rotation around X, qy around Y, qz around Z
            # Combined as q = qy * qx * qz for YXZ? Let's try YXZ which is common for FPS (yaw, pitch, roll)
            # Compute half angles
            cx = math.cos(x*0.5); sx = math.sin(x*0.5)
            cy = math.cos(y*0.5); sy = math.sin(y*0.5)
            cz = math.cos(z*0.5); sz = math.sin(z*0.5)
            # Y * X * Z order
            # qy * qx * qz
            # qx = (sx,0,0,cx), qy = (0,sy,0,cy), qz = (0,0,sz,cz)
            # Multiply qy * qx
            # q = qy * qx:
            # x = cy*sx, y = sy*cx, z = -sy*sx, w = cy*cx
            # Then q * qz:
            # final = (qy*qx) * qz
            # Let's compute stepwise
            # qyx = qy * qx
            qyx_x = cy*sx
            qyx_y = sy*cx
            qyx_z = -sy*sx
            qyx_w = cy*cx
            # qyx * qz
            q_x = qyx_w*0 + qyx_x*cz + qyx_y*sz - qyx_z*0  # Actually quaternion multiplication formula: (w1*x2 + x1*w2 + y1*z2 - z1*y2)
            # Let's use generic multiplication: (x1,y1,z1,w1)*(x2,y2,z2,w2) = 
            # x = w1*x2 + x1*w2 + y1*z2 - z1*y2
            # y = w1*y2 - x1*z2 + y1*w2 + z1*x2
            # z = w1*z2 + x1*y2 - y1*x2 + z1*w2
            # w = w1*w2 - x1*x2 - y1*y2 - z1*z2
            x1,y1,z1,w1 = qyx_x, qyx_y, qyx_z, qyx_w
            x2,y2,z2,w2 = 0,0,sz,cz
            qx = w1*x2 + x1*w2 + y1*z2 - z1*y2
            qy = w1*y2 - x1*z2 + y1*w2 + z1*x2
            qz = w1*z2 + x1*y2 - y1*x2 + z1*w2
            qw = w1*w2 - x1*x2 - y1*y2 - z1*z2
            return (qx,qy,qz,qw)

        qx,qy,qz,qw = euler_to_quat(rotation_euler)

        m_guid = get_model_guid(model_file)
        obj_path = os.path.join(ROOT, f"Assets/Models/Arena/{model_file}")
        mats = parse_obj_mats(obj_path) if os.path.exists(obj_path) else ["M_Arena_StoneWall"]
        mat_guids = []
        for mname in mats:
            mg = MAT_GUIDS.get(mname, MAT_GUIDS["M_Arena_StoneWall"])
            mat_guids.append(mg)
        # The MeshKit's original fog slabs were opaque-edged and under the floor.
        # A separate unlit, feathered mist material now keeps them in the periphery.
        if name.startswith("Fog_Volume_"):
            mat_guids = [guid_for("Assets/Materials/Arena/M_Arena_GroundMist.mat")]
        casts_shadows = not name.startswith(("Fog_Volume_", "Window_Glass_",
                                               "Candle_Cluster_", "Ritual_Plate_",
                                               "Ritual_Rune_", "Ritual_Center_"))

        # Determine collider size if not provided: try parse from filename
        if has_collider and collider_size is None:
            # default 1,1,1
            collider_size = (1,1,1)
            mm = re.search(r'(\d+)x(\d+)x(\d+)', model_file)
            if mm:
                try:
                    w = int(mm.group(1))/100.0
                    h = int(mm.group(2))/100.0
                    d = int(mm.group(3))/100.0
                    collider_size = (w,h,d)
                except:
                    pass

        # Build yaml
        yaml = f"""--- !u!1 &{go_id}
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  serializedVersion: 6
  m_Component:
  - component: {{fileID: {tr_id}}}
  - component: {{fileID: {mf_id}}}
  - component: {{fileID: {mr_id}}}
"""
        if has_collider:
            yaml += f"  - component: {{fileID: {col_id}}}\n"
        yaml += f"""  m_Layer: {layer}
  m_Name: {name}
  m_TagString: Untagged
  m_Icon: {{fileID: 0}}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 1
--- !u!4 &{tr_id}
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go_id}}}
  serializedVersion: 2
  m_LocalRotation: {{x: {qx:.6f}, y: {qy:.6f}, z: {qz:.6f}, w: {qw:.6f}}}
  m_LocalPosition: {{x: {position[0]:.4f}, y: {position[1]:.4f}, z: {position[2]:.4f}}}
  m_LocalScale: {{x: {scale[0]:.4f}, y: {scale[1]:.4f}, z: {scale[2]:.4f}}}
  m_ConstrainProportionsScale: 0
  m_Children: []
  m_Father: {{fileID: 1001}}
  m_LocalEulerAnglesHint: {{x: {rotation_euler[0]:.2f}, y: {rotation_euler[1]:.2f}, z: {rotation_euler[2]:.2f}}}
--- !u!33 &{mf_id}
MeshFilter:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go_id}}}
  m_Mesh: {{fileID: 4300000, guid: {m_guid}, type: 3}}
--- !u!23 &{mr_id}
MeshRenderer:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go_id}}}
  m_Enabled: 1
  m_CastShadows: {1 if casts_shadows else 0}
  m_ReceiveShadows: {1 if casts_shadows else 0}
  m_DynamicOccludee: 1
  m_StaticShadowCaster: 0
  m_MotionVectors: 1
  m_LightProbeUsage: 1
  m_ReflectionProbeUsage: 1
  m_RayTracingMode: 2
  m_RayTraceProcedural: 0
  m_RenderingLayerMask: 1
  m_RendererPriority: 0
  m_Materials:
"""
        for mg in mat_guids:
            yaml += f"  - {{fileID: 2100000, guid: {mg}, type: 2}}\n"
        yaml += """  m_StaticBatchInfo:
    firstSubMesh: 0
    subMeshCount: 0
  m_StaticBatchRoot: {fileID: 0}
  m_ProbeAnchor: {fileID: 0}
  m_LightmapVolume: {fileID: 0}
  m_ScaleInLightmap: 1
  m_ReceiveGI: 1
  m_PreserveUVs: 0
  m_IgnoreNormalsForChartDetection: 0
  m_ImportantGI: 0
  m_StitchLightmapSeams: 1
  m_SelectedEditorRenderState: 3
  m_MinimumChartSize: 4
  m_AutoUVMaxDistance: 0.5
  m_AutoUVMaxAngle: 89
  m_LightmapParameters: {fileID: 0}
  m_SortingLayerID: 0
  m_SortingLayer: 0
  m_SortingOrder: 0
  m_AdditionalVertexStreams: {fileID: 0}
"""
        if has_collider:
            cx,cy,cz = 0, collider_size[1]*0.5, 0
            yaml += f"""--- !u!65 &{col_id}
BoxCollider:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go_id}}}
  m_Material: {{fileID: 0}}
  m_IsTrigger: 0
  m_Enabled: 1
  serializedVersion: 2
  m_Size: {{x: {collider_size[0]:.4f}, y: {collider_size[1]:.4f}, z: {collider_size[2]:.4f}}}
  m_Center: {{x: {cx:.4f}, y: {cy:.4f}, z: {cz:.4f}}}
"""
        self.objects.append(yaml)
        self.root_children.append(tr_id)
        if name.startswith("Fog_Volume_"):
            self.fog_ids.append(tr_id)
        elif name.startswith(("Ritual_Plate_", "Ritual_Rune_", "Ritual_Center_")):
            self.ritual_ids.append(mr_id)
        return go_id

    def add_light(self, name, position, rotation_euler, light_type, color, intensity,
                  range_val, spot_angle=38, enabled=True):
        go_id = self.alloc_id()
        tr_id = go_id+1
        light_id = go_id+2

        def euler_to_quat(euler_deg):
            x = math.radians(euler_deg[0]); y = math.radians(euler_deg[1]); z = math.radians(euler_deg[2])
            cx = math.cos(x*0.5); sx = math.sin(x*0.5)
            cy = math.cos(y*0.5); sy = math.sin(y*0.5)
            cz = math.cos(z*0.5); sz = math.sin(z*0.5)
            qyx_x = cy*sx; qyx_y = sy*cx; qyx_z = -sy*sx; qyx_w = cy*cx
            x1,y1,z1,w1 = qyx_x, qyx_y, qyx_z, qyx_w
            x2,y2,z2,w2 = 0,0,sz,cz
            qx = w1*x2 + x1*w2 + y1*z2 - z1*y2
            qy = w1*y2 - x1*z2 + y1*w2 + z1*x2
            qz = w1*z2 + x1*y2 - y1*x2 + z1*w2
            qw = w1*w2 - x1*x2 - y1*y2 - z1*z2
            return (qx,qy,qz,qw)
        qx,qy,qz,qw = euler_to_quat(rotation_euler)

        # light type: 0 spot, 1 directional, 2 point
        yaml = f"""--- !u!1 &{go_id}
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  serializedVersion: 6
  m_Component:
  - component: {{fileID: {tr_id}}}
  - component: {{fileID: {light_id}}}
  m_Layer: 0
  m_Name: {name}
  m_TagString: Untagged
  m_Icon: {{fileID: 0}}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 1
--- !u!4 &{tr_id}
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go_id}}}
  serializedVersion: 2
  m_LocalRotation: {{x: {qx:.6f}, y: {qy:.6f}, z: {qz:.6f}, w: {qw:.6f}}}
  m_LocalPosition: {{x: {position[0]:.4f}, y: {position[1]:.4f}, z: {position[2]:.4f}}}
  m_LocalScale: {{x: 1, y: 1, z: 1}}
  m_ConstrainProportionsScale: 0
  m_Children: []
  m_Father: {{fileID: 1001}}
  m_LocalEulerAnglesHint: {{x: {rotation_euler[0]:.2f}, y: {rotation_euler[1]:.2f}, z: {rotation_euler[2]:.2f}}}
--- !u!108 &{light_id}
Light:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {go_id}}}
  m_Enabled: {1 if enabled else 0}
  serializedVersion: 10
  m_Type: {light_type}
  m_Shape: 0
  m_Color: {{r: {color[0]}, g: {color[1]}, b: {color[2]}, a: 1}}
  m_Intensity: {intensity}
  m_Range: {range_val}
  m_SpotAngle: {spot_angle}
  m_InnerSpotAngle: 21.80208
  m_CookieSize: 10
  m_Shadows:
    m_Type: 0
    m_Resolution: -1
    m_CustomResolution: -1
    m_Strength: 1
    m_Bias: 0.04
    m_NormalBias: 0.25
    m_NearPlane: 0.2
  m_Cookie: {{fileID: 0}}
  m_DrawHalo: 0
  m_Flare: {{fileID: 0}}
  m_RenderMode: 2
  m_CullingMask:
    serializedVersion: 2
    m_Bits: 4294967295
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
        self.objects.append(yaml)
        self.root_children.append(tr_id)
        if enabled:
            if name.startswith("Candle_Light_"):
                self.candle_ids.append(light_id)
            elif name.startswith("MoonShaft_"):
                self.shaft_ids.append(light_id)

    def build_file(self):
        def refs(ids):
            return "".join(f"  - {{fileID: {fid}}}\n" for fid in ids)

        # Build root with children list
        children_yaml = ""
        for cid in self.root_children:
            children_yaml += f"  - {{fileID: {cid}}}\n"
        # Reconstruct root yaml with correct children
        root_yaml = f"""%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!1 &1000
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  serializedVersion: 6
  m_Component:
  - component: {{fileID: 1001}}
  - component: {{fileID: 1002}}
  - component: {{fileID: 1003}}
  - component: {{fileID: 1004}}
  m_Layer: 0
  m_Name: Arena_RitualChamber_MeshKit
  m_TagString: Untagged
  m_Icon: {{fileID: 0}}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 1
--- !u!4 &1001
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 1000}}
  serializedVersion: 2
  m_LocalRotation: {{x: 0, y: 0, z: 0, w: 1}}
  m_LocalPosition: {{x: 0, y: 0, z: 0}}
  m_LocalScale: {{x: 1, y: 1, z: 1}}
  m_ConstrainProportionsScale: 0
  m_Children:
{children_yaml}  m_Father: {{fileID: 0}}
  m_LocalEulerAnglesHint: {{x: 0, y: 0, z: 0}}
--- !u!114 &1002
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 1000}}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {GUID_ArenaBounds}, type: 3}}
  m_Name: 
  m_EditorClassIdentifier: 
  playableRadius: 19
  clearCombatRadius: 12
  centralPlatformRadius: 5
  wallHeight: 16
  arenaCenter: {{fileID: 0}}
--- !u!114 &1003
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 1000}}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {GUID_ArenaFog}, type: 3}}
  m_Name: 
  m_EditorClassIdentifier: 
  fogPlanes:
{refs(self.fog_ids)}  driftAmplitude: 0.25
  opacityBreathing: 0.1
  baseFogDensity: 0.01
  extraFogDensity: 0.0015
  fogColor: {{r: 0.027, g: 0.033, b: 0.05, a: 1}}
  driftSpeed: 0.11
  breathingSpeed: 0.19
--- !u!114 &1004
MonoBehaviour:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 1000}}
  m_Enabled: 1
  m_EditorHideFlags: 0
  m_Script: {{fileID: 11500000, guid: {GUID_ArenaLighting}, type: 3}}
  m_Name: 
  m_EditorClassIdentifier: 
  candleLights:
{refs(self.candle_ids)}  candleFlickerAmplitude: 0.12
  candleFlickerSpeed: 5.2
  moonShafts:
{refs(self.shaft_ids)}  shaftBreathing: 0.035
  ritualEmissiveRenderers:
{refs(self.ritual_ids)}  ritualPulseSpeed: 0.32
  ritualPulseStrength: 0.14
"""
        return root_yaml + "".join(self.objects[1:])

def main():
    builder = PrefabBuilder()
    builder.add_root()

    # --- FLOOR ---
    # Central platform Tier1 14m
    builder.add_mesh_object("Platform_Tier1_14m", "SM_Arena_Platform_Cylinder_1400x030.obj", (0,0,0), (0,0,0), (1,1,1), True, 10, collider_size=(14,0.3,14))
    # Tier2 10m on top
    builder.add_mesh_object("Platform_Tier2_10m", "SM_Arena_Platform_Cylinder_1000x030.obj", (0,0.3,0), (0,0,0), (1,1,1), True, 10, collider_size=(10,0.3,10))
    # Rim
    builder.add_mesh_object("Platform_Rim", "SM_Arena_Platform_Rim_1400x015.obj", (0,0,0), (0,0,0), (1,1,1), False, 0)
    # Ritual center
    builder.add_mesh_object("Ritual_Center_3_2m", "SM_Arena_Ritual_Circle_320x002x320.obj", (0,0.62,0), (0,0,0), (1,1,1), False, 0)
    # Floor tiles grid 8x8 covering -16 to 16 step 4, only within radius 15 but outside central 7
    for x in range(-16, 17, 4):
        for z in range(-16, 17, 4):
            dist = math.sqrt(x*x + z*z)
            if dist < 7.5:  # inside platform, skip
                continue
            if dist > 15:
                continue
            # Add floor tile 4x4
            builder.add_mesh_object(f"Floor_4x4_{x}_{z}", "SM_Arena_Floor_400x400x050.obj", (x,0,z), (0,0,0), (1,1,1), True, 10, collider_size=(4,0.5,4))

    # Outer wedge ring 16 wedges at radius mid 17
    for i in range(16):
        angle_deg = i*22.5
        angle_rad = math.radians(angle_deg)
        r_mid = 17.0
        x = math.cos(angle_rad)*r_mid
        z = math.sin(angle_rad)*r_mid
        # Wedge pivot is at its center, we already shifted by r_mid in model, so we need to place at x,z and rotate by angle
        builder.add_mesh_object(f"Floor_Wedge_{i}", "SM_Arena_Floor_Wedge_22_5_R15_19.obj", (x,0,z), (0, -angle_deg, 0), (1,1,1), True, 10, collider_size=(4,0.5,4))

    # Ritual plates at r=7, 8 decals
    for i in range(8):
        ang = i*45
        rad = math.radians(ang)
        r=7.0
        x = math.cos(rad)*r
        z = math.sin(rad)*r
        builder.add_mesh_object(f"Ritual_Plate_{i}", "SM_Arena_Floor_Ritual_Plate_220x065.obj", (x,0.515,z), (0, -ang, 0), (1,1,1), False, 0)

    # --- WALLS ---
    # 16 walls around radius 19
    for i in range(16):
        ang_deg = i*22.5
        ang_rad = math.radians(ang_deg)
        r = 19.0
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        # wall faces inward: rotation Y = 90 - ang? Actually wall should be tangent to circle, so rotation = -ang + 90
        rot_y = -ang_deg + 90
        # alternate solid and window
        if i % 2 == 0:
            model = "SM_Arena_Wall_400x400x100.obj"
            # For full height, we need 4 stacked? Use 16m wall: use 400x1600
            model = "SM_Arena_Wall_400x1600x110.obj"
            builder.add_mesh_object(f"Wall_Solid_{i}", model, (x,0,z), (0, rot_y, 0), (1,1,1), True, 10, collider_size=(4,16,1.1))
            # Add base and cornice
            builder.add_mesh_object(f"Wall_Base_{i}", "SM_Arena_Wall_Base_400x050x110.obj", (x,0,z), (0, rot_y, 0), (1,1,1), False, 0)
            builder.add_mesh_object(f"Wall_Cornice_{i}", "SM_Arena_Wall_Cornice_400x030x020.obj", (x,14,z), (0, rot_y, 0), (1,1,1), False, 0)
        else:
            model = "SM_Arena_Wall_600x1400_Window_520x950.obj"
            builder.add_mesh_object(f"Wall_Window_{i}", model, (x,0,z), (0, rot_y, 0), (1,1,1), True, 10, collider_size=(6,14,1.1))
            # Window frame
            builder.add_mesh_object(f"Window_Frame_{i}", "SM_Arena_Window_Frame_520x950x020.obj", (x,1.2,z), (0, rot_y, 0), (1,1,1), False, 0)
            # Glass shards
            builder.add_mesh_object(f"Window_Glass_{i}", "SM_Arena_Window_Glass_Shards_Cluster.obj", (x,1.2,z), (0, rot_y, 0), (1,1,1), False, 0)
            # Buttress for solid walls? Add for window walls too
            # Add gargoyle
            builder.add_mesh_object(f"Gargoyle_{i}", "SM_Arena_Deco_Gargoyle_060x080x040.obj", (x,8,z), (0, rot_y+180, 0), (1,1,1), False, 0)

    # --- PILLARS ---
    for i in range(8):
        ang_deg = i*45
        ang_rad = math.radians(ang_deg)
        r = 17.5
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = -ang_deg
        if i % 2 == 0:
            model = "SM_Arena_Pillar_Full_140x1400.obj"
            builder.add_mesh_object(f"Pillar_Full_{i}", model, (x,0,z), (0, rot_y, 0), (1,1,1), True, 10, collider_size=(1.8,14,1.8))
        else:
            model = "SM_Arena_Pillar_Damaged_140x1400.obj"
            builder.add_mesh_object(f"Pillar_Damaged_{i}", model, (x,0,z), (0, rot_y, 0), (1,1,1), True, 10, collider_size=(1.8,14,1.8))
            # Add rubble pile near damaged
            builder.add_mesh_object(f"Rubble_Pillar_{i}", "SM_Arena_Debris_Rubble_Pile_150x040x150.obj", (x+0.5,0,z+0.5), (0, rot_y, 0), (1,1,1), False, 0)

    # --- ARCHES ---
    # Place 4 arches at cardinal directions between pillars? At radius 18, connecting?
    for i in range(4):
        ang_deg = i*90
        ang_rad = math.radians(ang_deg)
        r = 18.0
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = -ang_deg + 90
        builder.add_mesh_object(f"Arch_{i}", "SM_Arena_Arch_400x150x100.obj", (x,0,z), (0, rot_y, 0), (1,1,1), True, 10, collider_size=(4,2,1))
    # Ruined arch at NE
    builder.add_mesh_object("Arch_Ruined_NE", "SM_Arena_Arch_Ruined_400x150x100.obj", (12,0,12), (0, -45, 0), (1,1,1), True, 10)

    # --- STAIRS ---
    # 4 curved stairs for platform
    for i in range(4):
        ang_deg = i*90
        ang_rad = math.radians(ang_deg)
        r = 7.0
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = -ang_deg
        builder.add_mesh_object(f"Stairs_Curved_{i}", "SM_Arena_Stairs_Curved_Tier_1400.obj", (x,0,z), (0, rot_y, 0), (1,1,1), True, 10)
    # Broad south stair at south entry (0, -14)
    builder.add_mesh_object("Stairs_Broad_South", "SM_Arena_Stairs_Broad_400x060x200.obj", (0,0,-14), (0,0,0), (1,1,1), True, 10, collider_size=(4,0.6,2))
    # Straight stairs for platform access
    builder.add_mesh_object("Stairs_Straight_North", "SM_Arena_Stairs_Straight_220x090x300.obj", (0,0,6), (0,180,0), (1,1,1), True, 10)

    # --- STATUES ---
    # 4 upright at cardinal directions near wall
    for i in range(4):
        ang_deg = i*90
        ang_rad = math.radians(ang_deg)
        r = 16.0
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = -ang_deg + 180
        builder.add_mesh_object(f"Statue_Upright_{i}", "SM_Arena_Statue_Complete_120x260x120.obj", (x,0,z), (0, rot_y, 0), (1,1,1), False, 0)
        builder.add_mesh_object(f"Statue_Pedestal_{i}", "SM_Arena_Statue_Pedestal_120x100x120.obj", (x,0,z), (0, rot_y, 0), (1,1,1), False, 0)
    # 4 fallen at diagonals
    for i in range(4):
        ang_deg = 45 + i*90
        ang_rad = math.radians(ang_deg)
        r = 15.5
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = -ang_deg
        builder.add_mesh_object(f"Statue_Fallen_{i}", "SM_Arena_Statue_Fallen_180x060x060.obj", (x,0,z), (0, rot_y, 0), (1,1,1), False, 0)

    # --- CHAINS ---
    for i in range(8):
        ang_deg = i*45
        ang_rad = math.radians(ang_deg)
        r = 17.5
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        # hanging chain from pillar top
        builder.add_mesh_object(f"Chain_Hanging_Pillar_{i}", "SM_Arena_Chain_Segment_6Links_018x240.obj", (x,7.2,z), (0,0,0), (1,1,1), False, 0)
        builder.add_mesh_object(f"Chain_Anchor_Pillar_{i}", "SM_Arena_Chain_Anchor_018x018x018.obj", (x,9.6,z), (0,0,0), (1,1,1), False, 0)
    # Swags between pillars
    for i in range(8):
        ang_deg = i*45 + 22.5
        ang_rad = math.radians(ang_deg)
        r = 17.5
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = -ang_deg + 90
        builder.add_mesh_object(f"Chain_Swag_{i}", "SM_Arena_Chain_Swag_500x004x004.obj", (x,9,z), (0, rot_y, 0), (1,1,1), False, 0)

    # Window chains
    for i in range(8):
        ang_deg = i*45 + 22.5  # window positions
        ang_rad = math.radians(ang_deg)
        r = 19.0
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        builder.add_mesh_object(f"Chain_Hanging_Window_{i}", "SM_Arena_Chain_Segment_6Links_018x240.obj", (x,9.8,z), (0,0,0), (1,1,1), False, 0)

    # --- DAMAGED WOOD ---
    for i in range(6):
        ang_deg = i*60
        ang_rad = math.radians(ang_deg)
        r = 18.0
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = -ang_deg + 30
        builder.add_mesh_object(f"Wood_Beam_{i}", "SM_Arena_Wood_Beam_320x028x028.obj", (x,0.5,z), (15, rot_y, 0), (1,1,1), False, 0)
        builder.add_mesh_object(f"Wood_Plank_{i}", "SM_Arena_Wood_Plank_200x030x005.obj", (x+0.3,0.2,z+0.2), (0, rot_y, 10), (1,1,1), False, 0)

    # Scaffold at north
    builder.add_mesh_object("Wood_Scaffold_North", "SM_Arena_Wood_Scaffold_400x400x030.obj", (0,0,17), (0,0,0), (1,1,1), False, 0)

    # --- CANDLES ---
    # 20 candle clusters around
    import random
    random.seed(42)
    for i in range(20):
        ang_deg = i*18  # 20 around
        ang_rad = math.radians(ang_deg)
        r = 8 + random.uniform(2,6)  # between 10-14
        if i % 5 == 0:
            r = 16  # near wall
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = random.uniform(0,360)
        builder.add_mesh_object(f"Candle_Cluster_{i}", "SM_Arena_Candle_Cluster_3x_045.obj", (x,0.5,z), (0, rot_y, 0), (1,1,1), False, 0)
        # Add point light for each cluster
        builder.add_light(f"Candle_Light_{i}", (x,1.0,z), (0,0,0), 2,
                          (1.0,0.62,0.33), 0.53, 4.6, enabled=(i % 2 == 0))

    # Wall sconces 8
    for i in range(8):
        ang_deg = i*45
        ang_rad = math.radians(ang_deg)
        r = 18.8
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = -ang_deg + 180
        builder.add_mesh_object(f"Candle_Sconce_{i}", "SM_Arena_Candle_Wall_Sconce_020x030x015.obj", (x,2.5,z), (0, rot_y, 0), (1,1,1), False, 0)

    # --- RITUAL PROPS ---
    builder.add_mesh_object("Ritual_Brazier_Large", "SM_Arena_Ritual_Brazier_Large_080x060x080.obj", (0,0.5,10), (0,0,0), (1,1,1), False, 0)
    builder.add_mesh_object("Ritual_Altar_Slab", "SM_Arena_Ritual_Altar_Slab_200x080x100.obj", (0,0.5,12), (0,180,0), (1,1,1), True, 10, collider_size=(2,0.8,1))
    builder.add_mesh_object("Ritual_Chalice", "SM_Arena_Ritual_Chalice_020x030x020.obj", (0.3,1.3,12), (0,0,0), (1,1,1), False, 0)
    builder.add_mesh_object("Ritual_Incense", "SM_Arena_Ritual_Incense_Burner_025x035x025.obj", (-0.3,1.3,12), (0,0,0), (1,1,1), False, 0)
    builder.add_mesh_object("Ritual_Rune_1", "SM_Arena_Ritual_Rune_050x001x050.obj", (2,0.615,2), (0,45,0), (1,1,1), False, 0)
    builder.add_mesh_object("Ritual_Rune_2", "SM_Arena_Ritual_Rune_050x001x050.obj", (-2,0.615,-2), (0,-30,0), (1,1,1), False, 0)

    # --- DEBRIS ---
    for i in range(8):
        ang = i*45 + 10
        rad = math.radians(ang)
        r = 13 + (i%3)
        x = math.cos(rad)*r
        z = math.sin(rad)*r
        builder.add_mesh_object(f"Debris_Stone_Small_{i}", "SM_Arena_Debris_Stone_Small_030x020x030.obj", (x,0,z), (0, i*30, 0), (1,1,1), False, 0)
        builder.add_mesh_object(f"Debris_Stone_Medium_{i}", "SM_Arena_Debris_Stone_Medium_080x040x080.obj", (x+0.5,0,z+0.3), (0, i*20, 0), (1,1,1), False, 0)

    builder.add_mesh_object("Debris_Rubble_Pile_1", "SM_Arena_Debris_Rubble_Pile_150x040x150.obj", (5,0,-6), (0,20,0), (1,1,1), False, 0)
    builder.add_mesh_object("Debris_Rubble_Pile_2", "SM_Arena_Debris_Rubble_Pile_150x040x150.obj", (-6,0,5), (0,-30,0), (1,1,1), False, 0)
    builder.add_mesh_object("Debris_Glass_Shards", "SM_Arena_Debris_Glass_Shards_150x010x100.obj", (8,0,8), (0,0,0), (1,1,1), False, 0)
    builder.add_mesh_object("Debris_Wood_Splinters", "SM_Arena_Debris_Wood_Splinters_100x010x050.obj", (-8,0,-8), (0,0,0), (1,1,1), False, 0)

    # --- DOORS ---
    # Sealed stone door at north
    builder.add_mesh_object("Door_Sealed_North", "SM_Arena_Door_Sealed_Stone_400x400x100.obj", (0,0,19), (0,180,0), (1,1,1), True, 10, collider_size=(4,4,1))
    # Door frame at south entry
    builder.add_mesh_object("Door_Frame_South", "SM_Arena_Door_Frame_400x400x020.obj", (0,0,-19), (0,0,0), (1,1,1), True, 10)
    builder.add_mesh_object("Door_Gate_Iron_South", "SM_Arena_Door_Gate_Iron_380x380x005.obj", (0,0,-19), (0,0,0), (1,1,1), False, 0)

    # --- ENVIRONMENTAL DECORATIONS ---
    for i in range(8):
        ang_deg = i*45
        ang_rad = math.radians(ang_deg)
        r = 19.0
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        rot_y = -ang_deg + 180
        builder.add_mesh_object(f"Deco_Bracket_{i}", "SM_Arena_Deco_Iron_Bracket_030x020x040.obj", (x,3,z), (0, rot_y, 0), (1,1,1), False, 0)
        builder.add_mesh_object(f"Deco_Cornice_{i}", "SM_Arena_Deco_Cornice_400x020x020.obj", (x,6,z), (0, rot_y, 0), (1,1,1), False, 0)
        if i % 2 == 0:
            builder.add_mesh_object(f"Deco_Banner_{i}", "SM_Arena_Deco_Banner_Tattered_100x300x002.obj", (x,5,z), (0, rot_y, 0), (1,1,1), False, 0)
            builder.add_mesh_object(f"Deco_Candelabra_{i}", "SM_Arena_Deco_Candelabra_Wall_020x060x020.obj", (x,4,z), (0, rot_y, 0), (1,1,1), False, 0)

    # Fog volumes
    for i in range(4):
        ang_deg = 35 + i*90
        ang_rad = math.radians(ang_deg)
        r = 15  # edge haze, outside the 12m combat disc
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        builder.add_mesh_object(f"Fog_Volume_{i}", "SM_Arena_Deco_Fog_Volume_1000x002x1000.obj", (x,0.54,z), (0,0,0), (0.65,1,0.65), False, 0)

    # Moss patches
    for i in range(8):
        ang_deg = i*45 + 10
        ang_rad = math.radians(ang_deg)
        r = 18.5
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        builder.add_mesh_object(f"Moss_Patch_{i}", "SM_Arena_Deco_Moss_Patch_100x005x100.obj", (x,0.02,z), (0,0,0), (1,1,1), False, 0)

    # Moon shaft spot lights 8
    for i in range(8):
        ang_deg = i*45 + 22.5
        ang_rad = math.radians(ang_deg)
        r = 18.0
        x = math.cos(ang_rad)*r
        z = math.sin(ang_rad)*r
        # Spot pointing inward and down
        # Yaw = 270 - ang? As per design doc
        yaw = 270 - ang_deg
        builder.add_light(f"MoonShaft_{i}", (x,10,z), (50, yaw, 0), 0,
                          (0.63,0.74,0.92), 0.52, 20, 42,
                          enabled=(i in (1, 2, 4, 7)))

    # Explicit light/renderer references are authored in the root component.
    final_yaml = builder.build_file()
    with open(OUT_PREFAB, 'w', encoding='utf-8') as f:
        f.write(final_yaml)
    print(f"Wrote master prefab {OUT_PREFAB} with {len(builder.root_children)} children, {len(builder.objects)} objects total")

if __name__ == "__main__":
    main()
