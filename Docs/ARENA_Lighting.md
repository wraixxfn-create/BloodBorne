# Ritual Chamber — final lighting foundation

**Open:** `Assets/Scenes/Arena/Arena_RitualChamber_MeshKit.unity` in Unity 2022.3 (Built-in / Linear), then press Play. It is also build scene **0**. `Arena_RitualChamber.unity` is the earlier primitive version and shares the same lighting rig. `Main.unity` remains an unlit-environment movement sandbox. **No boss or combat implementation is included.**

## Art direction and visual hierarchy

The room is charcoal stone in cool exterior moonlight: dark boundaries and vaulted recesses, a readable floor and dais, small warm firelight landmarks, broken-glass colors confined to the walls, and low cyan ritual accents. Black is **not** the design target. The player must read against the floor at the entrance, dais and corners; a future boss can be lit without changing the room's exposure.

The scene instantiates `Assets/Prefabs/Arena/Arena_LightingRig.prefab` in addition to its environment prefab. The environment owns candles, window spots, mist meshes and ritual materials; the rig owns the one moon key, stable fills, stained-glass accents, volumetric *impostors* and particle anchors. Both arena scenes remove their old 1.35-intensity scene directional light; **do not add another directional key**. The original primitive scene lowers the rig by 0.5 m to match its floor at y=0; the MeshKit floor top is y=0.5.

| Authored zone / rig children | Place / role | Default treatment |
| --- | --- | --- |
| `01_Entrance` | South doorway (z=-15 to -19) | Two warm point sconces (0.56, 6.3 m), a navigation landmark rather than a wash across the fight. |
| `02_CentralArena` | Clear combat disc r≤12 m | Cold moon key (0.86, soft shadow strength 0.68), broad overhead spot (0.31), neutral subjects-only directional fill (0.34). The floor and moving figures do **not** depend on flickering candles. |
| `03_Corners_and_Glass` | Four r≈17 m alcoves; north/west windows | Four 0.28 spot fills stop corners going blind. Three low-intensity colored glass spots graze the wall and floor. Each has a feathered translucent veil and a non-colliding 5 m procedural glass pool at r≈14. Two window anchors release sparse dust in Play. |
| `04_ElevatedPlatform` | Raised central dais | One steady cool-neutral 0.38 overhead spot outlines a future subject at the centre without spotlighting the whole room. |
| `05_RitualArea` | Centre ring and north altar | Two faint cyan point accents (0.23/0.25) on **stone only** and a small ash emitter by the altar; emission on ring/runes pulses by ±14% at a slow rate. Not a telegraph or gameplay volume. |

The moon key is the **only realtime shadow caster** in either arena. Its light uses soft shadows with reduced strength, moderate bias and a cool color; every candle, window, corner, colored and ritual light has shadows **off**. The key, central floor, dais and character fill are Important lights; low-priority local lights may fall back to vertex lighting on low quality settings. Half the candle clusters remain visibly emissive without their own point light: 10/20 practicals in MeshKit, 8/16 in the primitive version. Only 4/8 cold window spots run in each room. Total active Unity Lights: **29** in MeshKit, **27** in the primitive scene, of which **one** has shadows. Colored glass and ritual spots exclude Player and Enemy to avoid muddying their material silhouettes.

### Character separation, without adding a boss

The neutral `Subjects_only_Player_Enemy` fill has culling mask **768** (Player layer 8 + reserved Enemy layer 9), soft **no shadows**, and remains steady even in the darkest corner. It does not brighten the stone. The existing player placeholder's surface has been lifted to a cooler mid-tone with a tiny warm-facing marker, distinct from the teal ritual floor and the grey stone. When adding a boss **later**, put its renderers on Enemy (9) and choose a value/hue distinct from the player: this rig will light it automatically. There is deliberately no boss GameObject, collider, AI, attack, encounter transition, hazard or telegraph in this pass.

The `MainCameraRig` prefab is not globally regraded. **Only the two arena scene instances** soften its vignette to 0.30, radius 0.62, contrast 1.02, and grain 0.025. Thus dark corners do not become crushed screen corners, and the Main sandbox retains its original settings. The scene uses flat cold ambient (`0.10, 0.112, 0.15`), no skybox, and restrained reflection intensity (0.35). Fog is exponential at 0.01 with at most ±0.00075 of slow breathing, not a thick foreground wall.

