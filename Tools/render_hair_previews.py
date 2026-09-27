#!/usr/bin/env python3
"""Hair-focused multi-angle preview renderer for the Vespershade protagonist.

The authoring environment has no Unity editor, so this script provides the
visual QA required for the hairstyle task: front / side / back / top close
views plus full-frame views at the normal gameplay camera distance
(4.5 m orbit distance, 52 degree FOV - matching MainCameraRig defaults).

It reuses the character preview rasterizer, but adds a Hair material
approximation of Assets/Art/Shaders/CharacterHair.shader: object-space
strand banding along the same flow field (crown sweep away from the part
line, down-and-back at the sides, straight down at the nape), root
darkening and a fake anisotropic sheen band. This is a preview analogue,
not the real lighting - the Unity shader remains the source of truth.

Usage:
    python3 Tools/render_hair_previews.py [output_dir]

Requires numpy + Pillow (authoring env only; never used by the game).
"""
import math
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import render_character_previews as rcp  # noqa: E402

OBJ_PATH = os.path.join(ROOT, "Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj")
OUT_DEFAULT = os.path.join(ROOT, "Docs/CharacterPreviews")

# name, yaw_deg, pitch_deg, target_y (or xyz), dist, fov, w, h
VIEWS = [
    ("hair_front",       0,   3, (0.0, 1.70, 0.0), 0.85, 34, 640, 800),
    ("hair_side",       90,   3, (0.0, 1.70, 0.0), 0.85, 34, 640, 800),
    ("hair_back",      180,   3, (0.0, 1.70, 0.0), 0.85, 34, 640, 800),
    ("hair_threeQ",     40,   8, (0.0, 1.70, 0.0), 0.85, 34, 640, 800),
    ("hair_top",         0,  85, (0.0, 1.70, 0.0), 0.85, 34, 640, 800),
    ("hair_ear",       -72,  12, (0.06, 1.66, 0.0), 0.42, 30, 640, 800),
    ("hair_gameplay_front",   0, 12, (0.0, 1.50, 0.0), 4.5, 52, 640, 800),
    ("hair_gameplay_side",   90, 12, (0.0, 1.50, 0.0), 4.5, 52, 640, 800),
    ("hair_gameplay_back",  180, 12, (0.0, 1.50, 0.0), 4.5, 52, 640, 800),
    ("hair_gameplay_threeQ", 40, 12, (0.0, 1.50, 0.0), 4.5, 52, 640, 800),
]


