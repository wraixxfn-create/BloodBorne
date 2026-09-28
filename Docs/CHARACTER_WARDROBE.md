# Veilbound Wayfarer - Wardrobe Design

This document covers the **protagonist's clothing redesign**: a fully layered,
original gothic wardrobe built as real geometry (cloth solids with thickness),
the generator that produces it, and the verification performed without a Unity
editor. No garment is copied from Bloodborne or any other game; the whole
figure, its costume and every ornament are original to Vespershade.

## Files

| File | Purpose |
| --- | --- |
| `Tools/create_original_protagonist.py` | Procedural generator: writes the OBJ + MTL (wardrobe, head and the sectioned "Vigil Sweep" hairstyle; see [CHARACTER_HAIR.md](CHARACTER_HAIR.md)) |
| `Tools/render_character_previews.py` | Offline 12-angle preview renderer (numpy z-buffer rasterizer) used for multi-angle QA; also writes `Docs/CharacterPreviews/` |
| `Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj` | Base mesh, ~68.5k triangles, 9 material submeshes (path and GUID unchanged, so the prefab keeps working) |
| `Assets/Models/Characters/SM_Character_VeilboundWayfarer_L1.obj` | LOD1, ~45.5k triangles |
| `Assets/Models/Characters/SM_Character_VeilboundWayfarer_L2.obj` | LOD2, ~38.9k triangles |
| `Assets/Prefabs/Player/Player.prefab` | Base renderer + LOD1/LOD2 renderers driven by a `LODGroup` (50% / 18% / 6% screen height) |
| `Docs/CharacterPreviews/` | Rendered verification images (`sheet.jpg`, per-angle PNGs, `PC_lod_comparison.png`) |

Regenerate all three meshes with:

```bash
python3 Tools/create_original_protagonist.py
WAYFARER_DETAIL=0.62 WAYFARER_SUFFIX=_L1 python3 Tools/create_original_protagonist.py
WAYFARER_DETAIL=0.34 WAYFARER_SUFFIX=_L2 python3 Tools/create_original_protagonist.py
```

`WAYFARER_DETAIL` only scales segment counts; every design shape, proportion
and feature is identical between LOD levels.

## Wardrobe layers (outer to inner)

The character faces +Z. Layers stack visibly in the coat's chest opening:
**shirt collar/cravat -> waistcoat -> coat bodice -> belt -> coat skirt ->
boot shafts**.

1. **Long greatcoat (Cloth)** - the primary garment. Two front panels close
   left-over-right: a deep V opens from the collar and closes below the chest
   (hooks take over below that). The bodice is a cloth solid (outer face +
   inner lining + bound edges, 11 mm thick). A split skirt continues from
   under the belt to an asymmetric hem (left panel lower, both swept back),
   with sway folds displaced front-to-back.
