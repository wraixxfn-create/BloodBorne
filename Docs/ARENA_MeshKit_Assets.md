# Hollow Sanctum — Modular Mesh Kit (original gothic arena)

> **Lighting update (2026-09-25):** The playable scene now instances a separate
> five-zone `Arena_LightingRig`. Light counts, fog heights and exposure below
> reflect the final pass; see [ARENA_Lighting.md](ARENA_Lighting.md) for tuning.
> No boss or combat has been added.

**Date:** 2026-09-25  
**Unity Version:** 2022.3 LTS Built-in  
**Root Folders:**
- Meshes: `Assets/Models/Arena/` (87 modular OBJs + 2 lighting VFX OBJs)
- Prefabs: `Assets/Prefabs/Arena/MeshKit/` (87 prefabs, 13 categories)
- Master Assembly: `Assets/Prefabs/Arena/Arena_RitualChamber_MeshKit.prefab` (321 children)
- Scene: `Assets/Scenes/Arena/Arena_RitualChamber_MeshKit.unity`
- Materials: `Assets/Materials/Arena/` (20 kit mats + 9 lighting VFX mats)

---

## 1. Design Goals

The kit builds a **recognizable 3D boss arena** that can be assembled directly in Unity without external DCC. It satisfies:

- Modular grid for easy modification
- Optimized for real-time Unity rendering
- Clean topology, appropriate polygon density, reusable meshes
- Sensible pivots (base center), correct scale (1 unit = 1 meter)
- Clean UVs (planar/box projected, 0-1 per face)
- Appropriate material slots (1-2 per mesh, 3 max for complex props)
- High-detail source only where necessary (statues, chains, candles)
- Lower-detail LODs for distant objects (pillars, walls, floor, statues)

All forms are **original** — no Bloodborne, Dark Souls, Elden Ring assets, names, or architecture are copied. The language is low broad arches, squat eroded pillars with slab capitals, two-tier dais, cold stone vs. warm candle.

---

## 2. Modular Grid

**Base Grid:** 4 meters (400 cm)

- All horizontal dimensions are multiples of 0.1 m, snapped to 4 m, 2 m, 1 m, 0.5 m where possible.
- Wall segments tile at 22.5° (16 segments = 360° exactly) for circular arena, but also work on straight 4 m grid.
- Pivot: **base center** (0,0,0) at bottom center of mesh. Rotating around Y places object on polar ring without height correction.
- Y up, 1 unit = 1 meter. Dais steps 0.30 m = `CharacterController.stepOffset` so player steps up without jump.
- Floor wedge: angle 22.5°, inner radius 15 m, outer 19 m, thickness 0.5 m, pivot at mid-radius center. 16 wedges form full outer ring ∅38 m.
- Wall: 4 m wide × 16 m tall × 1.1 m thick (full), also 4×4 and 4×8 variants for stacking.
- Pillar: 1.4 m footprint, 14 m tall (base 1 m + shaft 11 m + capital 0.9 m + tracery). Damaged variant splits shaft lower 7 m + upper 3.5 m with rubble.
- Arch: 4 m wide, rise 1.5 m, depth 1 m — broad low arch, not pointed fan vaulting. Ruined variant missing leg.
- Window: frame 5.2 m × 9.5 m for arena, plus modular 3 m × 4 m for corridors. Sill at 1.2 m above floor.
- Stairs: single step 2.2 m × 0.3 m × 1 m, straight 3-step, broad 4 m × 0.6 m × 2 m (south entry), curved tier wedge for platform (45°).
- Platform: cylinder 14 m dia × 0.3 m (Tier1) and 10 m dia × 0.3 m (Tier2). Rim 14 m dia × 0.15 m. Pivot base center.

**Assembly Rule:** Floor is sacred, vertical is flavor. Only floor, dais, walls, pillar shafts have BoxCollider on **Environment (10)** layer for camera collision. Statues, chains, candles, beams, glass, decals, fog are Default (0) visual-only to keep combat disc frictionless.

---

## 3. Asset List by Category

