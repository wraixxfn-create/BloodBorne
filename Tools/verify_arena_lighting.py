#!/usr/bin/env python3
"""Semantic checks for the final chamber lighting (run after structural validator).

Uses PyYAML via validate_unity_project.py. No Unity editor in this sandbox;
these tests catch missing zones, incorrect PPtrs, duplicate shadow sources,
missing mist/ritual markings and the former horizontal legacy window lights.
"""

import math
from pathlib import Path

from validate_unity_project import parse_documents
from generate_unity_guids import guid_for

ROOT = Path(__file__).resolve().parent.parent
RIG = "Assets/Prefabs/Arena/Arena_LightingRig.prefab"
MESH = "Assets/Prefabs/Arena/Arena_RitualChamber_MeshKit.prefab"
LEGACY = "Assets/Prefabs/Arena/Arena_RitualChamber.prefab"
SCENE_MESH = "Assets/Scenes/Arena/Arena_RitualChamber_MeshKit.unity"
SCENE_LEGACY = "Assets/Scenes/Arena/Arena_RitualChamber.unity"


def load(path):
    docs = parse_documents(str(ROOT / path))
    by_id = {fid: (kind, value) for kind, fid, value in docs}
    assert len(docs) == len(by_id), f"{path}: duplicate fileID"
    objects = {fid: value for kind, fid, value in docs if kind == 1}
    owners = {fid: value["m_GameObject"]["fileID"] for kind, fid, value in docs
              if kind in (4, 108, 23, 33, 65, 114)}
    transforms = {go: by_id[obj["m_Component"][0]["component"]["fileID"]][1]
                  for go, obj in objects.items()}
    names = {go: obj["m_Name"] for go, obj in objects.items()}
    lights = {fid: value for kind, fid, value in docs if kind == 108}
    return docs, by_id, objects, owners, transforms, names, lights


def headroom(room, candle_count):
    _, by_id, objects, owners, transforms, names, lights = room
    assert all(obj["m_Layer"] != 9 for obj in objects.values()), "No boss/enemy object yet"
    live = [light for light in lights.values() if light["m_Enabled"]]
    assert len(live) == candle_count + 4, "Only every-other practical and four spots are active"
    assert all(light["m_Shadows"]["m_Type"] == 0 for light in lights.values())
    assert all(light["m_Lightmapping"] == 4 for light in live), "Unbaked lights must be Realtime"
    assert all(light["m_Type"] in (0, 2) for light in lights.values())
    candles = [light for fid, light in lights.items()
               if names[owners[fid]].startswith("Candle") and light["m_Enabled"]]
    shafts = [light for fid, light in lights.items()
              if names[owners[fid]].startswith("MoonShaft") and light["m_Enabled"]]
    assert len(candles) == candle_count and len(shafts) == 4
    assert all(0.45 <= light["m_Intensity"] <= 0.56 for light in candles + shafts)
    assert all(light["m_Type"] == 2 for light in candles)
    assert all(light["m_Type"] == 0 for light in shafts)
    assert all(light["m_RenderMode"] == 2 for light in candles + shafts)

    fog = by_id[1003][1]
    practicals = by_id[1004][1]
    assert len(fog["fogPlanes"]) == 4 and fog["baseFogDensity"] <= 0.011
    assert fog["opacityBreathing"] <= 0.12
    assert len(practicals["candleLights"]) == candle_count
    assert len(practicals["moonShafts"]) == 4
    assert practicals["ritualPulseStrength"] <= 0.16
    for ref in practicals["candleLights"] + practicals["moonShafts"]:
        assert by_id[ref["fileID"]][1]["m_Enabled"] == 1

    # Spot forward vectors must descend toward the floor, not aim horizontally
    # as they did in the legacy prefab's original (incorrect) directional data.
    for fid, light in lights.items():
        if not names[owners[fid]].startswith("MoonShaft") or not light["m_Enabled"]:
            continue
        position = transforms[owners[fid]]["m_LocalPosition"]
        q = transforms[owners[fid]]["m_LocalRotation"]
        dy = 2 * (q["y"] * q["z"] - q["w"] * q["x"])
        dx = 2 * (q["x"] * q["z"] + q["w"] * q["y"])
        dz = 1 - 2 * (q["x"] ** 2 + q["y"] ** 2)
        assert (dy < -0.6 and dx * position["x"] + dz * position["z"] < -6), (
            "Window spot must aim DOWN and INWARD")
    return len(live)


