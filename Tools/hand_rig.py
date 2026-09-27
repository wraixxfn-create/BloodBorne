#!/usr/bin/env python3
"""Hand anatomy, rig and posing for the Veilbound Wayfarer (Vespershade).

Single source of truth shared by:
- Tools/create_original_protagonist.py (builds the hand + glove meshes from this
  anatomy and tags every hand part with a rig chain id),
- Tools/verify_hands.py (recomputes weights, poses the rig, renders and checks
  the hands while standing / walking / attacking / dodging).

Everything here is deterministic, dependency-free (math only) and expressed in
metres. The hand is authored ONCE in a canonical local space and placed per
side, so left and right are exact mirrors:

  local axes (right hand at the wrist joint):
    r = radial    (+ towards the thumb side)
    d = distal    (+ from the wrist crease towards the fingertips)
    n = dorsal    (+ out of the back of the hand, - into the palm)

Anatomical targets for a ~1.80 m figure (male hand ~18.5 cm long):
  palm length (wrist crease -> middle MCP)      ~97 mm
  hand length (wrist crease -> middle fingertip) ~185 mm
  knuckle row half width                        ~41 mm, little MCP ~17 mm proximal
  fingers: proximal > middle > distal phalanx, middle finger longest,
  index/ring near-equal, little shortest - each finger 3 phalanges + 3 creases
  thumb: 2 phalanges + saddle CMC inside the thenar, abducted ~40 deg forward
  knuckles: MCP bumps on the dorsal side, PIP/DIP bumps, palmar crease dips
  palm: transverse arch, thenar + hypothenar bulges, metacarpal valleys.

Bind pose = relaxed arms-at-side hang: fingers gently curled, thumb forward.
Poses add anatomical rotations (flex = palmar curl, abd = spread, twist).
"""
import math

# ---------------------------------------------------------------------------
# Small vector / matrix helpers (pure python)
# ---------------------------------------------------------------------------

def vadd(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vmul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    l = math.sqrt(dot(a, a))
    return vmul(a, 1.0/l) if l > 1e-12 else (0.0, 1.0, 0.0)
def lerp3(a, b, t): return tuple(a[i]*(1.0-t)+b[i]*t for i in range(3))
def clamp(x, lo, hi): return max(lo, min(hi, x))
def smoothstep(e0, e1, x):
    t = clamp((x-e0)/(e1-e0), 0.0, 1.0)
    return t*t*(3.0-2.0*t)
def gauss(x, mu, sig): return math.exp(-((x-mu)/sig)**2)

def rot_about(p, axis, deg):
    """Rotate point p (about the origin) around unit axis by deg degrees."""
    ax = norm(axis)
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)
    return vadd(vmul(p, ca), vadd(vmul(cross(ax, p), sa), vmul(ax, dot(ax, p)*(1.0-ca))))

def mat_mul(a, b):
    return tuple(tuple(sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)) for i in range(4))

def mat_translate(t):
    return ((1,0,0,t[0]),(0,1,0,t[1]),(0,0,1,t[2]),(0,0,0,1))

def mat_rot_axis(axis, deg):
    ax = norm(axis); a = math.radians(deg); ca, sa = math.cos(a), math.sin(a)
    x, y, z = ax
    return ((ca+x*x*(1-ca),   x*y*(1-ca)-z*sa, x*z*(1-ca)+y*sa, 0),
            (y*x*(1-ca)+z*sa, ca+y*y*(1-ca),   y*z*(1-ca)-x*sa, 0),
            (z*x*(1-ca)-y*sa, z*y*(1-ca)+x*sa, ca+z*z*(1-ca),   0),
            (0, 0, 0, 1))

def mat_apply(m, p):
    return (m[0][0]*p[0]+m[0][1]*p[1]+m[0][2]*p[2]+m[0][3],
            m[1][0]*p[0]+m[1][1]*p[1]+m[1][2]*p[2]+m[1][3],
            m[2][0]*p[0]+m[2][1]*p[1]+m[2][2]*p[2]+m[2][3])

# ---------------------------------------------------------------------------
# Canonical local anatomy (right hand, wrist joint at the origin)
# ---------------------------------------------------------------------------

PALM_LEN = 0.097          # wrist crease -> middle-finger MCP
PALM_HALF_R = 0.0285      # palm half width at the wrist (r axis)
PALM_HALF_N = 0.0185      # palm half thickness at the wrist (n axis)
KNUCKLE_HALF_R = 0.0410   # palm half width at the knuckle row (r axis)

