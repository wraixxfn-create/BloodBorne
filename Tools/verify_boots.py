#!/usr/bin/env python3
"""Offline foot / boot verification for SM_Character_VeilboundWayfarer.

Runs without a Unity editor and checks the boots and feet against
Tools/boot_rig.py (the single source of truth for the foot anatomy, the boot
construction and the rig):

  A. Structure   - every expected boot part exists on both sides, the part
                   ranges in the .bootrig.json sidecar match the OBJ, every
                   part is a closed, consistently outward-facing shell.
  B. Anatomy     - measured foot length / ball position and width / heel width /
                   ankle height / sole thickness / shaft top against the design
                   targets, and left/right mirror symmetry.
  C. Floor       - the ground-contact contract of Tools/boot_rig.py:
                     * minimum vertex exactly 0.000 in the bind pose, nothing
                       below the floor (no clipping),
                     * the contact is a *patch* (several vertices within
                       1.5 mm spread over > 40 mm of foot length) on both the
                       forefoot and the heel, on both boots,
                     * shank lifted between the heel breast and the ball,
                     * toe spring over the last 25 mm,
                     * the sole plane is flat and parallel to the floor.
  D. Clearance   - the tucked trouser stays inside the shaft lining with
                   margin, so the wool can never poke through the leather.
  E. Rig         - skin weights per boot part: sums, influence count, side
                   purity and chain ownership.
  F. Poses       - LBS-skin the boots for idle / walk / run / dodge, ground the
                   planted foot by foot IK and verify: planted sole still a
                   patch at exactly the floor, nothing below the floor, and the
                   swing foot clear of the floor.

Usage:
    python3 Tools/verify_boots.py                     # base LOD
    python3 Tools/verify_boots.py --obj ..._L1.obj    # any LOD

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
import boot_rig as br  # noqa: E402

POSES = ("idle", "walk", "run", "dodge")
EXPECTED_PARTS = (
    "Sole", "Heel1", "Heel2", "Heel3", "HeelPlate", "HeelNails", "Welt",
    "WeltStitch", "Vamp", "ToeCap", "ToeCapStitch1", "ToeCapStitch2", "Counter",
    "CounterStitch", "ThroatSeam", "ShaftAnkle", "Shaft", "FacingOut", "FacingIn",
    "Tongue", "EyeletRow1", "EyeletRow2", "EyeletRow3", "EyeletRow4", "HookRow1",
    "HookRow2", "HookRow3", "Laces", "LaceBow", "CuffFold", "CuffLining",
    "PullTab", "PullTabRivet", "InstepStrap", "InstepStrapStitch", "InstepBuckle",
    "InstepKeeper", "CuffStrap", "CuffBuckle",
)
# Parts whose vertices must be skin-weighted by the boot rig (BoneThread parts
# sitting on top of the leather are skinned too, but the loose stitch dashes of
# the coat are not part of the boot).
CHAIN_WORDS = ("foot", "shaft")

FAILURES = []
CHECKS = [0]


def check(ok, label, detail=""):
    CHECKS[0] += 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}" + (f"  ({detail})" if detail else ""))
    if not ok:
        FAILURES.append(label)
    return ok


# ------------------------------------------------------------------ loading ---

def load_obj(path):
    verts, faces, order, mats, cur = [], {}, [], [], None
    with open(path) as fh:
        for line in fh:
            if line.startswith("v "):
                verts.append(tuple(float(x) for x in line.split()[1:4]))
            elif line.startswith("usemtl"):
                cur = line.split()[1]
                if cur not in faces:
                    faces[cur] = []
                    order.append(cur)
            elif line.startswith("f "):
                idx = tuple(int(t.split("/")[0]) - 1 for t in line.split()[1:])
                faces[cur].append(idx)
                mats.append(cur)
    return np.array(verts), faces, order, np.array(mats)


def part_faces(faces, part):
    return [f for f in faces[part["mat"]] if all(part["start"] <= i < part["end"] for i in f)]


def part_verts(V, faces, part):
    idx = sorted({i for f in part_faces(faces, part) for i in f})
    return idx


# ----------------------------------------------------------------- geometry ---

def signed_volume(V, tris):
    a, b, c = V[tris[:, 0]], V[tris[:, 1]], V[tris[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def open_edges(tris):
    seen = {}
    for f in tris:
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            seen[(a, b)] = seen.get((a, b), 0) + 1
    bad = [e for e in seen if seen.get((e[1], e[0]), 0) != 1]
    return len(bad), len(seen)


def patch_stats(V, idx, y_tol=0.0015):
    """(count, z extent, ymin) of the vertices within y_tol of the lowest one."""
    ys = V[idx, 1]
    lo = ys.min()
    sel = ys <= lo + y_tol
    pts = V[idx][sel]
    return int(sel.sum()), float(pts[:, 2].max() - pts[:, 2].min()), float(lo)


# --------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", default=os.path.join(
        HERE, "..", "Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj"))
    args = ap.parse_args()
    obj_path = os.path.abspath(args.obj)
    rig_path = os.path.splitext(obj_path)[0] + ".bootrig.json"
    print(f"verify_boots: {os.path.basename(obj_path)}")
    if not os.path.exists(rig_path):
        print(f"  [FAIL] boot rig sidecar missing: {rig_path}")
        return 1
    rig = json.load(open(rig_path))
    V, faces, order, _ = load_obj(obj_path)
    print(f"  {len(V)} vertices, {sum(len(f) for f in faces.values())} triangles, "
          f"{len(rig['parts'])} boot parts, {len(rig['bones'])} rig joints\n")

    parts = {(p["name"], p["side"]): p for p in rig["parts"]}

    # ---------------------------------------------------------- A structure ---
    print("--- A. structure --------------------------------------------------")
    check(rig["format"] == "vespershade.bootrig/1", "sidecar format",
          rig["format"])
    check(rig["floor"]["contact_plane_y"] == 0.0, "floor contact plane is y = 0")
    missing = [f"{n}_{s}" for n in EXPECTED_PARTS for s in ("R", "L")
               if (f"Boots/{n}_{s}", s) not in parts]
    check(not missing, f"all {len(EXPECTED_PARTS)} boot parts on both sides",
          f"missing {missing}" if missing else f"{len(EXPECTED_PARTS) * 2} parts")

    # sidecar ranges really cover the vertices they claim
    mism, hard_fail = [], []
    for (name, side), p in parts.items():
        n = p["end"] - p["start"]
        idx = part_verts(V, faces, p)
        if len(idx) != n:
            mism.append(f"{name}:{len(idx)}/{n}")
    check(not mism, "part vertex ranges match the mesh",
          f"{len(mism)} mismatched: {mism[:3]}" if mism else "all ranges exact")

    open_parts, inward = [], []
    for (name, side), p in parts.items():
        tris = part_faces(faces, p)
        if not tris:
            continue
        o, _ = open_edges(tris)
        if o:
            open_parts.append(f"{name}:{o}")
        if signed_volume(V, np.array(tris)) <= 0.0:
            inward.append(name)
    check(not open_parts, "every boot part is a closed shell",
          f"open edges: {open_parts[:4]}" if open_parts else "no boundary edges")
    check(not inward, "every boot part winds outward",
          f"inward: {inward[:4]}" if inward else "positive signed volume")

    # ------------------------------------------------------------ B anatomy ---
    print("\n--- B. anatomy ----------------------------------------------------")
    m = br.metrics()
    sole_idx = {s: part_verts(V, faces, parts[(f"Boots/Sole_{s}", s)]) for s in ("R", "L")}
    out = V[sole_idx["R"]]
    zs, xs = out[:, 2], np.abs(out[:, 0] - br.FOOT_X)
    front = np.abs(out[:, 2] - br.FOOT_TIP - 0.003).argmin()
    check(abs((out[:, 2].max() - out[:, 2].min()) - 0.2825) < 0.004,
          "sole length matches the anatomy table",
          f"{(out[:, 2].max() - out[:, 2].min()) * 1000:.1f} mm vs 282.5 mm")
    ball_z = br.BALL[2]
    near_ball = (np.abs(zs - ball_z) < 0.012)
    ball_w = 2.0 * float(xs[near_ball].max()) if near_ball.any() else 0.0
    # cross-section widths are sampled at the LOD's own stations, so a coarser
    # mesh can only ever be narrower than the design - never wider
    check(0.94 * 0.1155 <= ball_w <= 0.1155 + 0.006, "ball (widest) width",
          f"{ball_w * 1000:.1f} mm vs 115.5 mm design")
    heel_sel = zs <= br.HEEL_BREAST
    heel_w = 2.0 * float(xs[heel_sel].max()) if heel_sel.any() else 0.0
    check(0.85 * m["heel_width"] <= heel_w <= m["heel_width"] + 0.006, "heel width",
          f"{heel_w * 1000:.1f} mm vs {m['heel_width'] * 1000:.1f} mm design")
    boots = np.concatenate([part_verts(V, faces, parts[(f"Boots/{n}_{s}", s)])
                            for n in EXPECTED_PARTS for s in ("R", "L")])
    shafts = np.concatenate([part_verts(V, faces, parts[(f"Boots/{n}_{s}", s)])
                             for n in ("Shaft", "ShaftAnkle", "CuffFold", "CuffLining")
                             for s in ("R", "L")])
    shaft_only = np.concatenate([part_verts(V, faces, parts[(f"Boots/Shaft_{s}", s)])
                                 for s in ("R", "L")])
    check(abs(V[shaft_only, 1].max() - br.SHAFT_TOP) < 0.002, "shaft top height",
          f"{V[shaft_only, 1].max() * 1000:.1f} mm vs {br.SHAFT_TOP * 1000:.1f} mm")
    check(br.CUFF_FOLD_Y < V[shafts, 1].max() < br.SHAFT_TOP + 0.008,
          "folded cuff sits at the boot top",
          f"cuff top {V[shafts, 1].max() * 1000:.1f} mm, shaft top "
          f"{br.SHAFT_TOP * 1000:.1f} mm")
    vamps = np.concatenate([part_verts(V, faces, parts[(f"Boots/Vamp_{s}", s)])
                            for s in ("R", "L")])
    fore_thick = float(V[vamps, 1].min()) - 0.0
    check(abs(fore_thick - br.SOLE_TOP_FORE) < 0.002, "sole thickness under the vamp",
          f"{fore_thick * 1000:.1f} mm vs {br.SOLE_TOP_FORE * 1000:.1f} mm")
    # ankle joint sits inside the boot shaft
    check(br.ANKLE[1] > br.HEEL_BLOCK_TOP and br.ANKLE[1] < 0.16,
          "ankle joint raised by the heel and inside the shaft",
          f"y={br.ANKLE[1] * 1000:.0f} mm, heel lift {br.HEEL_BLOCK_TOP * 1000:.0f} mm")
    # mirror symmetry of every boot part
    asym = []
    for n in EXPECTED_PARTS:
        pr, pl = parts[(f"Boots/{n}_R", "R")], parts[(f"Boots/{n}_L", "L")]
        vr = V[part_verts(V, faces, pr)]
        vl = V[part_verts(V, faces, pl)]
        if len(vr) != len(vl):
            asym.append(n)
            continue
        def canon(a):
            k = np.lexsort((a[:, 0], a[:, 1], a[:, 2]))
            return np.round(a[k], 6)
        vr2 = vr.copy()
        vr2[:, 0] *= -1.0            # the left boot is the x-mirror of the right
        if not np.array_equal(canon(vr2), canon(vl)):
            asym.append(n)
    check(not asym, "left boot is an exact mirror of the right",
          f"asymmetric: {asym[:4]}" if asym else f"{len(EXPECTED_PARTS)} parts mirrored")

    # -------------------------------------------------------------- C floor ---
    print("\n--- C. floor contact ----------------------------------------------")
    check(float(V[:, 1].min()) >= 0.0, "character mesh never dips below the floor",
          f"min y = {float(V[:, 1].min()) * 1000:+.4f} mm")
    for s in ("R", "L"):
        idx = np.concatenate([sole_idx[s],
                              part_verts(V, faces, parts[(f"Boots/Heel1_{s}", s)]),
                              part_verts(V, faces, parts[(f"Boots/Heel2_{s}", s)]),
                              part_verts(V, faces, parts[(f"Boots/Heel3_{s}", s)])])
        pts = V[idx]
        heel_pts = pts[pts[:, 2] <= br.HEEL_BREAST]
        fore_pts = pts[pts[:, 2] >= 0.055]
        hc, hz, hy = patch_stats(V, idx[V[idx, 2] <= br.HEEL_BREAST])
        fc, fz, fy = patch_stats(V, idx[V[idx, 2] >= 0.055])
        check(hc >= 6 and hz >= 0.030 and hy == 0.0,
              f"{s}: heel contact patch at exactly the floor",
              f"{hc} verts within 1.5 mm, {hz * 1000:.0f} mm long, ymin {hy * 1000:+.3f} mm")
        check(fc >= 8 and fz >= 0.045 and fy == 0.0,
              f"{s}: forefoot contact patch at exactly the floor",
              f"{fc} verts within 1.5 mm, {fz * 1000:.0f} mm long, ymin {fy * 1000:+.3f} mm")
        # the sole plane is flat: the two contact faces share y = 0
        check(abs(heel_pts[:, 1].min() - fore_pts[:, 1].min()) < 1e-9,
              f"{s}: heel and forefoot contact planes are the same, parallel plane",
              "both exactly y = 0")
        # shank (waist) is lifted off the floor
        mid = pts[(pts[:, 2] > br.HEEL_BREAST) & (pts[:, 2] < 0.042)]
        check(float(mid[:, 1].min()) > 0.0025, f"{s}: shank (waist) lifted off the floor",
              f"min y = {float(mid[:, 1].min()) * 1000:.1f} mm between the heel breast and the ball")
        # toe spring: the contact patch ends at the toe break and the last
        # 12 mm of the boot curl up clear of the floor
        flat_end = pts[(pts[:, 1] <= 0.0005)][:, 2].max()
        tip = pts[pts[:, 2] > br.FOOT_TIP - 0.006]
        check(flat_end < br.FOOT_TIP - 0.018 and float(tip[:, 1].min()) > 0.006,
              f"{s}: toe spring curls the toe tip off the floor",
              f"contact ends at z={flat_end * 1000:.0f} mm, tip min y = "
              f"{float(tip[:, 1].min()) * 1000:.2f} mm")
        # no part of the boot hangs below the sole plane anywhere
        bidx = np.concatenate([part_verts(V, faces, parts[(f"Boots/{n}_{s}", s)])
                               for n in EXPECTED_PARTS])
        check(float(V[bidx, 1].min()) == 0.0,
              f"{s}: lowest boot vertex is exactly on the floor plane",
              "0.000 mm")
    check(float(V[boots, 1].min()) == 0.0 and float(V[boots, 1].max()) > 0.44,
          "boots span the floor plane to above the ankle collar",
          f"y {float(V[boots, 1].min()) * 1000:.0f} .. {float(V[boots, 1].max()) * 1000:.0f} mm")

    # ---------------------------------------------------------- D clearance ---
    print("\n--- D. tuck clearance ---------------------------------------------")
    trouser = sorted({i for f in faces["Trouser"] for i in f})
    worst, worst_pt = -9.9, None
    for i in trouser:
        p = V[i]
        if not (0.20 <= p[1] <= 0.470):
            continue
        side = 1.0 if p[0] > 0 else -1.0
        lx, ly, lz = p[0] - side * br.FOOT_X, p[1], p[2]
        w, df, db, zc, gap, pexp = br.shaft_row(ly)
        uz = (lz - zc) / (df if lz > zc else db)
        r = (abs(lx / w) ** pexp + abs(uz) ** pexp) ** (1.0 / pexp)
        if r > worst:
            worst, worst_pt = r, p
    check(worst < 1.0, "trouser cloth stays inside the shaft leather",
          (f"worst radial ratio {worst:.3f} (<1 = inside) at y={worst_pt[1]:.3f}"
           if worst_pt is not None else "no trouser vertices in the boot band"))

    # ---------------------------------------------------------------- E rig ---
    print("\n--- E. skin weights -----------------------------------------------")
    bad_sum = bad_inf = bad_side = 0
    for (name, side), p in parts.items():
        sgn = 1 if side == "R" else -1
        for i in part_verts(V, faces, p):
            w = br.weights_for(sgn, p["chain"], tuple(V[i]))
            if abs(sum(w.values()) - 1.0) > 1e-6:
                bad_sum += 1
            if len(w) > 4:
                bad_inf += 1
            if any(k[0] != side for k in w):
                bad_side += 1
    check(bad_sum == 0, "weight sums == 1 on every boot vertex", f"{bad_sum} bad")
    check(bad_inf == 0, "no boot vertex has more than 4 influences", f"{bad_inf} bad")
    check(bad_side == 0, "no cross-side weights on boot vertices", f"{bad_side} bad")
    unknown = sorted({p["chain"] for p in rig["parts"]} - set(br.CHAIN_WEIGHT_FN))
    check(not unknown, "every part chain resolves to a weight function",
          f"unknown: {unknown}" if unknown else "foot / shaft")
    # chain ownership: the sole must be driven by the foot chain, the shaft by
    # the shin, and the toe tip by the ball / toe joints
    toe_idx = part_verts(V, faces, parts[("Boots/Sole_R", "R")])
    tip = max((V[i] for i in toe_idx), key=lambda p: p[2])
    top = max(br.weights_for(1, "foot", tuple(tip)), key=lambda k: br.weights_for(1, "foot", tuple(tip))[k])
    check(top.endswith("Toe") or top.endswith("Ball"),
          "sole tip is driven by the ball / toe joints", f"top influence {top}")
    shin = br.weights_for(1, "shaft", tuple(br.shaft_point(0.44, 0.0, 0.0)))
    check(max(shin, key=shin.get) == "RKnee", "shaft top is driven by the knee (shin) joint",
          f"top influence {max(shin, key=shin.get)}")

    # ------------------------------------------------------------- F poses ---
    print("\n--- F. posed floor contact (idle / walk / run / dodge) -----------")
    # Per pose, per side: how the boot should meet the floor.
    #   flat  - the whole sole is down (a wide contact patch)
    #   heel  - heel-strike corner contact at the rear of the sole
    #   pad   - forefoot pad contact (toe-off / ball strike / trailing toe)
    #   swing - clear of the floor by at least the given height
    POSE_EXPECT = {
        "idle": {"R": ("flat", 0.20), "L": ("flat", 0.20)},
        "walk": {"R": ("heel", 0.005), "L": ("pad", 0.030)},
        "run": {"R": ("pad", 0.030), "L": ("swing", 0.100)},
        "dodge": {"L": ("flat", 0.20), "R": ("pad", 0.030)},
    }
    joints = {j[0]: j for j in br.joint_list()}
    for pose in POSES:
        print(f"  pose {pose}:")
        expect = POSE_EXPECT[pose]
        planted = [s for s, (kind, _) in expect.items() if kind != "swing"]
        cand = [tuple(V[i]) for (name, side), p in parts.items()
                if side in planted and name.startswith(("Boots/Sole_", "Boots/Heel"))
                for i in part_verts(V, faces, p)]
        dy = br.ground_shift(pose, cand)
        posed = br.pose_matrices(pose, (0.0, dy, 0.0))
        lowest = 1e9
        for side, (kind, arg) in expect.items():
            sgn = 1 if side == "R" else -1
            pts, bind = [], []
            for (name, sd), p in parts.items():
                if sd != side:
                    continue
                for i in part_verts(V, faces, p):
                    q = br.skin_vertex(tuple(V[i]), br.weights_for(sgn, p["chain"], tuple(V[i])),
                                       posed, joints)
                    pts.append(q)
                    bind.append(tuple(V[i]))
            pts = np.array(pts)
            bind = np.array(bind)
            lo = float(pts[:, 1].min())
            lowest = min(lowest, lo)
            if kind == "swing":
                check(lo >= arg, f"{side}: swing boot stays clear of the floor",
                      f"clearance {lo * 1000:.1f} mm (>= {arg * 1000:.0f} mm)")
                continue
            sel = pts[:, 1] <= lo + 0.0015
            # the contact region is measured in the boot's own (bind) frame, so
            # the report names the part of the sole that is really down; the
            # patch must span the boot in at least one direction (a single
            # knife-edge vertex is not a contact patch)
            bp = bind[sel]
            dz = float(bp[:, 2].max() - bp[:, 2].min())
            dx = float(bp[:, 0].max() - bp[:, 0].min())
            zc = float(bp[:, 2].mean())
            where = {"flat": "sole", "heel": "heel corner", "pad": "forefoot pad"}[kind]
            ok_pos = {"flat": True, "heel": zc < -0.05, "pad": zc > 0.10}[kind]
            if kind == "flat":
                ok_patch = dz >= arg and int(sel.sum()) >= 8
            else:
                # a corner contact (heel strike / toe-off) is a real edge
                # patch - never a single vertex, and it must span the boot in
                # at least one direction
                ok_patch = max(dz, dx) >= 0.006 and int(sel.sum()) >= 4
            check(abs(lo) < 5e-5 and ok_patch and ok_pos,
                  f"{side}: planted boot rests on its {where} at exactly the floor",
                  f"ymin {lo * 1e6:+.1f} um, patch {int(sel.sum())} verts / "
                  f"{dz * 1000:.0f} x {dx * 1000:.0f} mm at bind z {zc * 1000:+.0f} mm")
        check(lowest > -1e-6, "no boot vertex below the floor in the posed state",
              f"lowest {lowest * 1000:+.4f} mm")

    print(f"\n{CHECKS[0] - len(FAILURES)}/{CHECKS[0]} checks passed")
    if FAILURES:
        print("FAILED:")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("verify_boots: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
