# Veilbound Wayfarer - Rig, Skinning and Deformation QA

This document covers the **protagonist's rig**: the skeleton, the Unity
humanoid mapping, the skin weights, and the deformation checks that were run
on it. Like the rest of the project it was authored and verified **without a
Unity editor in the loop**: the rig is data plus deterministic Python, and
`Tools/verify_rig.py` is the offline equivalent of posing the character in the
editor and watching the mesh.

Original work only. Nothing here is copied from Bloodborne or any other game.

## Status: what the rig is, and what it is not

| | |
| --- | --- |
| **Skeleton** | 60 bones in one hierarchy rooted at `Root` (see below) |
| **Weights** | deterministic functions of the bind position, one chain id per mesh part; 51,469 vertices bound, 420 parts bound as stiff solids, none left on `Root` |
| **Sidecar** | `Assets/Models/Characters/SM_Character_VeilboundWayfarer*.rig.json` (`vespershade.rig/1`): bones, humanoid map, 717 part ranges (586 on L1, 515 on L2) |
| **Pose vocabulary** | `bind`, `idle`, `walk`, `run`, `attack`, `dodge` - the same states `hand_rig`/`boot_rig` were verified with |
| **Runtime today** | the Player prefab still draws the OBJ through `MeshFilter`/`LODGroup`; there is no `SkinnedMeshRenderer`, `Animator` or `Avatar` in the scene |
| **Unity Humanoid** | *not enabled in the asset* - the OBJ carries no skeleton, so an Avatar cannot be built from it. The 52-slot mapping below is complete and verified, so switching to Humanoid is a mechanical step once the mesh ships with bones |
| **Gameplay controller** | untouched. `PlayerController` + `CharacterController` on `Player.prefab` are exactly as they were; the rig work touches no C# and no prefab wiring |

The rig exists so the character can be animated, and so deformation problems
can be found and fixed *before* they are visible in the editor. Fixing a
deformation bug in the generator (a missing loop, a weight seam) is part of
the mesh, not of the rig.

## Files

| File | Purpose |
| --- | --- |
| `Tools/body_rig.py` | **Source of truth**: skeleton, humanoid map, garment weight rules, pose tables, FK, linear blend skinning, bind metrics |
| `Tools/verify_rig.py` | Verifier: hierarchy, humanoid, bone placement, weights, bind identity, cross-rig FK, 45 pose/deformation cases, floor contact, pelvis isolation |
| `Tools/hand_rig.py` | Authoritative arm/hand bones and glove weights (pre-existing, unchanged) |
| `Tools/boot_rig.py` | Authoritative leg/foot bones, boot weights, ankle/ball IK (pre-existing, unchanged) |
| `Tools/create_original_protagonist.py` | Generates the mesh and the four sidecars; registers every mesh part with a chain id |
| `Assets/Models/Characters/*.rig.json` | Exported skeleton + part ranges + humanoid map, one per LOD |

Regenerate and verify:

```bash
python3 Tools/create_original_protagonist.py                    # mesh + all sidecars (L0)
WAYFARER_DETAIL=0.62 WAYFARER_SUFFIX=_L1 python3 Tools/create_original_protagonist.py
WAYFARER_DETAIL=0.34 WAYFARER_SUFFIX=_L2 python3 Tools/create_original_protagonist.py
python3 Tools/verify_rig.py --structure   # hierarchy, humanoid, placement, weights, bind (30 s)
python3 Tools/verify_rig.py --sweeps      # 45 deformation cases + animation states (100 s)
python3 Tools/verify_rig.py --sweeps --only elbow --debug   # one family, worst edges
python3 Tools/verify_rig.py --sweeps --report /tmp/rig.json # machine-readable report
```

`verify_rig.py` takes `--obj/--rig` so the LODs are checked with the same
rules:

```bash
python3 Tools/verify_rig.py --structure \
  --obj Assets/Models/Characters/SM_Character_VeilboundWayfarer_L2.obj \
  --rig Assets/Models/Characters/SM_Character_VeilboundWayfarer_L2.rig.json
```

