#!/usr/bin/env python3
"""Generate the Hollow Sanctum PBR material library (masters + Material Variants).

Architecture
------------
* 9 MASTER materials (Assets/Materials/Arena/Masters/M_Master_*.mat) - one per
  physical surface family. They own the texture sets and the full property
  block.
* VARIANTS (Unity 2022 Material Variants: `m_Parent` + only the overridden
  properties serialized) for every concrete use in the arena. Editing a master
  propagates to all its children; variants never duplicate textures.
* Existing arena materials keep their file names and GUIDs, so every prefab
  and scene reference is upgraded in place.

Re-runnable; deterministic GUIDs (uuid5 of asset path) for new assets.
"""

from __future__ import annotations

import os
import re
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "vespershade://unity-project")
TEX = "Assets/Art/Textures/Environment/Arena"
MAT = "Assets/Materials/Arena"
MASTERS = f"{MAT}/Masters"

SHADER_LIT = "Assets/Art/Shaders/Environment/VesperEnvironmentLit.shader"
SHADER_GLASS = "Assets/Art/Shaders/Environment/VesperStainedGlass.shader"


def guid_for(rel: str) -> str:
    return uuid.uuid5(NAMESPACE, rel.replace(os.sep, "/")).hex


def asset_guid(rel: str) -> str:
    """Existing .meta GUID wins; otherwise the deterministic one."""
    meta = os.path.join(ROOT, rel) + ".meta"
    if os.path.exists(meta):
        m = re.search(r"guid: ([0-9a-f]{32})", open(meta, encoding="utf-8").read())
        if m:
            return m.group(1)
    return guid_for(rel)


def tex(set_name: str, suffix: str) -> str:
    return f"{TEX}/{set_name}/T_{set_name}_{suffix}.png"


MACRO = f"{TEX}/Shared/T_Arena_MacroVariation.png"
DUST_BASE = tex("Dust", "BaseColor")
DUST_NRM = tex("Dust", "Normal")

# ---------------------------------------------------------------------------
# Default property block of Vespershade/Environment/Lit (mirrors the shader)
# ---------------------------------------------------------------------------
LIT_FLOATS = {
    "_BumpScale": 1, "_RoughnessMin": 0, "_RoughnessMax": 1, "_Metallic": 0,
    "_OcclusionStrength": 1, "_UVMapping": 0, "_TileSize": 2, "_BlendSharpness": 6,
    "_ObjectSpace": 0, "_MacroScale": 9, "_MacroAlbedo": 0.12, "_MacroRoughness": 0.05,
    "_VariationTintStrength": 0, "_ObjectVariation": 0.06, "_GrimeHeight": 1.5,
    "_GrimeStrength": 0, "_StreakStrength": 0, "_DustAmount": 0, "_DustSharpness": 3,
    "_DustCavityBias": 0.6, "_DustTileSize": 1.2, "_EmissionUV": 0,
    "_EmissionFlow": 0, "_EmissionFlowSpeed": 0.4, "_RitualPulse": 0,
    "_UseTranslucency": 0, "_Translucency": 0, "_TranslucencyWrap": 0.5,
}
LIT_COLORS = {
    "_Color": (1, 1, 1, 1), "_VariationTint": (1, 1, 1, 1), "_DustColor": (1, 1, 1, 1),
    "_DustCenter": (0, 0, 0, 0), "_DustRadius": (0, 0, 1, 0), "_EmissionColor": (0, 0, 0, 1),
    "_TranslucencyColor": (1, 0.55, 0.25, 1),
}
LIT_TEXTURES = ["_MainTex", "_BumpMap", "_RoughnessMap", "_MetallicGlossMap", "_OcclusionMap",
                "_MacroMap", "_DustMap", "_DustBumpMap", "_EmissionMap"]

GLASS_FLOATS = {"_SecondaryThreshold": 0.55, "_AccentThreshold": 0.9, "_BumpScale": 1,
                "_TileSize": 1.2, "_BlendSharpness": 8, "_GlassOpacity": 0.42,
                "_Transmission": 0.35, "_GrimeDarkening": 0.35, "_MacroScale": 5}
