# Veilbound Wayfarer — Material Polish Pass

A response-focused pass on the existing protagonist. **No silhouette, proportions,
pose, or vertex positions changed.** The original nine material slots remain in
place; the existing fitted glove and inset eyeball geometry now use two appended
material slots so their already-authored surfaces can receive the intended
leather and eye shaders. All 11 regions are present on the base mesh and both LODs.

## Surface response

All procedural patterns use character/object-space coordinates, so grain and
weave stay attached while the player moves. The imported OBJ has no UVs or
usable tangents; each shader builds a stable local tangent frame for its subtle
procedural normal detail. Ambient occlusion is applied once through the PBR
occlusion channel instead of also being multiplied into albedo.

| Shader | Assigned surface | Response |
| --- | --- | --- |
| `CharacterCloth.shader` | Greatcoat, mantle, lapels | Matte wool with restrained weave/fiber normals, low-contrast tone variation, roughness breakup, and a grazing sheen that is tinted by the actual scene light. |
| `CharacterShirt.shader` | Shirt, cravat and bone-thread details | Drier, slightly lighter woven fabric with softer thread-scale detail and lower sheen. |
| `CharacterLeather.shader` | Belt, baldric, straps, pouch and leather panels | Warm leather grain, fine stretched scuffs, varied roughness, and mild polish only on wear. |
| `CharacterGlove.shader` | Fitted gauntlet glove shells | Softer, more matte leather with a very restrained light-dependent suede edge response. |
| `CharacterBoot.shader` | Boot uppers and soles | Rough leather grain and low-key toe scuffs; the sole zone is measured in object space so it remains correct when the player jumps. |
| `CharacterMetal.shader` | Aged-brass hardware | The only strongly metallic character region. Lowered polish, subtle patina and scratches; hardware remains brass rather than mirror chrome. |
| `CharacterSkin.shader` | Face, ears, neck, forearms and hand skin | Low smoothness, restrained pore detail and a small light-coloured back-scatter term that follows direct-light colour/intensity. No broad plastic highlight or unlit glow. |
| `CharacterHair.shader` | "Vigil Sweep" hair | Object-locked strand flow and two subdued Kajiya–Kay lobes over diffuse shading; highlights inherit the key-light colour and the strands remain dark blue-black rather than flat black. |
| `CharacterEye.shader` | Existing inset eyeball spheres | Subdued blue-grey iris with radial fibers, dark limbal ring and pupil, warm off-white sclera, and controlled moisture response. No emission or pure-white surface. |

## Material assets

The original material GUIDs are preserved. The pre-existing dedicated materials
are now actually wired to their matching geometry:

- Existing slots 0–8: `M_Char_Cloth`, `M_Char_ClothAccent`,
  `M_Char_Trouser`, `M_Char_Leather`, `M_Char_Skin`, `M_Char_Hair`,
  `M_Char_AgedBrass`, `M_Char_BoneThread`, and `M_Char_BootSole`.
- Appended slot 9: `M_Char_Gloves` (`9433dd40…`) for the existing glove shells.
- Appended slot 10: `M_Char_Eyes` (`da9ac30c…`) for the existing inset eye spheres.

The metal stays local to brass hardware (metallic 0.72); cloth, leather, skin,
hair and eyes remain non-metallic. The cloth and hair colors are lifted only a
little from their previous blue-black/charcoal values so folds and edges retain
separation in the dark chamber. The bone-thread and eye sclera remain warm and
subdued, not white.

## Lighting and scope

The existing arena key, subject fill, ambient colour, post grade, and all scene
lighting assets are untouched. Material highlights are bounded by the actual
light colour and attenuation; there is no new emissive material. The existing
lighting budget and masks remain in force.

## Verification

- `Tools/verify_character_materials.py` checks PBR channels, material value
  bounds, the 11 OBJ material regions, and every base/LOD prefab material slot.
- `Tools/verify_hair.py`, `Tools/verify_hands.py`, and `Tools/verify_boots.py`
  check that the appended material regions did not disturb geometry ranges,
  shape, or rig sidecars.
- `Tools/render_character_previews.py` includes an eye-shader approximation
  for close-range readability. It is an offline palette renderer, not a Unity
  shader compile; Unity Play Mode remains the final visual check.
- `Tools/verify_arena_lighting.py` verifies the existing lighting configuration
  without editing it.
