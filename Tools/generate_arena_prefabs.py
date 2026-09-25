#!/usr/bin/env python3
"""
Generate Unity prefabs for the modular arena mesh kit.
Creates prefabs under Assets/Prefabs/Arena/MeshKit/ that reference the OBJ meshes.
Also generates a master assembly prefab Arena_RitualChamber_MeshKit.
"""

import os, uuid, re, math, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "Assets")
OUT_PREFAB_DIR = os.path.join(ASSETS, "Prefabs/Arena/MeshKit")
os.makedirs(OUT_PREFAB_DIR, exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Floor"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Wall"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Pillar"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Arch"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Window"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Stairs"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Platform"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Statue"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Chain"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Wood"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Candle"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Ritual"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Debris"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Door"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "Deco"), exist_ok=True)
os.makedirs(os.path.join(OUT_PREFAB_DIR, "LOD"), exist_ok=True)

NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "vespershade://unity-project")

def guid_for(relpath):
    relpath = relpath.replace(os.sep, "/")
    return uuid.uuid5(NAMESPACE, relpath).hex

def parse_obj_materials(obj_path):
    mats = []
    with open(obj_path, 'r') as f:
        for line in f:
            if line.startswith("usemtl "):
                mat = line.strip().split()[1]
                if mat not in mats:
                    mats.append(mat)
    return mats

# Material path mapping: material name -> asset path
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

# Precompute material GUIDs
MAT_GUIDS = {name: guid_for(path) for name, path in MAT_NAME_TO_PATH.items()}

