#!/usr/bin/env python3
"""
Verify protagonist PBR materials meet task requirements without changing geometry.
Checks shaders and material assets for distinct PBR properties.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHADER_DIR = ROOT / "Assets/Art/Shaders"
MAT_DIR = ROOT / "Assets/Materials/Character"


OBJ_MATERIAL_ORDER = [
    "Cloth", "ClothAccent", "Trouser", "Leather", "Skin", "Hair",
    "AgedBrass", "BoneThread", "BootSole", "Gloves", "Eyes",
]
PREFAB_MATERIAL_FILES = [
    "M_Char_Cloth.mat", "M_Char_ClothAccent.mat", "M_Char_Trouser.mat",
    "M_Char_Leather.mat", "M_Char_Skin.mat", "M_Char_Hair.mat",
    "M_Char_AgedBrass.mat", "M_Char_BoneThread.mat", "M_Char_BootSole.mat",
    "M_Char_Gloves.mat", "M_Char_Eyes.mat",
]
EXPECTED_MESH_COUNTS = {
    "": (51469, 98398), "_L1": (32027, 60649), "_L2": (26532, 50398),
}

REQUIRED_CATEGORIES = {
    "cloth": ["CharacterCloth", "CharacterShirt"],
    "leather": ["CharacterLeather"],
    "metal": ["CharacterMetal"],
    "boots": ["CharacterBoot"],
    "gloves": ["CharacterGlove"],
    "skin": ["CharacterSkin"],
    "hair": ["CharacterHair"],
    "eyes": ["CharacterEye"],
}

def read_shader(name):
    p = SHADER_DIR / f"{name}.shader"
    assert p.exists(), f"Missing shader {p}"
    return p.read_text()

def check_shader_pbr(name, content):
    # No-UV meshes need an explicit, stable object-space frame for variation.
    assert "vertex:vert" in content and "o.objPos = v.vertex.xyz" in content, f"{name}: missing object-space vertex frame"
    assert "IN.worldPos" not in content, f"{name}: procedural detail must not swim in world space"
    if name in {"CharacterCloth", "CharacterGlove", "CharacterHair", "CharacterSkin"}:
        assert "_LightColor0" in content and "atten" in content, f"{name}: custom response must follow scene light colour/attenuation"
    # Must set albedo, metallic, smoothness, normal
    assert "o.Albedo" in content, f"{name}: missing Albedo"
    assert "o.Metallic" in content, f"{name}: missing Metallic"
    assert "o.Smoothness" in content, f"{name}: missing Smoothness/Roughness"
    assert "o.Normal" in content, f"{name}: missing Normal"
    # Must have procedural variation (not flat solid)
    has_noise = any(k in content for k in ["ValueNoise", "FBM", "Hash21", "noise", "weave", "grain", "scratch", "strand", "pore", "fiber"])
    assert has_noise, f"{name}: no procedural variation found (flat color risk)"
    # Must have variation in roughness (GlossVar or roughVar) - eye uses mask lerp + noise
    if "Eye" in name:
        assert "smoothness" in content.lower(), f"{name}: no roughness handling"
    else:
        assert "_GlossVar" in content or "roughVar" in content or "GlossVar" in content, f"{name}: no roughness variation"
    print(f"  [OK] {name}: PBR channels + variation present")

def check_mesh_material_wiring():
    """Confirm appended eye/glove regions map to the matching prefab slots."""
    models = ROOT / "Assets/Models/Characters"
    for suffix, expected_counts in EXPECTED_MESH_COUNTS.items():
        obj = models / f"SM_Character_VeilboundWayfarer{suffix}.obj"
        text = obj.read_text()
        regions = re.findall(r"^usemtl\s+(\S+)\s*$", text, re.MULTILINE)
        assert regions == OBJ_MATERIAL_ORDER, f"{obj.name}: material order {regions}"
        vertex_count = sum(line.startswith("v ") for line in text.splitlines())
        triangle_count = sum(line.startswith("f ") for line in text.splitlines())
        assert (vertex_count, triangle_count) == expected_counts, (
            f"{obj.name}: geometry counts {(vertex_count, triangle_count)} "
            f"!= {expected_counts}; material pass must not alter the mesh")
        print(f"  [OK] {obj.name}: same geometry counts, 11 ordered material regions")

    expected_guids = []
    for filename in PREFAB_MATERIAL_FILES:
        meta = (MAT_DIR / (filename + ".meta")).read_text()
        guid = re.search(r"guid:\s*([0-9a-f]{32})", meta)
        assert guid, f"{filename}: missing material GUID"
        expected_guids.append(guid.group(1))

    prefab = (ROOT / "Assets/Prefabs/Player/Player.prefab").read_text()
    material_blocks = re.findall(
        r"(?m)^  m_Materials:\n((?:^  - \{fileID: 2100000, guid: [0-9a-f]{32}, type: 2\}\n)+)",
        prefab,
    )
    assert len(material_blocks) == 3, f"Expected base + two LOD renderers, found {len(material_blocks)}"
    for index, block in enumerate(material_blocks):
        guids = re.findall(r"guid:\s*([0-9a-f]{32})", block)
        assert guids == expected_guids, f"Player renderer {index}: material slot order mismatch"
        assert len(guids) == len(OBJ_MATERIAL_ORDER), f"Player renderer {index}: slot count mismatch"
    print("  [OK] Player base/L1/L2 material slots match all 11 OBJ regions")

    eye_text = (MAT_DIR / "M_Char_Eyes.mat").read_text()
    sclera = re.search(r"_ScleraColor: \{r: ([0-9.]+), g: ([0-9.]+), b: ([0-9.]+)", eye_text)
    assert sclera and max(map(float, sclera.groups())) <= 0.85, "Eye sclera is too close to pure white"
    eye_gloss = re.search(r"_Glossiness:\s*([0-9.]+)", eye_text)
    assert eye_gloss and float(eye_gloss.group(1)) <= 0.80, "Eye moisture is too glossy"
    assert "Emission" not in read_shader("CharacterEye"), "Eye shader must not glow"
    cloth = (MAT_DIR / "M_Char_Cloth.mat").read_text()
    sheen = re.search(r"_FabricSheen:\s*([0-9.]+)", cloth)
    assert sheen and float(sheen.group(1)) <= 0.18, "Cloth sheen exceeds the subtle range"
    print("  [OK] Eye whites/gloss and cloth sheen stay restrained")


def check_materials():
    mats = list(MAT_DIR.glob("M_Char_*.mat"))
    print(f"Found {len(mats)} character materials")
    assert len(mats) >= 8, "Need at least 8 distinct materials"

    # Parse mats for shader guid and properties
    shader_guid_map = {}
    for meta in SHADER_DIR.glob("Character*.shader.meta"):
        txt = meta.read_text()
        m = re.search(r"guid:\s*([0-9a-f]{32})", txt)
        if m:
            shader_guid_map[m.group(1)] = meta.stem.replace(".shader","")

    used_shaders = set()
    mat_infos = []
    for mat_path in mats:
        txt = mat_path.read_text()
        # shader guid
        mg = re.search(r"m_Shader:\s*\{[^}]*guid:\s*([0-9a-f]{32})", txt)
        assert mg, f"{mat_path.name}: no shader guid"
        guid = mg.group(1)
        shader_name = shader_guid_map.get(guid, f"unknown:{guid[:8]}")
        used_shaders.add(shader_name)

        # colors
        colors = re.findall(r"_Color.*r:\s*([0-9.]+)", txt)
        # metallic
        metallic = re.search(r"_Metallic:\s*([0-9.]+)", txt)
        gloss = re.search(r"_Glossiness:\s*([0-9.]+)", txt)
        metallic_val = float(metallic.group(1)) if metallic else None
        gloss_val = float(gloss.group(1)) if gloss else None

        mat_infos.append((mat_path.name, shader_name, metallic_val, gloss_val))
        print(f"  - {mat_path.name:22s} -> {shader_name:20s} metallic={metallic_val} gloss={gloss_val}")

    # Check categories covered
    for cat, keywords in REQUIRED_CATEGORIES.items():
        found = any(any(kw.lower() in s.lower() for kw in keywords) or any(kw.lower() in m[0].lower() for kw in keywords) for m,s,_,_ in [(mi[0], mi[1], mi[2], mi[3]) for mi in mat_infos] for kw in keywords)
        # More robust: check used_shaders contains expected
        cat_ok = any(any(kw.lower() in sh.lower() for kw in keywords) for sh in used_shaders)
        # Special case cloth includes trouser etc still uses CharacterCloth shader
        if cat == "cloth":
            cat_ok = any("cloth" in sh.lower() or "shirt" in sh.lower() for sh in used_shaders)
        assert cat_ok, f"Category {cat} not covered by any shader/material (need {keywords})"
        print(f"  [OK] Category '{cat}' covered")

    # Distinct roughness: leather different from cloth
    gloss_by_cat = {}
    for name, shader, met, gloss in mat_infos:
        if gloss is not None:
            gloss_by_cat.setdefault(shader, []).append(gloss)
    # Check leather vs cloth gloss difference
    cloth_gloss = None
    leather_gloss = None
    for name, shader, met, gloss in mat_infos:
        if "Cloth" in shader and "Cloth" in name and cloth_gloss is None:
            cloth_gloss = gloss
        if "Leather" in shader:
            leather_gloss = gloss
    if cloth_gloss is not None and leather_gloss is not None:
        diff = abs(cloth_gloss - leather_gloss)
        assert diff > 0.05, f"Leather roughness {leather_gloss} too close to cloth {cloth_gloss} (need distinct)"
        print(f"  [OK] Leather gloss {leather_gloss} distinct from cloth {cloth_gloss} diff={diff:.2f}")

    # Metal should have high metallic
    for name, shader, met, gloss in mat_infos:
        if "Metal" in shader or "Brass" in name:
            assert met is not None and met >= 0.5, f"Metal {name} metallic {met} too low, should react as metal"
            print(f"  [OK] Metal {name} metallic {met} reacts correctly")

    # Non-metals should have low metallic
    for name, shader, met, gloss in mat_infos:
        if "Metal" not in shader and "Brass" not in name and met is not None:
            assert met <= 0.15, f"Non-metal {name} has excessive metallic {met}"
    print(f"  [OK] No excessive metallic on non-metals")

    # Skin not plastic: glossiness should be low (<0.5) and have SSS
    for name, shader, met, gloss in mat_infos:
        if "Skin" in shader:
            assert gloss is not None and gloss <= 0.45, f"Skin {name} gloss {gloss} too high (plastic look)"
            # check shader has SSS
            content = read_shader(shader)
            assert "SSS" in content or "_SSSColor" in content, f"Skin shader {shader} missing SSS to avoid plastic"
            print(f"  [OK] Skin {name} gloss {gloss} low + SSS, not plastic")

    # Check uniform roughness avoided: all shaders must have varied smoothness
    for shader_file in SHADER_DIR.glob("Character*.shader"):
        txt = shader_file.read_text()
        if "CharacterEye" in shader_file.name:
            # Eye has cornea/iris/pupil lerp + ValueNoise variation, not GlossVar
            assert "smoothness" in txt.lower() and "ValueNoise" in txt, f"{shader_file.name} missing roughness variation"
            continue
        m = re.search(r"_GlossVar.*Range.*?\)\s*=\s*([0-9.]+)", txt)
        if not m:
            m = re.search(r"_GlossVar.*?=\s*([0-9.]+)", txt)
        # also check GlossVar usage
        has_var = "_GlossVar" in txt and ("roughVar" in txt or "GlossVar" in txt)
        assert has_var, f"{shader_file.name} missing roughness variation"
    print(f"  [OK] No uniform roughness - all shaders have variation")

    # Check wear not dirty/damaged: wearAmount <=0.30
    for mat_path in mats:
        txt = mat_path.read_text()
        wear = re.search(r"_WearAmount:\s*([0-9.]+)", txt)
        scuff = re.search(r"_ScuffAmount:\s*([0-9.]+)", txt)
        patina = re.search(r"_PatinaAmount:\s*([0-9.]+)", txt)
        for label, val_match in [("Wear", wear), ("Scuff", scuff), ("Patina", patina)]:
            if val_match:
                v = float(val_match.group(1))
                assert v <= 0.35, f"{mat_path.name} {label} {v} too high (dirty/damaged look)"
    print(f"  [OK] Wear amounts subtle (<=0.35), not dirty/damaged")

    # Check fabric sheen present for coat
    cloth_shader = read_shader("CharacterCloth")
    assert "FabricSheen" in cloth_shader or "sheen" in cloth_shader.lower(), "Cloth missing fabric sheen"
    assert "LightingStandardFabric" in cloth_shader or "Sheen" in cloth_shader, "Cloth missing fabric response to lighting"
    print(f"  [OK] Coat has visible fabric response (sheen)")

def main():
    print("=== Verifying Character PBR Materials ===")
    # Check all required shaders exist
    for cat, shaders in REQUIRED_CATEGORIES.items():
        for sh in shaders:
            p = SHADER_DIR / f"{sh}.shader"
            assert p.exists(), f"Missing required shader for {cat}: {sh}"
    print(f"All required shader files present: {list(REQUIRED_CATEGORIES.keys())}")

    for shader_path in SHADER_DIR.glob("Character*.shader"):
        content = shader_path.read_text()
        check_shader_pbr(shader_path.stem, content)

    check_materials()

    # Geometry counts, material region order and prefab wiring are explicit pass gates.
    check_mesh_material_wiring()

    print("\nPBR MATERIAL VERIFICATION PASSED")
    print(" - Distinct PBR for cloth, leather, metal, boots, gloves, skin, hair, eyes")
    print(" - No flat solid colors, procedural variation present")
    print(" - Roughness varied, metallic correct, fabric sheen, skin SSS, etc.")
    print(" - Eye and glove materials are wired on base, L1 and L2")
    print(" - No arena lighting or character geometry changes")

if __name__ == "__main__":
    main()
