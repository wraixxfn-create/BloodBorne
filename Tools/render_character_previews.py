#!/usr/bin/env python3
"""Offline multi-angle preview renderer for the Vespershade protagonist OBJ.

The authoring environment has no Unity editor, so this script provides the
visual Play-Mode-equivalent QA: it loads SM_Character_VeilboundWayfarer.obj,
renders it with a tiny z-buffer rasterizer (smooth vertex normals, two-light
Lambert + rim, per-material palette colours) from a fixed set of camera
angles and writes PNG files plus a contact sheet to a chosen directory.

Usage:
    python3 Tools/render_character_previews.py [output_dir]

Requires numpy + Pillow (authoring env only; never used by the game).
"""
import math
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJ_PATH = os.path.join(ROOT, "Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj")

# Match the in-game material palette (Tools/create_original_protagonist.py).
PALETTE = {
    "Cloth":       ((0.125, 0.150, 0.195), 0.24),
    "ClothAccent": ((0.245, 0.082, 0.115), 0.25),
    "Trouser":     ((0.140, 0.155, 0.180), 0.20),
    "Leather":     ((0.170, 0.110, 0.077), 0.40),
    "Skin":        ((0.520, 0.370, 0.300), 0.27),
    "Hair":        ((0.140, 0.155, 0.185), 0.34),
    "AgedBrass":   ((0.450, 0.310, 0.130), 0.56),
    "BoneThread":  ((0.600, 0.520, 0.390), 0.27),
    "BootSole":    ((0.105, 0.074, 0.056), 0.20),
    "Gloves":      ((0.135, 0.088, 0.061), 0.28),
    "Eyes":        ((0.760, 0.730, 0.680), 0.68),
}
MATERIALS = list(PALETTE.keys())

# name, yaw(deg), target_y, distance, fov_y(deg)
VIEWS = [
    ("front",         0,   0.95, 3.1, 38),
    ("threeQ_left",  40,   0.95, 3.1, 38),
    ("threeQ_right", -40,  0.95, 3.1, 38),
    ("back",         180,  0.95, 3.1, 38),
    ("left_profile", 90,   0.95, 2.9, 40),
    ("right_profile", -90, 0.95, 2.9, 40),
    ("close_collar", 30,   1.55, 1.05, 34),
    ("close_torso",  -28,  1.20, 1.10, 34),
    ("close_belt",   22,   0.98, 1.05, 34),
    ("close_knees",  -20,  0.52, 1.15, 34),
    ("close_boots",  26,   0.18, 1.15, 34),
    ("back_close",   150,  1.10, 1.20, 34),
    # hand close-ups: (name, yaw, pitch, ty, dist, fov, target) - full 7-tuple
    # form targets the hands directly (world-space hand centers).
    ("close_hand_R",  38, 8, 0.92, 0.46, 26, (0.390, 0.930, 0.046)),
    ("close_hand_L", -38, 8, 0.92, 0.46, 26, (-0.390, 0.930, 0.046)),
]
SHEET_COLS = 3


def load_obj(path):
    verts = []
    faces = {}
    order = []
    cur = None
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("v "):
                x, y, z = line.split()[1:4]
                verts.append((float(x), float(y), float(z)))
            elif line.startswith("usemtl"):
                cur = line.split()[1]
                if cur not in faces:
                    faces[cur] = []
                    order.append(cur)
            elif line.startswith("f "):
                idx = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
                for k in range(1, len(idx) - 1):
                    faces[cur].append((idx[0], idx[k], idx[k + 1]))
    return np.asarray(verts, dtype=np.float64), faces, order


def look_at(yaw_deg, pitch_deg, target, dist):
    yaw = math.radians(yaw_deg)
    pitch = math.radians(pitch_deg)
    eye = np.array([
        target[0] + dist * math.cos(pitch) * math.sin(yaw),
        target[1] + dist * math.sin(pitch),
        target[2] + dist * math.cos(pitch) * math.cos(yaw),
    ])
    fwd = np.asarray(target, dtype=np.float64) - eye
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, np.array([0.0, 1.0, 0.0]))
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    return eye, right, up, fwd


