#!/usr/bin/env python3
"""Wire the Hollow Sanctum material library into the arena prefabs.

Idempotent. Performs, for both arena assemblies:

  * per-object material reassignment (cracked stone on damaged pieces, rubble,
    ritual wax near the dais, sigil on the centre seal, trims on frames, ...)
  * adds one realtime (on-awake) box-projected ReflectionProbe so metals,
    wax and polished ritual basalt reflect the candle-lit room instead of the
    black void

For the primitive assembly (Arena_RitualChamber.prefab, used by Main.unity):
  * built-in mesh 10210 (Quad) -> 10202 (Cube). The generator intended boxes
    (BoxColliders, 3D scales); quads rendered walls/pillars as flat cards.
  * BoxCollider sizes normalised to mesh space (size / scale) - previously the
    size was multiplied by the transform scale a second time (e.g. walls had
    31 x 256 m colliders)
  * wall segments widened 5.6 -> 7.7 m so the 16-segment ring is closed
  * window frames / glass / shards pulled in front of the (now solid) wall
    face so they are visible
  * ritual plates moved from r=7 (half buried in the dais edge) to r=8.2

For the OBJ mesh kit: writes ModelImporter .meta files that pin the mesh
fileID 4300000 referenced by the MeshKit prefabs (internalIDToNameTable) and
disable material import (materials come from the prefabs).
"""

from __future__ import annotations

import math
import os
import re
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAT = "Assets/Materials/Arena"
PRIM = "Assets/Prefabs/Arena/Arena_RitualChamber.prefab"
KIT = "Assets/Prefabs/Arena/Arena_RitualChamber_MeshKit.prefab"


def mguid(name):
    meta = os.path.join(ROOT, MAT, name + ".mat.meta")
    return re.search(r"guid: ([0-9a-f]{32})", open(meta).read()).group(1)


# ---------------------------------------------------------------------------
# YAML doc helpers
# ---------------------------------------------------------------------------
HDR = re.compile(r"^--- !u!(\d+) &(-?\d+)", re.M)


def load(rel):
    text = open(os.path.join(ROOT, rel), encoding="utf-8").read()
    parts = HDR.split(text)
    head = parts[0]
    docs = []
    for i in range(1, len(parts), 3):
        docs.append([int(parts[i]), parts[i + 1], parts[i + 2]])
    return head, docs


def save(rel, head, docs):
    out = [head]
    for cls, fid, body in docs:
        out.append(f"--- !u!{cls} &{fid}{body}")
    with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join(out))


def index(docs):
    return {d[1]: d for d in docs}


def gameobjects(docs):
    by = index(docs)
    for d in docs:
        if d[0] != 1:
            continue
        name = re.search(r"m_Name: (.*)", d[2]).group(1).strip()
        comps = {}
        for cid in re.findall(r"component: \{fileID: (-?\d+)\}", d[2]):
            if cid in by:
                comps[by[cid][0]] = by[cid]
        yield name, d, comps


def vec(body, key):
    m = re.search(key + r": \{x: ([-\d.e]+), y: ([-\d.e]+), z: ([-\d.e]+)\}", body)
    return [float(m.group(i)) for i in (1, 2, 3)]


def set_vec(body, key, v):
    return re.sub(key + r": \{x: [-\d.e]+, y: [-\d.e]+, z: [-\d.e]+\}",
                  f"{key}: {{x: {round(v[0], 5)}, y: {round(v[1], 5)}, z: {round(v[2], 5)}}}", body, count=1)


def remap_materials(renderer_doc, mapping):
    """mapping: {old_guid or '*': new_guid}"""
    body = renderer_doc[2]
    head, rest = body.split("m_Materials:", 1)
    mats, tail = rest.split("m_StaticBatchInfo", 1)

    def rep(m):
        g = m.group(1)
        new = mapping.get(g, mapping.get("*", g))
        return f"guid: {new}, type: 2"
    mats = re.sub(r"guid: ([0-9a-f]{32}), type: 2", rep, mats)
    renderer_doc[2] = head + "m_Materials:" + mats + "m_StaticBatchInfo" + tail