def scene_check(path, offset):
    docs, _, _, _, _, _, lights = load(path)
    settings = next(v for kind, fid, v in docs if kind == 104)
    assert settings["m_Fog"] == 1 and settings["m_FogMode"] == 2
    assert settings["m_FogDensity"] <= 0.011 and settings["m_AmbientSkyColor"]["r"] >= 0.09
    assert not lights, f"{path} must not duplicate the rig's moon key"
    instances = {fid: v for kind, fid, v in docs if kind == 1001}
    rigs = [v for v in instances.values() if v["m_SourcePrefab"].get("guid") == guid_for(RIG)]
    assert len(rigs) == 1 and len(instances) == 3, f"{path}: expected player camera, arena, rig"
    roots = [v for v in instances.values() if v["m_SourcePrefab"].get("guid") == guid_for(MESH if offset == 0 else LEGACY)]
    assert len(roots) == 1, f"{path} references wrong environment prefab"
    rig_mods = rigs[0]["m_Modification"]["m_Modifications"]
    if offset == 0:
        assert not rig_mods
    else:
        assert len(rig_mods) == 1
        assert rig_mods[0]["target"]["fileID"] == 1001
        assert rig_mods[0]["propertyPath"] == "m_LocalPosition.y"
        assert rig_mods[0]["value"] == offset
    camera = next(v for v in instances.values() if v["m_SourcePrefab"].get("guid") ==
                  guid_for("Assets/Prefabs/Camera/MainCameraRig.prefab"))
    grade = {m["propertyPath"]: m["value"] for m in camera["m_Modification"]["m_Modifications"]}
    assert grade["vignetteIntensity"] <= 0.32 and grade["grainIntensity"] <= 0.03
    assert grade["contrast"] <= 1.03