### Floor Sections (7)
- `SM_Arena_Floor_400x400x050` — 4×4 tile, 0.5 thick, 24 verts, 12 tris, StoneFloor
- `SM_Arena_Floor_200x200x050` — 2×2 tile
- `SM_Arena_Floor_100x100x050` — 1×1 tile
- `SM_Arena_Floor_Wedge_22_5_R15_19` — wedge 22.5°, r15-19, circular outer ring
- `SM_Arena_Floor_Edge_400x020x050` — edge trim 4×0.2×0.5, StonePillar
- `SM_Arena_Floor_Ritual_Plate_220x065` — decal mesh 2.2×0.65×0.02 + rune, RitualMarking
- `SM_Arena_Floor_Ritual_Center_320` — disc 3.2 m dia, 0.02 thick, 24 segments, RitualMarking

### Wall Sections (7)
- `SM_Arena_Wall_400x400x100` — 4×4×1, StoneWall, collider
- `SM_Arena_Wall_400x800x100` — 4×8×1
- `SM_Arena_Wall_400x1600x110` — 4×16×1.1 full height, collider
- `SM_Arena_Wall_400x400_Window_250x300` — with opening 2.5×3.0, sill 0.5
- `SM_Arena_Wall_600x1400_Window_520x950` — large arena window wall, opening 5.2×9.5 sill 1.2
- `SM_Arena_Wall_Buttress_100x400x060` — 1×4×0.6, StonePillar
- `SM_Arena_Wall_Base_400x050x110` / `Cornice_400x030x020` — base plinth and cornice trim

### Pillars (5 + LOD)
- `SM_Arena_Pillar_Base_180x100x180` — base 1.8×1×1.8
- `SM_Arena_Pillar_Shaft_140x400x140` — shaft segment 4 m
- `SM_Arena_Pillar_Capital_170x090x170` — capital 1.7×0.9×1.7
- `SM_Arena_Pillar_Full_140x1400` — full assembly 14 m, 96 verts, 48 tris, 1 mat, collider
- `SM_Arena_Pillar_Damaged_140x1400` — damaged with rubble, 168 verts, 84 tris
- `SM_Arena_Pillar_Full_140x1400_LOD1` — LOD1 single box 1.6×14×1.6, 24 verts

### Arches (3)
- `SM_Arena_Arch_400x150x100` — low broad arch 4 m wide, rise 1.5 m, 192 verts, 6 segments approximated, StoneWall
- `SM_Arena_Arch_300x400x100` — tall arch 3×4×1, 72 verts
- `SM_Arena_Arch_Ruined_400x150x100` — broken, missing leg, rubble

### Windows (6)
- `SM_Arena_Window_Frame_300x400x020` — modular 3×4×0.2, StoneWall
- `SM_Arena_Window_Frame_520x950x020` — large 5.2×9.5, 168 verts
- `SM_Arena_Window_Tracery_Circle_100` — circular tracery 0.5 radius, 12 segments
- `SM_Arena_Window_Mullion_020x400x005` — mullion bar
- `SM_Arena_Window_Glass_Pane_280x380` — single pane 2.8×3.8×0.02, Glass_Blue
- `SM_Arena_Window_Glass_Shards_Cluster` — 5 shards 0.9-1.5 m, 3 mats (Blue/Red/Amber) for broken look

### Stairs (5)
- `SM_Arena_Stairs_Step_220x030x100` — single step 2.2×0.3×1
- `SM_Arena_Stairs_Straight_220x090x300` — 3 steps, 72 verts
- `SM_Arena_Stairs_Broad_400x060x200` — broad south entry 4×0.6×2, 2 steps
- `SM_Arena_Stairs_Curved_Tier_1400` — curved wedge 45°, r5-7, 2 steps, ritual floor mat
- `SM_Arena_Stairs_Plate_400x030x400` — landing plate

### Central Platform (5)
- `SM_Arena_Platform_Slab_400x400x030` — slab 4×4×0.3, ritual mat
- `SM_Arena_Platform_Cylinder_1000x030` — cylinder 10 m dia, 32 segments, 320 verts
- `SM_Arena_Platform_Cylinder_1400x030` — cylinder 14 m dia, 32 segments
- `SM_Arena_Platform_Rim_1400x015` — rim ring 14 m dia, 0.15 thick, 32 boxes, StonePillar
- `SM_Arena_Platform_StepRing_1400` — full cylinder with step notches placeholder