GLASS_COLORS = {"_Color": (0.2, 0.32, 0.7, 1), "_ColorSecondary": (0.3, 0.18, 0.55, 1),
                "_ColorAccent": (0.85, 0.55, 0.18, 1)}
GLASS_TEXTURES = ["_MainTex", "_BumpMap", "_RoughnessMap", "_MetallicGlossMap", "_OcclusionMap", "_MacroMap"]

KEYWORD_TOGGLES = {"_UVMapping": "_UV_MAPPING", "_EmissionUV": "_EMISSION_UV",
                   "_UseTranslucency": "_TRANSLUCENCY"}


def lit_set(set_name, metallic=False, emission=None):
    t = {
        "_MainTex": tex(set_name, "BaseColor"),
        "_BumpMap": tex(set_name, "Normal"),
        "_RoughnessMap": tex(set_name, "Roughness"),
        "_OcclusionMap": tex(set_name, "AO"),
        "_MacroMap": MACRO,
        "_DustMap": DUST_BASE,
        "_DustBumpMap": DUST_NRM,
    }
    if metallic:
        t["_MetallicGlossMap"] = tex(set_name, "Metallic")
    if emission:
        t["_EmissionMap"] = emission
    return t


# ---------------------------------------------------------------------------
# MASTERS
# ---------------------------------------------------------------------------
MASTER_DEFS = {
    "M_Master_OldStone": dict(
        shader="lit", textures=lit_set("OldStone"),
        floats={"_TileSize": 2.4, "_RoughnessMin": 0.55, "_RoughnessMax": 1.0, "_MacroAlbedo": 0.14,
                "_MacroRoughness": 0.05, "_VariationTintStrength": 0.35, "_ObjectVariation": 0.07,
                "_GrimeHeight": 1.8, "_GrimeStrength": 0.45, "_StreakStrength": 0.35,
                "_DustAmount": 0.25, "_DustSharpness": 4},
        colors={"_Color": (0.96, 0.96, 1.0, 1), "_VariationTint": (1.08, 0.97, 0.84, 1),
                "_DustColor": (0.92, 0.9, 0.88, 1)},
        doc="Salt-bitten ashlar masonry - walls, pillars, floors, trims."),
    "M_Master_CrackedStone": dict(
        shader="lit", textures=lit_set("CrackedStone"),
        floats={"_TileSize": 1.5, "_RoughnessMin": 0.6, "_RoughnessMax": 1.0, "_MacroAlbedo": 0.12,
                "_VariationTintStrength": 0.25, "_ObjectVariation": 0.08,
                "_GrimeHeight": 1.2, "_GrimeStrength": 0.35, "_DustAmount": 0.35, "_DustSharpness": 3},
        colors={"_VariationTint": (0.9, 0.95, 0.88, 1)},
        doc="Monolithic fractured, spalled stone - statues, broken pillars, rubble."),
    "M_Master_DarkWood": dict(
        shader="lit", textures=lit_set("DarkWood"),
        floats={"_TileSize": 1.2, "_ObjectSpace": 1, "_BlendSharpness": 10, "_RoughnessMin": 0.45,
                "_RoughnessMax": 1.0, "_MacroAlbedo": 0.1, "_ObjectVariation": 0.12,
                "_DustAmount": 0.3, "_DustSharpness": 3},
        colors={},
        doc="Aged, checked, ebonised timber - beams, braces, scaffolds, doors."),
    "M_Master_AgedMetal": dict(
        shader="lit", textures=lit_set("AgedMetal", metallic=True),
        floats={"_TileSize": 0.6, "_ObjectSpace": 1, "_Metallic": 1, "_RoughnessMin": 0.12,
                "_RoughnessMax": 1.0, "_MacroAlbedo": 0.08, "_ObjectVariation": 0.08,
                "_DustAmount": 0.15, "_DustSharpness": 4},
        colors={},
        doc="Blackened wrought iron with rust blooms - chains, hooks, gates."),
    "M_Master_OxidizedMetal": dict(
        shader="lit", textures=lit_set("OxidizedMetal", metallic=True),
        floats={"_TileSize": 0.5, "_ObjectSpace": 1, "_Metallic": 1, "_RoughnessMin": 0.1,
                "_RoughnessMax": 1.0, "_MacroAlbedo": 0.08, "_ObjectVariation": 0.1,
                "_DustAmount": 0.2},
        colors={},
        doc="Cast bronze under verdigris runs - braziers, candle holders, fittings."),
    "M_Master_StainedGlass": dict(
        shader="glass", textures={
            "_MainTex": tex("StainedGlass", "BaseColor"), "_BumpMap": tex("StainedGlass", "Normal"),
            "_RoughnessMap": tex("StainedGlass", "Roughness"),
            "_MetallicGlossMap": tex("StainedGlass", "Metallic"),
            "_OcclusionMap": tex("StainedGlass", "AO"), "_MacroMap": MACRO},
        floats={}, colors={},
        doc="Leaded glass, 3-colour palette per variant, fake moonlight transmission."),
    "M_Master_CandleWax": dict(
        shader="lit", textures=lit_set("CandleWax"),
        floats={"_TileSize": 0.22, "_ObjectSpace": 1, "_BlendSharpness": 4, "_RoughnessMin": 0.2,
                "_RoughnessMax": 0.9, "_MacroAlbedo": 0.06, "_ObjectVariation": 0.1,
                "_UseTranslucency": 1, "_Translucency": 0.9, "_TranslucencyWrap": 0.6,
                "_BumpScale": 0.8},
        colors={"_TranslucencyColor": (1.0, 0.62, 0.32, 1)},
        doc="Layered drip wax with wrap/back-lit translucency."),
    "M_Master_DustySurface": dict(
        shader="lit", textures=lit_set("Dust"),
        floats={"_TileSize": 1.2, "_RoughnessMin": 0.7, "_RoughnessMax": 1.0, "_MacroAlbedo": 0.12,
                "_ObjectVariation": 0.05, "_DustAmount": 0.0, "_BumpScale": 1.0},
        colors={},
        doc="Settled dust drifts / powdered debris. Other masters get dust as a layer."),
    "M_Master_RitualSurface": dict(
        shader="lit", textures=lit_set("Ritual", emission=tex("Ritual", "Emission")),
        floats={"_TileSize": 2.0, "_RoughnessMin": 0.08, "_RoughnessMax": 1.0, "_MacroAlbedo": 0.08,
                "_MacroRoughness": 0.08, "_ObjectVariation": 0.03, "_EmissionFlow": 0.45,
                "_EmissionFlowSpeed": 0.35, "_DustAmount": 0.2, "_DustSharpness": 3},
        colors={"_EmissionColor": (0.16, 0.52, 0.58, 1)},
        doc="Polished basalt with carved glyphs seeping cold light."),
}