# Finger table: mcp (r, d), phalanx lengths (prox, mid, dist incl. pulp),
# fan = proximal direction splay (deg, + = towards the little finger),
# curl = bind-pose flexion (MCP, PIP, DIP degrees), half radii (across r, along n)
DIGITS = [
    {"key": "Index",  "mcp": ( 0.0315, 0.0910), "segs": (0.038, 0.022, 0.020),
     "fan": -4.0, "curl": ( 8.0,  6.0, 3.0), "radius": (0.0092, 0.0084), "mcp_n": 0.0065},
    {"key": "Middle", "mcp": ( 0.0105, 0.0970), "segs": (0.041, 0.025, 0.021),
     "fan":  0.0, "curl": (10.0,  7.0, 4.0), "radius": (0.0096, 0.0088), "mcp_n": 0.0065},
    {"key": "Ring",   "mcp": (-0.0095, 0.0930), "segs": (0.039, 0.024, 0.020),
     "fan":  4.0, "curl": (11.0,  8.0, 4.0), "radius": (0.0090, 0.0082), "mcp_n": 0.0065},
    {"key": "Little", "mcp": (-0.0285, 0.0800), "segs": (0.030, 0.018, 0.017),
     "fan":  8.0, "curl": (13.0, 11.0, 6.0), "radius": (0.0078, 0.0072), "mcp_n": 0.0060},
]

# Thumb chain (local): saddle CMC in the carpus, MCP at the webbing, IP, tip.
THUMB = {
    "cmc": (0.026, 0.018, -0.004),
    "mcp": (0.052, 0.044, -0.010),
    "ip":  (0.079, 0.055, -0.008),
    "tip": (0.096, 0.064, -0.002),
    "radius": (0.0098, 0.0089),   # at the MCP
}

# Knuckle bump heights (dorsal, skin layer) at MCP / PIP / DIP
KNUCKLE_BUMP = (0.0016, 0.0013, 0.0008)
CREASE_DIP   = (0.0012, 0.0010, 0.0006)   # palmar crease recess at the joints

def _finger_chain(dig):
    """Local chain [MCP, PIP, DIP, TIP] with bind-pose fan + curl applied."""
    r0, d0 = dig["mcp"]
    mcp = (r0, d0, dig["mcp_n"])
    # proximal direction: +d fanned around the n axis (positive fan -> -r)
    prox = rot_about((0.0, 1.0, 0.0), (0.0, 0.0, 1.0), dig["fan"])
    m1, m2, m3 = dig["curl"]
    p1 = rot_about(prox, (1.0, 0.0, 0.0), -m1)          # palmar flexion = -n
    p2 = rot_about(p1,   (1.0, 0.0, 0.0), -m2)
    p3 = rot_about(p2,   (1.0, 0.0, 0.0), -m3)
    l1, l2, l3 = dig["segs"]
    pip = vadd(mcp, vmul(p1, l1))
    dip = vadd(pip, vmul(p2, l2))
    tip = vadd(dip, vmul(p3, l3))
    return [mcp, pip, dip, tip], (p1, p2, p3), prox

def _thumb_chain():
    return [THUMB["cmc"], THUMB["mcp"], THUMB["ip"], THUMB["tip"]]

def local_anatomy():
    """Local-space anatomy: palm profile params + digit chains (cached)."""
    digits = []
    for dig in DIGITS:
        chain, dirs, prox = _finger_chain(dig)
        digits.append(dict(dig, chain=chain, dirs=dirs, prox=prox))
    return {"digits": digits, "thumb": _thumb_chain()}

# ---------------------------------------------------------------------------
# World placement per side
# ---------------------------------------------------------------------------

ELBOW_LOCAL = (0.352, 1.185, 0.020)      # matches the coat sleeve elbow station
WRIST_LOCAL = (0.386, 0.992, 0.046)      # radiocarpal joint, inside the cuff stack
SHOULDER_LOCAL = (0.201, 1.462, -0.008)  # sleeve head station
FOREARM_LOCAL = (0.380, 1.090, 0.034)
PALM_FLEX_DEG = 6.0                      # relaxed wrist flexion baked into the bind pose

