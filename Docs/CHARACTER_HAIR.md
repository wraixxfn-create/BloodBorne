# Veilbound Wayfarer - Hairstyle ("the Vigil Sweep")

This document covers the **protagonist's hairstyle**: an original,
sectioned swept-solid hair build, the generator that produces it, the
material response, and the verification performed without a Unity editor.
The style is original to Vespershade - no named character, game or asset
was copied.

## Files

| File | Purpose |
| --- | --- |
| `Tools/create_original_protagonist.py` | Procedural generator; the hair block (`generate_gothic_hair` / `generate_hair_tie`) writes the lock geometry and the `.hairrig.json` sidecar |
| `Tools/verify_hair.py` | Offline structural verification (21 checks per LOD, all must pass) |
| `Tools/render_hair_previews.py` | Offline hair-focused renderer: close front/side/back/top/ear views **plus the four normal-gameplay-distance views** (4.5 m orbit, 52 degree FOV, matching `MainCameraRig`) |
| `Assets/Models/Characters/SM_Character_VeilboundWayfarer*.obj` | The hair is part of the player mesh (submesh 6, `Hair`), so it inherits every player transform exactly |
| `Assets/Models/Characters/SM_Character_VeilboundWayfarer*.hairrig.json` | Section map: every lock's vertex range + role, part line, hairline controls, clearance contract, triangle budget |
| `Assets/Art/Shaders/CharacterHair.shader` | Material response (see [CHARACTER_MATERIALS.md](CHARACTER_MATERIALS.md)) |
| `Assets/Materials/Character/M_Char_Hair.mat` | Material instance (GUID unchanged, prefab wiring untouched) |
| `Docs/CharacterPreviews/hair_*.png`, `hair_sheet.jpg` | Rendered verification images |

Regenerate (all three LODs) and verify:

```bash
python3 Tools/create_original_protagonist.py
WAYFARER_DETAIL=0.62 WAYFARER_SUFFIX=_L1 python3 Tools/create_original_protagonist.py
WAYFARER_DETAIL=0.34 WAYFARER_SUFFIX=_L2 python3 Tools/create_original_protagonist.py
python3 Tools/generate_unity_guids.py        # .meta for any new sidecar files
python3 Tools/verify_hair.py                 # + --obj ..._L1.obj / ..._L2.obj
python3 Tools/render_hair_previews.py        # writes Docs/CharacterPreviews/hair_*
```

## Design: "the Vigil Sweep"

Dark blue-black, mid-length hair swept back and across from an offset part
(just right of centre), collected low at the back of the crown into a bound
tail, with a layered nape draping over the greatcoat collar and face-framing
temple strands. Read at a glance: asymmetric sweep + gathered tail + bone
twine tie - a silhouette that survives the gameplay camera distance.

### Recognizable silhouette

- **Offset part line** running front hairline -> over the crown (authored as
  `HAIR_PART_2D`, modelled as a real groove in the cap).
- **Scalloped hairline** (`HAIRLINE_CTRL`): widow's peak, temple peaks, a
  raised notch over each sculpted ear, and a nape drop - never a smooth cap rim.
- **Deep diagonal sweep** across the crown to the character's left (the style's
  asymmetry), read from front and three-quarter views.
- **Gathered bound tail** with visible tie wraps, knot and two cord ends.

### Sections (the anti-blob requirement)

The style is built from **70 independent closed solids** (base LOD), each
recorded in the sidecar:

| Role | Count | What it is |
| --- | --- | --- |
| `cap` | 1 | Padded scalp shell (+7.5 mm base offset, sculpted crown dome, sweep ridge, occiput fullness), scalloped modelled hairline, part groove, side/back flow ripples |
| `crown` | 27 | Sweeps radiating from the part (R/L/B fans), dome fans, two apex whorl spirals |
| `fringe` | 5 | Asymmetric forehead sweep + shorter companion strands |
| `side` | 6 | Side vault sweeps above the ears + ear fills |
| `temple` | 4 | Cheek-framing strands in front of the ears + behind-ear tucks |
| `nape` | 8 | Staggered layers hugging the collar's outward slope, then draping onto the mantle |
| `gather` | 1 | Rippled dome where the mass is collected |
| `tail` | 4 | Twisted rope strands with staggered tip lengths around a curved, tapering axis |
| `wisp` | 8 | Short hairline rim wisps (base LOD only) |
| tie (`BoneThread`) | 6 | Two cord wraps, knot loops, two curled ends |

Every lock is a swept solid: Catmull-Rom centreline, elliptical flattened
cross-section with longitudinal grooves, twist, deterministic jitter, swollen
root sunk into the cap, pinched fan tip. No primitive (sphere/capsule/cone)
appears anywhere; neighbouring bands alternate in ride height and width so
valleys read between them.

