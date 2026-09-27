#!/usr/bin/env python3
"""Offline posable preview renderer for the boots over a floor.

Renders the four states the boots have to survive - idle, walk, run, dodge -
using the LBS rig in Tools/boot_rig.py, so the images show exactly the
deformation the game will apply:

  * the planted foot is grounded by the same foot-IK shift Tools/verify_boots.py
    uses (lowest planted vertex at y = 0),
  * the mesh is skinned per part (boot parts through their rig chain, the
    trousers through the leg chain, everything else follows the root),
  * the character is drawn over a 0.5 m checkerboard floor plane at y = 0.

That makes floating, clipping and sole contact directly visible.

Usage:
    python3 Tools/render_boot_previews.py [output_dir]     # default Docs/CharacterPreviews

Requires numpy + Pillow (authoring env only; never used by the game).
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import boot_rig as br  # noqa: E402

OBJ_PATH = os.path.join(ROOT, "Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj")

PALETTE = {
    "Cloth":       ((0.105, 0.140, 0.195), 0.35),
    "ClothAccent": ((0.255, 0.075, 0.110), 0.35),
    "Trouser":     ((0.125, 0.140, 0.165), 0.30),
    "Leather":     ((0.150, 0.088, 0.058), 0.55),
    "Skin":        ((0.48, 0.32, 0.24), 0.25),
    "Hair":        ((0.12, 0.135, 0.165), 0.40),
    "AgedBrass":   ((0.47, 0.30, 0.115), 0.90),
    "BoneThread":  ((0.63, 0.53, 0.36), 0.45),
    "BootSole":    ((0.06, 0.05, 0.045), 0.25),
}

# name, yaw(deg), pitch, target, distance, fov_y(deg), width, height
VIEWS = (
    ("full", 28.0, 6.0, (0.0, 0.75, 0.0), 3.1, 30.0, 420, 700),
    ("close", 38.0, 14.0, (0.0, 0.10, 0.06), 0.95, 30.0, 560, 420),
    ("side", -92.0, 4.0, (0.118, 0.09, 0.05), 0.66, 30.0, 560, 420),
)


def load_obj(path):
    verts, faces, order, mat_of_face, cur = [], {}, [], [], None
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
                mat_of_face.append(cur)
    return np.array(verts), faces, order, mat_of_face


def vert_owner(V, faces):
    """material/part chain + side for every vertex index."""
    owner = {}
    for i in range(len(V)):
        owner[i] = None
    return owner


def build_skin(V, faces, rig):
    """Per-vertex (side, chain) for the skinned layers: boot parts and trousers."""
    tag = np.zeros((len(V), 2), dtype=np.int16)      # [side sign, chain id]; 0 = root
    chains = list(br.CHAIN_WEIGHT_FN)
    for p in rig["parts"]:
        sgn = 1 if p["side"] == "R" else -1
        cid = chains.index(p["chain"])
        for f in faces[p["mat"]]:
            if all(p["start"] <= i < p["end"] for i in f):
                for i in f:
                    tag[i] = (sgn, cid)
    # trousers: the wool leg inside the boot follows the leg chain
    for f in faces.get("Trouser", []):
        for i in f:
            tag[i] = (1 if V[i][0] > 0 else -1, chains.index("leg"))
    return tag, chains


def skin_all(V, tag, chains, pose, shift):
    posed = br.pose_matrices(pose, (0.0, shift, 0.0))
    joints = {j[0]: j for j in br.joint_list()}
    out = np.array(V, dtype=float)
    for i in range(len(V)):
        sgn, cid = int(tag[i][0]), int(tag[i][1])
        if sgn == 0:                       # not a rigged limb: follows the root
            out[i] = (V[i][0], V[i][1] + shift, V[i][2])
            continue
        pt = tuple(V[i])
        w = br.weights_for(sgn, chains[cid], pt)
        out[i] = br.skin_vertex(pt, w, posed, joints)
    return out


def ground_shift(pose, V, faces, rig):
    planted = {"idle": ("R", "L"), "walk": ("R", "L"), "run": ("R",), "dodge": ("L",)}[pose]
    pts = []
    for p in rig["parts"]:
        if p["side"] in planted and p["name"].startswith(("Boots/Sole_", "Boots/Heel")):
            for f in faces[p["mat"]]:
                if all(p["start"] <= i < p["end"] for i in f):
                    pts.extend(tuple(V[i]) for i in f)
    return br.ground_shift(pose, pts)


def look(yaw, pitch, target, dist):
    y, p = math.radians(yaw), math.radians(pitch)
    eye = np.array([target[0] + dist * math.cos(p) * math.sin(y),
                    target[1] + dist * math.sin(p),
                    target[2] + dist * math.cos(p) * math.cos(y)])
    fwd = np.asarray(target, float) - eye
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0.0, 1.0, 0.0])
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return eye, right, up, fwd


def render(V, tris, mat_ids, vnorm, yaw, pitch, target, dist, fov, w, h):
    eye, right, up, fwd = look(yaw, pitch, target, dist)
    rel = V - eye
    x, y, z = rel @ right, rel @ up, rel @ fwd
    sc = (h * 0.5) / math.tan(math.radians(fov) * 0.5)
    sx, sy = w * 0.5 + x * sc / z, h * 0.5 - y * sc / z
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    fn = np.cross(V[b] - V[a], V[c] - V[a])
    ln = np.linalg.norm(fn, axis=1)
    ln[ln < 1e-12] = 1.0
    fn /= ln[:, None]
    img = np.zeros((h, w, 3))
    zbuf = np.full((h, w), 1e18)
    kd = np.array([-0.35, 0.72, 0.60]); kd /= np.linalg.norm(kd)
    fd = np.array([0.55, 0.10, -0.62]); fd /= np.linalg.norm(fd)
    for i in np.argsort(-np.min(z[[a, b, c]], axis=0)):
        ia, ib, ic = a[i], b[i], c[i]
        za, zb, zc = z[ia], z[ib], z[ic]
        if za <= 0.02 or zb <= 0.02 or zc <= 0.02:
            continue
        cen = (V[ia] + V[ib] + V[ic]) / 3.0
        if np.dot(fn[i], cen - eye) > 0:
            continue
        minx = max(int(math.floor(min(sx[ia], sx[ib], sx[ic]))), 0)
        maxx = min(int(math.ceil(max(sx[ia], sx[ib], sx[ic]))), w - 1)
        miny = max(int(math.floor(min(sy[ia], sy[ib], sy[ic]))), 0)
        maxy = min(int(math.ceil(max(sy[ia], sy[ib], sy[ic]))), h - 1)
        if minx > maxx or miny > maxy:
            continue
        xs = np.arange(minx, maxx + 1) + 0.5
        ys = np.arange(miny, maxy + 1) + 0.5
        px, py = np.meshgrid(xs, ys)
        d = ((sy[ib] - sy[ic]) * (sx[ia] - sx[ic]) + (sx[ic] - sx[ib]) * (sy[ia] - sy[ic]))
        if abs(d) < 1e-12:
            continue
        w0 = ((sy[ib] - sy[ic]) * (px - sx[ic]) + (sx[ic] - sx[ib]) * (py - sy[ic])) / d
        w1 = ((sy[ic] - sy[ia]) * (px - sx[ic]) + (sx[ia] - sx[ic]) * (py - sy[ic])) / d
        w2 = 1.0 - w0 - w1
        mask = (w0 >= -1e-7) & (w1 >= -1e-7) & (w2 >= -1e-7)
        if not mask.any():
            continue
        zi = 1.0 / (w0 / za + w1 / zb + w2 / zc)
        sub = zbuf[miny:maxy + 1, minx:maxx + 1]
        upd = mask & (zi < sub)
        if not upd.any():
            continue
        n = w0[:, :, None] * vnorm[ia] + w1[:, :, None] * vnorm[ib] + w2[:, :, None] * vnorm[ic]
        nl = np.linalg.norm(n, axis=2)
        nl[nl < 1e-9] = 1.0
        n = n / nl[:, :, None]
        view = eye - cen
        view /= np.linalg.norm(view)
        lk = np.clip(n @ kd, 0, None)
        lf = np.clip(n @ fd, 0, None)
        rim = (1.0 - np.abs(n @ view)) ** 3
        base, gloss = PALETTE.get(mat_ids[i], ((0.5, 0.5, 0.5), 0.3))
        base = np.asarray(base)
        col = base * (0.36 + 1.05 * lk[:, :, None] + 0.32 * lf[:, :, None]) + base * rim[:, :, None] * 0.10
        half = kd + view
        hl = np.linalg.norm(half)
        if hl > 1e-6:
            spec = np.clip(n @ (half / hl), 0, None) ** 24
            col += np.array([1.0, 0.95, 0.82]) * (spec * gloss * 0.45)[:, :, None]
        sub[upd] = zi[upd]
        img[miny:maxy + 1, minx:maxx + 1][upd] = np.clip(col[upd], 0, 1)

    # floor: analytic ray cast of the y = 0 plane per pixel (solid checkerboard
    # with a soft contact shade under the boots), z-buffered against the mesh
    jj, ii = np.mgrid[0:h, 0:w]
    dc = (fwd[None, None, :]
          + ((ii + 0.5 - w * 0.5) / sc)[:, :, None] * right[None, None, :]
          - ((jj + 0.5 - h * 0.5) / sc)[:, :, None] * up[None, None, :])
    dc /= np.linalg.norm(dc, axis=2)[:, :, None]
    with np.errstate(divide="ignore", invalid="ignore"):
        t = -eye[1] / dc[:, :, 1]
    hit = np.isfinite(t) & (t > 0.05)
    P = eye[None, None, :] + t[:, :, None] * dc
    depth = np.full((h, w), 1e18)
    depth[hit] = t[hit] * (dc[hit] @ fwd)
    chk = ((np.floor(P[:, :, 0] * 2.0) + np.floor(P[:, :, 2] * 2.0)) % 2).astype(int)
    colr = np.where(chk[:, :, None] == 0, np.array([0.115, 0.115, 0.125]),
                    np.array([0.150, 0.150, 0.162]))
    d1 = np.hypot(P[:, :, 0] - 0.118, P[:, :, 2] - 0.06)
    d2 = np.hypot(P[:, :, 0] + 0.118, P[:, :, 2] - 0.06)
    shade = 1.0 - 0.45 * np.exp(-(np.minimum(d1, d2) / 0.22) ** 2)
    colr = colr * shade[:, :, None]
    sel = hit & (depth < zbuf)
    img[sel] = np.clip(colr[sel], 0, 1)
    return (np.clip(img, 0, 1) * 255).astype(np.uint8)


def main():
    out_dir = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else \
        os.path.join(ROOT, "Docs/CharacterPreviews")
    os.makedirs(out_dir, exist_ok=True)
    rig_path = os.path.splitext(OBJ_PATH)[0] + ".bootrig.json"
    rig = json.load(open(rig_path))
    V, faces, order, mat_of_face = load_obj(OBJ_PATH)
    tag, chains = build_skin(V, faces, rig)
    print(f"Loaded {len(V)} verts, {len(rig['parts'])} boot parts")

    tris, mat_ids = [], []
    for m in order:
        for f in faces[m]:
            tris.append(f)
            mat_ids.append(m)
    tris = np.asarray(tris)
    mat_ids = np.asarray(mat_ids)

    paths = []
    for pose in br.POSES_ORDER:
        shift = ground_shift(pose, V, faces, rig)
        P = skin_all(V, tag, chains, pose, shift)
        vnorm = np.zeros_like(P)
        fn = np.cross(P[tris[:, 1]] - P[tris[:, 0]], P[tris[:, 2]] - P[tris[:, 0]])
        for k in range(3):
            np.add.at(vnorm, tris[:, k], fn)
        ln = np.linalg.norm(vnorm, axis=1)
        ln[ln < 1e-12] = 1.0
        vnorm = vnorm / ln[:, None]
        # aim the close cameras at the planted boot's contact point
        planted = {"idle": ("R", "L"), "walk": ("R", "L"), "run": ("R",), "dodge": ("L",)}[pose]
        print(f"  pose {pose}: root dy {shift * 1000:+.1f} mm, lowest skinned vertex "
              f"{P[:, 1].min() * 1000:+.2f} mm")
        cx = sum(1.0 if s == "R" else -1.0 for s in planted) / len(planted) * br.FOOT_X
        cz = br.BALL[2]
        for name, yaw, pitch, tgt, dist, fov, w, h in VIEWS:
            tgt = (tgt[0] + cx, tgt[1], tgt[2] + cz)
            img = render(P, tris, mat_ids, vnorm, yaw, pitch, tgt, dist, fov, w, h)
            path = os.path.join(out_dir, f"PC_boots_{pose}_{name}.png")
            Image.fromarray(img).save(path)
            paths.append(path)
            print(f"    wrote {path}")

    # contact sheet of the close-up views
    tiles = [Image.open(p) for p in paths if "_close" in p]
    if tiles:
        tw, th = tiles[0].size
        sheet = Image.new("RGB", (tw * 2, th * 2), (16, 16, 20))
        for i, im in enumerate(tiles[:4]):
            sheet.paste(im, ((i % 2) * tw, (i // 2) * th))
        sheet_path = os.path.join(out_dir, "PC_boots_sheet.jpg")
        sheet.save(sheet_path, quality=88)
        print(f"    wrote {sheet_path}")


if __name__ == "__main__":
    main()