def _right_frame():
    """World frame of the RIGHT hand: wrist centre + orthonormal (R, D, N)."""
    elbow = ELBOW_LOCAL; wrist = WRIST_LOCAL
    d_arm = norm(vsub(wrist, elbow))
    n = norm((0.92, 0.05, 0.40))                 # dorsal: outward + forward
    d = norm(rot_about(d_arm, norm(cross(d_arm, n)), -PALM_FLEX_DEG))
    # re-orthogonalise n against d, then build r to complete the frame
    n = norm(vsub(n, vmul(d, dot(d, n))))
    r = norm(cross(d, n))                        # radial: forward + medial
    return {"wrist": wrist, "R": r, "D": d, "N": n}

def _mirror(v): return (-v[0], v[1], v[2])

_FRAME_CACHE = {}

def frame(side):
    """Hand frame for side (+1 right, -1 left). Left = exact mirror of right."""
    if "R" not in _FRAME_CACHE:
        _FRAME_CACHE["R"] = _right_frame()
    f = dict(_FRAME_CACHE["R"])
    if side < 0:
        f["wrist"] = _mirror(f["wrist"])
        f["R"] = _mirror(f["R"]); f["D"] = _mirror(f["D"]); f["N"] = _mirror(f["N"])
    return f

def to_world(p_local, side):
    """local (r, d, n) -> world position."""
    f = frame(side)
    return vadd(f["wrist"], vadd(vmul(f["R"], p_local[0]),
           vadd(vmul(f["D"], p_local[1]), vmul(f["N"], p_local[2]))))

def to_local(p_world, side):
    """world position -> local (r, d, n)."""
    f = frame(side)
    rel = vsub(p_world, f["wrist"])
    return (dot(rel, f["R"]), dot(rel, f["D"]), dot(rel, f["N"]))

# ---------------------------------------------------------------------------
# Rig: joint list, axes, skin weights, poses, forward kinematics
# ---------------------------------------------------------------------------

def joint_list():
    """[(name, parent, world_head, axes)] for Root + both arms/hands.

    Axes are bind-pose world unit vectors; positive rotation about
    'flex' curls palmarly (or swings the arm forward for shoulder/elbow),
    'abd' moves the distal part towards the local radial side,
    'twist' rolls around the segment direction.
    """
    joints = [("Root", None, (0.0, 0.0, 0.0), None)]
    for side, pre in ((1, "R"), (-1, "L")):
        f = frame(side)
        C, R, D, N = f["wrist"], f["R"], f["D"], f["N"]
        flex = vmul(R, -side)               # + = palmar curl
        abd = vmul(N, -side)                # + = towards radial (thumb side)
        sh = tuple(v*side if i == 0 else v for i, v in enumerate(SHOULDER_LOCAL))
        el = tuple(v*side if i == 0 else v for i, v in enumerate(ELBOW_LOCAL))
        fa = tuple(v*side if i == 0 else v for i, v in enumerate(FOREARM_LOCAL))
        joints.append((f"{pre}Shoulder", "Root", sh,
                       {"flex": (-1, 0, 0), "abd": (0, 0, side), "twist": (0, -1, 0)}))
        joints.append((f"{pre}Elbow", f"{pre}Shoulder", el,
                       {"flex": (-1, 0, 0), "abd": (0, 0, side), "twist": norm(vsub(fa, el))}))
        joints.append((f"{pre}Forearm", f"{pre}Elbow", fa,
                       {"flex": (-1, 0, 0), "abd": (0, 0, side), "twist": norm(vsub(C, fa))}))
        joints.append((f"{pre}Wrist", f"{pre}Forearm", C,
                       {"flex": flex, "abd": abd, "twist": D}))
        joints.append((f"{pre}Hand", f"{pre}Wrist", to_world((0.0, 0.048, 0.0), side),
                       {"flex": flex, "abd": abd, "twist": D}))
        joints.append((f"{pre}ThumbCMC", f"{pre}Hand", to_world(THUMB["cmc"], side),
                       {"flex": flex, "abd": abd, "twist": norm(vsub(to_world(THUMB["mcp"], side), to_world(THUMB["cmc"], side)))}))
        joints.append((f"{pre}ThumbMCP", f"{pre}ThumbCMC", to_world(THUMB["mcp"], side),
                       {"flex": flex, "abd": abd, "twist": norm(vsub(to_world(THUMB["ip"], side), to_world(THUMB["mcp"], side)))}))
        joints.append((f"{pre}ThumbIP", f"{pre}ThumbMCP", to_world(THUMB["ip"], side),
                       {"flex": flex, "abd": abd, "twist": norm(vsub(to_world(THUMB["tip"], side), to_world(THUMB["ip"], side)))}))
        for dig in DIGITS:
            chain, _, _ = _finger_chain(dig)
            for ji, (seg, jn) in enumerate((("MCP", 0), ("PIP", 1), ("DIP", 2))):
                head = to_world(chain[ji], side)
                nxt = to_world(chain[ji+1], side)
                joints.append((f"{pre}{dig['key']}{seg}",
                               f"{pre}Hand" if ji == 0 else f"{pre}{dig['key']}{('MCP','PIP','DIP')[ji-1]}",
                               head, {"flex": flex, "abd": abd, "twist": norm(vsub(nxt, head))}))
    return joints