# ---------------------------------------------------------------------------
# Reflection probe
# ---------------------------------------------------------------------------
PROBE_GO, PROBE_TR, PROBE_RP = "990001", "990002", "990003"


def add_probe(docs, size=(42, 18, 42), center_y=8.0):
    if any(d[1] == PROBE_GO for d in docs):
        return
    root_tr = next(d for d in docs if d[0] == 4 and "m_Father: {fileID: 0}" in d[2])
    root_tr[2] = root_tr[2].replace("  m_Children:\n", f"  m_Children:\n  - {{fileID: {PROBE_TR}}}\n", 1)
    docs.append([1, PROBE_GO, f"""
GameObject:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  serializedVersion: 6
  m_Component:
  - component: {{fileID: {PROBE_TR}}}
  - component: {{fileID: {PROBE_RP}}}
  m_Layer: 0
  m_Name: ReflectionProbe_Sanctum
  m_TagString: Untagged
  m_Icon: {{fileID: 0}}
  m_NavMeshLayer: 0
  m_StaticEditorFlags: 0
  m_IsActive: 1
"""])
    docs.append([4, PROBE_TR, f"""
Transform:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {PROBE_GO}}}
  serializedVersion: 2
  m_LocalRotation: {{x: 0, y: 0, z: 0, w: 1}}
  m_LocalPosition: {{x: 0, y: {center_y}, z: 0}}
  m_LocalScale: {{x: 1, y: 1, z: 1}}
  m_ConstrainProportionsScale: 0
  m_Children: []
  m_Father: {{fileID: {root_tr[1]}}}
  m_LocalEulerAnglesHint: {{x: 0, y: 0, z: 0}}
"""])
    docs.append([215, PROBE_RP, f"""
ReflectionProbe:
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_GameObject: {{fileID: {PROBE_GO}}}
  m_Enabled: 1
  serializedVersion: 2
  m_Type: 0
  m_Mode: 1
  m_RefreshMode: 0
  m_TimeSlicingMode: 0
  m_Resolution: 128
  m_UpdateFrequency: 0
  m_BoxSize: {{x: {size[0]}, y: {size[1]}, z: {size[2]}}}
  m_BoxOffset: {{x: 0, y: 0, z: 0}}
  m_NearClip: 0.3
  m_FarClip: 60
  m_ShadowDistance: 40
  m_ClearFlags: 2
  m_BackGroundColor: {{r: 0.028, g: 0.032, b: 0.048, a: 0}}
  m_CullingMask:
    serializedVersion: 2
    m_Bits: 4294967295
  m_IntensityMultiplier: 1
  m_BlendDistance: 1
  m_HDR: 1
  m_BoxProjection: 1
  m_RenderDynamicObjects: 0
  m_UseOcclusionCulling: 1
  m_Importance: 1
  m_CustomBakedTexture: {{fileID: 0}}
"""])


# ---------------------------------------------------------------------------
# Primitive assembly
# ---------------------------------------------------------------------------

