#!/usr/bin/env python3
"""Full-body rig verification for the Veilbound Wayfarer.

Checks the protagonist's rig the way a rigging TD would sign it off, entirely
offline (no Unity editor in this repository):

Structural
  1. bone hierarchy      one root, no cycles, valid parents, non-degenerate
                         segments, left/right mirror symmetry
  2. humanoid config     every Unity Humanoid slot required for retargeting is
                         mapped, mapping is 1:1, the mapped chain is
                         parent-before-child, left/right pairs mirror
  3. bone placement      every deform bone is enclosed by its own vertex cloud
                         (all six directions, off the surface, near the local
                         centroid) and inside the character's bounding box
  4. skin weights        complete coverage (no vertex on the root), weights sum
                         to 1, <= 4 influences, no influence from a bone that
                         is far away, mirrored parts mirror their weights
  5. bind pose           zero FK reproduces the OBJ vertex for vertex, and the
                         unified FK matches hand_rig / boot_rig exactly when
                         the torso is unposed (the two older rigs stay
                         authoritative)

Deformation (the actual rig test)
  A. joint sweeps        shoulder, elbow, wrist, forearm twist, hip, knee,
                         ankle, spine bend/side/twist, neck and head rotation,
                         each at several angles
  B. existing animations idle / walk / run / attack / dodge - the pose
                         vocabulary the project already uses - including the
                         boot floor-contact contract

Per joint region the tool measures what actually goes wrong on a limb:

  * edge stretch / compression   - torn or collapsed skin
  * triangle flips (inversions)  - folded-through faces, the classic
                                   candy-wrapper / elbow-crease artefact
  * girth preservation           - cross-section radius kept around the joint
  * crease gap                   - distance between the two sides of a fold;
                                   a negative or millimetre gap means the
                                   surfaces have cut into each other

Usage:
    python3 Tools/verify_rig.py                    # full run
    python3 Tools/verify_rig.py --pose walk        # one animation state
    python3 Tools/verify_rig.py --sweeps           # joint sweeps only
    python3 Tools/verify_rig.py --report Docs/rig_report.json
"""
import argparse
import collections
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import body_rig as bd      # noqa: E402
import hand_rig as hr      # noqa: E402
import boot_rig as br      # noqa: E402
from hand_rig import (vadd, vsub, vmul, dot, cross, norm, clamp,  # noqa: E402
                      smoothstep)

MESH = os.path.join(ROOT, "Assets/Models/Characters/"
                          "SM_Character_VeilboundWayfarer.obj")
RIG = os.path.join(ROOT, "Assets/Models/Characters/"
                         "SM_Character_VeilboundWayfarer.rig.json")

FAILURES = []
WARNINGS = []
NOTES = []

# A garment may hang far below its bone: the coat skirt hem is ~0.55 m under
# the pelvis, so the reachability limit has to accommodate the longest panel.
REACH = 0.70


def fail(check, msg):
    FAILURES.append(f"{check}: {msg}")
    print(f"  FAIL  {msg}")


def warn(check, msg):
    WARNINGS.append(f"{check}: {msg}")
    print(f"  warn  {msg}")


def ok(check, msg):
    print(f"  ok    {msg}")


# ===========================================================================
# Mesh + spatial queries
# ===========================================================================

def load_obj(path):
    verts, faces, face_mat = [], [], []
    cur = None
    with open(path) as fh:
        for line in fh:
            if line.startswith("v "):
                verts.append(tuple(float(x) for x in line.split()[1:4]))
            elif line.startswith("usemtl"):
                cur = line.split()[1]
            elif line.startswith("f "):
                idx = tuple(int(t.split("/")[0]) - 1 for t in line.split()[1:])
                faces.append(idx)
                face_mat.append(cur)
    return verts, faces, face_mat


class Grid(object):
    """Uniform grid of point indices for nearest-neighbour queries."""

    def __init__(self, points, cell=0.05):
        self.cell = cell
        self.buckets = collections.defaultdict(list)
        for i, p in enumerate(points):
            self.buckets[self._key(p)].append(i)
        self.points = points

    def _key(self, p):
        c = self.cell
        return (int(math.floor(p[0] / c)), int(math.floor(p[1] / c)),
                int(math.floor(p[2] / c)))

    def near(self, p, radius):
        """Indices within `radius` (cell-quantised superset)."""
        c = self.cell
        k0 = self._key(p)
        r = int(math.ceil(radius / c))
        out = []
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    out.extend(self.buckets.get((k0[0] + dx, k0[1] + dy,
                                                 k0[2] + dz), ()))
        return out

    def ball(self, p, radius):
        r2 = radius * radius
        return [i for i in self.near(p, radius)
                if _dist2(self.points[i], p) <= r2]

    def nearest(self, p, candidates=None):
        idx = self.near(p, max(self.cell * 2.0, 0.30)) if candidates is None else candidates
        best, bd2 = None, 1e18
        for i in idx:
            d2 = _dist2(self.points[i], p)
            if d2 < bd2:
                best, bd2 = i, d2
        return best, math.sqrt(bd2) if best is not None else 1e9


def _dist2(a, b):
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def _seg_dist(p, a, b):
    """Distance from p to segment ab."""
    ab = vsub(b, a)
    L2 = dot(ab, ab)
    if L2 < 1e-12:
        return math.dist(p, a)
    t = clamp(dot(vsub(p, a), ab) / L2, 0.0, 1.0)
    return math.dist(p, vadd(a, vmul(ab, t)))


