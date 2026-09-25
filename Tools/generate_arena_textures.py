#!/usr/bin/env python3
"""Generate the Hollow Sanctum PBR texture sets + Unity TextureImporter metas.

All textures are procedurally synthesised (tileable, deterministic) - no
photo sources, no external assets. Re-running produces byte-identical PNGs.

    pip install numpy scipy pillow
    python3 Tools/generate_arena_textures.py            # all sets
    python3 Tools/generate_arena_textures.py OldStone   # a single set

Output: Assets/Art/Textures/Environment/Arena/<Set>/T_<Set>_<Map>.png
Map conventions (Built-in pipeline, Vespershade/Environment shaders):
  _BaseColor  sRGB RGB(A)   albedo (glass: A = palette key, dust: A = density)
  _Normal     linear RGB    tangent-space, OpenGL +Y (Unity native)
  _Roughness  linear R8     authored as roughness (shader converts to smoothness)
  _Metallic   linear R8     only for sets that actually contain metal
  _AO         linear R8     ambient occlusion
  _Emission   linear R8     ritual glyph mask
"""

from __future__ import annotations

import os
import sys
import uuid

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "texgen"))

import sets  # noqa: E402
from texlib import linear_to_srgb  # noqa: E402,F401

ROOT = os.path.dirname(HERE)
OUT_REL = "Assets/Art/Textures/Environment/Arena"
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "vespershade://unity-project")


def guid_for(rel: str) -> str:
    return uuid.uuid5(NAMESPACE, rel.replace(os.sep, "/")).hex


# name -> (recipe, kwargs, max import size)
SETS = {
    "OldStone":      (sets.old_stone,      {"size": 1024}, 1024),
    "CrackedStone":  (sets.cracked_stone,  {"size": 1024}, 1024),
    "DarkWood":      (sets.dark_wood,      {"size": 1024}, 1024),
    "AgedMetal":     (sets.aged_metal,     {"size": 512},  512),
    "OxidizedMetal": (sets.oxidized_metal, {"size": 512},  512),
    "StainedGlass":  (sets.stained_glass,  {"size": 1024}, 1024),
    "CandleWax":     (sets.candle_wax,     {"size": 512},  512),
    "Dust":          (sets.dust,           {"size": 512},  512),
    "Ritual":        (sets.ritual_surface, {"size": 1024}, 1024),
}

MAP_SUFFIX = {
    "base": "BaseColor",
    "normal": "Normal",
    "roughness": "Roughness",
    "metallic": "Metallic",
    "ao": "AO",
    "emission": "Emission",
}


# ---------------------------------------------------------------------------
# PNG writers
# ---------------------------------------------------------------------------

def _u8(x):
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def save_png(path, arr, mode):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(arr, mode).save(path, optimize=True)


def write_map(rel, kind, data, alpha=None):
    path = os.path.join(ROOT, rel)
    if kind == "base":
        rgb = _u8(data)
        if alpha is not None:
            save_png(path, np.dstack([rgb, _u8(alpha)]), "RGBA")
        else:
            save_png(path, rgb, "RGB")
    elif kind == "normal":
        save_png(path, _u8(data * 0.5 + 0.5), "RGB")
    elif kind == "macro":
        save_png(path, _u8(data), "RGB")
    else:
        save_png(path, _u8(data), "L")


# ---------------------------------------------------------------------------
# TextureImporter metas (Unity 2022.3)
# ---------------------------------------------------------------------------