### Statues (7 inc LOD)
- `SM_Arena_Statue_Pedestal_120x100x120` — pedestal 1.2×1×1.2
- `SM_Arena_Statue_Torso_Robed_070x160x060` — torso 0.7×1.2×0.6 + 0.25 rad cylinder
- `SM_Arena_Statue_Head_Hooded_030x030x030` — head 0.3³
- `SM_Arena_Statue_Complete_120x260x120` — full 1.2×2.6×1.2, 144 verts, pedestal+torso+head+arm stumps, Statue_Eroded
- `SM_Arena_Statue_Fallen_180x060x060` — fallen 1.8 long, pivot at one end, lying on side
- `SM_Arena_Statue_Ruined_Debris_080x040x080` — debris 0.8×0.4×0.8 + 0.4 chunk
- `SM_Arena_Statue_Complete_120x260x120_LOD1` — LOD1 single box 1.2×2.6×1.2

### Chains (5)
- `SM_Arena_Chain_Link_018x040` — single link 0.18×0.4, 4 boxes forming torus, 96 verts, Metal_Chain
- `SM_Arena_Chain_Segment_6Links_018x240` — 6 links vertical, alt yaw 0/90, 576 verts, 288 tris
- `SM_Arena_Chain_Swag_500x004x004` — swag 5 m, 10 segments catenary, 240 verts
- `SM_Arena_Chain_Anchor_018x018x018` — anchor cube 0.18³
- `SM_Arena_Chain_Hook_020x030x010` — hook 0.2×0.3

### Damaged Wood (5)
- `SM_Arena_Wood_Beam_320x028x028` — beam 3.2×0.28×0.28, 2 mats (Wood_Rotted + Metal_Chain nail plate)
- `SM_Arena_Wood_Brace_120x028x022` — brace 0.28×1.2×0.22
- `SM_Arena_Wood_Plank_200x030x005` — plank 2×0.05×0.3
- `SM_Arena_Wood_Scaffold_400x400x030` — scaffold frame 4×4, two posts + beam + plank
- `SM_Arena_Wood_Debris_100x020x050` — debris pile 1×0.2×0.5 + splinters

### Candles (5)
- `SM_Arena_Candle_Wax_009x018` — wax 0.09 dia ×0.18 tall, 12 segments, 120 verts, Candle_Wax
- `SM_Arena_Candle_Wax_010x025` — tall 0.10×0.25
- `SM_Arena_Candle_Holder_Brazier_045x006x045` — brazier 0.45 dia ×0.06 + rim, 320 verts, Brazier_Metal
- `SM_Arena_Candle_Cluster_3x_045` — 3 candles on brazier + flame boxes, 3 mats (Brazier, Wax, Flame), 592 verts
- `SM_Arena_Candle_Wall_Sconce_020x030x015` — sconce 0.2×0.3, 2 mats

### Ritual Props (6)
- `SM_Arena_Ritual_Brazier_Large_080x060x080` — large brazier 0.8 dia, 0.6 tall, 3 cylinders, 480 verts, Brazier_Metal
- `SM_Arena_Ritual_Circle_320x002x320` — center disc 3.2 m, 24 segments, 2 cylinders, RitualMarking
- `SM_Arena_Ritual_Rune_050x001x050` — rune 0.5×0.01×0.5, RitualMarking
- `SM_Arena_Ritual_Chalice_020x030x020` — chalice 0.2×0.3, 3 cylinders, Brazier_Metal
- `SM_Arena_Ritual_Incense_Burner_025x035x025` — burner 0.25×0.35
- `SM_Arena_Ritual_Altar_Slab_200x080x100` — altar 2×0.8×1, 2 mats (StonePillar + RitualMarking decal)

### Debris (6)
- `SM_Arena_Debris_Stone_Small_030x020x030` — 0.3×0.2×0.3, StonePillar
- `SM_Arena_Debris_Stone_Medium_080x040x080` — 0.8×0.4×0.8
- `SM_Arena_Debris_Stone_Large_120x060x120` — 1.2×0.6×1.2
- `SM_Arena_Debris_Glass_Shards_150x010x100` — 4 shards 0.3-0.6, 3 glass mats
- `SM_Arena_Debris_Rubble_Pile_150x040x150` — pile 1.5×0.4×1.5 + chunks, 2 mats
- `SM_Arena_Debris_Wood_Splinters_100x010x050` — splinters 0.6×0.05×0.1 etc, Wood_Rotted

### Doors (4)
- `SM_Arena_Door_Frame_400x400x020` — frame 4×4×0.2, StoneWall, collider
- `SM_Arena_Door_Wood_Heavy_380x380x010` — heavy door 3.8×3.8×0.1, 2 mats (Wood + Chain)
- `SM_Arena_Door_Gate_Iron_380x380x005` — iron gate 5 vertical bars + 3 horizontal, 192 verts, Metal_Chain
- `SM_Arena_Door_Sealed_Stone_400x400x100` — sealed stone 4×4×1, 2 mats, collider