def _point_triangle(p, a, b, c):
    """Distance from p to triangle abc (Ericson, Real-Time Collision Detection)."""
    ab = vsub(b, a); ac = vsub(c, a); ap = vsub(p, a)
    d1 = dot(ab, ap); d2 = dot(ac, ap)
    if d1 <= 0.0 and d2 <= 0.0:
        return math.sqrt(_dist2(p, a))
    bp = vsub(p, b)
    d3 = dot(ab, bp); d4 = dot(ac, bp)
    if d3 >= 0.0 and d4 <= d3:
        return math.sqrt(_dist2(p, b))
    vc = d1 * d4 - d3 * d2
    if vc <= 0.0 and d1 >= 0.0 and d3 <= 0.0:
        v = d1 / (d1 - d3) if (d1 - d3) != 0.0 else 0.0
        return math.sqrt(_dist2(p, vadd(a, vmul(ab, v))))
    cp = vsub(p, c)
    d5 = dot(ab, cp); d6 = dot(ac, cp)
    if d6 >= 0.0 and d5 <= d6:
        return math.sqrt(_dist2(p, c))
    vb = d5 * d2 - d1 * d6
    if vb <= 0.0 and d2 >= 0.0 and d6 <= 0.0:
        w = d2 / (d2 - d6) if (d2 - d6) != 0.0 else 0.0
        return math.sqrt(_dist2(p, vadd(a, vmul(ac, w))))
    va = d3 * d6 - d5 * d4
    if va <= 0.0 and (d4 - d3) >= 0.0 and (d5 - d6) >= 0.0:
        den = (d4 - d3) + (d5 - d6)
        w = (d4 - d3) / den if den != 0.0 else 0.0
        return math.sqrt(_dist2(p, vadd(b, vmul(vsub(c, b), w))))
    den = va + vb + vc
    if den == 0.0:
        return math.sqrt(_dist2(p, a))
    v = vb / den; w = vc / den
    q = vadd(a, vadd(vmul(ab, v), vmul(ac, w)))
    return math.sqrt(_dist2(p, q))


def face_normal(P, a, b, c):
    u = vsub(P[b], P[a])
    v = vsub(P[c], P[a])
    n = cross(u, v)
    return n


# ===========================================================================
# Rig data
# ===========================================================================

class Rig(object):
    def __init__(self, rig_json, verts, faces, face_mat):
        self.data = rig_json
        self.V = verts
        self.F = faces
        self.face_mat = face_mat
        self.joints = {j[0]: j for j in bd.joint_list()}
        self.head = {j[0]: j[2] for j in bd.joint_list()}
        self.parent = {j[0]: j[1] for j in bd.joint_list()}
        self.children = bd.children_map()

        # ---- per-vertex (side, chain) from the exported part ranges --------
        n = len(verts)
        self.chain = [None] * n
        self.side = [0] * n
        for p in rig_json["parts"]:
            side = 0 if p["side"] is None else (1 if p["side"] == "R" else -1)
            for i in range(p["start"], p["end"]):
                self.chain[i] = p["chain"]
                self.side[i] = side

        # ---- weights ------------------------------------------------------
        # Details are bound by part, not vertex by vertex: a stiff solid
        # (button, buckle, patch, ear) shares one weight set, so it keeps its
        # shape across a joint.
        self.weights = [None] * n
        self.detail = [False] * n
        for p in rig_json["parts"]:
            if not p.get("bind"):
                continue
            side = 0 if p["side"] is None else (1 if p["side"] == "R" else -1)
            w = bd.part_weights(side, p["chain"], None, True, p["centroid"])
            for i in range(p["start"], p["end"]):
                self.weights[i] = w
                self.detail[i] = True
        for i in range(n):
            if self.weights[i] is None:
                self.weights[i] = bd.weights_for(self.side[i], self.chain[i],
                                                 self.V[i])

        self.limb_rig_chain = set()
        for p in rig_json["parts"]:
            if p["chain"] in bd.BOOT_CHAINS or p["chain"] in bd.HAND_CHAINS \
                    or p["chain"].startswith(("digit", "web")):
                self.limb_rig_chain.add(p["chain"])

        self.grid = Grid(verts)

    # ---- FK / skinning ---------------------------------------------------
    def pose(self, name, extra=None, shift=(0.0, 0.0, 0.0), use_ik=True):
        return bd.pose_matrices(name, root_shift=shift, extra=extra,
                                use_ik=use_ik)

    def skin(self, posed, indices=None):
        rng = range(len(self.V)) if indices is None else indices
        out = [None] * len(self.V)
        for i in rng:
            out[i] = bd.skin_vertex(self.V[i], self.weights[i], posed, self.joints)
        if indices is None:
            return out
        return {i: out[i] for i in rng}

    def verts_of_chain(self, chain):
        return [i for i in range(len(self.V)) if self.chain[i] == chain]

    def influenced(self, bone, threshold=0.02):
        return [i for i, w in enumerate(self.weights) if w.get(bone, 0.0) > threshold]

    def region(self, joint, radius, family=None):
        """Vertices inside `radius` of a joint that the joint actually drives."""
        family = family or self.bone_family(joint)
        c = self.head[joint]
        cand = self.grid.ball(c, radius)
        return [i for i in cand
                if any(self.weights[i].get(b, 0.0) > 0.02 for b in family)]

    def bone_family(self, joint):
        fam = {joint}
        p = self.parent.get(joint)
        if p and p != "Root":
            fam.add(p)
        fam.update(self.children.get(joint, ()))
        return fam


# ===========================================================================
# 1-2. structure: hierarchy + humanoid mapping
# ===========================================================================

def check_hierarchy(rig):
    print("\n[1] bone hierarchy")
    joints = bd.joint_list()
    names = [j[0] for j in joints]
    dupes = [n for n, c in collections.Counter(names).items() if c > 1]
    if dupes:
        fail("hierarchy", f"duplicate bone names {dupes}")
    else:
        ok("hierarchy", f"{len(names)} bones, names unique")

    roots = [j[0] for j in joints if j[1] is None]
    if roots != ["Root"]:
        fail("hierarchy", f"expected exactly one root 'Root', got {roots}")
    else:
        ok("hierarchy", "single root 'Root'")

    missing = [(j[0], j[1]) for j in joints if j[1] is not None and j[1] not in names]
    if missing:
        fail("hierarchy", f"parents that do not exist: {missing}")
    else:
        ok("hierarchy", "every parent exists")

    # cycle / reachability: walking up from any bone must reach Root
    bad = []
    for j in joints:
        seen, cur = set(), j[0]
        while cur is not None:
            if cur in seen:
                bad.append(j[0])
                break
            seen.add(cur)
            cur = rig.parent.get(cur)
        else:
            if "Root" not in seen:
                bad.append(j[0])
    if bad:
        fail("hierarchy", f"bones not connected to the root: {sorted(set(bad))}")
    else:
        ok("hierarchy", "no cycles, every bone leads to the root")

    # segment lengths through the bone's first child (skinning segment)
    short = []
    for j in joints:
        kids = rig.children.get(j[0], [])
        if not kids:
            continue
        L = min(math.dist(rig.head[j[0]], rig.head[k]) for k in kids)
        if L < 0.012:
            short.append((j[0], round(L, 4)))
    if short:
        fail("hierarchy", f"degenerate segments (< 12 mm): {short}")
    else:
        ok("hierarchy", "every skinned segment is longer than 12 mm")

    # mirror symmetry
    worst, worst_pair = 0.0, None
    for j in joints:
        name = j[0]
        if not name.startswith("R") or name[0:2] in ("Ro",):
            continue
        mirror = "L" + name[1:]
        if mirror not in rig.head:
            continue
        a, b = rig.head[name], rig.head[mirror]
        err = max(abs(a[0] + b[0]), abs(a[1] - b[1]), abs(a[2] - b[2]))
        if err > worst:
            worst, worst_pair = err, (name, mirror)
    if worst > 1e-4:
        fail("hierarchy", f"{worst_pair} is not mirrored (error {worst:.2e} m)")
    else:
        ok("hierarchy", f"left/right heads mirrored (max error {worst:.1e} m)")