## Skeleton

60 bones, 1 m = 1 unit, +Y up, character faces +Z, feet at y = 0, height
1.85 m. The hierarchy is one tree; the arm and leg branches are the bones the
pre-existing hand/boot rigs already used, so their sidecars, verifiers and
part ranges keep working unchanged.

```
Root                                  character origin, on the floor
 +- Pelvis                            sacrum (hip joints 40 mm below)
 |   +- Spine1 -> Spine2 -> Chest     three-segment spine
 |   |   +- RClavicle -> RShoulder -> RElbow -> RForearm -> RWrist -> RHand
 |   |   |                              (hand_rig: + 4 fingers x 3 + thumb x 3)
 |   |   +- LClavicle -> ... -> LHand
 |   |   +- Neck -> Head -> HeadEnd    skull base -> crown
 |   +- RHip -> RKnee -> RAnkle -> RBall -> RToe
 |   +- LHip -> ... -> LToe            (boot_rig leg + foot chains)
```

Torso, clavicle and neck/head bones (the ones this rig adds); the arm, hand
and leg branches keep `hand_rig`/`boot_rig` coordinates and are listed in
those documents' companions. Left side heads are the mirror of the right
(exact, verified):

| Bone | Parent | Head (m) | Unity humanoid slot |
| --- | --- | --- | --- |
| `Root` | - | +0.000, 0.000, +0.000 | - |
| `Pelvis` | `Root` | +0.000, 0.945, -0.012 | `Hips` |
| `Spine1` | `Pelvis` | +0.000, 1.045, -0.010 | `Spine` |
| `Spine2` | `Spine1` | +0.000, 1.165, -0.012 | `Chest` |
| `Chest` | `Spine2` | +0.000, 1.290, -0.014 | `UpperChest` |
| `Neck` | `Chest` | +0.000, 1.432, -0.016 | `Neck` |
| `Head` | `Neck` | +0.000, 1.508, -0.020 | `Head` |
| `HeadEnd` | `Head` | +0.000, 1.808, -0.020 | - (tip) |
| `RClavicle` | `Chest` | +0.030, 1.428, +0.014 | `RightShoulder` |
| `RShoulder` | `RClavicle` | +0.201, 1.462, -0.008 | `RightUpperArm` |
| `RElbow` | `RShoulder` | +0.352, 1.185, +0.020 | `RightLowerArm` |
| `RForearm` | `RElbow` | +0.380, 1.090, +0.034 | - (roll bone) |
| `RWrist` | `RForearm` | +0.386, 0.992, +0.046 | - (roll bone) |
| `RHand` | `RWrist` | +0.390, 0.944, +0.050 | `RightHand` |
| `RHip` | `Pelvis` | +0.100, 0.905, +0.000 | `RightUpperLeg` |
| `RKnee` | `RHip` | +0.116, 0.492, +0.008 | `RightLowerLeg` |
| `RAnkle` | `RKnee` | +0.118, 0.105, -0.034 | `RightFoot` |
| `RBall` | `RAnkle` | +0.118, 0.031, +0.112 | `RightToes` |
| `RToe` | `RBall` | +0.118, 0.036, +0.176 | - (last joint) |
| `RThumbCMC` | `RHand` | +0.373, 0.975, +0.070 | `RightThumbProximal` |
| `RThumbMCP` | `RThumbCMC` | +0.359, 0.950, +0.094 | `RightThumbIntermediate` |
| `RThumbIP` | `RThumbMCP` | +0.351, 0.941, +0.120 | `RightThumbDistal` |
| `RIndexMCP/PIP/DIP` | chain | +0.386/0.383/0.380, 0.904/0.866/0.845, +0.086/0.089/0.091 | `RightIndexProximal/Intermediate/Distal` |
| `RMiddleMCP/PIP/DIP` | chain | +0.395/0.392/0.387, 0.897/0.856/0.832, +0.067/0.068/0.067 | `RightMiddle...` |
| `RRingMCP/PIP/DIP` | chain | +0.403/0.400/0.395, 0.900/0.861/0.838, +0.048/0.046/0.044 | `RightRing...` |
| `RLittleMCP/PIP/DIP` | chain | +0.409/0.407/0.402, 0.912/0.882/0.865, +0.030/0.026/0.022 | `RightLittle...` |