# ---------------------------------------------------------------------------
# VARIANTS  (path relative to MAT, parent master, overrides)
# `existing` = keep the file's current GUID (already referenced by prefabs)
# ---------------------------------------------------------------------------
DUST_SWEPT = {"_DustCenter": (0, 0, 0, 0), "_DustRadius": (6.5, 17.5, 0.3, 0)}

VARIANT_DEFS = {
    # ---- old stone -------------------------------------------------------
    "M_Arena_StoneWall": ("M_Master_OldStone",
        {"_TileSize": 2.4, "_GrimeHeight": 2.4, "_StreakStrength": 0.5},
        {"_Color": (0.93, 0.93, 0.97, 1)}, {}),
    "M_Arena_StonePillar": ("M_Master_OldStone",
        {"_TileSize": 1.6, "_GrimeHeight": 1.4, "_DustAmount": 0.45},
        {"_Color": (1.0, 0.99, 1.0, 1)}, {}),
    "M_Arena_StoneTrim": ("M_Master_OldStone",
        {"_TileSize": 1.2, "_RoughnessMin": 0.45, "_StreakStrength": 0.15},
        {"_Color": (1.04, 1.02, 1.02, 1)}, {}),
    "M_Arena_StoneFloor": ("M_Master_OldStone",
        {"_TileSize": 3.6, "_RoughnessMin": 0.4, "_GrimeHeight": 0.6, "_GrimeStrength": 0.25,
         "_StreakStrength": 0, "_DustAmount": 0.9, "_DustSharpness": 2, "_MacroScale": 14},
        dict({"_Color": (0.86, 0.86, 0.9, 1)}, **DUST_SWEPT), {}),
    # ---- cracked stone ---------------------------------------------------
    "M_Arena_Statue_Eroded": ("M_Master_CrackedStone",
        {"_TileSize": 0.9, "_DustAmount": 0.55, "_DustSharpness": 2.5, "_GrimeHeight": 0.9},
        {"_Color": (1.06, 1.05, 1.06, 1)}, {}),
    "M_Arena_Stone_Cracked": ("M_Master_CrackedStone",
        {"_TileSize": 1.6, "_DustAmount": 0.4}, {"_Color": (0.92, 0.92, 0.95, 1)}, {}),
    "M_Arena_Stone_Rubble": ("M_Master_CrackedStone",
        {"_TileSize": 0.7, "_DustAmount": 0.85, "_DustSharpness": 1.5, "_ObjectVariation": 0.15},
        {"_Color": (0.9, 0.89, 0.9, 1)}, {}),
    # ---- dark wood -------------------------------------------------------
    "M_Arena_Wood_Rotted": ("M_Master_DarkWood",
        {"_TileSize": 1.0, "_RoughnessMin": 0.6, "_DustAmount": 0.55, "_GrimeStrength": 0.4,
         "_GrimeHeight": 0.8, "_BumpScale": 1.3},
        {"_Color": (1.1, 1.05, 1.0, 1)}, {}),
    "M_Arena_Door_Wood": ("M_Master_DarkWood",
        {"_TileSize": 1.4, "_RoughnessMin": 0.35, "_DustAmount": 0.15},
        {"_Color": (0.82, 0.8, 0.8, 1)}, {}),
    # ---- metals ----------------------------------------------------------
    "M_Arena_Metal_Chain": ("M_Master_AgedMetal",
        {"_TileSize": 0.3, "_DustAmount": 0.1}, {}, {}),
    "M_Arena_Door_Iron": ("M_Master_AgedMetal",
        {"_TileSize": 0.8, "_GrimeStrength": 0.4, "_GrimeHeight": 1.2}, {}, {}),
    "M_Arena_Brazier_Metal": ("M_Master_OxidizedMetal",
        {"_TileSize": 0.35}, {}, {}),
    "M_Arena_Metal_Verdigris_Heavy": ("M_Master_OxidizedMetal",
        {"_TileSize": 0.5, "_RoughnessMin": 0.3, "_DustAmount": 0.35},
        {"_Color": (0.95, 1.0, 0.98, 1)}, {}),
    # ---- glass -----------------------------------------------------------
    "M_Arena_Glass_Blue": ("M_Master_StainedGlass", {"_Transmission": 0.38},
        {"_Color": (0.16, 0.27, 0.62, 1), "_ColorSecondary": (0.26, 0.2, 0.5, 1),
         "_ColorAccent": (0.78, 0.6, 0.26, 1)}, {}),
    "M_Arena_Glass_Red": ("M_Master_StainedGlass", {"_Transmission": 0.3, "_SecondaryThreshold": 0.6},
        {"_Color": (0.52, 0.08, 0.08, 1), "_ColorSecondary": (0.36, 0.06, 0.14, 1),
         "_ColorAccent": (0.2, 0.3, 0.55, 1)}, {}),
    "M_Arena_Glass_Amber": ("M_Master_StainedGlass", {"_Transmission": 0.32},
        {"_Color": (0.72, 0.46, 0.14, 1), "_ColorSecondary": (0.55, 0.36, 0.12, 1),
         "_ColorAccent": (0.3, 0.45, 0.35, 1)}, {}),
    # ---- wax -------------------------------------------------------------
    "M_Arena_Candle_Wax": ("M_Master_CandleWax", {}, {}, {}),
    "M_Arena_Candle_Wax_Ritual": ("M_Master_CandleWax",
        {"_Translucency": 0.7, "_RoughnessMin": 0.12},
        {"_Color": (0.42, 0.12, 0.1, 1), "_TranslucencyColor": (1.0, 0.3, 0.18, 1)}, {}),
    # ---- dust ------------------------------------------------------------
    "M_Arena_Dust_Drift": ("M_Master_DustySurface", {}, {}, {}),
    "M_Arena_Dust_Ash": ("M_Master_DustySurface",
        {"_RoughnessMin": 0.85}, {"_Color": (0.62, 0.62, 0.66, 1)}, {}),
    "M_Arena_Moss": ("M_Master_DustySurface",
        {"_RoughnessMin": 0.75, "_TileSize": 0.8, "_MacroAlbedo": 0.2},
        {"_Color": (0.42, 0.55, 0.36, 1)}, {}),
    # ---- ritual ----------------------------------------------------------
    "M_Arena_StoneFloor_Ritual": ("M_Master_RitualSurface",
        {"_TileSize": 2.0, "_EmissionFlow": 0.5},
        dict({"_EmissionColor": (0.1, 0.34, 0.38, 1)}, **{"_DustCenter": (0, 0, 0, 0),
             "_DustRadius": (4.2, 7.2, 0.0, 0)}), {}),
    "M_Arena_RitualMarking": ("M_Master_RitualSurface",
        {"_EmissionUV": 1, "_EmissionFlow": 0.35, "_DustAmount": 0},
        {"_EmissionColor": (0.3, 0.95, 1.05, 1)},
        {"_EmissionMap": f"{TEX}/Ritual/T_Ritual_GlyphStrip_Emission.png"}),
    "M_Arena_RitualSigil": ("M_Master_RitualSurface",
        {"_EmissionUV": 1, "_EmissionFlow": 0.3, "_DustAmount": 0},
        {"_EmissionColor": (0.32, 1.0, 1.1, 1)},
        {"_EmissionMap": f"{TEX}/Ritual/T_Ritual_Sigil_Emission.png"}),
    "M_Arena_Ritual_Altar": ("M_Master_RitualSurface",
        {"_TileSize": 1.2, "_EmissionFlow": 0.6}, {"_EmissionColor": (0.08, 0.26, 0.3, 1)}, {}),
}


