#!/usr/bin/env python3
"""Full-body humanoid rig for the Veilbound Wayfarer (Vespershade protagonist).

This module is the single source of truth for the character's **skeleton**,
**skin weights** and **pose vocabulary**. It joins the two pre-existing
local rigs into one hierarchy and adds everything that was missing:

* `Tools/hand_rig.py` owns the arms (shoulder -> elbow -> forearm -> wrist ->
  hand -> 20 finger/thumb bones) and their weights,
* `Tools/boot_rig.py` owns the legs (hip -> knee -> ankle -> ball -> toe), the
  boots and the trouser weights, including the foot IK used by the poses,
* this module adds the **torso chain** (pelvis -> spine x2 -> chest -> neck ->
  head -> head top), the **clavicles**, the garment weight rules for the coat,
  mantle, skirt, trousers, collar and hair, and the unified forward kinematics.

Nothing is re-defined: the arm/leg bone names, heads and axes are read straight
out of `hand_rig`/`boot_rig`, so the existing hand and boot sidecars, their
verifiers (Tools/verify_hands.py, Tools/verify_boots.py) and their part ranges
keep working unchanged.

Bind pose
---------
The mesh is authored in the bind pose (arms hanging at the sides, legs
straight); zero FK rotations reproduce the OBJ exactly, which
Tools/verify_rig.py asserts vertex by vertex.

Skeleton (36 deform bones + fingers, 1 unity of 1 m)
---------------------------------------------------
    Root                       character origin, on the floor plane
    +- Pelvis                  sacrum (hip joints hang 40 mm below)
    |  +- Spine1 -> Spine2 -> Chest
    |  |  +- RClavicle/LClavicle     sternoclavicular joint -> shoulder joint
    |  |  |  +- RShoulder ... LHand  (hand_rig arm + hand + finger chains)
    |  |  +- Neck -> Head -> HeadEnd skull base -> crown
    |  +- RHip ... RToe / LHip ... LToe   (boot_rig leg + foot chains)

Axis convention (every bone carries a `flex`/`abd`/`twist` triple, world
unit vectors in the bind pose):

    torso/neck/head  flex + = bend forward, abd + = bend to the character's
                     left, twist + = turn right
    clavicle         flex + = shoulder forward, abd + = shrug up
    arm              flex + = swing forward, abd + = outboard (thumb side),
                     twist + = roll of the segment
    leg              flex + = hip swings forward / knee folds backwards,
                     abd + = outboard, twist + = toes out
    foot             flex + = dorsiflexion (toes up)

Skinning
--------
Every vertex of the mesh is bound through a chain id (the generator registers
each part with one). Chains resolve to one of the weight functions below,
which are deterministic functions of the bind position - the same contract the
hand and boot rigs already use. Garment pieces are weighted by the body region
they cover, small props inherit the weights of the garment they sit on, and
nothing is left on the Root except the parts that are genuinely rigid to it.

    python3 Tools/body_rig.py            # prints the skeleton and weight map
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hand_rig as hr  # noqa: E402
import boot_rig as br  # noqa: E402
from hand_rig import (vadd, vsub, vmul, dot, cross, norm, lerp3, clamp,  # noqa: E402
                      smoothstep, gauss, mat_mul, mat_translate, mat_rot_axis,
                      mat_apply)

# ===========================================================================
# Torso anchors (metres, world space, character faces +Z, feet on y = 0)
#
# The pelvis sits on the sacrum, ~40 mm above the hip joints the boot rig
# owns; the spine stations follow the waist/belt (1.033), the waistcoat rows
# and the ribcage; the neck joins the skull at the atlas. Every anchor is
# verified to be inside the skinned shell by Tools/verify_rig.py.
# ===========================================================================

PELVIS = (0.000, 0.945, -0.012)      # sacrum, between/above the hip joints
SPINE1 = (0.000, 1.045, -0.010)      # L1, belt line
SPINE2 = (0.000, 1.165, -0.012)      # T9, waistcoat / baldric crossing
CHEST = (0.000, 1.290, -0.014)       # T4, breast / shoulder line
NECK = (0.000, 1.432, -0.016)        # C7 - T1, base of the neck
HEAD = (0.000, 1.508, -0.020)        # atlas (C1), skull base
HEAD_END = (0.000, 1.808, -0.020)    # crown (leaf, no skin weights)
CLAVICLE = (0.030, 1.428, 0.014)     # sternoclavicular joint (per side)

TORSO = ("Pelvis", "Spine1", "Spine2", "Chest", "Neck", "Head")
LEG_PARTS = ("Hip", "Knee", "Ankle", "Ball", "Toe")
SPINE_HEAD = {"Pelvis": PELVIS, "Spine1": SPINE1, "Spine2": SPINE2,
              "Chest": CHEST, "Neck": NECK, "Head": HEAD}

# torso/neck/head axes (see the module docstring)
TORSO_AXES = {"flex": (1.0, 0.0, 0.0), "abd": (0.0, 0.0, 1.0),
              "twist": (0.0, 1.0, 0.0)}


def clavicle_axes(side):
    """Clavicle axes: flex + = forward (protraction), abd + = shrug up."""
    return {"flex": (0.0, -side, 0.0), "abd": (0.0, 0.0, side),
            "twist": (side, 0.0, 0.0)}


# ===========================================================================
# Skeleton
# ===========================================================================

# Which pre-existing bone is re-parented to which new bone.
REPARENT = {"RShoulder": "RClavicle", "LShoulder": "LClavicle",
            "RHip": "Pelvis", "LHip": "Pelvis"}
# Pre-existing chains (kept verbatim; only their root changes parent).
ARM_LEG_CHAINS = ("Shoulder", "Elbow", "Forearm", "Wrist", "Hand", "Thumb",
                  "Index", "Middle", "Ring", "Little", "Hip", "Knee", "Ankle",
                  "Ball", "Toe")


def joint_list():
    """[(name, parent, world_head, axes, group)] for the whole body.

    `group` names the subsystem a bone belongs to: "root", "torso", "arm",
    "hand", "leg", "foot". Bone names, heads and axes of the arm/hand and
    leg/foot chains are taken from hand_rig/boot_rig unchanged.
    """
    joints = [("Root", None, (0.0, 0.0, 0.0), None, "root")]

    # ---- torso -----------------------------------------------------------
    joints.append(("Pelvis", "Root", PELVIS, TORSO_AXES, "torso"))
    joints.append(("Spine1", "Pelvis", SPINE1, TORSO_AXES, "torso"))
    joints.append(("Spine2", "Spine1", SPINE2, TORSO_AXES, "torso"))
    joints.append(("Chest", "Spine2", CHEST, TORSO_AXES, "torso"))
    joints.append(("Neck", "Chest", NECK, TORSO_AXES, "torso"))
    joints.append(("Head", "Neck", HEAD, TORSO_AXES, "torso"))
    joints.append(("HeadEnd", "Head", HEAD_END, TORSO_AXES, "torso"))

    # ---- clavicles -------------------------------------------------------
    for side, pre in ((1, "R"), (-1, "L")):
        head = (CLAVICLE[0] * side, CLAVICLE[1], CLAVICLE[2])
        joints.append((f"{pre}Clavicle", "Chest", head, clavicle_axes(side),
                       "torso"))

    # ---- arms + hands (hand_rig is authoritative) ------------------------
    for (name, parent, head, axes) in hr.joint_list():
        if name == "Root":
            continue
        parent = REPARENT.get(name, parent)
        side = 1 if name[0] == "R" else -1
        group = "hand" if _is_hand_bone(name) else "arm"
        joints.append((name, parent, head, axes, group))

    # ---- legs + feet (boot_rig is authoritative) -------------------------
    for (name, parent, head, axes) in br.joint_list():
        if name == "Root":
            continue
        joints.append((name, REPARENT.get(name, parent), head, axes, "leg"))

    return joints


def _is_hand_bone(name):
    """True for wrist-distal bones (the hand rig's own weight domain)."""
    if name.endswith(("Clavicle",)):
        return False
    stem = name[1:] if name[0] in "RL" else name
    return not stem.startswith(("Shoulder", "Elbow", "Forearm", "Wrist"))


JOINT_3 = None            # (name, parent, head) triples, built on demand
_FAMILY = None


def _joints():
    global JOINT_3
    if JOINT_3 is None:
        JOINT_3 = {j[0]: j for j in joint_list()}
    return JOINT_3


def parents():
    return {j[0]: j[1] for j in joint_list()}


def children_map():
    kids = {}
    for (name, parent, _, _, _) in joint_list():
        kids.setdefault(parent, []).append(name)
    return kids


def world_heads():
    return {j[0]: j[2] for j in joint_list()}


def bone_length(name):
    """Distance from a bone head to its first child head (0 for leaves)."""
    kids = children_map().get(name, [])
    if not kids:
        return 0.0
    heads = world_heads()
    return min(math.dist(heads[name], heads[k]) for k in kids)


# ---- Unity humanoid mapping ----------------------------------------------
# Bone -> Unity `HumanBodyBones` name (the Avatar mapping an FBX/DCC export
# must carry so Unity builds a valid Humanoid Avatar). Duplicate entries on
# the extra roll bones are deliberately absent: RForearm/RWrist/RThumbCMC and
# RToe stay unmapped helpers, which Unity keeps in the hierarchy.
HUMANOID_MAP = [
    ("Pelvis", "Hips"),
    ("Spine1", "Spine"),
    ("Spine2", "Chest"),
    ("Chest", "UpperChest"),
    ("Neck", "Neck"),
    ("Head", "Head"),
]
for _pre, _side in (("R", "Right"), ("L", "Left")):
    HUMANOID_MAP += [
        (f"{_pre}Clavicle", f"{_side}Shoulder"),
        (f"{_pre}Shoulder", f"{_side}UpperArm"),
        (f"{_pre}Elbow", f"{_side}LowerArm"),
        (f"{_pre}Hand", f"{_side}Hand"),
        (f"{_pre}ThumbCMC", f"{_side}ThumbProximal"),
        (f"{_pre}ThumbMCP", f"{_side}ThumbIntermediate"),
        (f"{_pre}ThumbIP", f"{_side}ThumbDistal"),
        (f"{_pre}Hip", f"{_side}UpperLeg"),
        (f"{_pre}Knee", f"{_side}LowerLeg"),
        (f"{_pre}Ankle", f"{_side}Foot"),
        (f"{_pre}Ball", f"{_side}Toes"),
    ]
    for _finger in ("Index", "Middle", "Ring", "Little"):
        HUMANOID_MAP += [
            (f"{_pre}{_finger}MCP", f"{_side}{_finger}Proximal"),
            (f"{_pre}{_finger}PIP", f"{_side}{_finger}Intermediate"),
            (f"{_pre}{_finger}DIP", f"{_side}{_finger}Distal"),
        ]

HUMANOID_REQUIRED = [
    "Hips", "Spine", "Chest", "Neck", "Head",
    "LeftShoulder", "LeftUpperArm", "LeftLowerArm", "LeftHand",
    "RightShoulder", "RightUpperArm", "RightLowerArm", "RightHand",
    "LeftUpperLeg", "LeftLowerLeg", "LeftFoot", "LeftToes",
    "RightUpperLeg", "RightLowerLeg", "RightFoot", "RightToes",
]
HUMANOID_OPTIONAL = ["UpperChest"] + [
    f"{s}{f}{j}" for s in ("Left", "Right")
    for f in ("Thumb", "Index", "Middle", "Ring", "Little")
    for j in ("Proximal", "Intermediate", "Distal")]
# helpers kept in the hierarchy but not mapped to a humanoid slot
HUMANOID_HELPERS = ["RForearm", "RFream", "LForearm", "RWrist", "LWrist",
                    "RThumbCMC", "LThumbCMC", "RToe", "LToe", "HeadEnd"]


def humanoid_bone_map():
    return {bone: human for (bone, human) in HUMANOID_MAP}


# ===========================================================================
# Skin weights
#
# Chain ids used by the generator (see Tools/create_original_protagonist.py):
#   torso     coat bodice, waistcoat, shirt, cravat, collars, mantle, belt,
#             baldric, epaulettes, seams/stitching/buttons/buckles on the
#             body; also the compass and watch chain (they ride the coat)
#   skirt     coat skirt panels, vent pleat, hem piping
#   hip       trouser yoke + seat (they span both hips and the pelvis)
#   legR/legL trousers, trouser side seams  -> boot_rig.leg_weights
#   armR/armL coat sleeves, arm skin, sleeve seams, elbow patch, cuff strap
#   head      face, scalp, neck skin, ears, eyes, eyebrows
#   hair      the Vigil Sweep hair (rigid to the head, per the hair contract)
#   + the hand_rig chains (palm/digitN/webN/cuff/bridge/guard) and the
#     boot_rig chains (foot/shaft/leg), delegated unchanged.
# ===========================================================================

# torso blend stations (bone, y): weight ramps from one to the next
TORSO_BAND = [("Pelvis", 0.945), ("Spine1", 1.045), ("Spine2", 1.165),
              ("Chest", 1.290), ("Neck", 1.432)]
# half width of the smoothstep band centred on each station
TORSO_RAMP = 0.070

ARM_NODES = ("Clavicle", "Shoulder", "Elbow", "Forearm", "Wrist")
HAIR_LOCK = "Head"          # rigid attachment contract (Docs/CHARACTER_HAIR.md)


def _prune(w, top=4):
    """Keep the strongest `top` influences and normalise to 1.0."""
    items = sorted(w.items(), key=lambda kv: -kv[1])
    out = {k: v for k, v in items[:top] if v > 1e-6}
    tot = sum(out.values())
    if tot <= 1e-9:
        return {"Root": 1.0}
    return {k: v / tot for k, v in out.items()}


def _side_tag(side):
    return "R" if side > 0 else "L"


def _boot_local(side, p):
    """World -> boot_rig local frame (the boot rig authors one foot at x=0)."""
    return (p[0] - side * br.FOOT_X, p[1], p[2] - br.FOOT_Z)


def _torso_band_weights(y, low, high):
    """Ramp one scalar across the torso stations `low`..`high` (names)."""
    order = [b for (b, _) in TORSO_BAND]
    ys = dict(TORSO_BAND)
    w = {}
    lo_i, hi_i = order.index(low), order.index(high)
    for i in range(lo_i, hi_i):
        b0, b1 = order[i], order[i + 1]
        if y < ys[b0] or y > ys[b1]:
            continue
        u = smoothstep(0.5 - TORSO_RAMP / max(1e-6, ys[b1] - ys[b0]),
                       0.5 + TORSO_RAMP / max(1e-6, ys[b1] - ys[b0]),
                       (y - ys[b0]) / (ys[b1] - ys[b0]))
        w[b0] = w.get(b0, 0.0) + (1.0 - u)
        w[b1] = w.get(b1, 0.0) + u
        return w
    return {order[hi_i]: 1.0} if y > ys[order[hi_i]] else {order[lo_i]: 1.0}


def torso_weights(side, p):
    """Coat bodice, waistcoat, shirt, mantle, belt, baldric: vertical spine ramp.

    Two corrections on top of the ramp, both driven by the *vertex* position
    (garment panels span both sides, so the chain cannot decide a side):

    * the shoulder region of the coat (outboard, above the chest) picks up
      clavicle influence, so a raised arm drags the coat shoulder instead of
      tearing the armhole open,
    * nothing in the torso chain ever reaches the neck: the coat collar is
      bound to the chest by name (`collar` chain) and the shirt collar/cravat
      to the neck (`neckwear` chain). A garment that straddled that boundary
      would tear, because the neck bone has a long lever arm (verified).
    """
    x, y, z = p
    w = _torso_band_weights(y, "Pelvis", "Chest")
    pre = _side_tag(1 if x >= 0 else -1)
    k_sh = smoothstep(0.150, 0.270, abs(x)) * smoothstep(1.235, 1.430, y)
    if k_sh > 1e-4:
        w = {k: v * (1.0 - k_sh) for k, v in w.items()}
        w[f"{pre}Clavicle"] = w.get(f"{pre}Clavicle", 0.0) + k_sh
    return _prune(w)


def collar_weights(side, p):
    """Standing coat collar, facing, piping, throat tab: rigid to the chest.

    A stiff standing collar is carried by the shoulders; letting it follow the
    neck swings it 40+ mm on every head turn and tears it off the coat.
    """
    return {"Chest": 1.0}


def neckwear_weights(side, p):
    """Shirt collar band, cravat and its tails.

    Deliberately the *same* rule as the neck skin (head_weights): collar and
    neck have to move together, or a turned head pushes one through the other
    (0.9 mm of interpenetration at a 60 deg yaw before this was shared).
    """
    return head_weights(side, p)


def coat_skirt_weights(side, p):
    """Coat skirt panels: the waist follows the pelvis, the fronts pick up
    thigh influence so a stepping leg does not cut through the cloth.

    The thigh band is centred on each thigh and reaches zero at the centre
    line and beyond the hip width - a vertex there is equidistant from both
    legs, and giving it one side's thigh (as a plain |x| ramp does) tears the
    panel apart at the spine seam.
    """
    x, y, z = p
    if y > 0.955:
        return _prune(_torso_band_weights(y, "Pelvis", "Chest"))
    pre = _side_tag(1 if x >= 0 else -1)
    band = smoothstep(0.030, 0.095, abs(x)) * (1.0 - smoothstep(0.185, 0.290, abs(x)))
    thigh = 0.45 * smoothstep(0.940, 0.560, y) * band
    return _prune({f"{pre}Hip": thigh, "Pelvis": 1.0 - thigh})


def trouser_hip_weights(side, p):
    """Trouser yoke + seat: pelvis in the middle, thighs at the sides.

    Gentle gradients on purpose: the yoke rows are ~25 mm apart and a hard
    pelvis/thigh switch across them collapses the seat when the hip flexes.
    """
    x, y, z = p
    k_side = smoothstep(0.030, 0.170, abs(x)) * smoothstep(1.040, 0.820, y)
    pre = _side_tag(1 if x >= 0 else -1)
    thigh = 0.50 * k_side
    return _prune({f"{pre}Hip": thigh, "Pelvis": 1.0 - thigh})


# Width of the weight hand-over window either side of an arm joint (m):
# wide enough to keep volume, narrow enough to keep the off-axis lever arm
# short. Index i = the joint at node i (Shoulder, Elbow, Forearm, Wrist).
ARM_BANDS = (0.000, 0.100, 0.046, 0.046, 0.046)
# The wrist hand-over plane sits BELOW the wrist joint by this much: the coat
# cuff (fold, strap, buckle, buttons) is a stiff band wrapped round the wrist
# and a joint plane running through it pinches the fold (31 mm edges collapsed
# to 6 mm at a 45 deg wrist). The wrist bone drives the hand, the glove and
# the forearm skin, which all start below this plane.
ARM_WRIST_PLANE_SHIFT = 0.032


def arm_weights(side, p):
    """Coat sleeve + arm skin: blend along the arm using hand_rig's anchors.

    `hand_rig` places the four arm bones at the shoulder, elbow, mid-forearm
    and wrist; the parameter is the projected arc-length along that polyline,
    so the sleeve is bound the same way the glove is.

    The blend is a *partition of unity built on the joint planes*: every bone
    owns the span between its two joints and hands over to its neighbour
    across a fixed window centred on the joint (ARM_BANDS).

    The weight parameter of a joint is the signed distance from its *bisector
    plane*, not an arc length along the bone polyline: a polyline parameter
    jumps across the joint's medial surface whenever the chain kinks, and a
    jump in the parameter is a jump in the weights - that tore the sleeve
    beside the elbow (2x) and the cuff beside the wrist (0.1x).
    """
    pre = _side_tag(side)
    mir = (lambda v: (v[0] * side, v[1], v[2]))
    sh, el, fa, wr = (mir(hr.SHOULDER_LOCAL), mir(hr.ELBOW_LOCAL),
                      mir(hr.FOREARM_LOCAL), mir(hr.WRIST_LOCAL))
    head = hr.to_world((0.0, 0.048, 0.0), side)
    nodes = ((f"{pre}Shoulder", sh), (f"{pre}Elbow", el),
             (f"{pre}Forearm", fa), (f"{pre}Wrist", wr), (f"{pre}Hand", head))
    pts = [n[1] for n in nodes]
    dirs = [norm(vsub(pts[i + 1], pts[i])) for i in range(len(pts) - 1)]

    handover = [1.0]
    for i in range(1, len(nodes)):
        axis = dirs[i - 1] if i == len(nodes) - 1 else \
            norm(vadd(dirs[i - 1], dirs[i]))
        origin = pts[i] if i != 3 else vadd(pts[i], vmul(dirs[2], ARM_WRIST_PLANE_SHIFT))
        b = ARM_BANDS[i]
        handover.append(smoothstep(-b, b, dot(vsub(p, origin), axis)))
    w = {}
    for i, (name, _p) in enumerate(nodes):
        up = handover[i]
        down = handover[i + 1] if i + 1 < len(nodes) else 0.0
        share = up - down
        if share > 1e-4:
            w[name] = share
    total = sum(w.values())
    if total > 0.0:
        w = {k: v / total for k, v in w.items()}

    # sleeve head / armpit: the top of the sleeve is handed to the clavicle
    # and chest so the shoulder keeps its volume when the arm comes up. The
    # blend is a function of the *distance along the arm* only: a radial term
    # would give the two sides of the 9 mm shell thickness different weights
    # and tear the sleeve head open (verified).
    k_sh = 0.45 * smoothstep(0.30, 0.03, dot(vsub(p, pts[0]), dirs[0]))
    if k_sh > 1e-4:
        w = {k: v * (1.0 - k_sh) for k, v in w.items()}
        w[f"{pre}Clavicle"] = w.get(f"{pre}Clavicle", 0.0) + k_sh * 0.62
        w["Chest"] = w.get("Chest", 0.0) + k_sh * 0.38
    return _prune(w)


def head_weights(side, p):
    """Face / scalp / neck skin / ears / eyes: neck ramp into the skull."""
    x, y, z = p
    k_head = smoothstep(1.452, 1.548, y)
    k_chest = 1.0 - smoothstep(1.400, 1.462, y)
    if k_head >= 1.0:
        return {"Head": 1.0}
    w = {"Head": k_head, "Neck": (1.0 - k_head) * (1.0 - k_chest),
         "Chest": (1.0 - k_head) * k_chest}
    return _prune(w)


def hair_weights(side, p):
    """Vigil Sweep hair: rigid to the head (the sidecar's stability contract)."""
    return {HAIR_LOCK: 1.0}


def rigid_weights(side, p):
    return {"Root": 1.0}


BODY_CHAIN_WEIGHT_FN = {
    "root": rigid_weights,
    "torso": torso_weights,
    "collar": collar_weights,
    "neckwear": neckwear_weights,
    "skirt": coat_skirt_weights,
    "hip": trouser_hip_weights,
    "armR": lambda side, p: arm_weights(1, p),
    "armL": lambda side, p: arm_weights(-1, p),
    "head": head_weights,
    "hair": hair_weights,
    "legR": lambda side, p: br.leg_weights(1, _boot_local(1, p)),
    "legL": lambda side, p: br.leg_weights(-1, _boot_local(-1, p)),
}

# chains owned by the other two rigs (delegated verbatim)
HAND_CHAINS = ("palm", "thumb", "guard", "cuff", "bridge", "webT")
BOOT_CHAINS = ("foot", "shaft", "leg")


# ---- part classification --------------------------------------------------
# Which chain a generated mesh part binds through. Hand/Glove/** and Boots/**
# parts are *not* listed here: the generator resolves them from hand_rig and
# boot_rig's own part tables, which stay authoritative for those regions.
_BODY_PART_RULES = (
    # (name prefix, chain, side required?)
    ("UpperClothing/CoatSleeve_", "arm", True),
    ("UpperClothing/SleeveSeam_", "arm", True),
    ("UpperClothing/SleeveSeamStitch_", "arm", True),
    ("UpperClothing/CuffFold_", "arm", True),
    ("UpperClothing/CuffButton_", "arm", True),
    ("UpperClothing/ShirtCuff_", "arm", True),
    ("UpperClothing/ShirtCuffButton_", "arm", True),
    ("UpperClothing/ElbowPatch_", "arm", True),
    ("Accessories/ElbowPatchStitch_", "arm", True),
    ("Accessories/CuffStrap_", "arm", True),
    ("Accessories/CuffBuckle_", "arm", True),
    ("Body/Forearm_", "arm", True),
    ("LowerBody/Leg_", "leg", True),
    ("LowerBody/SideSeam_", "leg", True),
    ("LowerBody/SideSeamStitch_", "leg", True),
    ("LowerBody/TrouserYoke", "hip", False),
    ("LowerBody/Seat", "hip", False),
    ("LowerClothing/CoatSkirt_", "skirt", False),
    ("LowerClothing/VentPleat", "skirt", False),
    ("Body/Torso", "torso", False),
    ("UpperClothing/CoatCollar", "collar", False),
    ("UpperClothing/CollarFacing", "collar", False),
    ("Accessories/Collar", "collar", False),
    ("UpperClothing/ShirtCollar", "neckwear", False),
    ("Accessories/Cravat", "neckwear", False),
    ("Head/", "head", False),
    ("Accessories/HairTie", "hair", False),
)
_TORSO_PREFIXES = ("Accessories/", "UpperClothing/")
_HELM = ("L", "R")


def _side_token(name):
    """The L/R token of a part name ('.../CoatSleeve_L' -> 'L'), else None."""
    for i, ch in enumerate(name):
        if ch not in _HELM:
            continue
        before = name[i - 1] if i else "/"
        after = name[i + 1] if i + 1 < len(name) else "_"
        if before in "/_" and after in "/_":
            return ch
    return None


def chain_for(name, mat):
    """(side, chain) for a generated part that is not owned by a limb rig.

    `side` is +1/-1 for parts that belong to one arm or leg, None otherwise.
    Unknown names raise: a new part must be classified explicitly rather than
    silently falling back to the root.
    """
    if mat == "Hair" and not name.startswith("Head/"):
        return None, "hair"
    for prefix, chain, want_side in _BODY_PART_RULES:
        if name.startswith(prefix):
            if chain in ("arm", "leg"):
                tok = _side_token(name)
                if tok is None:
                    if not want_side:
                        return None, chain
                    raise KeyError(f"'{name}' is a {chain} part without an L/R token")
                return (1 if tok == "R" else -1), f"{chain}{tok}"
            return None, chain
    if name.startswith(_TORSO_PREFIXES) or mat in ("Hair",):
        return None, "torso"
    raise KeyError(f"unclassified rig part '{name}' ({mat})")


# A part smaller than this is a *detail* (stitch dash, button, buckle, rivet,
# ring, patch, strap, ear, eye): it is bound at its centroid instead of being
# skinned vertex by vertex. Details are what tears first in a hand-authored
# rig - a 14 mm strap crossing a weight gradient stretched 2.1x at a 45 deg
# wrist, an elbow patch folded through itself at 100 deg - and a stiff solid
# that shares one weight set cannot do either.
DETAIL_MAX_DIAGONAL = 0.200   # bounding-box diagonal



def _bbox_diagonal(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return math.dist((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def _chain_axis(chain, side):
    """Unit vector the parts of a chain run along (their limb / body axis)."""
    j = {n: h for (n, _p, h, _a, _g) in joint_list()}
    side = 1 if side is None else side
    pre = "R" if side > 0 else "L"
    if chain == "armR":
        pre = "R"
    elif chain == "armL":
        pre = "L"
    elif chain == "legR":
        pre = "R"
    elif chain == "legL":
        pre = "L"
    if chain in ("armR", "armL"):
        a, b = j[f"{pre}Shoulder"], j[f"{pre}Wrist"]
    elif chain in ("legR", "legL"):
        a, b = j[f"{pre}Hip"], j[f"{pre}Ankle"]
    elif chain == "shaft":
        a, b = j[f"{pre}Knee"], j[f"{pre}Ankle"]
    elif chain == "foot":
        a, b = j[f"{pre}Ankle"], j[f"{pre}Toe"]
    elif chain in ("guard", "cuff", "palm") or chain.startswith(
            ("digit", "thumb", "web", "bridge")):
        a, b = j[f"{pre}Wrist"], j[f"{pre}Hand"]
    else:
        return (0.0, 1.0, 0.0)
    d = vsub(b, a)
    l = math.sqrt(dot(d, d))
    return vmul(d, 1.0 / l) if l > 1e-9 else (0.0, 1.0, 0.0)


def _axis_span(points, axis):
    us = [dot(p, axis) for p in points]
    return max(us) - min(us)


def part_weights(side, chain, point, rigid=False, centroid=None):
    """Weights for one vertex; a rigid detail uses its part centroid instead."""
    if rigid and centroid is not None:
        return weights_for(side, chain, tuple(centroid))
    return weights_for(side, chain, point)


def classify_parts(mesh_parts, rig_parts, vertex_of=None):
    """Resolve every generated part to (side, chain).

    `mesh_parts` are the raw add_mesh records ([{name, mat, ranges}]), so
    *everything* the generator emits is bound to a chain - nothing falls back
    to the root. A part that lies inside a hand_rig/boot_rig part range keeps
    that rig's side and chain (those rigs stay authoritative for the hands and
    the boots); every other part is classified by name. Returns
    [(name, mat, start, end, side, chain)] with local per-material indices.
    """
    limb = {}
    for p in rig_parts:
        limb.setdefault(p["mat"], []).append(p)
    out = []
    for part in mesh_parts:
        for (start, end) in part["ranges"]:
            owner = None
            for p in limb.get(part["mat"], ()):
                if p["start"] <= start and end <= p["end"]:
                    owner = p
                    break
            if owner is not None:
                side = 1 if owner["side"] == "R" else -1
                out.append((part["name"], part["mat"], start, end, side,
                            owner["chain"], None, None))
                continue
            side, chain = chain_for(part["name"], part["mat"])
            bind, centroid = None, None
            if vertex_of is not None and chain not in ("hair",) \
                    and chain not in HAND_CHAINS and chain not in BOOT_CHAINS:
                pts = [vertex_of(part["mat"], i) for i in range(start, end)]
                if len(pts) >= 3:
                    centroid = (sum(p[0] for p in pts) / len(pts),
                                sum(p[1] for p in pts) / len(pts),
                                sum(p[2] for p in pts) / len(pts))
                    axis = _chain_axis(chain, side)
                    if _bbox_diagonal(pts) <= DETAIL_MAX_DIAGONAL:
                        bind = "stiff"
            out.append((part["name"], part["mat"], start, end, side, chain,
                        bind, centroid))
    return out


def weights_for(side, chain, p_world):
    """Dispatch a registered part chain id to its weight function."""
    if chain in BODY_CHAIN_WEIGHT_FN:
        return BODY_CHAIN_WEIGHT_FN[chain](side, p_world)
    if chain in BOOT_CHAINS:
        return br.weights_for(side, chain, p_world)
    if chain in HAND_CHAINS or chain.startswith(("digit", "web")):
        return hr.weights_for(side, chain, p_world)
    raise KeyError(f"unknown rig chain '{chain}'")


# ===========================================================================
# Pose vocabulary
#
# The existing animation states are kept: the arm/hand poses come from
# hand_rig.POSES, the leg/foot poses (with their foot IK) from boot_rig.POSES,
# and this table adds the torso/head layer that was missing. `bind` is the
# authored pose (identity).
# ===========================================================================

POSES = {
    "bind":   {"hand": "stand", "boot": "idle", "body": {}},
    "idle":   {"hand": "stand", "boot": "idle", "body": {
        "Spine1": {"flex": 1.5}, "Spine2": {"flex": -1.0},
        "Chest": {"flex": 0.5}, "Neck": {"flex": 2.0}, "Head": {"flex": -1.5}}},
    "walk":   {"hand": "walk", "boot": "walk", "body": {
        "Spine1": {"flex": 2.5, "twist": 5.0},
        "Spine2": {"flex": -1.5, "twist": 3.0}, "Chest": {"twist": 4.0},
        "Neck": {"flex": 2.0, "twist": -3.0}, "Head": {"twist": -3.0}}},
    "run":    {"hand": "walk", "boot": "run", "body": {
        "Spine1": {"flex": 8.0, "twist": 8.0},
        "Spine2": {"flex": 5.0, "twist": 5.0}, "Chest": {"flex": 2.0, "twist": 6.0},
        "Neck": {"flex": -6.0, "twist": -4.0}, "Head": {"flex": -4.0}}},
    "attack": {"hand": "attack", "boot": "idle", "body": {
        "Spine1": {"flex": 4.0, "twist": 12.0},
        "Spine2": {"flex": 4.0, "abd": 3.0, "twist": 9.0},
        "Chest": {"flex": 2.0, "twist": 11.0}, "Neck": {"flex": -4.0, "twist": -6.0},
        "Head": {"twist": -5.0}}},
    "dodge":  {"hand": "dodge", "boot": "dodge", "body": {
        "Spine1": {"flex": 16.0, "twist": 6.0},
        "Spine2": {"flex": 10.0, "twist": 5.0}, "Chest": {"flex": 6.0, "twist": 7.0},
        "Neck": {"flex": -8.0, "twist": -5.0}, "Head": {"flex": -6.0}}},
}
# NOTE: the locomotion poses deliberately leave the *pelvis* unposed. The legs
# hang off the pelvis, so rotating it would move the planted boots away from
# the contact the boot rig solves and Tools/verify_boots.py signs off; hip lead
# is expressed one level up (Spine1 twist/counter-rotation) instead. Pelvis
# motion itself is exercised by the dedicated hip/pelvis sweeps in
# Tools/verify_rig.py.
POSES_ORDER = ("bind", "idle", "walk", "run", "attack", "dodge")


def _arm_family(name):
    """Pose family key for an arm/hand bone (delegates to hand_rig)."""
    return hr._family_map(name)


def _torso_family(name):
    stem = name[1:] if name[0] in "RL" and name[0].isupper() else name
    if stem == "Clavicle":
        return "Clavicle"
    return name if name in TORSO else None


def pose_rotations(pose_name, extra=None):
    """{bone: {flex, abd, twist}} resolved for every bone of the rig."""
    pose = POSES[pose_name]
    hand_spec = hr.POSES[pose["hand"]]
    out = {}
    for (name, _, _, _, group) in joint_list():
        p = {}
        if group == "torso":
            fam = _torso_family(name)
            if fam:
                p = dict(pose["body"].get(fam, {}))
        elif group in ("arm", "hand"):
            fam = _arm_family(name)
            if fam:
                p = dict(hand_spec.get(name[0], {}).get(fam, {}))
        if extra and name in extra:
            p.update(extra[name])
        out[name] = p
    return out


# ===========================================================================
# Forward kinematics + linear blend skinning
# ===========================================================================

def _identity():
    return ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))


def _rot_from_axes(axes, p):
    rot = _identity()
    for key in ("flex", "abd", "twist"):
        ang = p.get(key, 0.0)
        if abs(ang) > 1e-9:
            rot = mat_mul(rot, mat_rot_axis(axes[key], ang))
    return rot


def pose_matrices(pose_name, root_shift=(0.0, 0.0, 0.0), extra=None,
                  use_ik=True):
    """{bone: world 4x4} for a named pose.

    Legs run boot_rig's foot IK (a planted sole stays flat and grounded), so
    the ankle/ball angles are solved against the posed knee/ankle matrices
    exactly as Tools/verify_boots.py does. Pass use_ik=False for pure FK (the
    joint sweeps in Tools/verify_rig.py drive single joints with it).
    """
    joints = {j[0]: j for j in joint_list()}
    order = sorted(joints, key=lambda n: _depth(n, joints))
    angles = pose_rotations(pose_name, extra)
    boot_spec = br.POSES[POSES[pose_name]["boot"]]
    posed = {"Root": mat_translate(root_shift)}

    for name in order:
        if name == "Root":
            continue
        parent = joints[name][1]
        axes = joints[name][3]
        p = dict(angles.get(name, {}))
        pre, part = name[0], name[1:]
        side_spec = {}
        if name[1:] in LEG_PARTS and name[0] in ("R", "L"):
            side_spec = boot_spec.get(pre, {})
            p.update(side_spec.get(part, {}))
        if use_ik and part == "Ankle" and "sole_tilt" in side_spec:
            target = br._rot3(mat_rot_axis((1.0, 0.0, 0.0), -side_spec["sole_tilt"]))
            f, a, t = br._solve_ankle(posed[f"{pre}Knee"], target, axes,
                                     (p.get("flex", 0.0), p.get("abd", 0.0),
                                      p.get("twist", 0.0)))
            p.update({"flex": f, "abd": a, "twist": t})
        elif use_ik and part == "Ball" and "forefoot_tilt" in side_spec:
            target = br._rot3(mat_rot_axis((1.0, 0.0, 0.0), -side_spec["forefoot_tilt"]))
            p["flex"] = br._solve_ball(posed[f"{pre}Ankle"], axes, target)
        m_local = mat_mul(mat_translate(vsub(joints[name][2], joints[parent][2])),
                          _rot_from_axes(axes, p))
        posed[name] = mat_mul(posed[parent], m_local)
    return posed


def _depth(name, joints):
    d = 0
    while joints[name][1] is not None:
        name = joints[name][1]
        d += 1
    return d


def skin_vertex(p_world, weights, posed, joints):
    """Linear blend skin one world vertex (same contract as hand/boot rigs)."""
    acc = [0.0, 0.0, 0.0]
    for name, w in weights.items():
        j = joints[name]
        rigid = mat_mul(posed[name], mat_translate(vmul(j[2], -1.0)))
        q = mat_apply(rigid, p_world)
        acc[0] += w * q[0]
        acc[1] += w * q[1]
        acc[2] += w * q[2]
    return (acc[0], acc[1], acc[2])


def ground_shift(pose_name, planted_points, chains):
    """The dy that puts the lowest planted boot vertex on the floor."""
    joints = {j[0]: j for j in joint_list()}
    posed = pose_matrices(pose_name)
    lo = 1e9
    for p, side, chain in planted_points:
        q = skin_vertex(p, weights_for(side, chain, p), posed, joints)
        lo = min(lo, q[1])
    return -lo


def metrics():
    """Bone lengths and joint angles of the bind pose (verification input)."""
    heads = world_heads()
    out = {}
    for (name, _, _, _, _) in joint_list():
        out[name] = {"length": bone_length(name)}
    arms = {}
    for pre in ("R", "L"):
        v1 = vsub(heads[f"{pre}Elbow"], heads[f"{pre}Shoulder"])
        v2 = vsub(heads[f"{pre}Wrist"], heads[f"{pre}Elbow"])
        arms[f"{pre}_elbow_angle"] = math.degrees(
            math.acos(clamp(dot(norm(v1), norm(v2)), -1.0, 1.0)))
        down = norm(vsub(heads[f"{pre}Wrist"], heads[f"{pre}Shoulder"]))
        arms[f"{pre}_arm_from_vertical"] = math.degrees(
            math.acos(clamp(-down[1], -1.0, 1.0)))
        thigh = norm(vsub(heads[f"{pre}Knee"], heads[f"{pre}Hip"]))
        arms[f"{pre}_thigh_from_vertical"] = math.degrees(
            math.acos(clamp(-thigh[1], -1.0, 1.0)))
    out["bind_angles"] = arms
    return out


def _print_summary():
    heads = world_heads()
    print(f"{'bone':<14}{'parent':<14}{'head (m)':<28}{'len':>6}  humanoid")
    hmap = humanoid_bone_map()
    for (name, parent, head, _, group) in joint_list():
        print(f"{name:<14}{(parent or '-'):<14}"
              f"({head[0]:+.3f}, {head[1]:.3f}, {head[2]:+.3f})     "
              f"{bone_length(name):5.3f}  {hmap.get(name, '-')}")
    print(f"\n{len(joint_list())} bones, {len(HUMANOID_MAP)} humanoid slots mapped")
    m = metrics()["bind_angles"]
    for k in sorted(m):
        print(f"  {k:<26}{m[k]:6.1f} deg")


if __name__ == "__main__":
    _print_summary()