Every bone carries a `flex` / `abd` / `twist` axis triple (world unit vectors
in the bind pose), mirror-symmetric between sides:

| Family | `flex +` | `abd +` | `twist +` |
| --- | --- | --- | --- |
| torso, neck, head | bend forward | bend to the character's left | turn right |
| clavicle | shoulder forward | shrug up | - |
| arm | swing forward | outboard (thumb side) | roll of the segment |
| leg | hip swings forward / knee folds back | outboard | toes out |
| foot | dorsiflexion (toes up) | - | - |

Bind pose: arms 22.3 deg off vertical, elbows 18.7 deg, knees 2.5 deg - a
normal A-pose, which `verify_rig.py` asserts (a Humanoid Avatar is configured
from the bind pose, so every joint must be inside Unity's A-pose envelope).
Zero rotations reproduce the OBJ vertex-for-vertex (max error 1e-9 m).

## Unity humanoid mapping (52 slots, verified)

`body_rig.humanoid_bone_map()` maps 52 of the 60 bones onto
`UnityEngine.HumanBodyBones`. All 21 required slots are present, each slot is
used once, left/right pairs mirror exactly, and every mapped bone sits after
its parent in the list (Unity requires parent-before-child ordering when a
script builds the bones).

The 8 unmapped bones are roll/tip helpers Unity creates itself or ignores:
`Root`, `HeadEnd`, `RForearm`, `LForearm`, `RWrist`, `LWrist`, `RToe`, `LToe`.

| Unity slot | Bone | | Unity slot | Bone |
| --- | --- | --- | --- | --- |
| `Hips` | `Pelvis` | | `RightShoulder` | `RClavicle` |
| `Spine` | `Spine1` | | `RightUpperArm` | `RShoulder` |
| `Chest` | `Spine2` | | `RightLowerArm` | `RElbow` |
| `UpperChest` | `Chest` | | `RightHand` | `RHand` |
| `Neck` | `Neck` | | `LeftShoulder` | `LClavicle` |
| `Head` | `Head` | | `LeftUpperArm` | `LShoulder` |
| `RightUpperLeg` | `RHip` | | `LeftLowerArm` | `LElbow` |
| `RightLowerLeg` | `RKnee` | | `LeftHand` | `LHand` |
| `RightFoot` | `RAnkle` | | `LeftUpperLeg` | `LHip` |
| `RightToes` | `RBall` | | `LeftLowerLeg` | `LKnee` |
| `RightThumbProximal` | `RThumbCMC` | | `LeftFoot` | `LAnkle` |
| `RightThumbIntermediate` | `RThumbMCP` | | `LeftToes` | `LBall` |
| `RightThumbDistal` | `RThumbIP` | | `LeftThumbProximal` | `LThumbCMC` |
| `RightIndexProximal` | `RIndexMCP` | | `LeftThumbIntermediate` | `LThumbMCP` |
| `RightIndexIntermediate` | `RIndexPIP` | | `LeftThumbDistal` | `LThumbIP` |
| `RightIndexDistal` | `RIndexDIP` | | `LeftIndexProximal` | `LIndexMCP` |
| `RightMiddleProximal` | `RMiddleMCP` | | `LeftIndexIntermediate` | `LIndexPIP` |
| `RightMiddleIntermediate` | `RMiddlePIP` | | `LeftIndexDistal` | `LIndexDIP` |
| `RightMiddleDistal` | `RMiddleDIP` | | `LeftMiddleProximal` | `LMiddleMCP` |
| `RightRingProximal` | `RRingMCP` | | `LeftMiddleIntermediate` | `LMiddlePIP` |
| `RightRingIntermediate` | `RRingPIP` | | `LeftMiddleDistal` | `LMiddleDIP` |
| `RightRingDistal` | `RRingDIP` | | `LeftRingProximal` | `LRingMCP` |
| `RightLittleProximal` | `RLittleMCP` | | `LeftRingIntermediate` | `LRingPIP` |
| `RightLittleIntermediate` | `RLittlePIP` | | `LeftRingDistal` | `LRingDIP` |
| `RightLittleDistal` | `RLittleDIP` | | `LeftLittleProximal` | `LLittleMCP` |
| | | | `LeftLittleIntermediate` | `LLittlePIP` |
| | | | `LeftLittleDistal` | `LLittleDIP` |

### Enabling Humanoid in Unity

The mesh must first ship as a **skinned** asset (bones + skin weights inside
the imported model); an OBJ with `DefaultImporter` cannot carry them. Once it
does:

1. Select the model, `Rig > Animation Type: Humanoid`, `Avatar Definition:
   Create From This Model`.
2. Click `Configure...` and confirm the slot table above; the bind pose is
   already an A-pose, so no T-pose fix-up is needed.
3. `Animator > Avatar` = the generated avatar; clips imported with the same
   mapping retarget to it.
4. Unity creates `Root`-side helpers and the roll bones it wants (`Forearm`,
   `Wrist`) itself; leave `HeadEnd`/`Toe` unmapped.

`verify_rig.py` fails the build report if a slot is missing, duplicated,
non-mirrored, or ordered wrong, so a mapping regression is caught offline.

## Skin weights

Every mesh part is registered with a **chain id** when it is generated
(`Tools/create_original_protagonist.py` -> `_record_mesh_part`), and the chain
resolves to a deterministic weight function of the bind position. This is the
same contract the hand and boot rigs already used; the body chains were added
here.

| Chain | Weight rule | Covers |
| --- | --- | --- |
| `torso` | vertical ramp Pelvis->Spine1->Spine2->Chest over 70 mm bands, plus a clavicle/chest blend in the coat shoulder | coat bodice, waistcoat, shirt, mantle, belt, baldric, seams, buttons |
| `collar` | rigid to `Chest` | standing coat collar, facing, piping, throat tab |
| `neckwear` | neck ramp `head_weights` (same rule as the neck skin) | shirt collar band, cravat and tails |
| `skirt` | pelvis at the waist, thigh band centred on each leg | coat skirt panels, vent pleat, martingale |
| `hip` | pelvis/thigh ramp across the yoke | trouser yoke and seat |
| `armR`, `armL` | partition of unity on the arm joint planes (`hand_rig` anchors) | coat sleeves, elbow patch, sleeve seams, arm skin |
| `legR`, `legL`, `shaft`, `foot` | `boot_rig` rules (unchanged, verified by `verify_boots.py`) | trousers below the tuck, boots |
| `guard`, `cuff`, `palm`, `digit*`, `thumb*`, `web*` | `hand_rig` rules (unchanged, verified by `verify_hands.py`) | gloves, cuffs, fingers |
| `head` | neck->head ramp 1.452..1.548 | face, scalp, ears, eyes, brows |
| `hair` | rigid to `Head` | all 70 hair sections + ties |
| `root` | rigid to `Root` | nothing (kept as a fallback; the verifier fails if any vertex uses it) |

Rules that came out of the deformation checks:

* **Arm blend is a partition of unity on the joint planes.** Each bone owns the
  span between its joints and hands over across a fixed window centred on the
  joint (half-width: shoulder 50 mm, elbow 100 mm, forearm 46 mm, wrist 46 mm).
  Two failure
  modes are avoided by construction: a full-weight plateau *at* the joint
  (pinches the crease) and a ramp stretched over most of the segment (an
  off-axis sleeve vertex under a long lever tears - measured at 2.1x on a 90 mm
  edge before).
* **The weight parameter is the distance to the joint's bisector plane**, not
  an arc length along the bone polyline. A polyline parameter jumps across the
  joint's medial surface whenever the chain kinks (13.6 deg at the elbow here),
  and a jump in the parameter is a jump in the weights.
* **The wrist plane sits 32 mm below the wrist joint.** The coat cuff - fold,
  strap, buckle, buttons - is a stiff band wrapped around the wrist; a joint
  plane through the middle of it pinched the fold (31 mm edges down to 6 mm at
  a 45 deg wrist). The wrist bone drives the hand, the glove and the forearm
  skin, which all start below that plane.
* **Nothing in the torso chain reaches the neck.** The neck bone has a long
  lever arm (the head is 300 mm above it): a garment straddling the torso/neck
  boundary shears instead of following it. The coat collar is `Chest`, the
  shirt collar is `Neck`/`Head`.
* **The coat skirt follows the leg only in a band centred on each thigh**
  (30..95 mm off the centre line). A plain `|x|` ramp gives the coat's centre
  seam to one side's thigh, which tears the seam apart when a leg steps.
* **Details are bound by part, not vertex by vertex.** A part smaller than
  200 mm across is *stiff*: all its vertices share the weights of the part
  centroid, so it keeps its shape instead of folding through itself or shearing
  across a joint (stitch dashes, buttons, buckles, rivets, rings, patches,
  straps, ears, eyes - 420 of the 717 parts on LOD0, 315 of 586 on LOD1, 258 of
  515 on LOD2). The rule lives in `body_rig.classify_parts` and is exported per
  part in the sidecar. Bands that span the body axis (belt, piping, cravat) are
  *not* details: their weight rule is already uniform all the way round a ring,
  which is what a stiff band needs.
* **Hair is rigid to the head**, which is the contract the hair sidecar and
  `verify_hair.py` already assume.

Weight invariants asserted for every vertex of every LOD: influences sum to
1 (1e-6), at most 4 influences (GPU skinning), no NaN, no vertex left on
`Root`, every influence within 0.7 m (the coat hem hangs 0.55 m below the
pelvis), and left/right mirrored vertices carry mirrored weights (worst delta
0.006).

## Deformation QA

`Tools/verify_rig.py` poses the rig and measures the mesh, region by region.
Limits are chosen so that rigid joint motion can never register as a defect:
the triangle test compares the posed normal with the normal the vertex blend
*should* have produced.

| Metric | Limit | Meaning |
| --- | --- | --- |
| edge stretch | ratio > 2.0 **and** > 8 mm of added length | the surface is being pulled apart |
| edge collapse | ratio < 0.30 on a surface edge (>= 10 mm at rest) | the surface is pinching flat |
| inverted faces | > max(4, 0.5 % of the region) | the surface folded through itself |
| girth | mean radius around the joint axis >= 0.55 of rest | the limb is losing volume |
| crease gap | fails only when the two sides of a fold pass *through* each other | self-intersection at the crease |
| NaN / floor | no NaN, boot contact preserved | the pose is usable |

Regions are the vertices within the joint's radius that the joint actually
drives; `--debug` prints the worst edges with their chains and weights.

**Result (45 cases, 0 failures, 4 warnings).** The warnings are the two
over-range stress cases (`elbow_130` left and right, 130 deg against the 98 deg
the authored poses use): the inner fold of the sleeve inverts 9-14 faces out of
~1300 and closes to 15 % of its rest gap. Finite, area-consistent, hidden
inside the fold, and outside the range the animation set uses - recorded rather
than hidden.

| Family | Cases | Result |
| --- | --- | --- |
| shoulder abduct 90/135, flex 90 | 6 | pass (stretch <= 1.5x, no inversions) |
| clavicle shrug 18 | 2 | pass (1.14-1.23x) |
| elbow 90/100/130 | 6 | 90 and 100 pass; 130 is the stress warning above |
| forearm twist 90 | 2 | pass (<= 1.9x) |
| wrist flex 45, deviation 25 | 4 | pass (<= 1.7x) |
| hip flex 90, abduct 35 | 4 | pass (crease stays open, no inversions) |
| knee 90/130 | 4 | pass (stretch 1.00x, no inversions) |
| ankle dorsi 25, plantar 35 | 4 | pass (boot geometry follows the foot IK) |
| spine bend/twist/side 40/40/25 | 3 | pass (1.23-1.44x, no inversions) |
| pelvis tilt 20 | 1 | pass (1.00x) |
| head yaw 60 / pitch 30 / roll 25 | 3 | pass (<= 1.75x) |
| neck + head yaw (25 + 35) | 1 | pass (1.37x) |
| idle / walk / run / attack / dodge | 5 | pass: grounded, contact patch preserved |

Animation states (existing pose vocabulary, skinning through the full body):

```
idle   grounded dy +0.0000 m   contact patch 236 verts / 345 mm  lowest  -0.0 mm
walk   grounded dy -0.0194 m   contact patch  26 verts / 388 mm  lowest +19.4 mm
run    grounded dy +0.0171 m   contact patch  14 verts / 109 mm  lowest -17.1 mm
attack grounded dy +0.0000 m   contact patch 236 verts / 345 mm  lowest  -0.0 mm
dodge  grounded dy -0.1326 m   contact patch 116 verts / 252 mm  lowest +132.6 mm
```

None of the locomotion poses rotate the pelvis, so the boot contact solved by
`boot_rig` (plane y = 0, >= 40 mm patch, 1.5 mm tolerance) survives the torso
layer exactly; the verifier asserts that invariant every run.

Structural checks in `--structure` (all LODs):

* one root, no cycles, parents exist, no segment shorter than 12 mm;
* 52 humanoid slots correct (mapped once, mirrored, parent-before-child);
* 58 deform bones enclosed by their own geometry on all six sides, at least
  0.2 mm clear of the nearest triangle, inside the vertex cloud they drive;
* weights: coverage, sums, influence cap, reach, mirroring;
* bind identity (1e-9 m) and cross-rig FK: the arm chain matches `hand_rig`
  exactly (1.4e-17) and the leg chain matches `boot_rig` exactly (0.0e+00)
  including the foot IK.

## Fixes that came out of this pass

| Symptom | Cause | Fix |
| --- | --- | --- |
| Sleeve torn 2.1x beside the elbow (90 mm edge -> 187 mm) | weight ramp stretched over 55 % of the upper arm | partition of unity on joint bisector planes, 100 mm elbow window |
| Cuff fold pinched 31 mm -> 6 mm at a 45 deg wrist | joint plane running through a stiff cuff band | wrist plane moved 32 mm down the forearm |
| Seat collapsed 0.26x at hip flex 90 | hard pelvis/thigh switch across 25 mm yoke rows | gentler yoke ramp + loops between the yoke rows |
| Coat centre seam torn apart when a leg stepped | `abs(x)` thigh ramp gives the seam to one leg | thigh band centred on each leg, zero at the centre line |
| Shirt collar sheared 2.8x at 60 deg head yaw | a thin collar band taking host weights point by point round the ring | collar bands use the analytic neck ramp (uniform round the ring) |
| Strap stretched 2.1x at a 45 deg wrist | a 14 mm band across a weight gradient | small accessories bound as stiff solids (one weight set per part) |
| Knee "inversion" reports | rigid rotation of a face > 90 deg about an off-normal axis | flip test now compares against the skin-matrix-rotated normal |
| Ankle/toe "bone on the surface" reports | the boot shaft narrows to a 6 mm ring; the nearest *vertex* is a neighbour | placement uses clearance to the nearest *triangle* |

## Known limits

* The rig is offline data until the mesh ships as a skinned asset; the runtime
  prefab and the gameplay controller are deliberately untouched.
* `elbow_130` (left/right) is the only over-range case with a warning, as
  described above.
* `verify_rig.py` checks the deformation of the mesh, not the rendered image;
  the LOD1/LOD2 meshes are checked structurally with the same verifier.
* Thumb/pinky edge cases at extreme finger spreads are covered by
  `Tools/verify_hands.py`, which owns the glove rig.