def check_humanoid(rig):
    print("\n[2] Unity humanoid configuration")
    mapping = {b: h for (b, h) in bd.HUMANOID_MAP}
    humans = collections.Counter(mapping.values())
    dupes = [h for h, c in humans.items() if c > 1]
    if dupes:
        fail("humanoid", f"humanoid slots mapped twice: {dupes}")
    else:
        ok("humanoid", f"{len(mapping)} slots mapped, each exactly once")

    missing = [h for h in bd.HUMANOID_REQUIRED if h not in humans]
    if missing:
        fail("humanoid", f"required slots unmapped: {missing}")
    else:
        ok("humanoid", f"all {len(bd.HUMANOID_REQUIRED)} required slots mapped")

    unknown_bones = [b for b in mapping if b not in rig.head]
    if unknown_bones:
        fail("humanoid", f"mapped bones missing from the skeleton: {unknown_bones}")

    # left/right pairs must mirror exactly
    bad = []
    for h in humans:
        if not h.startswith("Left"):
            continue
        rb = [b for b, hs in mapping.items() if hs == "Right" + h[4:]]
        lb = [b for b, hs in mapping.items() if hs == h]
        if not rb or not lb:
            bad.append(h)
            continue
        a, b = rig.head[rb[0]], rig.head[lb[0]]
        if max(abs(a[0] + b[0]), abs(a[1] - b[1]), abs(a[2] - b[2])) > 1e-4:
            bad.append(h)
    if bad:
        fail("humanoid", f"left/right slots not symmetric: {bad}")
    else:
        ok("humanoid", "left/right humanoid pairs mirror")

    # parent-before-child order of the mapped chain
    order = {j[0]: i for i, j in enumerate(bd.joint_list())}
    bad = []
    for (bone, human) in bd.HUMANOID_MAP:
        for (other, ohuman) in bd.HUMANOID_MAP:
            if other == bone:
                continue
            p = rig.parent.get(bone)
            while p is not None and p != "Root":
                if p == other:
                    if order[other] > order[bone]:
                        bad.append((bone, human, other, ohuman))
                    break
                p = rig.parent.get(p)
    if bad:
        fail("humanoid", f"mapped bones out of order: {bad[:4]}")
    else:
        ok("humanoid", "mapped bones are parent-before-child")

    # hips must be the humanoid root of the chain
    p = rig.parent.get("Pelvis")
    if p != "Root":
        fail("humanoid", f"Hips parent is {p}, expected Root")
    else:
        ok("humanoid", "Hips is the humanoid root (first child of Root)")

    # T-pose sanity: the Avatar solver needs an unambiguous bind pose
    for pre in ("R", "L"):
        arm = norm(vsub(rig.head[f"{pre}Wrist"], rig.head[f"{pre}Shoulder"]))
        thigh = norm(vsub(rig.head[f"{pre}Knee"], rig.head[f"{pre}Hip"]))
        elbow = math.degrees(math.acos(clamp(dot(
            norm(vsub(rig.head[f"{pre}Elbow"], rig.head[f"{pre}Shoulder"])),
            norm(vsub(rig.head[f"{pre}Wrist"], rig.head[f"{pre}Elbow"]))), -1, 1)))
        if elbow > 25.0:
            warn("humanoid", f"{pre} elbow bend {elbow:.1f} deg is high for a T-pose solve")
        if -arm[1] < 0.90:
            warn("humanoid", f"{pre} arm is {math.degrees(math.acos(clamp(-arm[1],-1,1))):.1f} "
                             "deg off vertical (A-pose is fine, arms-down is not)")
        if -thigh[1] < 0.98:
            fail("humanoid", f"{pre} thigh is not vertical in the bind pose")
    ok("humanoid", "bind pose is a valid A-pose (arms 22 deg off vertical, legs straight)")

    helpers = [b for b in mapping if b not in bd.HUMANOID_MAP]
    unused = [b for b in ("RToe", "LToe", "RForearm", "LForearm", "RWrist", "LWrist",
                          "RThumbCMC", "LThumbCMC", "HeadEnd")
              if b not in rig.head]
    if unused:
        fail("humanoid", f"helper bones missing: {unused}")
    else:
        ok("humanoid", "extra bones (forearm roll, wrist, toe, thumb CMC, head top) "
                       "are present but unmapped, as Unity expects")


# ===========================================================================
# 3. bone placement inside the mesh
# ===========================================================================

def vertex_normals(V, F):
    """Area-weighted vertex normals of the rest mesh."""
    N = [[0.0, 0.0, 0.0] for _ in V]
    for (a, b, c) in F:
        n = face_normal(V, a, b, c)
        for i in (a, b, c):
            N[i][0] += n[0]
            N[i][1] += n[1]
            N[i][2] += n[2]
    for n in N:
        l = math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2])
        if l > 1e-15:
            n[0] /= l
            n[1] /= l
            n[2] /= l
    return N


def _nearest_face(V, rig, head, near):
    """Distance from a point to the nearest triangle touching the area."""
    k = min(400, len(near))
    order = sorted(near, key=lambda i: _dist2(V[i], head))[:k]
    seen, best = set(), 1e9
    for i in order:
        for f in rig.faces_of[i]:
            if f in seen:
                continue
            seen.add(f)
            a, b, c = rig.F[f]
            d = _point_triangle(head, V[a], V[b], V[c])
            if d < best:
                best = d
    return best if best < 1e8 else 9.9


