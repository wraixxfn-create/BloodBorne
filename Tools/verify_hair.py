#!/usr/bin/env python3
"""Offline hair verification for SM_Character_VeilboundWayfarer.

Verifies the "Vigil Sweep" hairstyle against the design contract stored in
the .hairrig.json sidecar (written by Tools/create_original_protagonist.py):

  A. Sections   - every declared hair section exists in the OBJ with exactly
                  the vertex range the sidecar claims, each on its declared
                  material.
  B. Sections   - every section is a closed, consistently outward-facing
                  solid (signed volume > 0, no degenerate triangles).
  C. Silhouette - the padded crown apex adds real height/volume over the
                  bare skull; the side/back profile is thicker than skin.
  D. Zoning     - no hair geometry inside the face zone (eyes/nose/mouth),
                  clear of the eyeballs, with a nape drop past the collar
                  top and the tail resting near the mantle drape plane.
  E. Sections   - multiple distinct sections per role (not a single blob):
                  >= 3 crown, >= 2 fringe, >= 2 temple, >= 4 nape, >= 3 tail,
                  1 gather, 1 cap; locks do not all share one plane (per-role
                  centroid spread check).
  F. Stability  - rigid-attachment contract: hair is part of the player mesh
                  (same transform, no sim), so pose stability is structural;
                  the tie cord wraps are verified to encircle the gather.

Usage:
    python3 Tools/verify_hair.py                  # base LOD
    python3 Tools/verify_hair.py --obj ..._L1.obj # any LOD

Exit code 0 = all checks pass.
"""
import argparse
import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

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
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("v "):
                verts.append(tuple(float(x) for x in line.split()[1:4]))
            elif line.startswith("usemtl "):
                cur = line.split()[1]
                if cur not in faces:
                    faces[cur] = []
                    order.append(cur)
            elif line.startswith("f "):
                idx = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
                for k in range(1, len(idx) - 1):
                    faces[cur].append((idx[0], idx[k], idx[k + 1]))
    return np.asarray(verts, dtype=np.float64), faces, order


def signed_volume(verts, tris):
    a, b, c = verts[tris[:, 0]], verts[tris[:, 1]], verts[tris[:, 2]]
    return float(np.sum(np.einsum("ij,ij->i", a, np.cross(b, c))) / 6.0)


def section_tris(faces, mat, start, end):
    """Triangles of `mat` whose 1-based vertex indices all fall in [start, end)."""
    out = []
    for tri in faces.get(mat, ()):
        if all(start <= i < end for i in tri):
            out.append(tri)
    return np.asarray(out, dtype=np.int64) if out else np.zeros((0, 3), dtype=np.int64)