def fix_primitive():
    head, docs = load(PRIM)
    G = {n: mguid(n) for n in ["M_Arena_StonePillar", "M_Arena_StoneWall", "M_Arena_Stone_Cracked",
                               "M_Arena_Stone_Rubble", "M_Arena_StoneTrim", "M_Arena_RitualSigil",
                               "M_Arena_StoneFloor_Ritual", "M_Arena_Candle_Wax",
                               "M_Arena_Candle_Wax_Ritual", "M_Arena_RitualMarking",
                               "M_Arena_Metal_Chain", "M_Arena_Door_Iron"]}
    changed = 0
    for name, go, comps in gameobjects(docs):
        mf, tr, mr, bc = comps.get(33), comps.get(4), comps.get(23), comps.get(65)
        # quads -> cubes
        if mf and "fileID: 10210," in mf[2]:
            mf[2] = mf[2].replace("fileID: 10210,", "fileID: 10202,")
            changed += 1
        if tr is None:
            continue
        scale = vec(tr[2], "m_LocalScale")
        # widen wall ring
        if name.startswith("Wall_Segment_") and abs(scale[0] - 5.6) < 1e-3:
            scale[0] = 7.7
            tr[2] = set_vec(tr[2], "m_LocalScale", scale)
        # collider sizes -> mesh space
        if bc:
            size = vec(bc[2], "m_Size")
            already = size in ([1.0, 1.0, 1.0], [1.0, 2.0, 1.0])
            if not already and (any(abs(size[i] - scale[i]) < 1e-3 for i in range(3)) or name.startswith("Wall_Segment_")):
                new = [round(size[i] / scale[i], 5) if scale[i] else size[i] for i in range(3)]
                if name.startswith("Wall_Segment_"):
                    new = [1, 1, 1]
                bc[2] = set_vec(bc[2], "m_Size", new)
        pos = vec(tr[2], "m_LocalPosition")
        r = math.hypot(pos[0], pos[2])
        # windows in front of the wall face (inner face at r = 19 - 0.55)
        target = None
        if name.startswith("WindowFrame_"):
            target = 18.2
        elif name.startswith("WindowGlass_"):
            target = 17.93
        elif name.startswith("WindowGlassShard"):
            target = 17.86 if "ShardA" in name else 17.82
        elif name.startswith("RitualMarking_"):
            target = 8.2
        if target and r > 1e-3 and abs(r - target) > 1e-3:
            k = target / r
            pos[0] *= k
            pos[2] *= k
            tr[2] = set_vec(tr[2], "m_LocalPosition", pos)
        # material assignment
        if mr is None:
            continue
        if name.startswith("Pillar_") and name.endswith("_Damaged"):
            remap_materials(mr, {"*": G["M_Arena_Stone_Cracked"]})
        elif name.startswith("RubbleFragment") or name.startswith("RubblePile"):
            remap_materials(mr, {"*": G["M_Arena_Stone_Rubble"]})
        elif name.startswith("WindowFrame_"):
            remap_materials(mr, {"*": G["M_Arena_StoneTrim"]})
        elif name.startswith("RitualCircle_Center") or name.startswith("RitualRuneInner"):
            remap_materials(mr, {"*": G["M_Arena_RitualSigil"]})
        elif name.startswith("RitualEdgeRing"):
            remap_materials(mr, {"*": G["M_Arena_StoneFloor_Ritual"]})
        elif name.startswith("Candle_Platform_"):
            remap_materials(mr, {G["M_Arena_Candle_Wax"]: G["M_Arena_Candle_Wax_Ritual"]})
        elif name.startswith("Stairs_") and name != "Stairs_South_Broad":
            remap_materials(mr, {G["M_Arena_StonePillar"]: G["M_Arena_StoneTrim"]})
    add_probe(docs)
    save(PRIM, head, docs)
    print(f"primitive assembly: {changed} quad->cube fixes, materials + probe wired")


# ---------------------------------------------------------------------------
# Mesh kit assembly (+ individual MeshKit prefabs)
# ---------------------------------------------------------------------------