# List of meshes with category, filename, collider?, layer
# layer 10 = Environment for blocking, 0 = Default for non-blocking
MESHES = [
    # Floor
    ("Floor", "SM_Arena_Floor_400x400x050.obj", True, 10, "StoneFloor"),
    ("Floor", "SM_Arena_Floor_200x200x050.obj", True, 10, "StoneFloor"),
    ("Floor", "SM_Arena_Floor_100x100x050.obj", True, 10, "StoneFloor"),
    ("Floor", "SM_Arena_Floor_Wedge_22_5_R15_19.obj", True, 10, "StoneFloor"),
    ("Floor", "SM_Arena_Floor_Edge_400x020x050.obj", False, 0, "StonePillar"),
    ("Floor", "SM_Arena_Floor_Ritual_Plate_220x065.obj", False, 0, "Ritual"),
    ("Floor", "SM_Arena_Floor_Ritual_Center_320.obj", False, 0, "Ritual"),
    # Wall
    ("Wall", "SM_Arena_Wall_400x400x100.obj", True, 10, "StoneWall"),
    ("Wall", "SM_Arena_Wall_400x800x100.obj", True, 10, "StoneWall"),
    ("Wall", "SM_Arena_Wall_400x1600x110.obj", True, 10, "StoneWall"),
    ("Wall", "SM_Arena_Wall_400x400_Window_250x300.obj", True, 10, "StoneWall"),
    ("Wall", "SM_Arena_Wall_600x1400_Window_520x950.obj", True, 10, "StoneWall"),
    ("Wall", "SM_Arena_Wall_Buttress_100x400x060.obj", True, 10, "StonePillar"),
    ("Wall", "SM_Arena_Wall_Cornice_400x030x020.obj", False, 0, "StoneWall"),
    ("Wall", "SM_Arena_Wall_Base_400x050x110.obj", True, 10, "StonePillar"),
    # Pillar
    ("Pillar", "SM_Arena_Pillar_Base_180x100x180.obj", True, 10, "StonePillar"),
    ("Pillar", "SM_Arena_Pillar_Shaft_140x400x140.obj", True, 10, "StonePillar"),
    ("Pillar", "SM_Arena_Pillar_Capital_170x090x170.obj", False, 0, "StonePillar"),
    ("Pillar", "SM_Arena_Pillar_Full_140x1400.obj", True, 10, "StonePillar"),
    ("Pillar", "SM_Arena_Pillar_Damaged_140x1400.obj", True, 10, "StonePillar"),
    # Arch
    ("Arch", "SM_Arena_Arch_400x150x100.obj", True, 10, "StoneWall"),
    ("Arch", "SM_Arena_Arch_300x400x100.obj", True, 10, "StoneWall"),
    ("Arch", "SM_Arena_Arch_Ruined_400x150x100.obj", True, 10, "StoneWall"),
    # Window
    ("Window", "SM_Arena_Window_Frame_300x400x020.obj", False, 0, "StoneWall"),
    ("Window", "SM_Arena_Window_Frame_520x950x020.obj", False, 0, "StoneWall"),
    ("Window", "SM_Arena_Window_Tracery_Circle_100.obj", False, 0, "StoneWall"),
    ("Window", "SM_Arena_Window_Mullion_020x400x005.obj", False, 0, "StoneWall"),
    ("Window", "SM_Arena_Window_Glass_Pane_280x380.obj", False, 0, "Glass"),
    ("Window", "SM_Arena_Window_Glass_Shards_Cluster.obj", False, 0, "Glass"),
    # Stairs
    ("Stairs", "SM_Arena_Stairs_Step_220x030x100.obj", True, 10, "StoneFloor"),
    ("Stairs", "SM_Arena_Stairs_Straight_220x090x300.obj", True, 10, "StoneFloor"),
    ("Stairs", "SM_Arena_Stairs_Broad_400x060x200.obj", True, 10, "StoneFloor"),
    ("Stairs", "SM_Arena_Stairs_Curved_Tier_1400.obj", True, 10, "StoneFloor_Ritual"),
    ("Stairs", "SM_Arena_Stairs_Plate_400x030x400.obj", True, 10, "StoneFloor"),
    # Platform
    ("Platform", "SM_Arena_Platform_Slab_400x400x030.obj", True, 10, "StoneFloor_Ritual"),
    ("Platform", "SM_Arena_Platform_Cylinder_1000x030.obj", True, 10, "StoneFloor_Ritual"),
    ("Platform", "SM_Arena_Platform_Cylinder_1400x030.obj", True, 10, "StoneFloor_Ritual"),
    ("Platform", "SM_Arena_Platform_Rim_1400x015.obj", False, 0, "StonePillar"),
    ("Platform", "SM_Arena_Platform_StepRing_1400.obj", True, 10, "StoneFloor_Ritual"),
    # Statue
    ("Statue", "SM_Arena_Statue_Pedestal_120x100x120.obj", False, 0, "Statue"),
    ("Statue", "SM_Arena_Statue_Torso_Robed_070x160x060.obj", False, 0, "Statue"),
    ("Statue", "SM_Arena_Statue_Head_Hooded_030x030x030.obj", False, 0, "Statue"),
    ("Statue", "SM_Arena_Statue_Complete_120x260x120.obj", False, 0, "Statue"),
    ("Statue", "SM_Arena_Statue_Fallen_180x060x060.obj", False, 0, "Statue"),
    ("Statue", "SM_Arena_Statue_Ruined_Debris_080x040x080.obj", False, 0, "Statue"),
    # Chain
    ("Chain", "SM_Arena_Chain_Link_018x040.obj", False, 0, "Chain"),
    ("Chain", "SM_Arena_Chain_Segment_6Links_018x240.obj", False, 0, "Chain"),
    ("Chain", "SM_Arena_Chain_Swag_500x004x004.obj", False, 0, "Chain"),
    ("Chain", "SM_Arena_Chain_Anchor_018x018x018.obj", False, 0, "Chain"),
    ("Chain", "SM_Arena_Chain_Hook_020x030x010.obj", False, 0, "Chain"),
    # Wood
    ("Wood", "SM_Arena_Wood_Beam_320x028x028.obj", False, 0, "Wood"),
    ("Wood", "SM_Arena_Wood_Brace_120x028x022.obj", False, 0, "Wood"),
    ("Wood", "SM_Arena_Wood_Plank_200x030x005.obj", False, 0, "Wood"),
    ("Wood", "SM_Arena_Wood_Scaffold_400x400x030.obj", False, 0, "Wood"),
    ("Wood", "SM_Arena_Wood_Debris_100x020x050.obj", False, 0, "Wood"),
    # Candle
    ("Candle", "SM_Arena_Candle_Wax_009x018.obj", False, 0, "CandleWax"),
    ("Candle", "SM_Arena_Candle_Wax_010x025.obj", False, 0, "CandleWax"),
    ("Candle", "SM_Arena_Candle_Holder_Brazier_045x006x045.obj", False, 0, "Brazier"),
    ("Candle", "SM_Arena_Candle_Cluster_3x_045.obj", False, 0, "CandleCluster"),
    ("Candle", "SM_Arena_Candle_Wall_Sconce_020x030x015.obj", False, 0, "CandleSconce"),
    # Ritual
    ("Ritual", "SM_Arena_Ritual_Brazier_Large_080x060x080.obj", False, 0, "Brazier"),
    ("Ritual", "SM_Arena_Ritual_Circle_320x002x320.obj", False, 0, "Ritual"),
    ("Ritual", "SM_Arena_Ritual_Rune_050x001x050.obj", False, 0, "Ritual"),
    ("Ritual", "SM_Arena_Ritual_Chalice_020x030x020.obj", False, 0, "Brazier"),
    ("Ritual", "SM_Arena_Ritual_Incense_Burner_025x035x025.obj", False, 0, "Brazier"),
    ("Ritual", "SM_Arena_Ritual_Altar_Slab_200x080x100.obj", True, 10, "Altar"),
    # Debris
    ("Debris", "SM_Arena_Debris_Stone_Small_030x020x030.obj", False, 0, "StonePillar"),
    ("Debris", "SM_Arena_Debris_Stone_Medium_080x040x080.obj", False, 0, "StonePillar"),
    ("Debris", "SM_Arena_Debris_Stone_Large_120x060x120.obj", False, 0, "StonePillar"),
    ("Debris", "SM_Arena_Debris_Glass_Shards_150x010x100.obj", False, 0, "Glass"),
    ("Debris", "SM_Arena_Debris_Rubble_Pile_150x040x150.obj", False, 0, "Rubble"),
    ("Debris", "SM_Arena_Debris_Wood_Splinters_100x010x050.obj", False, 0, "Wood"),
    # Door
    ("Door", "SM_Arena_Door_Frame_400x400x020.obj", True, 10, "StoneWall"),
    ("Door", "SM_Arena_Door_Wood_Heavy_380x380x010.obj", True, 10, "WoodDoor"),
    ("Door", "SM_Arena_Door_Gate_Iron_380x380x005.obj", True, 10, "IronGate"),
    ("Door", "SM_Arena_Door_Sealed_Stone_400x400x100.obj", True, 10, "StoneWall"),
    # Deco
    ("Deco", "SM_Arena_Deco_Gargoyle_060x080x040.obj", False, 0, "StoneWall"),
    ("Deco", "SM_Arena_Deco_Cornice_400x020x020.obj", False, 0, "StoneWall"),
    ("Deco", "SM_Arena_Deco_Banner_Tattered_100x300x002.obj", False, 0, "Wood"),
    ("Deco", "SM_Arena_Deco_Iron_Bracket_030x020x040.obj", False, 0, "Chain"),
    ("Deco", "SM_Arena_Deco_Candelabra_Wall_020x060x020.obj", False, 0, "Candelabra"),
    ("Deco", "SM_Arena_Deco_Fog_Volume_1000x002x1000.obj", False, 0, "Fog"),
    ("Deco", "SM_Arena_Deco_Moss_Patch_100x005x100.obj", False, 0, "StonePillar"),
    # LODs
    ("LOD", "SM_Arena_Floor_400x400x050_LOD1.obj", False, 0, "StoneFloor"),
    ("LOD", "SM_Arena_Wall_400x400x100_LOD1.obj", False, 0, "StoneWall"),
    ("LOD", "SM_Arena_Pillar_Full_140x1400_LOD1.obj", False, 0, "StonePillar"),
    ("LOD", "SM_Arena_Statue_Complete_120x260x120_LOD1.obj", False, 0, "Statue"),
]