# ---------------------------------------------------------------------------
# YAML emission
# ---------------------------------------------------------------------------

def fmt(v):
    if isinstance(v, float):
        s = f"{v:.4f}".rstrip("0").rstrip(".")
        return s if s not in ("", "-0") else "0"
    return str(v)


def color_line(name, c):
    r, g, b, a = c
    return f"    - {name}: {{r: {fmt(float(r))}, g: {fmt(float(g))}, b: {fmt(float(b))}, a: {fmt(float(a))}}}"


def tex_block(name, rel, scale=(1, 1)):
    ref = f"{{fileID: 2800000, guid: {asset_guid(rel)}, type: 3}}" if rel else "{fileID: 0}"
    return (f"    - {name}:\n"
            f"        m_Texture: {ref}\n"
            f"        m_Scale: {{x: {scale[0]}, y: {scale[1]}}}\n"
            f"        m_Offset: {{x: 0, y: 0}}")


def keywords_for(floats):
    return sorted(kw for prop, kw in KEYWORD_TOGGLES.items() if float(floats.get(prop, 0)) > 0.5)


def material_yaml(name, shader_rel, parent_rel, textures, floats, colors, keywords, transparent):
    parent = (f"{{fileID: 2100000, guid: {asset_guid(parent_rel)}, type: 2}}" if parent_rel else "{fileID: 0}")
    kw = "[]" if not keywords else "\n" + "\n".join(f"  - {k}" for k in keywords)
    tex_lines = "\n".join(tex_block(k, v) for k, v in textures.items())
    float_lines = "\n".join(f"    - {k}: {fmt(float(v))}" for k, v in sorted(floats.items()))
    color_lines = "\n".join(color_line(k, v) for k, v in sorted(colors.items()))
    tag = "\n    RenderType: Transparent" if transparent else " {}"
    return f"""%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!21 &2100000
Material:
  serializedVersion: 8
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_Name: {name}
  m_Shader: {{fileID: 4800000, guid: {asset_guid(shader_rel)}, type: 3}}
  m_Parent: {parent}
  m_ModifiedSerializedProperties: 0
  m_ValidKeywords: {kw}
  m_InvalidKeywords: []
  m_LightmapFlags: 2
  m_EnableInstancingVariants: 1
  m_DoubleSidedGI: 0
  m_CustomRenderQueue: -1
  stringTagMap:{tag}
  disabledShaderPasses: []
  m_LockedProperties: 
  m_SavedProperties:
    serializedVersion: 3
    m_TexEnvs:{(chr(10) + tex_lines) if tex_lines else ' []'}
    m_Ints: []
    m_Floats:{(chr(10) + float_lines) if float_lines else ' []'}
    m_Colors:{(chr(10) + color_lines) if color_lines else ' []'}
  m_BuildTextureStacks: []
  m_AllowLocking: 1
"""