# ---- skin weights -----------------------------------------------------------

def _project_chain(p, chain):
    """Param s along a polyline chain (0 at chain[0]) + index of best segment."""
    best = (0.0, 0, 1e9)
    acc = 0.0
    for i in range(len(chain)-1):
        a, b = chain[i], chain[i+1]
        ab = vsub(b, a); L2 = dot(ab, ab)
        t = clamp(dot(vsub(p, a), ab)/L2, 0.0, 1.0) if L2 > 1e-12 else 0.0
        q = vadd(a, vmul(ab, t))
        d2 = dot(vsub(p, q), vsub(p, q))
        if d2 < best[2]:
            best = (acc + t*math.sqrt(L2), i, d2)
        acc += math.sqrt(L2)
    return best[0]

def _prune_top4(w):
    items = sorted(w.items(), key=lambda kv: -kv[1])
    out = dict(items[:4])
    tot = sum(out.values())
    return {k: v/tot for k, v in out.items()} if tot > 1e-9 else {"Root": 1.0}

def digit_weights(side, dig_index, p_world):
    """Weights for a finger (dig_index 0..3) vertex: MCP/PIP/DIP blend + Hand root."""
    dig = DIGITS[dig_index]
    chain, _, _ = _finger_chain(dig)
    l1, l2, l3 = dig["segs"]
    nodes = (0.0, l1, l1+l2, l1+l2+l3)      # MCP, PIP, PIP+mid, TIP params
    pre = "R" if side > 0 else "L"
    names = (f"{pre}{dig['key']}MCP", f"{pre}{dig['key']}PIP", f"{pre}{dig['key']}DIP")
    s = _project_chain(to_local(p_world, side), chain)
    w = {}
    if s <= 0.0:                                   # root embedded in the palm
        k = clamp(-s/0.018, 0.0, 1.0)*0.85
        w[names[0]] = 1.0-k; w[f"{pre}Hand"] = k
        return w
    if s >= nodes[2]:                              # distal phalanx rides the DIP
        w[names[2]] = 1.0; return w
    for seg in (0, 1):
        n0, n1 = nodes[seg], nodes[seg+1]
        if n0 <= s <= n1:
            u = smoothstep(0.18, 0.82, (s-n0)/(n1-n0))
            w[names[seg]] = 1.0-u; w[names[seg+1]] = u
            break
    return _prune_top4(w)

def thumb_weights(side, p_world):
    chain = _thumb_chain()
    pre = "R" if side > 0 else "L"
    l_cmc_mcp = math.dist(THUMB["cmc"], THUMB["mcp"])
    l_mcp_ip = math.dist(THUMB["mcp"], THUMB["ip"])
    nodes = (0.0, l_cmc_mcp, l_cmc_mcp + l_mcp_ip)
    names = (f"{pre}ThumbCMC", f"{pre}ThumbMCP", f"{pre}ThumbIP")
    s = _project_chain(to_local(p_world, side), chain)
    w = {}
    if s <= 0.0:
        k = clamp(-s/0.020, 0.0, 1.0)*0.8
        w[names[0]] = 1.0-k; w[f"{pre}Hand"] = k
        return w
    if s >= nodes[2]:                       # distal phalanx rides the IP
        w[names[2]] = 1.0; return w
    for seg in (0, 1):
        n0, n1 = nodes[seg], nodes[seg+1]
        if n0 <= s <= n1:
            u = smoothstep(0.2, 0.8, (s-n0)/(n1-n0))
            w[names[seg]] = 1.0-u; w[names[seg+1]] = u
            break
    return _prune_top4(w)