def texture_meta(guid, kind, max_size, has_alpha=False):
    srgb = 1 if kind in ("base", "macro_srgb") else 0
    texture_type = {"normal": 1}.get(kind, 0)
    single = kind in ("roughness", "metallic", "ao", "emission")
    if single:
        texture_type = 10  # Single Channel
    aniso = 8 if kind in ("base", "normal", "roughness", "ao") else 4
    alpha_usage = 1 if (kind == "base" and has_alpha) else (0 if kind != "base" else 1)
    return f"""fileFormatVersion: 2
guid: {guid}
TextureImporter:
  internalIDToNameTable: []
  externalObjects: {{}}
  serializedVersion: 12
  mipmaps:
    mipMapMode: 0
    enableMipMap: 1
    sRGBTexture: {srgb}
    linearTexture: 0
    fadeOut: 0
    borderMipMap: 0
    mipMapsPreserveCoverage: 0
    alphaTestReferenceValue: 0.5
    mipMapFadeDistanceStart: 1
    mipMapFadeDistanceEnd: 3
  bumpmap:
    convertToNormalMap: 0
    externalNormalMap: 0
    heightScale: 0.25
    normalMapFilter: 0
    flipGreenChannel: 0
  isReadable: 0
  streamingMipmaps: 1
  streamingMipmapsPriority: 0
  vTOnly: 0
  ignoreMipmapLimit: 0
  grayScaleToAlpha: 0
  generateCubemap: 6
  cubemapConvolution: 0
  seamlessCubemap: 0
  textureFormat: 1
  maxTextureSize: 2048
  textureSettings:
    serializedVersion: 2
    filterMode: 2
    aniso: {aniso}
    mipBias: 0
    wrapU: 0
    wrapV: 0
    wrapW: 0
  nPOTScale: 1
  lightmap: 0
  compressionQuality: 50
  spriteMode: 0
  spriteExtrude: 1
  spriteMeshType: 1
  alignment: 0
  spritePivot: {{x: 0.5, y: 0.5}}
  spritePixelsToUnits: 100
  spriteBorder: {{x: 0, y: 0, z: 0, w: 0}}
  spriteGenerateFallbackPhysicsShape: 1
  alphaUsage: {alpha_usage}
  alphaIsTransparency: 0
  spriteTessellationDetail: -1
  textureType: {texture_type}
  textureShape: 1
  singleChannelComponent: {1 if single else 0}
  flipbookRows: 1
  flipbookColumns: 1
  maxTextureSizeSet: 0
  compressionQualitySet: 0
  textureFormatSet: 0
  ignorePngGamma: 0
  applyGammaDecoding: 0
  swizzle: 50462976
  cookieLightType: 0
  platformSettings:
  - serializedVersion: 3
    buildTarget: DefaultTexturePlatform
    maxTextureSize: {max_size}
    resizeAlgorithm: 0
    textureFormat: -1
    textureCompression: 1
    compressionQuality: 50
    crunchedCompression: 0
    allowsAlphaSplitting: 0
    overridden: 0
    ignorePlatformSupport: 0
    androidETC2FallbackOverride: 0
    forceMaximumCompressionQuality_BC6H_BC7: 0
  - serializedVersion: 3
    buildTarget: Standalone
    maxTextureSize: {max_size}
    resizeAlgorithm: 0
    textureFormat: -1
    textureCompression: 1
    compressionQuality: 50
    crunchedCompression: 0
    allowsAlphaSplitting: 0
    overridden: 0
    ignorePlatformSupport: 0
    androidETC2FallbackOverride: 0
    forceMaximumCompressionQuality_BC6H_BC7: 0
  spriteSheet:
    serializedVersion: 2
    sprites: []
    outline: []
    physicsShape: []
    bones: []
    spriteID: 
    internalID: 0
    vertices: []
    indices: 
    edges: []
    weights: []
    secondaryTextures: []
    nameFileIdTable: {{}}
  mipmapLimitGroupName: 
  pSDRemoveMatte: 0
  userData: 
  assetBundleName: 
  assetBundleVariant: 
"""


def write_meta(rel, kind, max_size, has_alpha=False):
    path = os.path.join(ROOT, rel) + ".meta"
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(texture_meta(guid_for(rel), kind, max_size, has_alpha))


def folder_meta(rel):
    path = os.path.join(ROOT, rel) + ".meta"
    if os.path.exists(path):
        return
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(
            "fileFormatVersion: 2\n"
            f"guid: {guid_for(rel)}\n"
            "folderAsset: yes\n"
            "DefaultImporter:\n"
            "  externalObjects: {}\n"
            "  userData: \n"
            "  assetBundleName: \n"
            "  assetBundleVariant: \n"
        )


def ensure_folders(rel_dir):
    parts = rel_dir.split("/")
    for i in range(2, len(parts) + 1):
        sub = "/".join(parts[:i])
        os.makedirs(os.path.join(ROOT, sub), exist_ok=True)
        folder_meta(sub)


# ---------------------------------------------------------------------------

def build_set(name):
    recipe, kwargs, max_size = SETS[name]
    print(f"[{name}] generating ...", flush=True)
    maps = recipe(**kwargs)
    rel_dir = f"{OUT_REL}/{name}"
    ensure_folders(rel_dir)
    for kind in ("base", "normal", "roughness", "metallic", "ao", "emission"):
        if kind not in maps:
            continue
        rel = f"{rel_dir}/T_{name}_{MAP_SUFFIX[kind]}.png"
        alpha = maps.get("base_alpha") if kind == "base" else None
        write_map(rel, kind, maps[kind], alpha)
        write_meta(rel, kind, max_size, has_alpha=alpha is not None)
        print(f"   wrote {rel}")


def build_extras():
    shared = f"{OUT_REL}/Shared"
    ensure_folders(shared)
    rel = f"{shared}/T_Arena_MacroVariation.png"
    write_map(rel, "macro", sets.macro_variation(256))
    write_meta(rel, "macro", 256)
    print(f"   wrote {rel}")

    ritual = f"{OUT_REL}/Ritual"
    ensure_folders(ritual)
    rel = f"{ritual}/T_Ritual_Sigil_Emission.png"
    write_map(rel, "emission", sets.ritual_sigil(1024))
    write_meta(rel, "emission", 1024)
    print(f"   wrote {rel}")
    rel = f"{ritual}/T_Ritual_GlyphStrip_Emission.png"
    write_map(rel, "emission", sets.ritual_glyph_strip(1024, 256))
    write_meta(rel, "emission", 1024)
    print(f"   wrote {rel}")


def main(argv):
    names = argv[1:] or list(SETS)
    for n in names:
        if n == "extras":
            continue
        build_set(n)
    if len(argv) == 1 or "extras" in argv:
        build_extras()
    print("done")


if __name__ == "__main__":
    main(sys.argv)