def mat_meta(guid):
    return ("fileFormatVersion: 2\n"
            f"guid: {guid}\n"
            "NativeFormatImporter:\n"
            "  externalObjects: {}\n"
            "  mainObjectFileID: 2100000\n"
            "  userData: \n"
            "  assetBundleName: \n"
            "  assetBundleVariant: \n")


def write(rel, text):
    path = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def ensure_meta(rel, guid_text):
    meta = os.path.join(ROOT, rel) + ".meta"
    if not os.path.exists(meta):
        write(rel + ".meta", guid_text)


def folder_meta(rel):
    meta = os.path.join(ROOT, rel) + ".meta"
    if not os.path.exists(meta):
        write(rel + ".meta", "fileFormatVersion: 2\n"
              f"guid: {guid_for(rel)}\nfolderAsset: yes\nDefaultImporter:\n"
              "  externalObjects: {}\n  userData: \n  assetBundleName: \n  assetBundleVariant: \n")


def master_full_block(defn):
    if defn["shader"] == "glass":
        floats = dict(GLASS_FLOATS)
        colors = dict(GLASS_COLORS)
        textures = {k: None for k in GLASS_TEXTURES}
    else:
        floats = dict(LIT_FLOATS)
        colors = dict(LIT_COLORS)
        textures = {k: None for k in LIT_TEXTURES}
    floats.update(defn["floats"])
    colors.update(defn["colors"])
    textures.update(defn["textures"])
    return textures, floats, colors


def main():
    os.makedirs(os.path.join(ROOT, MASTERS), exist_ok=True)
    folder_meta(MASTERS)
    master_state = {}
    for name, d in MASTER_DEFS.items():
        rel = f"{MASTERS}/{name}.mat"
        textures, floats, colors = master_full_block(d)
        shader = SHADER_GLASS if d["shader"] == "glass" else SHADER_LIT
        master_state[name] = (shader, textures, floats, d["shader"] == "glass")
        write(rel, material_yaml(name, shader, None, textures, floats, colors,
                                 keywords_for(floats), d["shader"] == "glass"))
        ensure_meta(rel, mat_meta(guid_for(rel)))
        print(f"master  {rel}")

    for name, (parent, fov, cov, tov) in VARIANT_DEFS.items():
        rel = f"{MAT}/{name}.mat"
        shader, _, pfloats, transparent = master_state[parent]
        merged = dict(pfloats)
        merged.update(fov)
        write(rel, material_yaml(name, shader, f"{MASTERS}/{parent}.mat", tov, fov, cov,
                                 keywords_for(merged), transparent))
        ensure_meta(rel, mat_meta(guid_for(rel)))
        print(f"variant {rel}  <- {parent}")


if __name__ == "__main__":
    main()