def kit_rules():
    G = {n: mguid(n) for n in [
        "M_Arena_StonePillar", "M_Arena_StoneWall", "M_Arena_Stone_Cracked", "M_Arena_Stone_Rubble",
        "M_Arena_StoneTrim", "M_Arena_RitualSigil", "M_Arena_Ritual_Altar", "M_Arena_Candle_Wax",
        "M_Arena_Candle_Wax_Ritual", "M_Arena_Metal_Chain", "M_Arena_Door_Iron", "M_Arena_Moss",
        "M_Arena_Banner_Cloth", "M_Arena_Wood_Rotted", "M_Arena_Statue_Eroded", "M_Arena_Door_Wood",
        "M_Arena_Brazier_Metal", "M_Arena_Metal_Verdigris_Heavy"]}
    P, W = G["M_Arena_StonePillar"], G["M_Arena_StoneWall"]
    return G, [
        (r"^(SM_Arena_)?Pillar_Damaged", {P: G["M_Arena_Stone_Cracked"]}),
        (r"^(SM_Arena_)?Arch_Ruined", {W: G["M_Arena_Stone_Cracked"]}),
        (r"^(SM_Arena_)?Debris_Stone", {P: G["M_Arena_Stone_Rubble"]}),
        (r"^(SM_Arena_)?(Debris_Rubble_Pile|Rubble_Pillar)", {P: G["M_Arena_Stone_Rubble"], W: G["M_Arena_Stone_Cracked"]}),
        (r"^(SM_Arena_)?Statue_Ruined", {"*": G["M_Arena_Stone_Rubble"]}),
        (r"^(SM_Arena_)?(Deco_)?Moss_Patch", {"*": G["M_Arena_Moss"]}),
        (r"^(SM_Arena_)?(Deco_)?Banner", {G["M_Arena_Wood_Rotted"]: G["M_Arena_Banner_Cloth"]}),
        (r"^(SM_Arena_)?(Deco_Bracket|Deco_Iron_Bracket|Door_Gate_Iron)", {G["M_Arena_Metal_Chain"]: G["M_Arena_Door_Iron"]}),
        (r"^(SM_Arena_)?Door_Sealed", {P: G["M_Arena_Stone_Cracked"]}),
        (r"^(SM_Arena_)?Door_Wood", {G["M_Arena_Wood_Rotted"]: G["M_Arena_Door_Wood"]}),
        (r"^(SM_Arena_)?Ritual_Altar", {P: G["M_Arena_Ritual_Altar"]}),
        (r"^(SM_Arena_)?(Ritual_Center|Ritual_Rune|Floor_Ritual_Center|Ritual_Circle)", {"*": G["M_Arena_RitualSigil"]}),
        (r"^(SM_Arena_)?Ritual_Brazier", {G["M_Arena_Brazier_Metal"]: G["M_Arena_Metal_Verdigris_Heavy"]}),
        (r"^(SM_Arena_)?Window_(Frame|Tracery|Mullion)", {W: G["M_Arena_StoneTrim"], P: G["M_Arena_StoneTrim"]}),
        (r"^(SM_Arena_)?(Deco_)?Gargoyle", {W: G["M_Arena_Statue_Eroded"]}),
        (r"^(SM_Arena_)?(Wall_Base|Platform_Rim|Deco_Cornice|Wall_Cornice)", {P: G["M_Arena_StoneTrim"], W: G["M_Arena_StoneTrim"]}),
    ]


def apply_rules(rel, rules, G, ritual_wax_radius=None):
    head, docs = load(rel)
    n = 0
    for name, go, comps in gameobjects(docs):
        mr = comps.get(23)
        if mr is None:
            continue
        for pat, mapping in rules:
            if re.search(pat, name):
                remap_materials(mr, mapping)
                n += 1
                break
        if ritual_wax_radius and name.startswith("Candle_Cluster") and 4 in comps:
            p = vec(comps[4][2], "m_LocalPosition")
            if math.hypot(p[0], p[2]) < ritual_wax_radius:
                remap_materials(mr, {G["M_Arena_Candle_Wax"]: G["M_Arena_Candle_Wax_Ritual"]})
                n += 1
    return head, docs, n


def fix_kit():
    G, rules = kit_rules()
    head, docs, n = apply_rules(KIT, rules, G, ritual_wax_radius=9.5)
    add_probe(docs)
    save(KIT, head, docs)
    print(f"mesh kit assembly: {n} renderer material remaps, probe wired")
    total = 0
    kit_dir = os.path.join(ROOT, "Assets/Prefabs/Arena/MeshKit")
    for dp, _, files in os.walk(kit_dir):
        for f in files:
            if f.endswith(".prefab"):
                rel = os.path.relpath(os.path.join(dp, f), ROOT)
                h, d, k = apply_rules(rel, rules, G)
                if k:
                    save(rel, h, d)
                    total += k
    print(f"mesh kit prefabs: {total} renderer material remaps")


# ---------------------------------------------------------------------------
# OBJ ModelImporter metas
# ---------------------------------------------------------------------------