### Environmental Decorations (7)
- `SM_Arena_Deco_Gargoyle_060x080x040` — gargoyle 0.6×0.8×0.4, 3 boxes, StoneWall
- `SM_Arena_Deco_Cornice_400x020x020` — cornice 4×0.2×0.2
- `SM_Arena_Deco_Banner_Tattered_100x300x002` — banner 1×3×0.02, Wood_Rotted placeholder (use Banner_Cloth mat for final)
- `SM_Arena_Deco_Iron_Bracket_030x020x040` — bracket 0.3×0.2×0.4, Metal_Chain
- `SM_Arena_Deco_Candelabra_Wall_020x060x020` — candelabra 0.2×0.6×0.2, 2 mats
- `SM_Arena_Deco_Fog_Volume_1000x002x1000` — fog plane 10×0.02×10, scaled to 6.5 m and placed at y=0.54; master uses feathered `M_Arena_GroundMist` (alpha 0.07), not a hard-edged slab
- `SM_Arena_Deco_Moss_Patch_100x005x100` — moss 1×0.05×1, StonePillar (use Moss mat for final)

### LODs (4)
- `SM_Arena_Floor_400x400x050_LOD1` — same as LOD0 but marked LOD1
- `SM_Arena_Wall_400x400x100_LOD1` — single box
- `SM_Arena_Pillar_Full_140x1400_LOD1` — single box 1.6×14×1.6
- `SM_Arena_Statue_Complete_120x260x120_LOD1` — single box

---

## 4. Topology & Optimization

- **Clean Topology:** Boxes use 24 verts (hard edges) with per-face normals, proper UVs. Cylinders use 12-32 segments, caps as fans. No ngons — all quads triangulated by Unity.
- **Polygon Density:** Floor/wall/debris 12 tris, pillar full 48 tris, platform cylinder 128 tris, chain segment 288 tris, candle cluster 244 tris, brazier large 192 tris. The kit master has ~180 mesh renderers; many share StoneWall, StonePillar and StoneFloor. Profile actual draw calls in Unity with the separate lighting rig.
- **Reusable Meshes:** Shaft, base, capital are separate but also combined in full pillar. Floor tile 4×4 reused 30+ times. Wall 4×16 reused 8 times. Candle cluster reused 20 times.
- **Pivots:** All at base center (0,0,0 bottom). Verified in OBJ: bottom vertices at y=0, top at y=height, x/z centered.
- **Scale:** 1 unit = 1 meter. All dimensions from filenames: e.g., 400 = 4.00 m, 050 = 0.50 m.
- **UVs:** Planar per face, 0-1 range, uv_scale 1 per meter. Top faces use w×d UV, side faces w×h. Cylinders use cylindrical UV (u = angle/2π *2, v = height).
- **Material Slots:** 1 slot for 90% of meshes, 2 slots for wood beam (wood+metal), door wood (wood+metal), sealed stone (wall+pillar), altar (pillar+ritual), 3 slots for glass cluster (blue/red/amber) and candle cluster (brazier/wax/flame). Keeps batch count low.
- **High-detail only where necessary:** Statue torso uses extra cylinder for hood, chain link uses 4 boxes for torus shape, candle uses 12 segments for roundness. Walls/floor stay low.
- **LOD:** LOD1 versions are single boxes, 24 verts, same material, same pivot. Can be used with LODGroup (LOD0 0-15 m, LOD1 15-40 m, culled beyond). Fog and chains are already low.

---

## 5. Materials (20)

All use Built-in Standard shader (fileID 46). No textures — color, metallic, smoothness, emission only.

