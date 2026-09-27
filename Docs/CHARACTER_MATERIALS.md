# Veilbound Wayfarer - PBR Material Pass

This pass upgrades the protagonist from flat Standard materials to 8 distinct procedural PBR materials without changing geometry. All variation is generated in-shader from worldPos noise, so no textures are required and the existing OBJ (42k tris, 9 submeshes, no UVs) stays untouched.

## Shader Inventory (Assets/Art/Shaders/)

| Shader | Category | Key PBR Response |
|---|---|---|
| `CharacterCloth.shader` | Coat, lapels, waistcoat, trousers | Fabric sheen via `LightingStandardFabric` (grazing retroreflection tinted by _SheenColor), weave normal from sin/cos + ValueNoise, albedo variation via FBM, smoothness 0.22-0.28 with 0.14-0.18 variation |
| `CharacterShirt.shader` | Shirt / cravat (BoneThread) | Lighter weave, thread tint in crevices, lower sheen, same cloth family but distinct color/roughness |
| `CharacterLeather.shader` | Belt, baldric, pouch, gloves base | Leather grain: cellular FBM + pore noise, stretched scratch noise, smoothness 0.48 base (polished vs cloth 0.26), wear adds polish in scratches, crevice darkening |
| `CharacterGlove.shader` | Gauntlet gloves (new M_Char_Gloves) | Softer leather, suede fuzz via rim lighting (`pow(1-NdotV,2.8)`), grain scale 58 vs belt 42, gloss 0.34 distinct from both cloth and boot |
| `CharacterBoot.shader` | Boots (Leather + BootSole) | Multi-zone: upper leather vs sole (isSole mask by worldPos.y), scuff highlights at toe/heel, grain 32, gloss 0.22 rougher than gloves, sole even rougher |
| `CharacterMetal.shader` | AgedBrass fasteners | Metallic 0.78, patina in recesses (reduces metallic locally), micro-scratch anisotropic noise, smoothness 0.62 varied ±0.16, polished wear on exposed edges |
| `CharacterSkin.shader` | Skin | SSS wrap lighting (`_SSSColor` added with pow(wrap,2.2)), low gloss 0.33 to avoid plastic, pore normal 0.18, redness mask for cheeks/nose, varied roughness via pore + FBM |
| `CharacterHair.shader` | Hair | Anisotropic secondary highlight via `LightingStandardHair` (Kajiya-Kay-ish), strand sin pattern, gloss 0.34 with 0.22 var, highlight tint |
| `CharacterEye.shader` | Eyes (new M_Char_Eyes) | Iris procedural: polar angle + radial fibers, pupil/iris/sclera masks, cornea high gloss 0.92 but sclera 0.35, iris concave normal, ValueNoise avoids uniform roughness |

## Material Assets (Assets/Materials/Character/)

Existing 9 preserved GUIDs (prefab wiring intact):
- `M_Char_Cloth` (998ffde9...) -> CharacterCloth, dark desaturated blue-grey (0.11,0.135,0.175)
- `M_Char_ClothAccent` (98de5209...) -> CharacterCloth, wine (0.235,0.075,0.11) with wine sheen tint
- `M_Char_Trouser` (de06ec70...) -> CharacterCloth, charcoal (0.125,0.14,0.165) lower sheen 0.18
- `M_Char_Leather` (dee34953...) -> CharacterLeather, belt brown (0.165,0.105,0.072) gloss 0.48
- `M_Char_Skin` (c875113b...) -> CharacterSkin
- `M_Char_Hair` (c17c22c2...) -> CharacterHair
- `M_Char_AgedBrass` (cabaea5e...) -> CharacterMetal
- `M_Char_BoneThread` (040edb54...) -> CharacterShirt, bone (0.60,0.52,0.39)
- `M_Char_BootSole` (0050f5e9...) -> CharacterBoot

New distinct categories to satisfy 8-material requirement:
- `M_Char_Gloves` (9433dd40...) -> CharacterGlove, glove brown (0.145,0.095,0.065) gloss 0.34
- `M_Char_Eyes` (da9ac30c...) -> CharacterEye, iris blue-grey

## PBR Compliance Checklist

- **No flat solid colors**: every shader uses FBM/ValueNoise/Hash for albedo, normal, smoothness variation
- **Albedo, roughness, metallic, normal**: all shaders set o.Albedo, o.Metallic, o.Smoothness, o.Normal, o.Occlusion
- **Coat fabric response**: custom `LightingStandardFabric` adds grazing sheen, visible under arena moon key + subject fill
- **Leather vs cloth roughness**: cloth gloss 0.22-0.28, leather belt 0.48, gloves 0.34, boots 0.22 - all distinct
- **Metal fasteners**: metallic 0.78, smoothness varied, patina reduces metallic in recesses, reacts correctly to directional moon key
- **Skin not plastic**: gloss 0.33, SSS wrap, pore normal, redness - avoids plastic specular
- **No excessive metallic**: non-metals ≤0.03, metal 0.78 only
- **No uniform roughness**: GlossVar 0.14-0.24 + procedural roughVar, eye uses mask lerp + noise
- **Subtle wear**: _WearAmount 0.12-0.26, _ScuffAmount 0.26, _PatinaAmount 0.22 - wear lightens/highlights but not dirty/damaged
- **Arena lighting**: validated via `verify_arena_lighting.py` (29 MeshKit lights, 5 zones, 1 shadow key, mist/motes) - no lighting changes

## Testing

- `Tools/validate_unity_project.py` passes (341 assets, unique GUIDs, YAML check)
- `Tools/verify_arena_lighting.py` passes (light budget ≤30)
- `Tools/verify_character_materials.py` passes (8 categories, distinct gloss, metallic, SSS, sheen)
- `Tools/render_character_previews.py` still renders OBJ (12 angles) - geometry unchanged

## Future Work (not in this pass)

- Assign M_Char_Gloves to a split glove submesh if geometry is ever re-exported with 11 groups
- Assign M_Char_Eyes to separate eye spheres for proper cornea refraction
- Texture-based detail (currently procedural only to avoid texture budget)