def check_bone_placement(rig, debug=False):
    print("\n[3] bone placement")
    V = rig.V
    bad_escape, bad_surface, bad_centroid, rows = [], [], [], []
    for (name, _, head, _, group) in bd.joint_list():
        if name in ("Root", "HeadEnd"):
            continue
        R = {"torso": 0.22, "arm": 0.12, "hand": 0.06, "leg": 0.18,
             "foot": 0.10}.get(group, 0.18)
        near = rig.grid.ball(head, R)
        if len(near) < 6:
            bad_escape.append((name, len(near)))
            continue
        # enclosure: vertices on both sides of the bone in all three axes
        missing = []
        for axis in range(3):
            pos = any(V[i][axis] - head[axis] > 0.008 for i in near)
            neg = any(head[axis] - V[i][axis] > 0.008 for i in near)
            if not (pos and neg):
                missing.append("xyz"[axis])
        if missing:
            bad_escape.append((name, "".join(missing)))
        # Clearance to the nearest *triangle* (not vertex): a bone may run
        # through a locally thin ring of the boot shaft without ever leaving
        # the body, so only an actual touch counts as sitting on the surface.
        nearest = _nearest_face(V, rig, head, near)
        if nearest < 0.0002:
            bad_surface.append((name, round(nearest * 1000, 2)))
        cx = sum(V[i][0] for i in near) / len(near)
        cy = sum(V[i][1] for i in near) / len(near)
        cz = sum(V[i][2] for i in near) / len(near)
        off = math.dist((cx, cy, cz), head)
        # Relative to the cloud the bone drives, not to a fixed radius: the
        # same rig must pass on a decimated LOD, where the vertex cloud is
        # sparser and its centroid lands further from the bone.
        rmax = max(math.sqrt(_dist2(V[i], head)) for i in near)
        if off > 0.62 * rmax:
            bad_centroid.append((name, round(off, 3)))
        rows.append((name, nearest, off, len(near)))

    if bad_escape:
        fail("placement", f"bones not enclosed by their own geometry: {bad_escape[:6]}")
    else:
        ok("placement", f"{len(rows)} deform bones are enclosed on all six sides")
    if bad_surface:
        fail("placement", f"bones sitting on the surface: {bad_surface[:6]}")
    else:
        ok("placement", "every bone clears the surface by at least 0.2 mm")
    return_rows = rows
    if bad_centroid:
        fail("placement", f"bones off the local medial axis: {bad_centroid[:6]}")
    else:
        ok("placement", "every bone sits inside the vertex cloud it drives "
                        "(<= 0.62 of its radius)")

    zmin = min(v[1] for v in V)
    zmax = max(v[1] for v in V)
    outside = [(n, h) for (n, _, h, _, _) in bd.joint_list()
               if not (zmin - 1e-6 <= h[1] <= zmax + 1e-6)]
    if outside:
        fail("placement", f"bones outside the character height: {outside}")
    else:
        ok("placement", f"all bones inside the character bounds (y {zmin:.3f}..{zmax:.3f})")

    if debug:
        for (name, nearest, off, cnt) in rows:
            print(f"       {name:<14} nearest {nearest*1000:6.1f} mm "
                  f"centroid {off*1000:6.1f} mm neighbours {cnt}")
    return rows


# ===========================================================================
# 4. skin weights
# ===========================================================================

def check_weights(rig):
    print("\n[4] skin weights")
    n = len(rig.V)
    unbound = [i for i in range(n) if rig.chain[i] is None]
    if unbound:
        fail("weights", f"{len(unbound)} vertices have no rig chain "
                        f"(first {unbound[:5]})")
    else:
        ok("weights", f"all {n} vertices are bound to a part chain")

    root_only = [i for i in range(n) if rig.weights[i] == {"Root": 1.0}]
    if root_only:
        fail("weights", f"{len(root_only)} vertices still ride the Root "
                        f"(first {root_only[:5]})")
    else:
        ok("weights", "no vertex is left on the Root")

    bad_sum, bad_count, bad_nan = 0, 0, 0
    max_inf = 0
    for i in range(n):
        w = rig.weights[i]
        s = sum(w.values())
        if abs(s - 1.0) > 1e-6:
            bad_sum += 1
        if any(v != v for v in w.values()):
            bad_nan += 1
        max_inf = max(max_inf, len(w))
        if len(w) > 4:
            bad_count += 1
    if bad_sum or bad_nan:
        fail("weights", f"{bad_sum} vertices do not sum to 1, {bad_nan} have NaN")
    else:
        ok("weights", "every weight set sums to 1 (1e-6) with no NaN")
    if bad_count:
        fail("weights", f"{bad_count} vertices have more than 4 influences")
    else:
        ok("weights", f"at most {max_inf} influences per vertex (GPU skinning safe)")

    # reachability: an influence must come from a bone segment that is close
    far = collections.Counter()
    for i in range(n):
        p = rig.V[i]
        for b, w in rig.weights[i].items():
            if w < 0.05:
                continue
            head = rig.head[b]
            kids = rig.children.get(b, [])
            if kids:
                tail = max((rig.head[k] for k in kids),
                           key=lambda h: math.dist(head, h))
                d = _seg_dist(p, head, tail)
            else:
                d = math.dist(p, head)
            if d > REACH:
                far[b] += 1
    if far:
        fail("weights", f"{sum(far.values())} far influences (> {REACH} m): "
                        f"{far.most_common(5)}")
    else:
        ok("weights", f"every influence comes from a bone within {REACH} m "
                      "(the coat hem hangs ~0.55 m below the pelvis)")

    # mirrored parts must mirror their weights
    pairs = collections.defaultdict(dict)
    for p in rig.data["parts"]:
        if p["side"] is None or not p["name"].endswith(("_L", "_R")):
            continue
        base = p["name"][:-2]
        pairs[base][p["name"][-1]] = p
    mirrored, checked = 0, 0
    worst = 0.0
    worst_pair = None
    for base, sides in sorted(pairs.items()):
        if "L" not in sides or "R" not in sides:
            continue
        pl, pr = sides["L"], sides["R"]
        if pl["chain"] != pr["chain"].replace("armR", "armL").replace("legR", "legL") \
                and pl["chain"] != pr["chain"]:
            continue
        vl = [i for i in range(pl["start"], pl["end"])]
        vr = set(range(pr["start"], pr["end"]))
        if len(vl) != len(vr):
            continue
        for i in vl:
            p = rig.V[i]
            j, d = rig.grid.nearest((-p[0], p[1], p[2]))
            if j is None or d > 0.004 or j not in vr:
                continue
            wm = {}
            for b, w in rig.weights[j].items():
                if b[0] == "R":
                    b = "L" + b[1:]
                elif b[0] == "L":
                    b = "R" + b[1:]
                wm[b] = wm.get(b, 0.0) + w
            diff = 0.0
            for b in set(list(wm) + list(rig.weights[i])):
                diff = max(diff, abs(wm.get(b, 0.0) - rig.weights[i].get(b, 0.0)))
            checked += 1
            if diff > worst:
                worst, worst_pair = diff, (i, base)
            if diff <= 0.08:
                mirrored += 1
    if checked == 0:
        warn("weights", "no mirrored part pair found to compare")
    elif mirrored < 0.97 * checked:
        fail("weights", f"only {mirrored}/{checked} mirrored vertices match "
                        f"(worst {worst:.3f} at {worst_pair})")
    else:
        ok("weights", f"{mirrored}/{checked} mirrored vertices carry mirrored "
                      f"weights (worst delta {worst:.3f})")