def generate_single_prefab(category, filename, has_collider, layer, description):
    model_rel = f"Assets/Models/Arena/{filename}"
    model_guid = guid_for(model_rel)
    obj_path = os.path.join(ROOT, model_rel)
    materials = parse_obj_materials(obj_path)
    # map material names to guids
    mat_guids = []
    for mname in materials:
        if mname in MAT_GUIDS:
            mat_guids.append((mname, MAT_GUIDS[mname]))
        else:
            # unknown material -> fallback to StoneWall
            print(f"WARNING: unknown material {mname} in {filename}, fallback to StoneWall")
            mat_guids.append((mname, MAT_GUIDS["M_Arena_StoneWall"]))

    # Determine mesh fileID: Unity uses 4300000 for first mesh
    mesh_fileid = 4300000
    # For multi-material, there are submeshes but still same mesh asset

    prefab_name = filename.replace(".obj", "")
    # e.g., SM_Arena_Floor_400x400x050 -> keep
    out_path = os.path.join(OUT_PREFAB_DIR, category, prefab_name + ".prefab")
    # Build YAML
    # IDs: 1000 GameObject, 1001 Transform, 1002 MeshFilter, 1003 MeshRenderer, 1004 BoxCollider if needed
    # For simplicity, single GO
    # Determine collider size from mesh name? We'll approximate: for floor, size = dimensions from name; for others, use 1,1,1 but we can parse?
    # We'll just use BoxCollider size 1,1,1 and let user adjust, but for floor/wall we can approximate from filename.
    # Parse dimensions from filename like 400x400x050 -> 4.00 x 0.50 x 4.00? Actually format: numbers are cm? 400 = 4.00m, 050=0.50m
    # We'll attempt to extract
    collider_size = (1,1,1)
    # Try regex
    m = re.search(r'(\d+)x(\d+)x(\d+)', filename)
    if m:
        try:
            # interpret as cm: 400 -> 4.0
            w = int(m.group(1))/100.0
            h = int(m.group(2))/100.0
            d = int(m.group(3))/100.0
            # For many assets, order is W x H x D or W x D x H? We'll assume first is X, second Y, third Z, but for floor 400x400x050, second is actually X? Actually floor 400x400x050 means 4x0.5x4? So second is maybe? We'll keep as parsed but swap if needed: for floor, height is 0.5 which is third number 050, so it's W x D x H? Let's handle: if filename contains Floor, then dimensions are W x D x H where third is height.
            # For simplicity, if category Floor, then size = (w, h_third, d_second)
            if category == "Floor":
                # 400x400x050 -> w=4, d=4, h=0.5
                collider_size = (w, int(m.group(3))/100.0, int(m.group(2))/100.0)
            else:
                collider_size = (w, h, d)
        except:
            pass
    # For cylinder platform, collider size approximated
    if "Cylinder" in filename:
        # radius from name: 1000 -> 10m diameter -> radius 5, but box collider will be diameter
        m2 = re.search(r'Cylinder_(\d+)x', filename)
        if m2:
            dia = int(m2.group(1))/100.0
            collider_size = (dia, 0.3, dia)
    if "Platform_Rim" in filename:
        collider_size = (14,0.15,14)

    yaml = f"""%YAML 1.1
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
"""
    if has_collider:
        yaml += f"  - component: {{fileID: 1004}}\n"
    yaml += f"""  m_Layer: {layer}
  m_Name: {prefab_name}
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
  m_Children: []
  m_Father: {{fileID: 0}}
  m_LocalEulerAnglesHint: {{x: 0, y: 0, z: 0}}
--- !u!33 &1002
MeshFilter:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 1000}}
  m_Mesh: {{fileID: {mesh_fileid}, guid: {model_guid}, type: 3}}
--- !u!23 &1003
MeshRenderer:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 1000}}
  m_Enabled: 1
  m_CastShadows: 1
  m_ReceiveShadows: 1
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
    for _, mguid in mat_guids:
        yaml += f"  - {{fileID: 2100000, guid: {mguid}, type: 2}}\n"
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
        yaml += f"""--- !u!65 &1004
BoxCollider:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: 1000}}
  m_Material: {{fileID: 0}}
  m_IsTrigger: 0
  m_Enabled: 1
  serializedVersion: 2
  m_Size: {{x: {collider_size[0]}, y: {collider_size[1]}, z: {collider_size[2]}}}
  m_Center: {{x: 0, y: {collider_size[1]*0.5}, z: 0}}
"""
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(yaml)
    print(f"Generated prefab {out_path}")

def generate_all():
    for cat, fname, has_coll, layer, desc in MESHES:
        generate_single_prefab(cat, fname, has_coll, layer, desc)

if __name__ == "__main__":
    generate_all()
    print("All meshkit prefabs generated.")