def render_view(verts, tris, mat_ids, vnorm, yaw, pitch, target, dist, fov_deg, width, height):
    eye, right, up, fwd = look_at(yaw, pitch, target, dist)
    rel = verts - eye
    x = rel @ right
    y = rel @ up
    z = rel @ fwd
    scale = (height * 0.5) / math.tan(math.radians(fov_deg) * 0.5)
    sx = width * 0.5 + x * scale / z
    sy = height * 0.5 - y * scale / z

    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    fn = np.cross(verts[b] - verts[a], verts[c] - verts[a])
    ln = np.linalg.norm(fn, axis=1)
    ln[ln < 1e-12] = 1.0
    fn = fn / ln[:, None]

    img = np.zeros((height, width, 3), dtype=np.float64)
    zbuf = np.full((height, width), 1e18)

    key_dir = np.array([-0.35, 0.72, 0.60]); key_dir /= np.linalg.norm(key_dir)
    fill_dir = np.array([0.55, 0.10, -0.62]); fill_dir /= np.linalg.norm(fill_dir)
    key_color, fill_color, ambient = 1.05, 0.32, 0.36

    order = np.argsort(-np.min(z[[a, b, c]], axis=0))  # render far first (helps z-test less)
    for i in order:
        ia, ib, ic = a[i], b[i], c[i]
        za, zb, zc = z[ia], z[ib], z[ic]
        if za <= 0.02 or zb <= 0.02 or zc <= 0.02:
            continue
        centroid = (verts[ia] + verts[ib] + verts[ic]) / 3.0
        if np.dot(fn[i], centroid - eye) > 0.0:
            continue  # backface
        minx = max(int(math.floor(min(sx[ia], sx[ib], sx[ic]))), 0)
        maxx = min(int(math.ceil(max(sx[ia], sx[ib], sx[ic]))), width - 1)
        miny = max(int(math.floor(min(sy[ia], sy[ib], sy[ic]))), 0)
        maxy = min(int(math.ceil(max(sy[ia], sy[ib], sy[ic]))), height - 1)
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
        sub_z = zbuf[miny:maxy + 1, minx:maxx + 1]
        upd = mask & (zi < sub_z)
        if not upd.any():
            continue
        n = w0[:, :, None] * vnorm[ia] + w1[:, :, None] * vnorm[ib] + w2[:, :, None] * vnorm[ic]
        nl = np.linalg.norm(n, axis=2); nl[nl < 1e-9] = 1.0
        n = n / nl[:, :, None]
        view = eye - centroid; view /= np.linalg.norm(view)
        lam_key = np.clip(n @ key_dir, 0.0, None)
        lam_fill = np.clip(n @ fill_dir, 0.0, None)
        rim = (1.0 - np.abs(n @ view)) ** 3
        material = MATERIALS[mat_ids[i]]
        base, gloss = PALETTE.get(material, ((0.5, 0.5, 0.5), 0.3))
        base = np.asarray(base)
        if material == "Eyes":
            # Approximate CharacterEye.shader per pixel in local mesh space:
            # subdued blue-grey iris, dark pupil/limbal ring and warm sclera.
            persp = w0 / za + w1 / zb + w2 / zc
            p = (w0[:, :, None] * verts[ia] / za
                 + w1[:, :, None] * verts[ib] / zb
                 + w2[:, :, None] * verts[ic] / zc) / np.maximum(persp[:, :, None], 1e-8)
            center_x = np.where(p[:, :, 0] < 0.0, -0.033, 0.033)
            dx = p[:, :, 0] - center_x
            dy = p[:, :, 1] - 1.692
            radius = np.sqrt(dx * dx + dy * dy)
            angle = np.arctan2(dy, dx)
            iris_radius = 0.0052
            pupil_radius = iris_radius * 0.30
            smooth = lambda lo, hi, x: np.clip((x - lo) / (hi - lo), 0.0, 1.0) ** 2 * (3.0 - 2.0 * np.clip((x - lo) / (hi - lo), 0.0, 1.0))
            iris_mask = 1.0 - smooth(iris_radius * 0.94, iris_radius * 1.06, radius)
            pupil_mask = 1.0 - smooth(pupil_radius * 0.82, pupil_radius * 1.10, radius)
            radial_t = np.clip(radius / iris_radius, 0.0, 1.0)
            fibers = 0.5 + 0.5 * np.sin(angle * 36.0 + radial_t * 17.0 + np.sin(angle * 7.0) * 0.55)
            iris_noise = 0.5 + 0.5 * np.sin(np.cos(angle) * 31.0 + np.sin(angle) * 37.0 + radial_t * 9.0)
            iris_col = np.array([0.18, 0.31, 0.42]) + (np.array([0.27, 0.39, 0.47]) - np.array([0.18, 0.31, 0.42])) * np.clip(0.22 + fibers * 0.36 + iris_noise * 0.28, 0.0, 1.0)[:, :, None]
            inner_shadow = 1.0 - smooth(0.08, 0.72, radial_t)
            iris_col *= (0.74 + 0.26 * inner_shadow)[:, :, None]
            limbal = smooth(0.76, 0.99, radial_t) * iris_mask
            iris_col = iris_col * (1.0 - limbal[:, :, None] * 0.72) + np.array([0.055, 0.085, 0.11]) * (limbal[:, :, None] * 0.72)
            sclera_noise = 0.97 + (0.5 + 0.5 * np.sin(p[:, :, 0] * 180.0 + p[:, :, 1] * 230.0)) * 0.045
            sclera = np.array([0.76, 0.73, 0.68]) * sclera_noise[:, :, None]
            eye_base = sclera * (1.0 - iris_mask[:, :, None]) + iris_col * iris_mask[:, :, None]
            eye_base = eye_base * (1.0 - pupil_mask[:, :, None] * iris_mask[:, :, None]) + np.array([0.025, 0.03, 0.04]) * (pupil_mask[:, :, None] * iris_mask[:, :, None])
            base = eye_base
        col = base * (ambient + key_color * lam_key[:, :, None] + fill_color * lam_fill[:, :, None])
        col += base * rim[:, :, None] * 0.10
        half = key_dir + view
        hl = np.linalg.norm(half)
        if hl > 1e-6:
            spec = np.clip(n @ (half / hl), 0.0, None) ** 24
            col += np.array([1.0, 0.95, 0.82]) * (spec * gloss * 0.45)[:, :, None]
        sub_z[upd] = zi[upd]
        img[miny:maxy + 1, minx:maxx + 1][upd] = np.clip(col[upd], 0.0, 1.0)

    return (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8)


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "Docs/CharacterPreviews")
    os.makedirs(out_dir, exist_ok=True)
    verts, faces, order = load_obj(OBJ_PATH)
    tris, mat_ids = [], []
    for mi, m in enumerate(order):
        for tri in faces[m]:
            tris.append(tri)
            mat_ids.append(mi)
    tris = np.asarray(tris)
    mat_ids = np.asarray(mat_ids)
    total = len(tris)
    print(f"Loaded {len(verts)} verts, {total} tris, {len(order)} materials: {', '.join(order)}")
    for m in MATERIALS:
        n = len(faces.get(m, []))
        print(f"  {m:12s} {n:7d} tris ({100.0 * n / max(total, 1):5.1f}%)")

    # smooth vertex normals (angle-weighted would be nicer; area-weighted is fine)
    vnorm = np.zeros_like(verts)
    fn = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]], verts[tris[:, 2]] - verts[tris[:, 0]])
    for k in range(3):
        np.add.at(vnorm, tris[:, k], fn)
    ln = np.linalg.norm(vnorm, axis=1); ln[ln < 1e-12] = 1.0
    vnorm = vnorm / ln[:, None]

    paths = []
    for view in VIEWS:
        if len(view) == 7:
            name, yaw, pitch, ty, dist, fov, target = view
        else:
            name, yaw, ty, dist, fov = view
            pitch, target = 3.0, (0.0, ty, 0.0)
        img = render_view(verts, tris, mat_ids, vnorm, yaw, pitch, target, dist, fov, 640, 800)
        path = os.path.join(out_dir, f"PC_{name}.png")
        Image.fromarray(img).save(path)
        paths.append(path)
        print(f"  wrote {path}")

    w, h = 640, 800
    cols = SHEET_COLS
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (w * cols, h * rows), (16, 16, 20))
    for i, p in enumerate(paths):
        sheet.paste(Image.open(p), ((i % cols) * w, (i // cols) * h))
    sheet = sheet.resize((w * cols // 2, h * rows // 2))
    sheet_path = os.path.join(out_dir, "sheet.jpg")
    sheet.save(sheet_path, quality=88)
    print(f"  wrote {sheet_path}")


if __name__ == "__main__":
    main()