def palm_weights(side, p_world):
    """Palm: Wrist -> Hand along d, then wedges to the MCP row / thumb CMC."""
    r, d, n = to_local(p_world, side)
    pre = "R" if side > 0 else "L"
    w = {}
    w[f"{pre}Wrist"] = 1.0 - smoothstep(0.012, 0.052, d)
    base = smoothstep(0.012, 0.052, d)
    mcp_share = 0.85*smoothstep(0.060, 0.090, d)
    hand_share = base*(1.0 - mcp_share)
    if hand_share > 1e-4:
        w[f"{pre}Hand"] = hand_share
    if mcp_share > 1e-4:
        tot = 0.0
        for dig in DIGITS:
            g = gauss(r, dig["mcp"][0], 0.0125)
            if g > 0.02:
                w[f"{pre}{dig['key']}MCP"] = w.get(f"{pre}{dig['key']}MCP", 0.0) + g
                tot += g
        if tot > 1e-6:
            k = mcp_share/tot
            for key in list(w):
                if key.endswith("MCP") and not key.endswith("ThumbMCP"):
                    w[key] *= k
    # thenar -> thumb CMC (only near the thumb base, palmar-radial corner)
    cmc = THUMB["cmc"]
    g = gauss(((r-cmc[0])**2 + (d-cmc[1])**2 + (n-cmc[2])**2) ** 0.5, 0.0, 0.016)
    if g > 0.05:
        w[f"{pre}ThumbCMC"] = w.get(f"{pre}ThumbCMC", 0.0) + 0.55*g*(1.0-smoothstep(0.03, 0.06, d))
    return _prune_top4(w)

def guard_weights(side, p_world):
    """Knuckle guard / ridges: wedge across the MCP row."""
    r, _, _ = to_local(p_world, side)
    pre = "R" if side > 0 else "L"
    w = {}
    for dig in DIGITS:
        g = gauss(r, dig["mcp"][0], 0.014)
        if g > 0.02:
            w[f"{pre}{dig['key']}MCP"] = g
    return _prune_top4(w)

def web_weights(side, pair_index, p_world):
    """Webbing gusset between finger pair_index and pair_index+1."""
    pre = "R" if side > 0 else "L"
    a, b = DIGITS[pair_index]["key"], DIGITS[pair_index+1]["key"]
    return {f"{pre}{a}MCP": 0.45, f"{pre}{b}MCP": 0.45, f"{pre}Hand": 0.10}

def thumb_web_weights(side, p_world):
    """Webbing span between the thumb metacarpal and the index base."""
    pre = "R" if side > 0 else "L"
    return {f"{pre}ThumbCMC": 0.45, f"{pre}IndexMCP": 0.45, f"{pre}Hand": 0.10}

def rigid_wrist_weights(side, p_world):
    pre = "R" if side > 0 else "L"
    return {f"{pre}Wrist": 1.0}

CHAIN_WEIGHT_FN = {
    "palm": palm_weights, "thumb": thumb_weights, "guard": guard_weights,
    "cuff": rigid_wrist_weights, "bridge": rigid_wrist_weights,
    "webT": thumb_web_weights,
}

def weights_for(side, chain, p_world):
    """Dispatch a mesh part chain id to its weight function."""
    if chain in CHAIN_WEIGHT_FN:
        return CHAIN_WEIGHT_FN[chain](side, p_world)
    if chain.startswith("digit"):
        return digit_weights(side, int(chain[5:]), p_world)
    if chain.startswith("web"):
        return web_weights(side, int(chain[3:]), p_world)
    raise KeyError(f"unknown rig chain '{chain}'")

# ---- poses ------------------------------------------------------------------

def _fam(spec, family, key, default=0.0):
    v = spec.get(family, {})
    return v.get(key, default)