## Atmospheric implementation (Built-in, no packages)

- **Ground mist:** Four mesh volumes in MeshKit now sit *above* its 0.5 m floor, at r=15, scaled to 6.5 m. `M_Arena_GroundMist` (alpha 0.07) / `ArenaGroundMist.shader` feather the edges, fade near the camera, and never write depth or cast shadows. `ArenaFogController` drifts them at most 0.25 m and gently **reduces** their authored alpha; it never boosts haze over the fight. The older primitive scene retains its dim Standard fog material.
- **Window shafts:** `ArenaLightVeil.shader` on two crossed, tapered sheets per window is a cheap visual suggestion of light scattering, not physically correct volumetric lighting. Alpha stays under 0.055, the edges and ends fade, and nearby camera views fade the sheets out. Their colored spots are real lights; the veils themselves are not.
- **Glass influence:** `ArenaStainedLight.shader` creates small additive feathered pools with two broken lead lines. These are deliberately placed outside r=12 at y=0.535 above the MeshKit floor, y=0.035 in the primitive scene. Three corresponding shadowless spots provide actual colored spill to the environment. Neither pools nor shafts have colliders, shadows, lightmapping or dynamics.
- **Dust and ash:** `ArenaAtmosphereParticles` creates two bounded dust systems beside the lit north windows (≤24 billboards each) and one ash system by the altar (≤16). Emission is ~1.15/s and 0.55/s respectively. `ArenaMote.shader` draws feathered, short-lived particles with no texture, collision, lights or shadows. Systems are constructed only in Play mode and destroyed on unload; there are no full-arena particles, no simulated smoke occluding a figure.

### Practical setup and controls

1. Expand **Arena_LightingRig** in the Hierarchy, select a zone, then adjust child `Light` intensities/ranges/colors. The `ArenaLightingZones` component draws zone discs when selected; they are **visual guides**, not trigger volumes. Leave the subjects-only mask (768) and its neutral color in place.
2. Select the environment prefab instance's `ArenaLightingController` for candle flicker and ritual emission breathing. Explicit light/renderer arrays are serialized; older versions can still discover components independently by name. The controller uses cached intensities and a reusable `MaterialPropertyBlock`, and restores them when disabled.
3. Select its `ArenaFogController` for distance-fog baseline and local mist drift/opacity. Reduce fog and vignette, **not the steady fills**, before evaluating combat visibility.
4. Play at the spawn and walk to the dais, north windows, all four corners and back: the floor edge, player body/facing marker, tier steps and ritual circle should remain readable at every position. The stained-glass pools should tint only stone; the two northern shafts should suggest depth without becoming opaque curtains. With no boss yet, check the empty upper dais for a distinguishable neutral-light staging area.
5. Test in the Game view at both medium and low quality, including looking into the entrance from the dais and orbiting near a wall. Turn off the rig temporarily to confirm it contributes, then restore it. Shadows, particle density and perceived brightness need final visual QA in Unity — this repository has no Unity editor executable in the authoring environment.

## Reproducibility / verification

Regenerate after editing the Python sources (the original primitive prefab is patched, not rebuilt):

```bash
python3 Tools/generate_arena_lighting.py
python3 Tools/generate_arena_master.py
python3 Tools/generate_arena_scene.py
python3 Tools/tune_legacy_arena_lighting.py
python3 Tools/generate_unity_guids.py
python3 Tools/validate_unity_project.py       # needs PyYAML
python3 Tools/csharp_smoke_check.py
python3 Tools/verify_arena_lighting.py        # needs PyYAML; asserts light budgets and zone wiring
```

All new asset GUIDs are deterministic. Validation checks YAML syntax and references, zone ownership, subject culling mask, the single shadow key, old window-spot direction, mist and ritual heights, camera overrides, both scene instances and the no-boss constraint. Structural checks cannot replace an actual Unity lighting pass; no HDRP/URP or third-party volumetrics are needed.
