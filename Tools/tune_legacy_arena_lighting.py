#!/usr/bin/env python3
"""Bring the original primitive chamber's practicals in line with the shared rig.

Unlike the MeshKit prefab, this original master was hand assembled. Patch its
existing object IDs rather than regenerating the geometry. Idempotent; requires
only the Python standard library. Both scene variants use Arena_LightingRig.
"""

import math
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PATH = ROOT / "Assets/Prefabs/Arena/Arena_RitualChamber.prefab"
text = PATH.read_text(encoding="utf-8")
chunks = re.split(r"(?=^--- !u!\d+ &\d+\s*$)", text, flags=re.M)
header, docs = chunks[0], chunks[1:]


def info(doc):
    m = re.match(r"--- !u!(\d+) &(\d+)", doc)
    return (int(m[1]), int(m[2])) if m else (-1, -1)


names = {}
for doc in docs:
    if info(doc)[0] == 1:
        name = re.search(r"(?m)^  m_Name: (.*)$", doc)
        names[info(doc)[1]] = name[1] if name else ""


def owner(doc):
    m = re.search(r"m_GameObject: \{fileID: (\d+)\}", doc)
    return names.get(int(m[1]), "") if m else ""


candles, shafts, fog_planes, ritual = [], [], [], []
new_docs = []
for doc in docs:
    class_id, file_id = info(doc)
    name = owner(doc)
    if class_id == 4:
        if name.startswith("FogPlane_Large_"):
            fog_planes.append(file_id)
        elif name.startswith("MoonShaft_"):
            # The legacy shafts were eight *horizontal* directionals. A true
            # window spot has to aim 50 degrees down toward the stone floor.
            degrees = float(name.rsplit("_", 1)[1])
            yaw = 270.0 - degrees
            pitch = 50.0
            x, y = math.radians(pitch) / 2, math.radians(yaw) / 2
            qx, qy, qz, qw = (math.sin(x) * math.cos(y),
                              math.cos(x) * math.sin(y),
                             -math.sin(x) * math.sin(y),
                              math.cos(x) * math.cos(y))
            doc = re.sub(r"(?m)^  m_LocalRotation: .*?$",
                f"  m_LocalRotation: {{x: {qx:.7f}, y: {qy:.7f}, z: {qz:.7f}, w: {qw:.7f}}}", doc)
            doc = re.sub(r"(?m)^  m_LocalEulerAnglesHint: .*?$",
                f"  m_LocalEulerAnglesHint: {{x: {pitch}, y: {yaw}, z: 0}}", doc)
    elif class_id == 23:
        if name.startswith(("RitualMarking_", "RitualRuneInner_", "RitualCircle_")):
            ritual.append(file_id)
        if name.startswith(("FogPlane_", "MistVolume_", "DarkCornerFog_",
                            "CandleFlame_", "WindowGlass_", "RitualMarking_",
                            "RitualRuneInner_", "RitualCircle_")):
            doc = re.sub(r"(?m)^  m_CastShadows: \d+$", "  m_CastShadows: 0", doc)
    elif class_id == 108:
        is_candle = name.startswith("CandleLight_")
        is_shaft = name.startswith("MoonShaft_")
        if is_candle or is_shaft:
            if is_candle:
                # 4 every-other platform flames + 4 wall practicals. Statue
                # candles remain visibly emissive; their nearby walls light them.
                enabled = name.startswith("CandleLight_Wall_") or (
                    name.startswith("CandleLight_Platform_") and
                    int(name.rsplit("_", 1)[1]) % 90 == 0)
                intensity = 0.5 if name.startswith("CandleLight_Wall_") else 0.51
                radius = 4.6
                kind = 2  # the original prefab incorrectly serialized these as spots
                if enabled: candles.append(file_id)
            else:
                enabled = name.rsplit("_", 1)[1] in ("067.5", "112.5", "202.5", "337.5")
                intensity, radius, kind = 0.52, 20, 0  # originally 8 shadowed DIRECTIONALS
                if enabled: shafts.append(file_id)
            doc = re.sub(r"(?m)^  m_Enabled: \d+$", f"  m_Enabled: {int(enabled)}", doc)
            doc = re.sub(r"(?m)^  m_Type: \d+$", f"  m_Type: {kind}", doc, count=1)
            doc = re.sub(r"(?m)^  m_Intensity: [\d.]+$", f"  m_Intensity: {intensity}", doc)
            doc = re.sub(r"(?m)^  m_Range: [\d.]+$", f"  m_Range: {radius}", doc)
            doc = re.sub(r"(?m)^  m_SpotAngle: [\d.]+$", "  m_SpotAngle: 42", doc)
            doc = re.sub(r"(?m)^(  m_Shadows:\n    m_Type:) \d+", r"\g<1> 0", doc)
            doc = re.sub(r"(?m)^  m_RenderMode: \d+$", "  m_RenderMode: 2", doc)
            doc = re.sub(r"(?m)^  m_Lightmapping: \d+$", "  m_Lightmapping: 4", doc)
    new_docs.append(doc)

assert len(candles) == 8 and len(shafts) == 4, (len(candles), len(shafts))
assert len(fog_planes) == 4 and len(ritual) >= 17, (len(fog_planes), len(ritual))


def refs(ids):
    return "".join(f"  - {{fileID: {fid}}}\n" for fid in ids)