2. **Back half-cape / shoulder mantle (Cloth)** - covers the shoulders and
   back only, deepest at the left-back (the design's main asymmetry), bound
   hem with bone piping, brass stud pins at both shoulder edges.
3. **Folded-back lapels (ClothAccent)** - wide wine panels flanking the V,
   narrow at the collar, widening over the chest; built as thick panels, not
   painted strips. The left lapel is broader than the right.
4. **Standing coat collar (ClothAccent + Cloth facing)** - wraps the back of
   the neck, open at the throat, taller behind; contrasting inner facing, bone
   piping along the top edge, a leather throat tab with a miniature brass
   buckle closing asymmetrically across the gap.
5. **Waistcoat (ClothAccent)** - fitted wine wool visible inside the V, with
   an offset bone-button placket (asymmetric), two pocket welts, bound hem.
6. **Shirt (BoneThread)** - standing collar band hugging the sculpted neck
   plus cuffs peeking beyond the coat cuffs; a wrapped cravat with an
   off-centre knot and two unequal tails.
7. **Trousers (Trouser)** - fitted wool under the coat: yoked waistband,
   knee tension creases, ankle wrinkles, hems tucked inside the boot shafts.
8. **Belt (Leather)** - wide belt cinched over the coat with a brass frame
   buckle + prong, two leather keepers, a punched hanging tip (three holes +
   brass eyelet), a flapped field pouch on the right-back hip, and a left
   hanger strap carrying a brass D-ring and a wine "mourning tassel".
9. **Baldric + hollow compass (Leather/Brass)** - one stitched band from the
   right shoulder to the left hip carrying the Wayfarer's original navigation
   instrument: two nested brass rings, a balanced needle and a dark face on a
   drop strap. (Original ornament - not a weapon, not from any existing game.)
10. **Boots (Leather/BootSole)** - rebuilt on real foot anatomy
    (`Tools/boot_rig.py`): the foot is 276 mm long with the ball line at 70 %
    of its length, an ankle joint raised by the heel; the boot is a full-length
    sole slab whose ground faces are exactly on the floor plane (feathered
    edges, a measured outboard wear flat, toe spring over the last 25 mm) with
    a canvas shank lifted between the heel breast and the ball; three stacked
    heel laminations, a brass heel edge plate and nail heads; a welt bead with
    welt stitching; a vamp lofted through 24 fitted cross-sections, a stitched
    toe cap panel and a heel counter; a fitted shaft (closed ankle tube plus a
    laced upper with a real lacing slit, raised facings, tongue, four brass
    eyelets + three speed hooks per facing, crossed leather laces and a tied
    bow); a folded wine cuff with lining and a riveted rear pull tab; and
    crossed instep straps with a brass buckle + keeper on **both** boots -
    replacing the old one-sided asymmetry with a properly fastened pair (the
    left/right asymmetry of the figure now lives in the coat, lapels and
    wrist). The trouser legs are *tucked*: they are compressed inside the
    shaft (>= 12 mm of clearance to the lining) and flare back out above the
    cuff opening, so no wool pokes through the leather.
11. **Gauntlet gloves (Leather/Skin)** - anatomically rebuilt hands: skin
    palms with thenar/hypothenar bulges and 12-station sculpting, four
    individual fingers (root flare, MCP/PIP/DIP knuckle bumps, palmar creases,
    tapered fingertips with pulp flatten) and an opposable thumb with saddle
    root, per side. Over each hand a fitted leather glove: palm stall, five
    finger stalls and a thumb stall as ~2.6-2.9 mm offset shells, dorsal
    seam beads, web gussets between the fingers, thumb-web gore, a bridged
    knuckle guard band with four raised ridges and saddle stitching, bound
    gauntlet cuff, wrist strap + buckle on the right hand, brass button on
    the left.

### Small straps and fasteners (inventory)

Collar tab + buckle, 4 coat hooks + studs, 5 waistcoat buttons, belt buckle +
prong + 2 keepers + eyelet, 2 boot instep straps + 2 buckles, boot heel plates
+ nail heads, right cuff strap + buckle, wrist strap + buckle, baldric with
stitch dashes, pouch flap + stud, mantle stud pins, toe-cap, counter, welt and
flap saddle stitching.

### Believability details

- **Thickness everywhere**: coat 11 mm, trousers 6-7 mm, boots 5-7 mm,
  belts/straps 3-9 mm, lapels 5-6 mm - each garment is a closed solid, so
  edges and hems show real material, never a texture painted on the body.
- **Folds/tension**: gathered sleeve heads, elbow creases and a stitched
  elbow patch (left), waist gathers under the belt, shoulder-blade drape
  creases, knee creases, ankle wrinkles, boot-shaft slouch, skirt sway folds.
- **Asymmetry**: left-over-right closure, deeper left shoulder mantle,
  broader left lapel, single baldric, one wrist buckle, unequal coat tails,
  offset button plackets. (The boots are a matched, properly buckled pair.)
- **Budget discipline**: the head carries the sculpted face plus the sectioned
  "Vigil Sweep" hairstyle (70 swept-solid sections, 14.5k tris on the base LOD -
  see [CHARACTER_HAIR.md](CHARACTER_HAIR.md)); garments use fewer segments where
  cloth is flat or hidden; hidden body parts are absent entirely (the coat and
  gloves cover them; the face, neck and forearms are the only visible skin).

## Rig / gameplay integration

- Same file name, same 9 submesh order (Cloth, ClothAccent, Trouser, Leather,
  Skin, Hair, AgedBrass, BoneThread, BootSole) and same material GUIDs - the
  existing `Player.prefab` wiring keeps working untouched.
- The player is intentionally still a static mesh child of the capsule
  (this foundation has no animation rig yet); the wardrobe adds no bones,
  no scripts, no physics and no input changes. `CharacterController`,
  `PlayerController` and the camera are untouched.
- Each LOD regenerates a `SM_Character_VeilboundWayfarer*.handrig.json`
  sidecar (`vespershade.handrig/1`): 41 joints (Root + per side
  Shoulder/Elbow/Forearm/Wrist/Hand chain + full digit chains) with axis
  conventions, and the 66 rigged part ranges (global OBJ vertex indices)
  that map hand geometry to those joints. The sidecar is authored data for
  future rigging - the prefab consumes nothing from it at runtime.

## Multi-angle verification (offline)

Because this repository is authored without a Unity editor, Play-Mode-style
visual QA runs through `Tools/render_character_previews.py`, which renders
the exact OBJ the game imports from 14 cameras (front / three-quarter L+R /
back / profiles / collar, torso, belt, knee, boot close-ups / rear close-up /
left + right hand close-ups) into `Docs/CharacterPreviews/`, plus
`Tools/render_boot_previews.py`, which poses the boots through the LBS rig for
idle / walk / run / dodge over a 0.5 m floor grid (`PC_boots_<pose>_*.png`). The exported `sheet.jpg` is the final
verification of this revision. `PC_lod_comparison.png` shows L0/L1/L2 side by
side. In-editor checks on first open: open
`Assets/Scenes/Arena/Arena_RitualChamber_MeshKit.unity`, press Play, orbit the
camera around the spawn point and confirm the layers at close range; the
LODGroup can be verified with the Scene view's "Render Modes > LOD" overlay.

## Structural checks

`Tools/validate_unity_project.py` (learned Unity's built-in `LODGroup` class
id 205 in this change), `Tools/audit_serialized_types.py`,
`Tools/csharp_smoke_check.py`, `Tools/test_serialized_types.py` and
`Tools/verify_arena_lighting.py` all pass after this redesign.

`Tools/verify_boots.py [--obj ...]` performs offline foot/boot QA on any LOD:
part inventory (39 boot parts per side) and part-range integrity, closed-shell
and outward-winding checks, measured anatomy (foot length, ball position and
width, heel width, ankle height, sole thickness, shaft height) against
`Tools/boot_rig.py`, exact left/right mirror symmetry, the floor-contact
contract (minimum vertex exactly 0.000, both boots resting on a real contact
patch, shank lift, toe spring, flat parallel sole plane), trouser-tuck
clearance, skin weights, and LBS deformation for idle / walk / run / dodge
with each planted boot grounded at exactly the floor by foot IK and each swing
boot clear of it. `Tools/render_boot_previews.py` renders those four states
over a checkerboard floor (`Docs/CharacterPreviews/PC_boots_*.png` + contact
sheet). All 47 checks pass on all three LODs.

`Tools/verify_hands.py [--obj ...]` performs offline hand QA on any LOD:
part inventory, palm/finger/thumb proportions and knuckle definition, skin
finger separation (anti-mitten), skin weights (sums, influence counts, side
purity, per-digit chains), glove containment and clearance, and full
linear-blend-skin deformation for the stand / walk / attack / dodge poses
(palm tracks the hand joint, glove shell drift, no stall interpenetration,
fingertips never tunnel through the palm, grip closure). All 114 checks pass
on all three LODs.

A full-mesh winding audit (signed volume per connected component + raycast
visibility) now runs as part of regeneration QA: every one of the 729 closed
components on the base mesh (and every closed component on L1/L2) has
positive orientation, and raycast spot checks confirm previously inside-out
parts (belt, shirt cuffs, cuff buttons, coat skirt, shoulder mantle, boot
rims, button rims) are visible from outside.