def main():
    rig = load(RIG)
    _, by_id, objects, owners, transforms, names, lights = rig
    assert all(obj["m_Layer"] != 9 for obj in objects.values())
    assert objects[1000]["m_Name"] == "Arena_LightingRig"
    zone = by_id[1002][1]
    for field, label in (
        ("entranceZone", "01_Entrance"), ("centralArenaZone", "02_CentralArena"),
        ("cornersZone", "03_Corners_and_Glass"),
        ("elevatedPlatformZone", "04_ElevatedPlatform"),
        ("ritualAreaZone", "05_RitualArea"),
    ):
        transform_id = zone[field]["fileID"]
        assert by_id[transform_id][0] == 4 and names[owners[transform_id]] == label
        assert len(by_id[transform_id][1]["m_Children"]) >= 1, f"{label} has no fixtures"
    for field in ("moonKey", "subjectFill", "centralArenaFill", "elevatedPlatformFill"):
        assert by_id[zone[field]["fileID"]][0] == 108

    key = lights[zone["moonKey"]["fileID"]]
    subject = lights[zone["subjectFill"]["fileID"]]
    assert key["m_Type"] == 1 and key["m_Shadows"]["m_Type"] == 2
    assert 0.55 < key["m_Shadows"]["m_Strength"] < 0.8
    assert subject["m_Type"] == 1 and subject["m_Shadows"]["m_Type"] == 0
    assert subject["m_CullingMask"]["m_Bits"] == (1 << 8) | (1 << 9)
    assert subject["m_Intensity"] >= 0.3 and subject["m_RenderMode"] == 1
    assert sum(l["m_Enabled"] and l["m_Shadows"]["m_Type"] != 0 for l in lights.values()) == 1
    assert all(l["m_Shadows"]["m_Type"] == 0 for fid, l in lights.items()
               if names[owners[fid]].startswith("Glass_") or names[owners[fid]].startswith("Alcove_"))
    assert len(lights) == 15
    assert all(l["m_Lightmapping"] == 4 for l in lights.values())

    # The custom transparent materials must point at real shaders with a
    # bounded authored opacity. A missing shader would render pink slabs.
    for mat, shader, max_alpha in (
        ("M_Arena_GroundMist", "ArenaGroundMist", 0.075),
        ("M_Arena_VeilMoon", "ArenaLightVeil", 0.06),
        ("M_Arena_PoolBlue", "ArenaStainedLight", 0.15),
        ("M_Arena_DustMote", "ArenaMote", 0.4),
    ):
        path = f"Assets/Materials/Arena/{mat}.mat"
        material = next(value for kind, _, value in parse_documents(str(ROOT / path)) if kind == 21)
        assert material["m_Shader"]["guid"] == guid_for(
            f"Assets/Art/Shaders/{shader}.shader")
        assert 0 < material["m_SavedProperties"]["m_Colors"][0]["_Color"]["a"] <= max_alpha

    particle = by_id[1003][1]
    assert len(particle["moteAnchors"]) == 2 and particle["ritualAshAnchor"]["fileID"]
    assert particle["motesPerSecond"] <= 1.3 and particle["ashPerSecond"] <= 0.65
    for ref in particle["moteAnchors"] + [particle["ritualAshAnchor"]]:
        assert by_id[ref["fileID"]][0] == 4

    pool_names = [go for go, name in names.items() if name.endswith("_floor_pool")]
    veil_names = [go for go, name in names.items() if name.endswith("_soft_veil")]
    assert len(pool_names) == len(veil_names) == 3
    for go in pool_names + veil_names:
        assert not any(kind in (65, 64) and owners.get(fid) == go
                       for fid, (kind, _) in by_id.items()), "Decor is non-colliding"
        renderer = next(v for kind, fid, v in rig[0] if kind == 23 and owners[fid] == go)
        assert renderer["m_CastShadows"] == renderer["m_ReceiveShadows"] == 0
        assert renderer["m_Materials"][0]["guid"] != ""
        if go in pool_names:
            assert transforms[go]["m_LocalPosition"]["y"] >= 0.53
            assert math.hypot(transforms[go]["m_LocalPosition"]["x"],
                              transforms[go]["m_LocalPosition"]["z"]) > 12

    mesh = load(MESH)
    legacy = load(LEGACY)
    active_mesh = headroom(mesh, 10)
    active_legacy = headroom(legacy, 8)
    assert active_mesh + len(lights) <= 30, "Forward light budget blown"
    assert active_legacy + len(lights) <= 30
    for go, name in mesh[5].items():
        y = mesh[4][go]["m_LocalPosition"]["y"]
        if name.startswith("Fog_Volume_"):
            assert y > 0.53 and math.hypot(mesh[4][go]["m_LocalPosition"]["x"],
                                           mesh[4][go]["m_LocalPosition"]["z"]) >= 14
        elif name.startswith("Ritual_Plate_"):
            assert y > 0.5, "Ritual floor markings buried beneath 0.5m floor"
        elif name.startswith("Candle_Cluster_"):
            assert y >= 0.5, "Candle flames buried beneath 0.5m floor"

    scene_check(SCENE_MESH, 0)
    scene_check(SCENE_LEGACY, -0.5)
    build = next(v for kind, _, v in parse_documents(str(ROOT / "ProjectSettings/EditorBuildSettings.asset"))
                 if kind == 1045)
    assert build["m_Scenes"][0]["path"] == SCENE_MESH
    print("Lighting verification passed: five zones, one shadow key, subject fill,"
          f" {active_mesh + len(lights)} MeshKit lights, colored glass, mist, motes, two scenes.")


if __name__ == "__main__":
    main()