def hair_shade(centroids, key_dir, view):
    """Vectorised approximation of the hair shader's banding/occlusion."""
    p = centroids
    upness = np.clip((p[:, 1] - 1.60) / (1.72 - 1.60), 0.0, 1.0)
    backness = np.clip((0.01 - p[:, 2]) / (-0.05 - 0.01), 0.0, 1.0)
    side = np.where(p[:, 0] > 0.006, 1.0, -1.0)
    crown = np.stack([side * 0.85, np.full(len(p), -0.35), np.full(len(p), -0.55)], axis=1)
    crown /= np.linalg.norm(crown, axis=1, keepdims=True)
    down = np.tile(np.array([[0.0, -1.0, -0.18]]), (len(p), 1))
    down /= np.linalg.norm(down, axis=1, keepdims=True)
    sidem = np.stack([0.15 * np.sign(p[:, 0] + 1e-5), np.full(len(p), -0.8), np.full(len(p), -0.62)], axis=1)
    sidem /= np.linalg.norm(sidem, axis=1, keepdims=True)
    flow = down * ((1 - backness) * (1 - upness))[:, None] \
        + sidem * (backness * (1 - upness))[:, None] + crown * upness[:, None]
    flow /= np.linalg.norm(flow, axis=1, keepdims=True)
    # normal ~ radial from the head axis (good enough for banding phase)
    nrm = np.stack([p[:, 0], np.full(len(p), 0.12), p[:, 2]], axis=1)
    nrm /= np.linalg.norm(nrm, axis=1, keepdims=True)
    b = np.cross(flow, nrm)
    b /= (np.linalg.norm(b, axis=1, keepdims=True) + 1e-9)
    v = np.einsum("ij,ij->i", p, b)
    u = np.einsum("ij,ij->i", p, flow)
    band = 0.5 + 0.5 * np.sin(v * 140.0)
    shade = 0.82 + 0.30 * band
    # root darkening toward the hairline
    hairline = 1.735 - 0.16 * np.clip((0.05 - p[:, 2]) / (-0.10 - 0.05), 0.0, 1.0)
    rootT = np.clip((hairline - p[:, 1]) / 0.05, 0.0, 1.0)
    shade *= 1.0 - 0.40 * rootT
    # sheen: brighten where the flow is near-perpendicular to the half vector
    h = key_dir + view
    h = h / np.linalg.norm(h)
    sinTH = np.sqrt(np.clip(1.0 - np.einsum("ij,j->i", flow, h) ** 2, 0.0, None))
    sheen = (sinTH ** 22.0) * 0.16
    return shade, sheen


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else OUT_DEFAULT
    os.makedirs(out_dir, exist_ok=True)

    for k in rcp.PALETTE:
        rcp.PALETTE[k] = tuple(rcp.PALETTE[k])

    verts, faces, order = rcp.load_obj(OBJ_PATH)
    tris, mat_ids = [], []
    for mi, m in enumerate(order):
        for tri in faces[m]:
            tris.append(tri)
            mat_ids.append(mi)
    tris = np.asarray(tris)
    mat_ids = np.asarray(mat_ids)
    print(f"Loaded {len(verts)} verts, {len(tris)} tris")

    vnorm = np.zeros_like(verts)
    fn = np.cross(verts[tris[:, 1]] - verts[tris[:, 0]], verts[tris[:, 2]] - verts[tris[:, 0]])
    for k in range(3):
        np.add.at(vnorm, tris[:, k], fn)
    ln = np.linalg.norm(vnorm, axis=1)
    ln[ln < 1e-12] = 1.0
    vnorm = vnorm / ln[:, None]

    hair_mask = mat_ids == [i for i, m in enumerate(order) if m == "Hair"][0]
    base = np.asarray(rcp.PALETTE["Hair"][0], dtype=np.float64)

    paths = []
    for name, yaw, pitch, tgt, dist, fov, w, h in VIEWS:
        target = np.asarray(tgt, dtype=np.float64)
        eye, right, up, fwd = rcp.look_at(yaw, pitch, tuple(target), dist)
        key_dir = np.array([-0.35, 0.72, 0.60]); key_dir /= np.linalg.norm(key_dir)
        view = eye - verts[tris[hair_mask]].mean(axis=(0, 1))
        view = view / np.linalg.norm(view)
        shade, sheen = hair_shade(
            (verts[tris[:, 0]] + verts[tris[:, 1]] + verts[tris[:, 2]]) / 3.0, key_dir, view)

        # render with per-triangle hair shade applied through the palette hook
        img = _render_with_hair_shade(verts, tris, mat_ids, vnorm, yaw, pitch,
                                      tuple(target), dist, fov, w, h,
                                      hair_mask, base, shade, sheen)
        path = os.path.join(out_dir, f"{name}.png")
        Image.fromarray(img).save(path)
        paths.append(path)
        print(f"  wrote {path}")

    # contact sheet
    tw, th = 320, 400
    cols = 5
    rows = (len(paths) + cols - 1) // cols
    sheet = Image.new("RGB", (tw * cols, th * rows), (14, 14, 18))
    for i, p in enumerate(paths):
        im = Image.open(p).resize((tw, th))
        sheet.paste(im, ((i % cols) * tw, (i // cols) * th))
    sheet_path = os.path.join(out_dir, "hair_sheet.jpg")
    sheet.save(sheet_path, quality=88)
    print(f"  wrote {sheet_path}")


def _render_with_hair_shade(verts, tris, mat_ids, vnorm, yaw, pitch, target,
                            dist, fov, w, h, hair_mask, base, shade, sheen):
    """Copy of render_view with per-triangle hair banding applied."""
    eye, right, up, fwd = rcp.look_at(yaw, pitch, target, dist)
    rel = verts - eye
    x = rel @ right
    y = rel @ up
    z = rel @ fwd
    scale = (h * 0.5) / math.tan(math.radians(fov) * 0.5)
    sx = w * 0.5 + x * scale / z
    sy = h * 0.5 - y * scale / z

    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    fnl = np.cross(verts[b] - verts[a], verts[c] - verts[a])
    ln = np.linalg.norm(fnl, axis=1)
    ln[ln < 1e-12] = 1.0
    fnl = fnl / ln[:, None]

    img = np.zeros((h, w, 3), dtype=np.float64)
    zbuf = np.full((h, w), 1e18)

    key_dir = np.array([-0.35, 0.72, 0.60]); key_dir /= np.linalg.norm(key_dir)
    fill_dir = np.array([0.55, 0.10, -0.62]); fill_dir /= np.linalg.norm(fill_dir)
    key_color, fill_color, ambient = 1.05, 0.32, 0.36

    hair_base = base
    order = np.argsort(-np.min(z[[a, b, c]], axis=0))
    for i in order:
        ia, ib, ic = a[i], b[i], c[i]
        za, zb, zc = z[ia], z[ib], z[ic]
        if za <= 0.02 or zb <= 0.02 or zc <= 0.02:
            continue
        centroid = (verts[ia] + verts[ib] + verts[ic]) / 3.0
        if np.dot(fnl[i], centroid - eye) > 0.0:
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
        gloss = rcp.PALETTE[rcp.MATERIALS[mat_ids[i]]][1]
        if hair_mask[i]:
            bs = hair_base * shade[i]
            gloss = 0.40
        else:
            bs = np.asarray(rcp.PALETTE[rcp.MATERIALS[mat_ids[i]]][0])
        col = bs * (ambient + key_color * lam_key[:, :, None] + fill_color * lam_fill[:, :, None])
        col += bs * rim[:, :, None] * 0.10
        half = key_dir + view
        hl = np.linalg.norm(half)
        if hl > 1e-6:
            spec = np.clip(n @ (half / hl), 0.0, None) ** 24
            col += np.array([1.0, 0.95, 0.82]) * (spec * gloss * 0.45)[:, :, None]
        if hair_mask[i]:
            col += np.array([0.55, 0.52, 0.45])[None, None, :] * sheen[i]
        sub_z[upd] = zi[upd]
        img[miny:maxy + 1, minx:maxx + 1][upd] = np.clip(col[upd], 0.0, 1.0)

    return (np.clip(img, 0.0, 1.0) * 255).astype(np.uint8)


if __name__ == "__main__":
    main()