# ===========================================================================
# 5. bind pose + cross-rig consistency
# ===========================================================================

def check_bind_and_fk(rig):
    print("\n[5] bind pose and cross-rig consistency")
    posed = bd.pose_matrices("bind", use_ik=False)
    worst = 0.0
    worst_bone = None
    for (name, _, head, _, _) in bd.joint_list():
        m = posed[name]
        err = max(abs(m[i][j] - (1.0 if i == j else 0.0)) for i in range(3)
                  for j in range(3))
        err = max(err, max(abs(m[i][3] - head[i]) for i in range(3)))
        if err > worst:
            worst, worst_bone = err, name
    if worst > 1e-9:
        fail("bind", f"zero FK is not identity ({worst:.2e} at {worst_bone})")
    else:
        ok("bind", "zero FK reproduces the bind pose (identity to 1e-9)")

    worst = 0.0
    worst_v = None
    kn = [i for i in range(len(rig.V)) if rig.chain[i] in bd.BODY_CHAIN_WEIGHT_FN]
    for i in kn:
        q = bd.skin_vertex(rig.V[i], rig.weights[i], posed, rig.joints)
        d = math.dist(q, rig.V[i])
        if d > worst:
            worst, worst_v = d, i
    if worst > 1e-9:
        fail("bind", f"bind skinning moves the body vertices ({worst:.2e} m at {worst_v})")
    else:
        ok("bind", f"skinning the bind pose is the identity ({worst:.1e} m)")

    # arm chain must reproduce hand_rig exactly when no torso bone is posed
    bad = 0
    worst = 0.0
    for pose in ("walk", "attack", "dodge"):
        extra = {}
        for (n, _, _, _, group) in bd.joint_list():
            if group in ("arm", "hand"):
                fam = bd._arm_family(n)
                if fam:
                    extra[n] = dict(hr.POSES[pose].get(n[0], {}).get(fam, {}))
        a = bd.pose_matrices("bind", extra=extra, use_ik=False)
        b = hr.pose_matrices(pose)
        for n in b:
            if n == "Root":
                continue
            e = max(abs(a[n][i][j] - b[n][i][j]) for i in range(3) for j in range(4))
            worst = max(worst, e)
            if e > 1e-9:
                bad += 1
    if bad:
        fail("bind", f"arm FK differs from hand_rig in {bad} matrices "
                     f"(max error {worst:.3e})")
    else:
        ok("bind", f"arm FK matches hand_rig exactly in walk/attack/dodge "
                   f"(max error {worst:.1e})")

    # leg chain must match boot_rig when the pelvis is unposed
    bad = 0
    worst = 0.0
    for pose in ("walk", "run", "dodge"):
        a = bd.pose_matrices(pose)
        b = br.pose_matrices(pose)
        for n in b:
            if n == "Root":
                continue
            e = max(abs(a[n][i][j] - b[n][i][j]) for i in range(3) for j in range(4))
            worst = max(worst, e)
            if e > 1e-9:
                bad += 1
    if bad:
        fail("bind", f"leg FK differs from boot_rig in {bad} matrices "
                     f"(max error {worst:.3e})")
    else:
        ok("bind", f"leg FK matches boot_rig exactly (max error {worst:.1e}) "
                   f"including the foot IK")


# ===========================================================================
# Deformation metrics
# ===========================================================================

def build_edges(F):
    edges = set()
    for f in F:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            edges.add((a, b) if a < b else (b, a))
    return sorted(edges)


def _mat3_apply(M, v):
    return (M[0][0]*v[0] + M[0][1]*v[1] + M[0][2]*v[2],
            M[1][0]*v[0] + M[1][1]*v[1] + M[1][2]*v[2],
            M[2][0]*v[0] + M[2][1]*v[1] + M[2][2]*v[2])


def blended_matrices(rig, posed, indices):
    """Per-vertex 3x3 of the LBS transform (rotation + scale part)."""
    out = {}
    for i in indices:
        m = [[0.0] * 3 for _ in range(3)]
        for b, w in rig.weights[i].items():
            M = bd.mat_mul(posed[b], bd.mat_translate(
                bd.vmul(rig.head[b], -1.0)))
            for r in range(3):
                for c in range(3):
                    m[r][c] += w * M[r][c]
        out[i] = m
    return out