POSES = {
    # Relaxed bind pose: nothing moves - sculpted anatomy only.
    "stand": {"R": {}, "L": {}},
    # Mid-stride: arms swing opposite, fingers a touch looser, wrists articulate.
    "walk": {
        "R": {"Shoulder": {"flex": 22}, "Elbow": {"flex": 14}, "Wrist": {"flex": 8},
              "FingerMCP": {"flex": 8}, "FingerPIP": {"flex": 6}, "FingerDIP": {"flex": 4},
              "ThumbMCP": {"flex": 6}},
        "L": {"Shoulder": {"flex": -14}, "Elbow": {"flex": 22}, "Wrist": {"flex": -5},
              "FingerMCP": {"flex": 12}, "FingerPIP": {"flex": 9}, "FingerDIP": {"flex": 5},
              "ThumbMCP": {"flex": 8}},
    },
    # Overhead slash (right) with a weapon grip; left hand open in guard.
    "attack": {
        "R": {"Shoulder": {"flex": 98}, "Elbow": {"flex": 42}, "Wrist": {"flex": -12, "abd": -6},
              "FingerMCP": {"flex": 58}, "FingerPIP": {"flex": 74}, "FingerDIP": {"flex": 34},
              "ThumbCMC": {"flex": 18, "abd": -10}, "ThumbMCP": {"flex": 40}, "ThumbIP": {"flex": 26}},
        "L": {"Shoulder": {"flex": 16}, "Elbow": {"flex": 34}, "Wrist": {"flex": 4},
              "FingerMCP": {"flex": 24}, "FingerPIP": {"flex": 18}, "FingerDIP": {"flex": 10},
              "ThumbCMC": {"abd": 12}, "ThumbMCP": {"flex": 8}},
    },
    # Tucked roll: elbows bent hard, fists clenched, wrists flexed.
    "dodge": {
        "R": {"Shoulder": {"flex": 34}, "Elbow": {"flex": 98}, "Wrist": {"flex": 18},
              "FingerMCP": {"flex": 72}, "FingerPIP": {"flex": 82}, "FingerDIP": {"flex": 52},
              "ThumbCMC": {"flex": 26}, "ThumbMCP": {"flex": 46}, "ThumbIP": {"flex": 30}},
        "L": {"Shoulder": {"flex": 38}, "Elbow": {"flex": 92}, "Wrist": {"flex": 16},
              "FingerMCP": {"flex": 68}, "FingerPIP": {"flex": 80}, "FingerDIP": {"flex": 50},
              "ThumbCMC": {"flex": 24}, "ThumbMCP": {"flex": 44}, "ThumbIP": {"flex": 28}},
    },
}

def _family_map(name):
    """Joint name -> pose family key (e.g. 'RMiddlePIP' -> 'FingerPIP')."""
    if "Thumb" in name:
        for fam in ("ThumbCMC", "ThumbMCP", "ThumbIP"):
            if name.endswith(fam):
                return fam
        return None
    for dig in DIGITS:
        if dig["key"] in name:
            for seg in ("MCP", "PIP", "DIP"):
                if name.endswith(seg):
                    return f"Finger{seg}"
    return name[1:] if name[1:] in ("Shoulder", "Elbow", "Forearm", "Wrist", "Hand") else None

def pose_matrices(pose_name):
    """{joint: world 4x4 posed matrix} for a named pose (both sides)."""
    joints = {j[0]: j for j in joint_list()}
    posed = {"Root": ((1,0,0,0),(0,1,0,0),(0,0,1,0),(0,0,0,1))}
    spec = POSES[pose_name]
    order = ["Root"]
    while len(order) < len(joints):
        progressed = False
        for name in joints:
            if name in posed:
                continue
            parent = joints[name][1]
            if parent in posed:
                side_pre = name[0]
                fam = _family_map(name)
                rot = mat_translate((0, 0, 0))
                if fam:
                    p = spec.get(side_pre, {}).get(fam, {})
                    axes = joints[name][3]
                    for key in ("flex", "abd", "twist"):
                        ang = p.get(key, 0.0)
                        if abs(ang) > 1e-6:
                            rot = mat_mul(rot, mat_rot_axis(axes[key], ang))
                m_par = posed[parent]
                m_local = mat_mul(mat_translate(vsub(joints[name][2], joints[parent][2])), rot)
                posed[name] = mat_mul(m_par, m_local)
                order.append(name)
                progressed = True
        if not progressed:
            break
    for name in joints:
        if name not in posed:
            posed[name] = posed.get(joints[name][1], posed["Root"])
    return posed

def skin_vertex(p_world, weights, posed, joints):
    """Linear-blend-skin one world vertex. weights = {joint_name: w}."""
    acc = [0.0, 0.0, 0.0]
    for name, w in weights.items():
        j = joints[name]
        m = posed[name]
        rigid = mat_mul(m, mat_translate(vmul(j[2], -1.0)))
        q = mat_apply(rigid, p_world)
        acc[0] += w*q[0]; acc[1] += w*q[1]; acc[2] += w*q[2]
    return (acc[0], acc[1], acc[2])