def model_meta(guid, mesh_name):
    return f"""fileFormatVersion: 2
guid: {guid}
ModelImporter:
  serializedVersion: 22200
  internalIDToNameTable:
  - first:
      43: 4300000
    second: {mesh_name}
  externalObjects: {{}}
  materials:
    materialImportMode: 0
    materialName: 0
    materialSearch: 1
    materialLocation: 1
  animations:
    legacyGenerateAnimations: 4
    bakeSimulation: 0
    resampleCurves: 1
    optimizeGameObjects: 0
    removeConstantScaleCurves: 0
    motionNodeName: 
    animationImportErrors: 
    animationImportWarnings: 
    animationRetargetingWarnings: 
    animationDoRetargetingWarnings: 0
    importAnimatedCustomProperties: 0
    importConstraints: 0
    animationCompression: 1
    animationRotationError: 0.5
    animationPositionError: 0.5
    animationScaleError: 0.5
    animationWrapMode: 0
    extraExposedTransformPaths: []
    extraUserProperties: []
    clipAnimations: []
    isReadable: 0
  meshes:
    lODScreenPercentages: []
    globalScale: 1
    meshCompression: 0
    addColliders: 0
    useSRGBMaterialColor: 1
    sortHierarchyByName: 1
    importPhysicalCameras: 1
    importVisibility: 1
    importBlendShapes: 0
    importCameras: 0
    importLights: 0
    nodeNameCollisionStrategy: 1
    fileIdsGeneration: 2
    swapUVChannels: 0
    generateSecondaryUV: 0
    useFileUnits: 1
    keepQuads: 0
    weldVertices: 1
    bakeAxisConversion: 0
    preserveHierarchy: 0
    skinWeightsMode: 0
    maxBonesPerVertex: 4
    minBoneWeight: 0.001
    optimizeBones: 1
    meshOptimizationFlags: -1
    indexFormat: 0
    secondaryUVAngleDistortion: 8
    secondaryUVAreaDistortion: 15.000001
    secondaryUVHardAngle: 88
    secondaryUVMarginMethod: 1
    secondaryUVMinLightmapResolution: 40
    secondaryUVMinObjectScale: 1
    secondaryUVPackMargin: 4
    useFileScale: 1
    strictVertexDataChecks: 0
  tangentSpace:
    normalSmoothAngle: 60
    normalImportMode: 0
    tangentImportMode: 3
    normalCalculationMode: 4
    legacyComputeAllNormalsFromSmoothingGroupsWhenMeshHasBlendShapes: 0
    blendShapeNormalImportMode: 1
    normalSmoothingSource: 0
  referencedClips: []
  importAnimation: 0
  humanDescription:
    serializedVersion: 3
    human: []
    skeleton: []
    armTwist: 0.5
    foreArmTwist: 0.5
    upperLegTwist: 0.5
    legTwist: 0.5
    armStretch: 0.05
    legStretch: 0.05
    feetSpacing: 0
    globalScale: 1
    rootMotionBoneName: 
    hasTranslationDoF: 0
    hasExtraRoot: 0
    skeletonHasParents: 1
  lastHumanDescriptionAvatarSource: {{instanceID: 0}}
  autoGenerateAvatarMappingIfUnspecified: 1
  animationType: 0
  humanoidOversampling: 1
  avatarSetup: 0
  addHumanoidExtraRootOnlyWhenUsingAvatar: 1
  importBlendShapeDeformPercent: 1
  remapMaterialsIfMaterialImportModeIsNone: 0
  additionalBone: 0
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""


def fix_obj_metas():
    d = os.path.join(ROOT, "Assets/Models/Arena")
    n = 0
    for f in sorted(os.listdir(d)):
        if not f.endswith(".obj"):
            continue
        meta = os.path.join(d, f + ".meta")
        guid = re.search(r"guid: ([0-9a-f]{32})", open(meta).read()).group(1)
        obj = open(os.path.join(d, f)).read()
        m = re.search(r"^o (\S+)", obj, re.M)
        name = m.group(1) if m else os.path.splitext(f)[0]
        with open(meta, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(model_meta(guid, name))
        n += 1
    print(f"OBJ ModelImporter metas: {n}")


if __name__ == "__main__":
    fix_primitive()
    fix_kit()
    fix_obj_metas()