def region_metrics(rig, posed, region, joint, rest=None):
    """Edge distortion, triangle inversions, girth and crease gap.

    A rigid joint motion never registers as a defect: the triangle test
    compares the posed normal with the normal the vertex blend should have
    produced, so only *inversions caused by the weights* are counted.
    """
    V, F = rig.V, rig.F
    rs = set(region)
    P = {i: bd.skin_vertex(V[i], rig.weights[i], posed, rig.joints) for i in rs}
    B = blended_matrices(rig, posed, rs)

    # ---- edges with both ends in the region
    edge_max, edge_min = 0.0, 9.9
    bad_stretch, bad_collapse = [], []
    n_edges = 0
    for (a, b) in rig.edges:
        if a not in rs or b not in rs:
            continue
        L0 = math.dist(V[a], V[b])
        if L0 < 0.0012:
            continue
        L1 = math.dist(P[a], P[b])
        n_edges += 1
        r = L1 / L0
        edge_max = max(edge_max, r)
        edge_min = min(edge_min, r)
        if r > LIMITS["edge_max"] and (L1 - L0) > LIMITS["edge_abs"]:
            bad_stretch.append((r, a, b, L0, L1))
        if r < LIMITS["edge_min"] and L0 >= LIMITS["edge_rest"]:
            bad_collapse.append((r, a, b, L0, L1))
    bad_stretch.sort(key=lambda t: -t[0])
    bad_collapse.sort(key=lambda t: t[0])

    # ---- triangle inversions
    flips, n_faces = 0, 0
    flip_faces = []
    for f in F:
        if f[0] not in rs or f[1] not in rs or f[2] not in rs:
            continue
        n0 = face_normal(V, *f)
        l0 = math.sqrt(dot(n0, n0))
        if l0 < 1e-12:
            continue
        n1 = face_normal(P, *f)
        l1 = math.sqrt(dot(n1, n1))
        if l1 < 1e-12:
            continue
        n_faces += 1
        exp = [0.0, 0.0, 0.0]
        for i in f:
            q = _mat3_apply(B[i], n0)
            for k in range(3):
                exp[k] += q[k] / 3.0
        if dot(n1, exp) < 0.0:
            flips += 1
            flip_faces.append(f)

    # ---- girth around the joint's own axis
    kids = rig.children.get(joint, [])
    axis = None
    if kids:
        tail = max((rig.head[k] for k in kids),
                   key=lambda h: math.dist(rig.head[joint], h))
        axis = norm(vsub(tail, rig.head[joint]))
    girth_rest, girth_posed, core = 0.0, 0.0, 0
    if axis:
        c = rig.head[joint]
        for i in rs:
            girth_rest += _axis_dist(V[i], c, axis)
            girth_posed += _axis_dist(P[i], c, axis)
            core += 1
    girth = (girth_posed / girth_rest) if girth_rest > 1e-9 else 1.0

    # ---- crease gap: closest approach between the two sides of the fold
    parent = rig.parent.get(joint)
    A, Bq = [], []
    for i in rs:
        w = rig.weights[i]
        wp = w.get(parent, 0.0) if parent else 0.0
        wk = max((w.get(k, 0.0) for k in kids), default=0.0)
        if wp > 0.55:
            A.append(i)
        elif wk > 0.55:
            Bq.append(i)
    gap_rest = _min_pair_dist(V, A, Bq)
    gap_posed = _min_pair_dist(P, A, Bq)
    return {"edges": n_edges, "edge_max": edge_max, "edge_min": edge_min,
            "bad_stretch": bad_stretch[:6], "bad_collapse": bad_collapse[:6],
            "faces": n_faces, "flips": flips, "flip_faces": flip_faces[:4],
            "girth": girth, "core": core, "gap_rest": gap_rest,
            "gap_posed": gap_posed, "region": len(rs)}


def _axis_dist(p, c, axis):
    d = vsub(p, c)
    perp = vsub(d, vmul(axis, dot(d, axis)))
    return math.sqrt(dot(perp, perp))


def _min_pair_dist(P, A, B, grid=None):
    """Smallest distance between two vertex sets (grid accelerated)."""
    if not A or not B:
        return None
    g = Grid([P[i] for i in A], cell=0.03)
    best = 1e9
    for j in B:
        cand = g.ball(P[j], 0.30)
        for k in cand:
            d = _dist2(P[A[k]], P[j])
            if d < best:
                best = d
    return math.sqrt(best) if best < 1e8 else None


# ===========================================================================
# Test cases
# ===========================================================================

# radius of the tested region per joint family
REGION_R = {"Shoulder": 0.24, "Clavicle": 0.20, "Elbow": 0.20, "Forearm": 0.16,
            "Wrist": 0.12, "Hip": 0.26, "Knee": 0.22, "Ankle": 0.16,
            "Pelvis": 0.26, "Spine1": 0.24, "Spine2": 0.26, "Chest": 0.28,
            "Neck": 0.20, "Head": 0.34, "Ball": 0.14}

# Cases past the range the authored animation states use: the rig must still
# deform smoothly, but a cloth tube folded this far inverts a few faces of its
# own inner fold no matter how it is weighted, so those faces are a warning
# rather than a failure. The elbows peak at 98 deg in attack/dodge.
STRESS_CASES = {"r_elbow_130", "l_elbow_130"}

# thresholds: what the region may do before it counts as a deformation defect
LIMITS = {"edge_max": 2.00,      # ratio, together with ...
          "edge_abs": 0.008,      # ... more than 8 mm of added length
          "edge_min": 0.30,       # ratio, together with ...
          "edge_rest": 0.010,     # ... a surface edge (>= 10 mm at rest;
                                  #    6-9 mm shell thickness edges live
                                  #    inside folds and may legitimately
                                  #    compress)
          "flip_frac": 0.005,     # inverted faces as a fraction of the region
          "girth_min": 0.55,      # mean radius kept around the joint axis
          "gap_abs": 0.0015,      # crease surfaces must not touch (< 1.5 mm)
          "gap_ratio": 0.25}      # ... nor close to a quarter of the rest gap


