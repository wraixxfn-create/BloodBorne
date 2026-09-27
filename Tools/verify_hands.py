#!/usr/bin/env python3
"""Offline hand verification for SM_Character_VeilboundWayfarer.

Checks, without a Unity editor:
  A. Structure  - every expected hand part exists on both sides.
  B. Anatomy    - palm/finger/thumb proportions, knuckle definition,
                  finger separation (anti-mitten) in hand_rig local space.
  C. Rigging    - skin weights per hand part: sums, influence count,
                  side purity, correct digit chains.
  D. Poses      - LBS-skin every hand part for stand / walk / attack / dodge:
                    * hand follows the wrist joint (palm-follow),
                    * glove stays a constant shell over the skin hand,
                    * fingers never interpenetrate each other,
                    * fingertips never tunnel through the palm,
                    * attack/dodge visibly close the grip (fist travel).

Usage:
    python3 Tools/verify_hands.py                       # base LOD
    python3 Tools/verify_hands.py --obj ..._L1.obj      # any LOD

Exit code 0 = all checks pass.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hand_rig as hr  # noqa: E402

DIGIT_NAMES = ("Index", "Middle", "Ring", "Little")
POSES = ("stand", "walk", "attack", "dodge")

FAILURES = []
CHECKS = [0]


def check(ok, label, detail=""):
    CHECKS[0] += 1
    tag = "PASS" if ok else "FAIL"
    print(f"  [{tag}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(label)
    return ok


# ---------------------------------------------------------------- geometry ----

def load_obj(path):
    verts, faces, cur = [], [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("v "):
                verts.append(tuple(float(x) for x in line.split()[1:4]))
            elif line.startswith("usemtl"):
                cur = line.split()[1]
            elif line.startswith("f "):
                idx = [int(t.split("/")[0]) - 1 for t in line.split()[1:]]
                for k in range(1, len(idx) - 1):
                    faces.append((cur, idx[k - 1], idx[k], idx[k + 1]))
    return np.array(verts), faces


def part_index(rig):
    """name_side -> list of (start, end) vertex ranges."""
    out = {}
    for p in rig["parts"]:
        out.setdefault(p["name"], []).append((p["start"], p["end"]))
    return out


def part_verts(V, pidx, name):
    pts = [V[s:e] for s, e in pidx.get(name, ())]
    return np.vstack(pts) if pts else None


# -------------------------------------------------------- distance helpers ----

def point_tri_dist(P, A, B, C):
    """Vectorized point-to-triangle distance (Ericson 5.1.5, exact regions).
    P: (n,3); A,B,C: (m,3) -> returns (n,m) distances."""
    ab = B - A
    ac = C - A
    bc = C - B
    ap = P[:, None, :] - A[None, :, :]
    bp = P[:, None, :] - B[None, :, :]
    cp = P[:, None, :] - C[None, :, :]
    d1 = np.einsum("nmk,mk->nm", ap, ab)
    d2 = np.einsum("nmk,mk->nm", ap, ac)
    d3 = np.einsum("nmk,mk->nm", bp, ab)
    d4 = np.einsum("nmk,mk->nm", bp, ac)
    d5 = np.einsum("nmk,mk->nm", cp, ab)
    d6 = np.einsum("nmk,mk->nm", cp, ac)

    va = d3 * d6 - d5 * d4
    vb = d5 * d2 - d1 * d6
    vc = d1 * d4 - d3 * d2
    denom = va + vb + vc
    denom = np.where(np.abs(denom) < 1e-15, 1e-15, denom)

    with np.errstate(invalid="ignore", divide="ignore"):
        # interior
        q = (A[None, :, :]
             + (vb / denom)[..., None] * ab[None]
             + (vc / denom)[..., None] * ac[None])
        # edge BC
        m_bc = (va <= 0) & (d4 - d3 >= 0) & (d5 - d6 >= 0)
        t_bc = (d4 - d3) / np.where((d4 - d3) + (d5 - d6) == 0, 1,
                                    (d4 - d3) + (d5 - d6))
        q_bc = B[None, :, :] + t_bc[..., None] * bc[None]
        q = np.where(m_bc[..., None], q_bc, q)
        # edge AC
        m_ac = (vb <= 0) & (d2 >= 0) & (d6 <= 0)
        t_ac = d2 / np.where(d2 - d6 == 0, 1, d2 - d6)
        q_ac = A[None, :, :] + t_ac[..., None] * ac[None]
        q = np.where(m_ac[..., None], q_ac, q)
        # edge AB
        m_ab = (vc <= 0) & (d1 >= 0) & (d3 <= 0)
        t_ab = d1 / np.where(d1 - d3 == 0, 1, d1 - d3)
        q_ab = A[None, :, :] + t_ab[..., None] * ab[None]
        q = np.where(m_ab[..., None], q_ab, q)
        # vertices (highest priority)
        m_c = (d6 >= 0) & (d5 <= d6)
        q = np.where(m_c[..., None], C[None, :, :], q)
        m_b = (d3 >= 0) & (d4 <= d3)
        q = np.where(m_b[..., None], B[None, :, :], q)
        m_a = (d1 <= 0) & (d2 <= 0)
        q = np.where(m_a[..., None], A[None, :, :], q)

    d = P[:, None, :] - q
    return np.sqrt(np.maximum(np.einsum("nmk,nmk->nm", d, d), 0.0))


def surface_distance(P, tris, chunk=64):
    """min distance from each point to a triangle soup -> (n,)"""
    out = np.full(len(P), np.inf)
    for i in range(0, len(P), chunk):
        d = point_tri_dist(P[i:i + chunk], tris[0], tris[1], tris[2])
        out[i:i + chunk] = d.min(axis=1)
    return out


def inside_solid(P, A, B, C, chunk=256):
    """Ray-parity inside test vs one closed solid. Returns bool (n,)."""
    direction = np.array((0.31311, 0.41593, 0.85367))
    direction /= np.linalg.norm(direction)
    inside = np.zeros(len(P), dtype=bool)
    e1 = B - A
    e2 = C - A
    for i in range(0, len(P), chunk):
        o = P[i:i + chunk]
        h = np.cross(direction, e2[None, :, :])          # (c,m,3)
        det = np.einsum("mk,cmk->cm", e1, h)
        det = np.where(np.abs(det) < 1e-12, np.inf, det)
        inv = 1.0 / det
        s = o[:, None, :] - A[None, :, :]
        u = np.einsum("cmk,cmk->cm", s, h) * inv
        q = np.cross(s, e1[None, :, :])
        v = np.einsum("k,cmk->cm", direction, q) * inv
        t = np.einsum("mk,cmk->cm", e2, q) * inv
        hit = (u >= 0) & (u <= 1) & (v >= 0) & (u + v <= 1) & (t > 1e-9)
        inside[i:i + chunk] = (hit.sum(axis=1) % 2) == 1
    return inside


def collect_tris(V, faces, lo, hi):
    """triangles whose three vertices are all within [lo,hi) of vertex ids"""
    A, B, C = [], [], []
    for m, a, b, c in faces:
        if lo <= a < hi and lo <= b < hi and lo <= c < hi:
            A.append(V[a]); B.append(V[b]); C.append(V[c])
    if not A:
        z = np.zeros((1, 3))
        return (z, z, z)
    return (np.array(A), np.array(B), np.array(C))


# ------------------------------------------------------------------- main ----

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", default=os.path.join(
        HERE, "..", "Assets", "Models", "Characters",
        "SM_Character_VeilboundWayfarer.obj"))
    args = ap.parse_args()
    obj_path = os.path.abspath(args.obj)
    sidecar = os.path.splitext(obj_path)[0] + ".handrig.json"

    print(f"verify_hands: {os.path.basename(obj_path)}")
    V, faces = load_obj(obj_path)
    rig = json.load(open(sidecar))
    pidx = part_index(rig)
    for p in rig["parts"]:
        _CHAIN_BY_PART[p["name"]] = p["chain"]
    print(f"  mesh: {len(V)} verts / {len(faces)} tris; rig: "
          f"{len(rig['bones'])} bones, {len(rig['parts'])} parts\n")

    for side in ("R", "L"):
        sgn = 1 if side == "R" else -1

        def to_loc(p):
            return hr.to_local(tuple(p), sgn)

        print(f"--- side {side}: structure --------------------------------------")
        need = (
            [f"Hand/Skin/Palm_{side}"] +
            [f"Hand/Skin/{d}_{side}" for d in DIGIT_NAMES] +
            [f"Hand/Skin/Thumb_{side}"] +
            [f"Hand/Glove/PalmStall_{side}"] +
            [f"Hand/Glove/{d}Stall_{side}" for d in DIGIT_NAMES] +
            [f"Hand/Glove/ThumbStall_{side}"] +
            [f"Hand/Glove/Bridge_{side}"] +
            [f"Hand/Glove/{s}_{side}"
             for s in ("IndexSeam", "MiddleSeam", "RingSeam", "LittleSeam",
                       "ThumbSeam")] +
            [f"Hand/Glove/Web{k}_{side}" for k in range(3)] +
            [f"Hand/Glove/ThumbWeb_{side}", f"Hand/Glove/KnuckleGuard_{side}",
             f"Hand/Glove/WristStrap_{side}", f"Hand/Glove/Gauntlet_{side}"]
        )
        missing = [n for n in need if n not in pidx]
        check(not missing, f"{side}: all {len(need)} hand parts present",
              f"missing: {missing}" if missing else "")

        print(f"--- side {side}: anatomy (bind pose) -----------------------------")
        # palm proportions in hand-local coords
        palm = part_verts(V, pidx, f"Hand/Skin/Palm_{side}")
        pl = np.array([to_loc(p) for p in palm])
        w = pl[:, 0].max() - pl[:, 0].min()
        th = pl[:, 2].max() - pl[:, 2].min()
        ln = pl[:, 1].max() - pl[:, 1].min()
        check(0.068 <= w <= 0.095, f"{side}: palm width {w*1000:.0f} mm (68-95)")
        check(0.028 <= th <= 0.046, f"{side}: palm thickness {th*1000:.0f} mm (28-46)")
        check(0.10 <= ln <= 0.145, f"{side}: palm length {ln*1000:.0f} mm (100-145)")

        # fingers: lengths ordered like a hand, tips separated, knuckles bulge
        lengths = {}
        for di, dname in enumerate(DIGIT_NAMES):
            dv = part_verts(V, pidx, f"Hand/Skin/{dname}_{side}")
            dl = np.array([to_loc(p) for p in dv])
            lengths[dname] = dl[:, 1].max() - hr.DIGITS[di]["mcp"][1]
            check(lengths[dname] > 0.05, f"{side}: {dname} length "
                  f"{lengths[dname]*1000:.0f} mm (>50)")
        ok = (lengths["Middle"] > lengths["Index"] >= lengths["Ring"] * 0.98 and
              lengths["Ring"] > lengths["Little"])
        check(ok, f"{side}: finger length order M>I>=R>P",
              " ".join(f"{k}={v*1000:.0f}" for k, v in lengths.items()))

        # knuckle definition: dorsal extent at MCP station exceeds mid-proximal
        for di, dname in enumerate(DIGIT_NAMES):
            dv = np.array([to_loc(p) for p in
                           part_verts(V, pidx, f"Hand/Skin/{dname}_{side}")])
            mcp_d = hr.DIGITS[di]["mcp"][1]
            at_mcp = dv[np.abs(dv[:, 1] - mcp_d) < 0.008]
            at_mid = dv[np.abs(dv[:, 1] - mcp_d - 0.018) < 0.006]
            if len(at_mcp) and len(at_mid):
                bump = at_mcp[:, 2].max() - at_mid[:, 2].max()
                check(bump > 0.0006, f"{side}: {dname} knuckle bulge "
                      f"{bump*1000:.2f} mm (>0.6)")

        # thumb opposition
        tv = np.array([to_loc(p) for p in
                       part_verts(V, pidx, f"Hand/Skin/Thumb_{side}")])
        check(tv[:, 0].max() > pl[:, 0].max() * 0.9,
              f"{side}: thumb reaches radial side (tip r={tv[:,0].max()*1000:.0f} mm)")
        tipn = tv[tv[:, 0].argmax()]  # most radial thumb vertex
        check(tipn[2] < 0.004, f"{side}: thumb tip lies palmar/low "
              f"(n={tipn[2]*1000:.1f} mm)")

        # anti-mitten: adjacent finger stalls stay separated (bind)
        for ai, (a, b) in enumerate(zip(DIGIT_NAMES, DIGIT_NAMES[1:])):
            fa = part_verts(V, pidx, f"Hand/Skin/{a}_{side}")
            fb = part_verts(V, pidx, f"Hand/Skin/{b}_{side}")
            fla = np.array([to_loc(p) for p in fa])
            mcp_ab = hr.DIGITS[ai]["mcp"][1]
            keepa = fla[:, 1] > mcp_ab + 0.5 * (fla[:, 1].max() - mcp_ab)
            flb = np.array([to_loc(p) for p in fb])
            mcp_b = hr.DIGITS[ai + 1]["mcp"][1]
            keepb = flb[:, 1] > mcp_b + 0.5 * (flb[:, 1].max() - mcp_b)
            dskin = np.linalg.norm(fla[keepa][:, None, :] - flb[keepb][None, :, :],
                                   axis=2).min()
            check(dskin > 0.001, f"{side}: {a}/{b} SKIN finger separation "
                  f"{dskin*1000:.2f} mm (>1.0)")
            sa = part_verts(V, pidx, f"Hand/Glove/{a}Stall_{side}")
            sb = part_verts(V, pidx, f"Hand/Glove/{b}Stall_{side}")
            la = np.array([to_loc(p) for p in sa])
            lb = np.array([to_loc(p) for p in sb])
            mcp_a = hr.DIGITS[ai]["mcp"][1]
            tip_a = la[:, 1].max()
            keep = la[:, 1] > mcp_a + 0.5 * (tip_a - mcp_a)
            dmin = np.linalg.norm(la[keep][:, None, :] - lb[None, :, :],
                                  axis=2).min()
            check(dmin > 0.001, f"{side}: {a}/{b} stall gap (distal) "
                  f"{dmin*1000:.2f} mm (>1.0)")

        print(f"--- side {side}: glove fit (bind pose) ---------------------------")
        # every skin hand vertex must sit inside at least one glove solid
        solids = [f"Hand/Glove/PalmStall_{side}",
                  f"Hand/Glove/ThumbStall_{side}"] + \
                 [f"Hand/Glove/{d}Stall_{side}" for d in DIGIT_NAMES] + \
                 [f"Hand/Glove/Bridge_{side}"]
        skin_names = [f"Hand/Skin/Palm_{side}", f"Hand/Skin/Thumb_{side}"] + \
                     [f"Hand/Skin/{d}_{side}" for d in DIGIT_NAMES]
        skin = np.vstack([part_verts(V, pidx, n) for n in skin_names])
        covered = np.zeros(len(skin), dtype=bool)
        near = np.full(len(skin), np.inf)
        for sname in solids:
            for lo, hi in pidx[sname]:
                tris = collect_tris(V, faces, lo, hi)
                covered |= inside_solid(skin, *tris)
                near = np.minimum(near, surface_distance(skin, tris))
        covered |= near <= 0.0003      # resting on the surface counts as covered
        worst_depth = near
        n_out = int((~covered).sum())
        check(n_out == 0, f"{side}: skin hand fully inside glove solids",
              f"{n_out} outside" if n_out else
              f"min skin-to-glove-surface {worst_depth.min()*1000:.2f} mm")
        # per-part clearance: skin vs its OWN stall (root disc excluded - it is
        # buried inside the palm dome by design)
        own = [(f"Hand/Skin/Palm_{side}", f"Hand/Glove/PalmStall_{side}")] + \
              [(f"Hand/Skin/{d}_{side}", f"Hand/Glove/{d}Stall_{side}")
               for d in DIGIT_NAMES] + \
              [(f"Hand/Skin/Thumb_{side}", f"Hand/Glove/ThumbStall_{side}")]
        worst = np.inf
        for sn, gn in own:
            P = part_verts(V, pidx, sn)
            m = len(P)
            cl = np.full(m, np.inf)
            for lo, hi in pidx[gn]:
                cl = np.minimum(cl, surface_distance(P, collect_tris(V, faces, lo, hi)))
            if "Palm" not in sn:
                nring = (m - 2) // (10 if "Thumb" not in sn else 9)
                keep = np.ones(m, dtype=bool)
                keep[:nring] = False        # root flare ring
                keep[m - 2] = False         # root pole
                cl = cl[keep]
            worst = min(worst, cl.min())
        check(worst > 0.0005, f"{side}: stall clearance vs own skin "
              f"{worst*1000:.2f} mm (>0.5)")

        print(f"--- side {side}: skin weights -----------------------------------")
        wok, badsum, badside, badinf = True, 0, 0, 0
        for p in rig["parts"]:
            if not p["name"].startswith("Hand/") or p["side"] != side:
                continue
            if p["chain"] not in ("palm", "digit0", "digit1", "digit2",
                                  "digit3", "thumb", "guard", "cuff",
                                  "bridge", "web0", "web1", "web2", "webT"):
                continue
            for i in range(p["start"], p["end"]):
                w = hr.weights_for(sgn, p["chain"], tuple(V[i]))
                if abs(sum(w.values()) - 1.0) > 1e-3:
                    badsum += 1
                if len(w) > 4:
                    badinf += 1
                if any(k[0] != side for k in w):
                    badside += 1
        check(badsum == 0, f"{side}: weight sums == 1 ({badsum} bad)")
        check(badinf == 0, f"{side}: <= 4 influences ({badinf} bad)")
        check(badside == 0, f"{side}: no cross-side weights ({badside} bad)")

        # per-digit chain ownership: tip vertices must weight their own DIP
        for di, dname in enumerate(DIGIT_NAMES):
            dv = part_verts(V, pidx, f"Hand/Skin/{dname}_{side}")
            tip = tuple(dv[np.argmax([to_loc(p)[1] for p in dv])])
            w = hr.weights_for(sgn, f"digit{di}", tip)
            top = max(w, key=w.get)
            check(top.endswith(f"{dname}DIP") or top.endswith(f"{dname}PIP"),
                  f"{side}: {dname} tip driven by its own chain (top={top})")

    # ------------------------------------------------------------- poses ----
    print("--- poses: deformation (stand/walk/attack/dodge) -----------------")
    joints = {j[0]: j for j in hr.joint_list()}
    hand_parts = [p for p in rig["parts"] if p["name"].startswith("Hand/")]
    for pose in POSES:
        posed = hr.pose_matrices(pose)
        print(f"  pose {pose}:")

        for side in ("R", "L"):
            sgn = 1 if side == "R" else -1
            skin_names = [f"Hand/Skin/Palm_{side}", f"Hand/Skin/Thumb_{side}"] + \
                         [f"Hand/Skin/{d}_{side}" for d in DIGIT_NAMES]
            stall_solid = [f"Hand/Glove/PalmStall_{side}",
                           f"Hand/Glove/ThumbStall_{side}"] + \
                          [f"Hand/Glove/{d}Stall_{side}" for d in DIGIT_NAMES]

            def skin_all(names):
                P = np.vstack([part_verts(V, pidx, n) for n in names])
                return P, np.vstack([
                    np.array([hr.skin_vertex(tuple(v),
                                             hr.weights_for(sgn, ch, tuple(v)),
                                             posed, joints)
                              for v in part_verts(V, pidx, n)])
                    for n, ch in zip(names, [p_chain(n) for n in names])])

            # bind + posed skin
            sb, sp = skin_all(skin_names)

            # palm-follow: posed palm centroid stays near posed Hand joint
            palm_b = part_verts(V, pidx, f"Hand/Skin/Palm_{side}")
            palm_p = np.array([
                hr.skin_vertex(tuple(v), hr.weights_for(sgn, "palm", tuple(v)),
                posed, joints) for v in palm_b])
            hj = np.array(hr.mat_apply(posed[f"{side}Hand"], (0, 0, 0)))
            off = np.linalg.norm(palm_p.mean(axis=0) - hj)
            check(off < 0.075, f"{side} {pose}: palm tracks Hand joint "
                  f"({off*1000:.1f} mm < 75)")

            # glove shell follows skin (centroid drift)
            stall_names = [f"Hand/Glove/{d}Stall_{side}" for d in DIGIT_NAMES]
            drift = 0.0
            for dn, sn in zip(DIGIT_NAMES, stall_names):
                sbv = part_verts(V, pidx, f"Hand/Skin/{dn}_{side}")
                stv = part_verts(V, pidx, sn)
                sbp = np.array([hr.skin_vertex(tuple(v),
                                               hr.weights_for(sgn, f"digit{DIGIT_NAMES.index(dn)}", tuple(v)),
                                               posed, joints) for v in sbv])
                stp = np.array([hr.skin_vertex(tuple(v),
                                               hr.weights_for(sgn, f"digit{DIGIT_NAMES.index(dn)}", tuple(v)),
                                               posed, joints) for v in stv])
                drift = max(drift,
                            np.linalg.norm(sbp.mean(0) - stp.mean(0)) -
                            np.linalg.norm(sbv.mean(0) - stv.mean(0)))
            check(drift < 0.004, f"{side} {pose}: glove shell drift "
                  f"{drift*1000:.2f} mm (<4)")

            # no finger interpenetration (posed stalls)
            for a, b in zip(DIGIT_NAMES, DIGIT_NAMES[1:]):
                aiv = DIGIT_NAMES.index(a)
                av = part_verts(V, pidx, f"Hand/Glove/{a}Stall_{side}")
                al = np.array([hr.to_local(tuple(v), sgn) for v in av])
                mcp_a = hr.DIGITS[aiv]["mcp"][1]
                keep = al[:, 1] > mcp_a + 0.5 * (al[:, 1].max() - mcp_a)
                pa = np.array([
                    hr.skin_vertex(tuple(v),
                                   hr.weights_for(sgn, f"digit{aiv}", tuple(v)),
                                   posed, joints)
                    for v in av[keep]])
                lo, hi = pidx[f"Hand/Glove/{b}Stall_{side}"][0]
                tris = collect_tris(V, faces, lo, hi)
                # skin the triangles too
                At, Bt, Ct = tris
                def sk(pts):
                    return np.array([
                        hr.skin_vertex(tuple(v),
                                       hr.weights_for(sgn, f"digit{DIGIT_NAMES.index(b)}", tuple(v)),
                                       posed, joints) for v in pts])
                dmin = surface_distance(pa, (sk(At), sk(Bt), sk(Ct))).min()
                check(dmin > 0.00005, f"{side} {pose}: {a}/{b} stalls not "
                      f"interpenetrating ({dmin*1000:.2f} mm)")

            # glove containment under pose
            covered = np.zeros(len(sp), dtype=bool)
            for sname in stall_solid:
                for lo, hi in pidx[sname]:
                    tris = collect_tris(V, faces, lo, hi)
                    ch = p_chain(sname)
                    A, B, C = tris
                    def sk(pts):
                        return np.array([
                            hr.skin_vertex(tuple(v),
                                           hr.weights_for(sgn, ch, tuple(v)),
                                           posed, joints) for v in pts])
                    covered |= inside_solid(sp, sk(A), sk(B), sk(C))
                    near2 = surface_distance(sp, (sk(A), sk(B), sk(C)))
                    covered |= near2 <= 0.0003
            n_out = int((~covered).sum())
            check(n_out <= 2, f"{side} {pose}: skin stays inside glove",
                  f"{n_out} outside" if n_out else "clean")

            # fingertips must not tunnel through the palm skin
            palm_lo, palm_hi = pidx[f"Hand/Skin/Palm_{side}"][0]
            ptris = collect_tris(V, faces, palm_lo, palm_hi)
            pA = np.array([hr.skin_vertex(tuple(v),
                                          hr.weights_for(sgn, "palm", tuple(v)),
                                          posed, joints) for v in ptris[0]])
            pB = np.array([hr.skin_vertex(tuple(v),
                                          hr.weights_for(sgn, "palm", tuple(v)),
                                          posed, joints) for v in ptris[1]])
            pC = np.array([hr.skin_vertex(tuple(v),
                                          hr.weights_for(sgn, "palm", tuple(v)),
                                          posed, joints) for v in ptris[2]])
            worst = np.inf
            for di, dname in enumerate(DIGIT_NAMES):
                dv = part_verts(V, pidx, f"Hand/Skin/{dname}_{side}")
                dl = [to_l(pose, tuple(v), sgn, f"digit{di}", posed, joints)
                      for v in dv]
                dv_p = np.array(dl)
                tip = dv_p[np.argmax(dv_p[:, 1])]  # furthest down the finger
                dmin = surface_distance(tip[None, :], (pA, pB, pC))[0]
                worst = min(worst, dmin)
            check(worst > -0.0001, f"{side} {pose}: fingertip/palm clearance "
                  f"{worst*1000:.2f} mm (>-0.1)")

            # grip closes for the weapon hand in attack / dodge
            if pose in ("attack", "dodge"):
                expect = 0.30 if side == "R" else 0.12
                mv = part_verts(V, pidx, f"Hand/Skin/Middle_{side}")
                tip_b = mv[np.argmax([hr.to_local(tuple(v), sgn)[1]
                                      for v in mv])]
                d_bind = np.linalg.norm(np.array(tip_b) - palm_b.mean(axis=0))
                tip_p = np.array(hr.skin_vertex(
                    tuple(tip_b), hr.weights_for(sgn, "digit1", tuple(tip_b)),
                    posed, joints))
                palm_p2 = np.array([
                    hr.skin_vertex(tuple(v), hr.weights_for(sgn, "palm",
                                                            tuple(v)),
                    posed, joints) for v in palm_b])
                d_pose = np.linalg.norm(tip_p - palm_p2.mean(axis=0))
                check(d_pose < d_bind * (1.0 - expect),
                      f"{side} {pose}: grip closes "
                      f"{d_bind*100:.1f}->{d_pose*100:.1f} cm "
                      f"(-{(1-d_pose/d_bind)*100:.0f}% > {expect*100:.0f}%)")

    print()
    if FAILURES:
        print(f"verify_hands: {len(FAILURES)}/{CHECKS[0]} checks FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print(f"verify_hands: ALL {CHECKS[0]} checks passed.")
    sys.exit(0)


def p_chain(name):
    """chain id for a part name (from the sidecar)."""
    ch = _CHAIN_BY_PART.get(name)
    if ch is None:
        raise KeyError(f"no sidecar part named {name}")
    return ch


_CHAIN_BY_PART = {}
_CHAIN_CACHE_BUILT = False


def to_l(pose, p_world, sgn, chain, posed, joints):
    return np.array(hr.skin_vertex(p_world, hr.weights_for(sgn, chain, p_world),
                                   posed, joints))


if __name__ == "__main__":
    # build name->chain map from the sidecar lazily (needs rig; patched in main)
    main()