| Material | Color (sRGB) | Metallic | Gloss | Emission | Use |
|---|---|---|---|---|---|
| StoneFloor | 0.135,0.138,0.162 | 0.04 | 0.08 | none | outer floor, cold blue |
| StoneFloor_Ritual | 0.142,0.145,0.170 | 0.06 | 0.08 | 0.06,0.14,0.16 | dais tiers, ritual catch |
| StoneWall | 0.180,0.178,0.195 | 0.02 | 0.07 | none | walls, frames, arches, gargoyle |
| StonePillar | 0.165,0.160,0.155 | 0.03 | 0.06 | none | pillars, buttress, base, rim, debris, moss patch |
| StoneTrim | 0.19,0.185,0.20 | 0.02 | 0.07 | none | trim variant, warmer |
| Metal_Chain | 0.085,0.082,0.088 | 0.75 | 0.28 | none | chains, lead came, nail plates, brackets, iron gate |
| Wood_Rotted | 0.110,0.072,0.048 | 0 | 0.04 | none | beams, planks, scaffold |
| Door_Wood | 0.18,0.12,0.08 | 0 | 0.08 | none | heavy wood door |
| Door_Iron | 0.08,0.08,0.09 | 0.8 | 0.25 | none | iron gate |
| Statue_Eroded | 0.190,0.186,0.175 | 0.01 | 0.05 | none | statues, pedestals, palest stone |
| Glass_Blue | 0.18,0.28,0.62 a0.38 | 0 | 0.85 | 0.04,0.07,0.18 | blue glass, transparent |
| Glass_Red | 0.58,0.14,0.145 a0.36 | 0 | 0.82 | 0.14,0.02,0.02 | red glass |
| Glass_Amber | 0.60,0.38,0.09 a0.34 | 0 | 0.80 | 0.12,0.06,0.01 | amber glass |
| Candle_Wax | 0.84,0.80,0.71 | 0 | 0.15 | none | wax |
| Candle_Flame | 0.95,0.72,0.22 | 0 | 0.60 | 1.35,0.62,0.12 | flame emissive |
| RitualMarking | 0.22,0.235,0.25 | 0.02 | 0.12 | 0.22,0.48,0.52 | decals, rune, circle |
| Fog_Plane | 0.18,0.195,0.22 a0.075 | 0 | 0.02 | none | modular prefab / primitive chamber mist; master MeshKit uses `M_Arena_GroundMist` a0.07 |
| Brazier_Metal | 0.19,0.165,0.11 | 0.68 | 0.32 | none | braziers, holders, chalice |
| Banner_Cloth | 0.62,0.18,0.16 | 0 | 0.12 | none | tattered banners |
| Moss | 0.15,0.25,0.12 | 0 | 0.05 | none | moss patches |

**Philosophy:** Stone palette narrow 0.13-0.19 so candles (0.84) and ritual cyan pop. Metal dark (0.08-0.19) reads as line. Glass saturated but dim alpha 0.34-0.38 + low emission.

---

## 6. Prefab Structure

Each mesh has a prefab under `MeshKit/<Category>/`:

- GameObject name = mesh name
- Layer: Environment (10) for blocking (floor, wall, pillar, platform, stairs, door), Default (0) for non-blocking
- Components: Transform (base center), MeshFilter (guid to OBJ mesh 4300000), MeshRenderer (material guids), optional BoxCollider sized to mesh (center y = height*0.5)
- No extra scripts — tuning via root ArenaBounds / Fog / Lighting controllers

**Master Prefab:** `Arena_RitualChamber_MeshKit.prefab`

- Root (1000) with Transform (1001) + ArenaBounds (1002) + ArenaFogController (1003) + ArenaLightingController (1004)
- 321 children (Transforms 2001-5201) placed via polar coordinates
- Includes: 2 platform cylinders + rim + ritual center, floor tiles / wedges / eight raised ritual plates, 16 walls (8 window), 8 pillars, 5 arches, stairs, 8 statues, chains, wood, 20 candle clusters, ritual props, debris, doors and periphery decoration. It still serializes 20 candle point + 8 window spot **components**, but only 10 + 4 are enabled. Candle flames and stained glass remain visible at disabled practicals.
- Total: 1353 GameObject entries (including m_GameObject refs), 322 Transforms, ~180 renderers, 28 lights

**Scene:** `Arena_RitualChamber_MeshKit.unity`

- RenderSettings: exponential fog 0.027/0.033/0.05, density 0.01, flat cold ambient 0.10/0.112/0.15, no skybox
- PrefabInstance of `Arena_LightingRig` (five zones; 0.86-intensity moon key, only soft shadow caster, character-only neutral fill) — **no scene-level directional**
- Ground (disabled placeholder 12×1×12); MeshKit outer floor top is **y=0.5**
- SpawnPoint at (0,0.8,-14) facing north
- GameCore with GameManager, SceneFlowManager, GameBootstrap (spawns Player.prefab)
- PrefabInstance for MainCameraRig and Arena_RitualChamber_MeshKit at (0,0,0)

---