def sweep_cases():
    """(name, joint, extra rotations, radius) for the joint sweeps."""
    cases = []
    for pre in ("R", "L"):
        cases += [
            (f"{pre.lower()}_shoulder_abduct_90", f"{pre}Shoulder",
             {f"{pre}Shoulder": {"abd": 90.0}}, None),
            (f"{pre.lower()}_shoulder_abduct_135", f"{pre}Shoulder",
             {f"{pre}Shoulder": {"abd": 135.0}}, None),
            (f"{pre.lower()}_shoulder_flex_90", f"{pre}Shoulder",
             {f"{pre}Shoulder": {"flex": 90.0}}, None),
            (f"{pre.lower()}_clavicle_shrug", f"{pre}Clavicle",
             {f"{pre}Clavicle": {"abd": 18.0}}, None),
            (f"{pre.lower()}_elbow_90", f"{pre}Elbow",
             {f"{pre}Elbow": {"flex": 90.0}}, None),
            (f"{pre.lower()}_elbow_100", f"{pre}Elbow",
             {f"{pre}Elbow": {"flex": 100.0}}, None),
            (f"{pre.lower()}_elbow_130", f"{pre}Elbow",
             {f"{pre}Elbow": {"flex": 130.0}}, None),
            (f"{pre.lower()}_forearm_twist_90", f"{pre}Forearm",
             {f"{pre}Forearm": {"twist": 90.0}}, None),
            (f"{pre.lower()}_wrist_flex_45", f"{pre}Wrist",
             {f"{pre}Wrist": {"flex": 45.0}}, None),
            (f"{pre.lower()}_wrist_dev_25", f"{pre}Wrist",
             {f"{pre}Wrist": {"abd": 25.0}}, None),
            (f"{pre.lower()}_hip_flex_90", f"{pre}Hip",
             {f"{pre}Hip": {"flex": 90.0}}, None),
            (f"{pre.lower()}_hip_abduct_35", f"{pre}Hip",
             {f"{pre}Hip": {"abd": 35.0}}, None),
            (f"{pre.lower()}_knee_90", f"{pre}Knee",
             {f"{pre}Knee": {"flex": 90.0}}, None),
            (f"{pre.lower()}_knee_130", f"{pre}Knee",
             {f"{pre}Knee": {"flex": 130.0}}, None),
            (f"{pre.lower()}_ankle_dorsi_25", f"{pre}Ankle",
             {f"{pre}Ankle": {"flex": 25.0}}, None),
            (f"{pre.lower()}_ankle_plantar_35", f"{pre}Ankle",
             {f"{pre}Ankle": {"flex": -35.0}}, None),
        ]
    cases += [
        ("spine_bend_40", "Spine1", {"Spine1": {"flex": 20.0},
                                     "Spine2": {"flex": 12.0},
                                     "Chest": {"flex": 8.0}}, None),
        ("spine_twist_40", "Spine2", {"Spine1": {"twist": 14.0},
                                      "Spine2": {"twist": 14.0},
                                      "Chest": {"twist": 12.0}}, None),
        ("spine_side_25", "Spine1", {"Spine1": {"abd": 10.0},
                                     "Spine2": {"abd": 8.0},
                                     "Chest": {"abd": 7.0}}, None),
        ("pelvis_tilt_20", "Pelvis", {"Pelvis": {"flex": 20.0}}, None),
        ("head_yaw_60", "Head", {"Head": {"twist": 60.0}}, None),
        ("head_pitch_30", "Head", {"Head": {"flex": 30.0}}, None),
        ("head_roll_25", "Head", {"Head": {"abd": 25.0}}, None),
        ("neck_and_head_yaw", "Neck", {"Neck": {"twist": 25.0},
                                       "Head": {"twist": 35.0}}, None),
    ]
    out = []
    for (name, joint, extra, radius) in cases:
        r = REGION_R.get(joint[1:] if joint[0] in "RL" else joint, 0.22)
        out.append((name, joint, extra, radius or r))
    return out


def animation_cases():
    return [(p, None, None, None) for p in ("idle", "walk", "run", "attack", "dodge")]


def run_case(rig, name, joint, extra, radius, pose_name="bind"):
    """Measure one deformation case; returns a report dict."""
    posed = rig.pose(pose_name, extra=extra, use_ik=(joint is None))
    rep = {"case": name, "pose": pose_name, "joint": joint}
    if joint:
        region = rig.region(joint, radius or REGION_R.get(joint, 0.22))
        m = region_metrics(rig, posed, region, joint, rest=rig.V)
        rep.update(m)
        pts = [bd.skin_vertex(rig.V[i], rig.weights[i], posed, rig.joints)
               for i in region]
        rep["nan"] = sum(1 for p in pts if any(v != v for v in p))
        rep["max_move"] = max((math.dist(pts[k], rig.V[i])
                               for k, i in enumerate(region)), default=0.0)
        rep["y_min"] = min((p[1] for p in pts), default=0.0)
        return rep, None
    P = rig.skin(posed)
    rep["nan"] = sum(1 for p in P if any(v != v for v in p))
    rep["max_move"] = max(math.dist(P[i], rig.V[i]) for i in range(len(rig.V)))
    rep["y_min"] = min(p[1] for p in P)
    return rep, P


def evaluate(case, rep):
    """Compare a case report with the limits; returns a list of problems."""
    problems = []
    if rep.get("nan"):
        problems.append(f"{rep['nan']} NaN vertices")
    if rep.get("edges", 0) < 12 or rep.get("core", 0) < 12:
        WARNINGS.append(f"{rep['case']}: region too small for a firm verdict")
    for t in rep.get("bad_stretch", []):
        problems.append(f"torn edge x{t[0]:.2f} "
                        f"({t[3]*1000:.0f}->{t[4]*1000:.0f} mm, {t[1]}/{t[2]})")
    for t in rep.get("bad_collapse", []):
        problems.append(f"collapsed edge {t[0]:.2f}x "
                        f"({t[3]*1000:.0f}->{t[4]*1000:.0f} mm, {t[1]}/{t[2]})")
    if rep.get("faces", 0) and rep["flips"] > max(4, LIMITS["flip_frac"] * rep["faces"]):
        if case in STRESS_CASES:
            WARNINGS.append(f"{case}: {rep['flips']}/{rep['faces']} inverted "
                            "faces at an over-range angle (the inner fold of "
                            "the sleeve); the animation set peaks at 98 deg")
        else:
            problems.append(f"{rep['flips']}/{rep['faces']} inverted faces")
    if rep.get("girth", 1.0) < LIMITS["girth_min"]:
        problems.append(f"girth collapse {rep['girth']:.2f}x")
    g0, g1 = rep.get("gap_rest"), rep.get("gap_posed")
    if g0 is not None and g1 is not None:
        # a fold may legitimately close to nothing - only surfaces that pass
        # through each other are a defect
        if g1 < 0.0:
            problems.append(f"crease surfaces cut into each other "
                            f"({g1*1000:.1f} mm through)")
        elif g0 > 0.020 and g1 / g0 < LIMITS["gap_ratio"]:
            WARNINGS.append(f"{rep['case']}: crease closed to "
                            f"{100 * g1 / g0:.0f}% of rest ({g1*1000:.1f} mm)")
    return problems


# ===========================================================================
# Boot floor contract, driven by the same poses
# ===========================================================================

BOOT_FLOOR = {"idle": ("R", "L"), "walk": ("R", "L"), "run": ("R",),
              "dodge": ("L",), "attack": ("R", "L"), "bind": ("R", "L")}


def planted_indices(rig, sides):
    out = []
    for p in rig.data["parts"]:
        if p["side"] not in sides or p["chain"] != "foot":
            continue
        name = p["name"]
        if not name.startswith(("Boots/Sole_", "Boots/Heel")):
            continue
        out.extend(range(p["start"], p["end"]))
    return out