### Believable volume

- Padded crown apex reaches **y = 1.833** over the bare skull apex (1.815)
  - at least 12 mm of modelled lift (verified).
- Side profile is roughly **55 mm thicker than bare skin** across the ear
  band (verified r95 vs the bare-head spline radius).
- The silhouette thickness tapers: deep at the sweep ridge, low over the
  ears, full at the occiput - not an inflated bubble.

### Material response

`CharacterHair.shader` (rewritten for this style):

- **Object-space strand flow** (custom vertex function): a flow field that
  matches the groom (away from the part on the crown, down-and-back at the
  sides, straight down at the nape). Because the pattern is a function of
  bind-pose mesh coordinates it **cannot swim, crawl or slide** during
  movement, animation or camera orbits - the classic failure of
  world/triplanar procedural hair.
- **Kajiya-Kay two-lobe anisotropic specular** over the flow tangent:
  tight shifted primary + wider tinted secondary, on a wrapped diffuse.
- **Strand banding** along the flow (two frequencies, noise-warped so bands
  wave and split), perturbed normals along the band profile, roughness
  variation, per-region tint patches, **root darkening** toward the
  hairline, and valley occlusion between bundles.
- All parameters exposed on `M_Char_Hair` (base/variation/highlight colours,
  strand scale, anisotropy, root darkening, flow strength, smoothness).

### Stability during movement / animation

- The hair is **rigid geometry of the player mesh**: one transform, one
  `MeshFilter`/`MeshRenderer`, one LODGroup - there is no cloth, jiggle or
  physics simulation to destabilise, and it is skinned/animated exactly
  like the rest of the figure when that future rig arrives.
- Loose elements keep verified clearance: face-zone emptiness (z > 0.082,
  y < 1.702, |x| < 0.055 is hair-free), eyeball clearance >= 24 mm, ear
  notch keeps the cap rim off the ears, and the tail axis keeps ~10 mm from
  the collar top while resting on the mantle drape.
- The shader pattern is object-space (see above), so shading is stable even
  at high animation speeds.

## Budgets

| LOD | Hair triangles | Sections | Whole mesh |
| --- | --- | --- | --- |
| Base | 14,538 (14.8%) | 70 | 98,398 tris |
| L1 | 6,553 (10.8%) | 56 | 60,649 tris |
| L2 | 5,608 (11.1%) | 56 | 50,398 tris |

LOD reductions: `WAYFARER_DETAIL` drops segment counts (cap ring/side
density, lock sides/stations) and removes the wisps below detail 0.8; the
section layout and silhouette are identical at every LOD.

## Verification performed (no Unity editor in the loop)

`Tools/verify_hair.py` - 21 checks per LOD, all passing:

- **A. Ranges**: every sidecar section exists in the OBJ with exactly the
  claimed vertex range; Hair ranges are contiguous; every non-eyebrow Hair
  face belongs to exactly one section.
- **B. Solids**: every section is a closed, consistently outward-facing
  solid (positive signed volume).
- **C. Silhouette**: crown apex >= 12 mm above the skull apex; side profile
  thicker than bare skin across the ear band.
- **D. Zoning**: no hair in the face zone; >= 24 mm eyeball clearance; nape
  drops past the collar top; tail rests within 30 mm of the mantle drape.
- **E. Sectioning**: minimum counts per role; per-role centroid spread so
  locks never share one plane (blob detection).
- **F. Stability**: rigid-attachment contract; tie wraps encircle the gather.

`Tools/render_hair_previews.py` renders the required test views with a
preview analogue of the hair shader (banding + root occlusion + sheen):

- close **front**, **side**, **back** (+ three-quarter, top, ear close-up)
- **normal gameplay distance** front / side / back / three-quarter
  (4.5 m orbit distance, 52 degree FOV - the `MainCameraRig` defaults)

Output lives in `Docs/CharacterPreviews/` (`hair_*.png`, `hair_sheet.jpg`).

### Manual QA still recommended on first open

The authoring environment has no Unity editor; static + offline-render
checks are not evidence of an exception-free Console. On first open:
confirm `M_Char_Hair` compiles (`Vespershade/CharacterHair`), walk/sprint/
jump in `Arena_RitualChamber_MeshKit` and confirm the silhouette holds from
the orbit camera at 1.8 m - 8 m, and check the LOD transitions
(50% / 18% / 6% screen height) do not pop the silhouette.

## Gameplay systems untouched

The hair geometry, its original submesh slot, `LODGroup`, input, camera and
scene behaviour are unchanged. Two appended material slots now route the
already-existing glove and eye surfaces to their dedicated shaders. The hair
rides the same player mesh; `M_Char_Hair` keeps GUID `c17c22c2...` and its
shader GUID is unchanged.