for i, doc in enumerate(new_docs):
    if info(doc) == (114, 1003):  # ArenaFogController
        head = doc.split("  fogPlanes:", 1)[0]
        new_docs[i] = head + f"""  fogPlanes:
{refs(fog_planes)}  driftAmplitude: 0.25
  opacityBreathing: 0.1
  baseFogDensity: 0.01
  extraFogDensity: 0.0015
  fogColor: {{r: 0.027, g: 0.033, b: 0.05, a: 1}}
  driftSpeed: 0.11
  breathingSpeed: 0.19
"""
    elif info(doc) == (114, 1004):  # ArenaLightingController
        field = "  moonLight:" if "  moonLight:" in doc else "  candleLights:"
        head = doc.split(field, 1)[0]
        new_docs[i] = head + f"""  candleLights:
{refs(candles)}  candleFlickerAmplitude: 0.12
  candleFlickerSpeed: 5.2
  moonShafts:
{refs(shafts)}  shaftBreathing: 0.035
  ritualEmissiveRenderers:
{refs(ritual)}  ritualPulseSpeed: 0.32
  ritualPulseStrength: 0.14
"""

updated = header + "".join(new_docs)
if updated != text:
    PATH.write_text(updated, encoding="utf-8")
print(f"Tuned {PATH.relative_to(ROOT)}: {len(candles)} candles, {len(shafts)} spots, {len(fog_planes)} mist planes")

# The original scene's ground top is y=0, versus y=0.5 for the MeshKit.
# Reuse the same lighting rig, lowered by half a meter so the stained-glass
# pools sit ON the floor in both versions, rather than making two rigs.
from generate_unity_guids import guid_for

scene_path = ROOT / "Assets/Scenes/Arena/Arena_RitualChamber.unity"
scene = scene_path.read_text(encoding="utf-8")
scene = scene.replace("m_FogColor: {r: 0.028, g: 0.032, b: 0.048, a: 1}",
                      "m_FogColor: {r: 0.027, g: 0.033, b: 0.05, a: 1}")
scene = scene.replace("  m_FogMode: 3", "  m_FogMode: 2")
scene = scene.replace("  m_FogDensity: 0.015", "  m_FogDensity: 0.01")
scene = scene.replace("m_AmbientSkyColor: {r: 0.11, g: 0.115, b: 0.17, a: 1}",
                      "m_AmbientSkyColor: {r: 0.10, g: 0.112, b: 0.15, a: 1}")
scene = scene.replace("m_AmbientEquatorColor: {r: 0.105, g: 0.115, b: 0.135, a: 1}",
                      "m_AmbientEquatorColor: {r: 0.08, g: 0.095, b: 0.13, a: 1}")
scene = scene.replace("m_AmbientGroundColor: {r: 0.042, g: 0.038, b: 0.032, a: 1}",
                      "m_AmbientGroundColor: {r: 0.045, g: 0.05, b: 0.068, a: 1}")
scene = scene.replace("  m_ReflectionIntensity: 1", "  m_ReflectionIntensity: 0.35")
if "--- !u!1 &10000\nGameObject:" in scene:
    start = scene.index("--- !u!1 &10000\nGameObject:")
    end = scene.index("--- !u!1 &20000\nGameObject:", start)
    scene = scene[:start] + scene[end:]

camera_guid = guid_for("Assets/Prefabs/Camera/MainCameraRig.prefab")
cam_start = scene.index("--- !u!1001 &50000\nPrefabInstance:")
cam_end = scene.index("--- !u!1001 &60000\nPrefabInstance:", cam_start)
cam_block = scene[cam_start:cam_end]
if "propertyPath: vignetteIntensity" not in cam_block:
    mods = "".join(
        f"    - target: {{fileID: 720005, guid: {camera_guid}, type: 3}}\n"
        f"      propertyPath: {field}\n"
        f"      value: {value}\n"
        "      objectReference: {fileID: 0}\n"
        for field, value in (
            ("vignetteIntensity", 0.3), ("vignetteRadius", 0.62),
            ("contrast", 1.02), ("grainIntensity", 0.025)))
    cam_block = cam_block.replace("    m_Modifications: []\n", "    m_Modifications:\n" + mods)
    scene = scene[:cam_start] + cam_block + scene[cam_end:]

rig_guid = guid_for("Assets/Prefabs/Arena/Arena_LightingRig.prefab")
if f"guid: {rig_guid}" not in scene:
    scene = scene.rstrip() + f"""
--- !u!1001 &70000
PrefabInstance:
  m_ObjectHideFlags: 0
  serializedVersion: 3
  m_Modification:
    serializedVersion: 3
    m_TransformParent: {{fileID: 0}}
    m_Modifications:
    - target: {{fileID: 1001, guid: {rig_guid}, type: 3}}
      propertyPath: m_LocalPosition.y
      value: -0.5
      objectReference: {{fileID: 0}}
    m_RemovedComponents: []
    m_RemovedGameObjects: []
    m_AddedGameObjects: []
    m_AddedComponents: []
  m_SourcePrefab: {{fileID: 1000, guid: {rig_guid}, type: 3}}
"""
if scene != scene_path.read_text(encoding="utf-8"):
    scene_path.write_text(scene, encoding="utf-8")
print(f"Tuned {scene_path.relative_to(ROOT)} with the shared lighting rig at y=-0.5")