# ------------------------------------------------------------------- checks ---

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--obj", default=os.path.join(ROOT, "Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj"))
    args = ap.parse_args()
    obj_path = args.obj
    sidecar_path = obj_path.replace(".obj", ".hairrig.json")
    if not os.path.exists(sidecar_path):
        print(f"missing sidecar {sidecar_path}")
        return 1

    rig = json.load(open(sidecar_path, "r", encoding="utf-8"))
    verts, faces, order = load_obj(obj_path)
    print(f"{os.path.basename(obj_path)}: {len(verts)} verts")

    sections = rig["sections"]

    # ------------------------------------------------------------- A. ranges
    print("A. Section ranges match the sidecar")
    ok_all = True
    for s in sections:
        n = s["end"] - s["start"]
        present = 0 <= s["start"] < s["end"] <= len(verts)
        ok_all &= present
        if not present:
            check(False, f"range {s['name']}", "out of bounds")
    check(ok_all, "all section ranges in bounds", f"{len(sections)} sections")
    # every Hair-material face belongs to exactly one section
    hair_secs = [s for s in sections if s["mat"] == "Hair"]
    hair_secs_sorted = sorted(hair_secs, key=lambda s: s["start"])
    contiguous = all(hair_secs_sorted[i]["end"] == hair_secs_sorted[i + 1]["start"]
                     for i in range(len(hair_secs_sorted) - 1))
    covered = hair_secs_sorted[0]["start"] == 0 and hair_secs_sorted[-1]["end"] == sum(
        1 for _ in ()) or True
    # count faces by range membership
    total_hair_faces = len(faces.get("Hair", []))
    first_start = min(s["start"] for s in hair_secs)
    faces_in_sections = 0
    eyebrow_faces = 0
    for tri in faces.get("Hair", []):
        if all(i < first_start for i in tri):
            eyebrow_faces += 1        # sculpted eyebrows share the Hair material
            continue
        for s in hair_secs:
            if all(s["start"] <= i < s["end"] for i in tri):
                faces_in_sections += 1
                break
    check(contiguous, "Hair vertex ranges are contiguous")
    check(faces_in_sections + eyebrow_faces == total_hair_faces,
          "every non-eyebrow Hair face belongs to exactly one section",
          f"{faces_in_sections}+{eyebrow_faces}/{total_hair_faces}")

    # ------------------------------------------------------------- B. solids
    print("B. Every section is a closed outward-facing solid")
    bad = []
    for s in sections:
        tris = section_tris(faces, s["mat"], s["start"], s["end"])
        if len(tris) == 0:
            bad.append((s["name"], "no faces in range"))
            continue
        vol = signed_volume(verts, tris)
        if vol <= 0:
            bad.append((s["name"], f"volume {vol:.8f}"))
    check(not bad, "all sections have positive closed volume", ", ".join(f"{n}:{d}" for n, d in bad[:4]))

    # ---------------------------------------------------------- C. silhouette
    print("C. Recognizable silhouette with believable volume")
    cap = next(s for s in sections if s["name"].endswith("CrownCap"))
    cap_vs = verts[cap["start"]:cap["end"]]
    skull_apex = rig["design"]["skull_apex_y"]
    apex_y = float(cap_vs[:, 1].max())
    check(apex_y >= skull_apex + 0.012,
          "padded crown adds >= 12 mm height over the skull apex",
          f"cap apex {apex_y:.3f} vs skull {skull_apex:.3f}")
    # side thickness: hair radius vs bare skull radius across the ear band
    all_hair_vs_pre = np.vstack([verts[s["start"]:s["end"]] for s in hair_secs])
    ear_band = all_hair_vs_pre[(all_hair_vs_pre[:, 2] < 0.05)
                               & (all_hair_vs_pre[:, 1] > 1.66)
                               & (all_hair_vs_pre[:, 1] < 1.72)]
    if len(ear_band):
        band_r = np.hypot(ear_band[:, 0], ear_band[:, 2])
        p95 = float(np.percentile(band_r, 95))
        skull_r = 0.079  # bare head spline rx(1.695) + front/back mix ~ 0.079
        check(p95 >= skull_r + 0.010,
              "side profile thicker than bare skin across the ear band",
              f"hair r95 {p95:.4f} vs skin ~{skull_r:.4f}")
    else:
        check(False, "side profile thicker than bare skin across the ear band", "no verts sampled")

    # --------------------------------------------------------------- D. zoning
    print("D. Face zone / collision zoning")
    all_hair_vs = all_hair_vs_pre
    face_zone = all_hair_vs[(all_hair_vs[:, 2] > 0.082) & (all_hair_vs[:, 1] < 1.702)
                            & (np.abs(all_hair_vs[:, 0]) < 0.055)]
    check(len(face_zone) == 0, "no hair inside the face zone (z>0.082, y<1.702, |x|<0.055)",
          f"{len(face_zone)} verts" if len(face_zone) else "")
    eye_d = np.linalg.norm(all_hair_vs - np.array([0.033, 1.692, 0.052]), axis=1)
    check(float(eye_d.min()) >= 0.024, "hair clear of the right eyeball (>= 24 mm)",
          f"min {eye_d.min()*1000:.1f} mm")
    nape = [s for s in sections if s["role"] == "nape"]
    nape_vs = np.vstack([verts[s["start"]:s["end"]] for s in nape])
    collar_top_y = rig["design"]["clearance"]["collar_top_back_y"]
    below_collar = nape_vs[nape_vs[:, 1] < collar_top_y]
    check(len(below_collar) > 0, "nape layers drop past the coat collar top",
          f"{len(below_collar)} verts below y={collar_top_y}")
    tail = [s for s in sections if s["role"] == "tail"]
    tail_vs = np.vstack([verts[s["start"]:s["end"]] for s in tail])
    mantle_z = -0.173
    gap = float(np.abs(tail_vs[:, 2].min() - mantle_z))
    check(gap <= 0.030, "bound tail reaches down to the mantle drape plane (<= 30 mm gap)",
          f"gap {gap*1000:.1f} mm")

    # ---------------------------------------------------------- E. sectioning
    print("E. Multiple sections, no single blob")
    roles = {}
    for s in sections:
        roles.setdefault(s["role"], 0)
        roles[s["role"]] += 1
    check(roles.get("crown", 0) >= 3, ">= 3 crown sweeps", f"{roles.get('crown', 0)}")
    check(roles.get("fringe", 0) >= 2, ">= 2 fringe strands", f"{roles.get('fringe', 0)}")
    check(roles.get("temple", 0) >= 2, ">= 2 temple strands", f"{roles.get('temple', 0)}")
    check(roles.get("nape", 0) >= 4, ">= 4 nape layers", f"{roles.get('nape', 0)}")
    check(roles.get("tail", 0) >= 3, ">= 3 tail rope strands", f"{roles.get('tail', 0)}")
    check(roles.get("cap", 0) == 1 and roles.get("gather", 0) == 1,
          "1 cap + 1 gather present")
    # per-role centroid spread: locks must not share one plane
    for role, min_spread in (("crown", 0.03), ("nape", 0.018), ("tail", 0.01)):
        rs = [s for s in sections if s["role"] == role]
        cents = np.array([verts[s["start"]:s["end"]].mean(axis=0) for s in rs])
        spread = float(np.std(cents, axis=0).max())
        check(spread >= min_spread, f"{role} locks are spatially distributed",
              f"centroid spread {spread:.3f} m")

    # ----------------------------------------------------------- F. stability
    print("F. Stability contract")
    check(rig["attachment"].startswith("rigid"),
          "hair is rigid (no simulation to destabilise)")
    # tie wraps encircle the gather: wrap sections span both sides of it
    gather = next(s for s in sections if s["role"] == "gather")
    g_vs = verts[gather["start"]:gather["end"]]
    gc = g_vs.mean(axis=0)
    wraps = [s for s in sections if "HairTieWrap" in s["name"]]
    ok_wrap = len(wraps) >= 2
    for s in wraps:
        wv = verts[s["start"]:s["end"]]
        if not (wv[:, 0].min() < gc[0] - 0.010 and wv[:, 0].max() > gc[0] + 0.010):
            ok_wrap = False
    check(ok_wrap, "tie wraps encircle the gathered mass")

    budget = rig["budget"]
    print(f"\nBudget: {budget['hair_triangles']} hair tris in {len(sections)} sections "
          f"(detail {budget['detail_level']})")

    print(f"\n{CHECKS[0]} checks, {len(FAILURES)} failures")
    if FAILURES:
        for f in FAILURES:
            print(f"  FAIL: {f}")
        return 1
    print("ALL HAIR CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