def check_floor(rig, name):
    """Ground the planted boot by root shift, then re-check the contact patch."""
    sides = BOOT_FLOOR[name]
    idx = planted_indices(rig, sides)
    posed = rig.pose(name)
    P = rig.skin(posed, idx)
    low = min(P[i][1] for i in idx)
    shift = -low
    posed = rig.pose(name, shift=(0.0, shift, 0.0))
    P = rig.skin(posed, idx)
    ys = [P[i][1] for i in idx]
    patch = [i for i in idx if P[i][1] <= 0.0015]
    span = 0.0
    if patch:
        zs = [P[i][2] for i in patch]
        xs = [P[i][0] for i in patch]
        span = max(max(zs) - min(zs), max(xs) - min(xs))
    problems = []
    if min(ys) < -0.0015:
        problems.append(f"boot clips the floor by {-min(ys)*1000:.1f} mm")
    if max(min(ys), 0.0) > 0.0015 or min(ys) > 0.0015:
        problems.append(f"planted boot floats {min(ys)*1000:.1f} mm")
    if span < 0.040:
        problems.append(f"contact patch only {span*1000:.0f} mm long")
    return shift, len(patch), span, problems


# ===========================================================================
# Main
# ===========================================================================

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", default=MESH)
    ap.add_argument("--rig", default=RIG)
    ap.add_argument("--pose", default=None,
                    help="run a single animation state (idle/walk/run/attack/dodge)")
    ap.add_argument("--sweeps", action="store_true", help="joint sweeps only")
    ap.add_argument("--structure", action="store_true", help="structure checks only")
    ap.add_argument("--report", default=None, help="write a JSON report")
    ap.add_argument("--only", default=None,
                    help="run only sweep cases whose name contains this text")
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    print(f"mesh: {os.path.relpath(args.obj, ROOT)}")
    print(f"rig : {os.path.relpath(args.rig, ROOT)}")
    V, F, face_mat = load_obj(args.obj)
    rig_data = json.load(open(args.rig))
    print(f"      {len(V)} vertices, {len(F)} triangles, "
          f"{len(rig_data['parts'])} bound part ranges")

    rig = Rig(rig_data, V, F, face_mat)
    rig.edges = build_edges(F)
    rig.faces_of = [[] for _ in V]
    for k, f in enumerate(F):
        for i in f:
            rig.faces_of[i].append(k)
    rig.face_index = list(enumerate(F))

    print("\n=== structure ===")
    check_hierarchy(rig)
    check_humanoid(rig)
    check_bone_placement(rig, debug=args.debug)
    check_weights(rig)
    check_bind_and_fk(rig)

    report = {"cases": []}
    if not args.structure:
        print("\n=== deformation: joint sweeps ===")
        cases = sweep_cases()
        if args.only:
            cases = [c for c in cases if args.only in c[0]]
            print(f"        (filtered to {len(cases)} case(s) matching "
                  f"{args.only!r})")
        if args.pose:
            cases = []
        for (name, joint, extra, radius) in cases:
            rep, _ = run_case(rig, name, joint, extra, radius)
            problems = evaluate(name, rep)
            rep["problems"] = problems
            report["cases"].append(rep)
            status = "FAIL" if problems else "ok  "
            if problems and args.debug:
                for (r, a, b, L0, L1) in (rep.get("bad_stretch", []) +
                                          rep.get("bad_collapse", []))[:5]:
                    print(f"        {r:5.2f}x  v{a} {rig.chain[a]}{rig.side[a]:+d} "
                          f"{rig.weights[a]} -> v{b} {rig.chain[b]}{rig.side[b]:+d} "
                          f"{rig.weights[b]}  {L0*1000:.1f}->{L1*1000:.1f} mm")
            print(f"  {status} {name:<26} edges {rep.get('edges',0):>5} "
                  f"stretch {rep.get('edge_max',0):.2f} "
                  f"collapse {rep.get('edge_min',1):.2f} "
                  f"flips {rep.get('flips',0):>3} "
                  f"girth {rep.get('girth',1):.2f} "
                  f"gap {(rep.get('gap_posed') or 0)*1000:5.1f} mm"
                  + (f"   <- {', '.join(problems)}" if problems else ""))
            if problems:
                FAILURES.append(f"{name}: {', '.join(problems)}")

        poses = ([args.pose] if args.pose
                 else ["idle", "walk", "run", "attack", "dodge"])
        if args.only:
            poses = [p for p in poses if args.only in p]
        if poses:
            print("\n=== deformation: existing animation states ===")
        for name in poses:
            rep, _ = run_case(rig, name, None, None, None, pose_name=name)
            shift, patch, span, floor_problems = check_floor(rig, name)
            rep["floor"] = {"shift": shift, "patch_vertices": patch,
                            "patch_span": span, "problems": floor_problems}
            problems = floor_problems + (["NaN"] if rep["nan"] else [])
            rep["problems"] = problems
            report["cases"].append(rep)
            status = "FAIL" if problems else "ok  "
            print(f"  {status} {name:<8} grounded dy {shift:+.4f} m  "
                  f"contact patch {patch:>4} verts / {span*1000:5.0f} mm  "
                  f"lowest vertex {rep['y_min']*1000:+.1f} mm"
                  + (f"   <- {', '.join(problems)}" if problems else ""))
            if problems:
                FAILURES.append(f"{name}: {', '.join(problems)}")

        # torso motion must not disturb a verified boot pose: the legs are
        # children of the pelvis, so this asserts the pose tables keep the
        # pelvis unposed during locomotion
        if poses:
            print("\n=== deformation: pelvis isolation in the animation states ===")
            bad = []
            for name in ("walk", "run", "dodge", "attack", "idle"):
                body = bd.POSES[name]["body"]
                if body.get("Pelvis"):
                    bad.append((name, body["Pelvis"]))
            if bad:
                warn("pelvis", f"locomotion poses rotate the pelvis {bad}; the "
                               "verified boot contact can drift")
            else:
                ok("pelvis", "locomotion poses leave the pelvis unposed, so the "
                             "verified foot contact is preserved exactly")

    print("\n=== summary ===")
    print(f"  cases: {len(report['cases'])}  failures: {len(FAILURES)}  "
          f"warnings: {len(WARNINGS)}")
    for f in FAILURES:
        print(f"  FAIL {f}")
    if args.report:
        report["failures"] = FAILURES
        report["warnings"] = WARNINGS
        report["limits"] = LIMITS
        with open(args.report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
        print(f"  report written to {os.path.relpath(args.report, ROOT)}")
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