## 7. Gameplay Considerations

- **Clear combat disc:** r 0-12 m guaranteed pillar/statue/wall free. Only low dais (0.6 m) and ritual decals.
- **Penumbra:** r 12-17 m breathing ring with candles 0.5 m, low debris, ritual ring r7.
- **Periphery:** r 17-19 m walls, pillars, statues, chains, glass — vertical detail only, no floor clutter.
- **Movement:** Walk 3.2 m/s, Sprint 6.6 m/s, crossing 24 m disc 3.6 s walk / 1.8 s sprint. Dodge ~2.5 m, 4 dodges from center to penumbra.
- **Camera:** Environment layer colliders (walls + pillar shafts) pull camera in via ThirdPersonCameraRig spherecast radius 0.25. Minimum wall distance 19 m from center → ≥7 m from edge of combat disc to wall, so camera distance 4.5 never clips.
- **Lighting for telegraphs:** Ritual decals below knee height, candle flicker at 0.5-1 m, moon shafts 10 m high. Altitude-separated, no competition.
- **Boss provisions:** Spawn at (0,0.6,0) on upper dais, facing south. Forced step-down entrance. ArenaBounds exposes IsInsidePlayable, ClampToPlayable for AI. Penumbra empty for phase 2 hazards. Ritual ring decals (2.2×0.65) ~ one dodge-roll diameter, can light sequentially for AoE.

---

## 8. How to Assemble in Unity

1. Open `Assets/Scenes/Arena/Arena_RitualChamber_MeshKit.unity`
2. Press Play — capsule spawns at south broad stair, camera orbits, fog drifts, candles flicker, ritual pulses.
3. To modify:
   - Drag **both** `Arena_RitualChamber_MeshKit.prefab` and `Arena_LightingRig.prefab` into any scene at (0,0,0), then copy the arena scene's RenderSettings and camera grade overrides
   - Expand root, select any child, adjust Transform — pivot base center ensures rotation around Y stays on floor
   - Replace mesh by swapping MeshFilter mesh guid or swapping prefab child with another MeshKit prefab (e.g., replace `Wall_Solid` with `Wall_Window`)
   - For grid snapping: set Unity snap to 4 m (Edit > Snap Settings > Move 4, 0.5, 4) and rotate 22.5° increments
   - For LOD: add LODGroup component to pillar/wall/statue parent, assign LOD0 = Full mesh, LOD1 = LOD1 mesh, set screen relative heights 0.6 and 0.15
   - For new material: assign `M_Arena_Banner_Cloth` to banner, `M_Arena_Moss` to moss patch, `M_Arena_Door_Wood`/`Door_Iron` to doors
4. To build custom room:
   - Start with floor tiles 4×4 grid or wedges for circular
   - Add walls at radius, rotate tangent (rotY = -angle+90)
   - Add pillars at 45° increments, radius 17.5
   - Add platform cylinders at center
   - Scatter statues, chains, wood, candles, debris in periphery (r>12)
   - Add feathered mist at the **floor top + 0.04 m** (y=0.54 here), in the outer ring; do not cover the combat disc

---

## 9. Performance Budget

- Verts: ~8k for master (average 25 verts per mesh × 321)
- Tris: ~4k (average 12 tris per mesh, plus cylinders)
- Measure draw calls and transparent overdraw in Unity after importing the lighting meshes; no frame-time estimate is asserted from generated YAML.
- **Active** lights: MeshKit 10 candle point + 4 window spots (all shadowless) + rig 15 (one soft shadow key) = **29**, not 44. The other physical candles remain emissive.
- No textures for lighting, no lightmaps; translucent veils and motes use low-cost unlit shaders. Frame-rate targets need in-editor profiling on target hardware, not estimates from this sandbox.
- Future optimization: mark fixed Environment objects static, merge wall segments by material, bake lightmaps, add occlusion culling.

---

## 10. Future Hooks

- Boss intro: animate Tier2 y 0.45→0.60, chains clink via audio tied to lighting pulse
- Phase change: swap pillar Full → Damaged at runtime, drop rubble colliders into penumbra
- Weather: enable/disable window spot lights for rain shafts, boarded variant
- Corridors: reuse Wall_400x400, Floor_400x400, Pillar_Shaft, Arch_300x400 to build hallways

---

*This kit is one room that earns its keep by being empty enough to fight in and rich enough to remember after the fight. Every mesh is original, pivot-correct, and ready for Unity.*
