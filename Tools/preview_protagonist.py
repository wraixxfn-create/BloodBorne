#!/usr/bin/env python3
"""Offline turntable renderer for the Vespershade protagonist mesh.

The authoring environment has no Unity editor, so this tool renders the *shipped*
Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj from the same fixed
directions a Play Mode turntable would use (front, back, both profiles, two
three-quarter angles plus detail framings of collar, waist, hands and boots).

Shading uses the real material colours/gloss/metallic parsed out of
Assets/Materials/Character/*.mat, three-point lighting and a z-buffer, so the
images are a usable stand-in for looking at the character in the editor.

Usage:
    python3 Tools/preview_protagonist.py [--out Dirs] [--size 900] [--supersample 2]
                                         [--views front,three_quarter_front_left,...]
"""
import argparse
import math
import os
import re
import sys

import numpy as np
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJ_PATH = os.path.join(ROOT, "Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj")
MAT_DIR = os.path.join(ROOT, "Assets/Materials/Character")

# Fallback palette (matches the published .mtl) used when a .mat cannot be read.
FALLBACK = {
    "Cloth": ((0.105, 0.132, 0.170), 0.04, 0.22),
    "ClothAccent": ((0.28, 0.09, 0.12), 0.04, 0.22),
    "Trouser": ((0.14, 0.155, 0.175), 0.02, 0.16),
    "Leather": ((0.20, 0.125, 0.085), 0.03, 0.30),
    "Skin": ((0.39, 0.25, 0.19), 0.0, 0.18),
    "Hair": ((0.09, 0.10, 0.12), 0.0, 0.26),
    "AgedBrass": ((0.46, 0.32, 0.13), 0.75, 0.42),
    "BoneThread": ((0.62, 0.53, 0.38), 0.0, 0.34),
    "BootSole": ((0.06, 0.055, 0.05), 0.0, 0.18),
    "Linen": ((0.30, 0.30, 0.28), 0.0, 0.20),
    "Iron": ((0.14, 0.14, 0.155), 0.80, 0.36),
}


def read_unity_materials():
    """Material name -> (linear rgb, metallic, glossiness) from the .mat assets."""
    out = {}
    if not os.path.isdir(MAT_DIR):
        return out
    for fname in sorted(os.listdir(MAT_DIR)):
        if not fname.endswith(".mat"):
            continue
        text = open(os.path.join(MAT_DIR, fname), encoding="utf-8").read()
        color = re.search(r"- _Color: \{r: ([-\d.eE]+), g: ([-\d.eE]+), b: ([-\d.eE]+)", text)
        metal = re.search(r"- _Metallic: ([-\d.eE]+)", text)
        gloss = re.search(r"- _Glossiness: ([-\d.eE]+)", text)
        if not color:
            continue
        key = fname[len("M_Char_"):-len(".mat")]
        out[key] = (
            (float(color.group(1)), float(color.group(2)), float(color.group(3))),
            float(metal.group(1)) if metal else 0.0,
            float(gloss.group(1)) if gloss else 0.2,
        )
    return out


def load_obj(path):
    verts = []
    faces = []          # (i0, i1, i2) 0-based
    face_mat = []       # index into materials list
    materials = []
    mat_index = {}
    current = 0
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("v "):
                _, x, y, z = line.split()[:4]
                verts.append((float(x), float(y), float(z)))
            elif line.startswith("usemtl"):
                name = line.split()[1]
                if name not in mat_index:
                    mat_index[name] = len(materials)
                    materials.append(name)
                current = mat_index[name]
            elif line.startswith("f "):
                idx = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
                for k in range(1, len(idx) - 1):
                    faces.append((idx[0], idx[k], idx[k + 1]))
                    face_mat.append(current)
    return (np.asarray(verts, dtype=np.float64),
            np.asarray(faces, dtype=np.int32),
            np.asarray(face_mat, dtype=np.int32),
            materials)


def vertex_normals(verts, faces):
    normals = np.zeros_like(verts)
    tri = verts[faces]
    fn = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    for k in range(3):
        np.add.at(normals, faces[:, k], fn)
    length = np.linalg.norm(normals, axis=1, keepdims=True)
    length[length < 1e-12] = 1.0
    return normals / length


def look_at(eye, target, up=(0.0, 1.0, 0.0)):
    eye = np.asarray(eye, dtype=np.float64)
    target = np.asarray(target, dtype=np.float64)
    forward = target - eye
    forward /= np.linalg.norm(forward)
    up = np.asarray(up, dtype=np.float64)
    right = np.cross(forward, up)
    if np.linalg.norm(right) < 1e-6:
        right = np.cross(forward, (0.0, 0.0, 1.0))
    right /= np.linalg.norm(right)
    true_up = np.cross(right, forward)
    return right, true_up, forward


def shade_fragment(normal, view_dir, base, metallic, gloss, lights, ambient):
    """Blinn-Phong with a metal tint and three-point rig; normals face the camera."""
    n = normal
    facing = np.einsum("ij,ij->i", n, view_dir) < 0.0
    n = np.where(facing[:, None], -n, n)
    diffuse = np.zeros_like(n[:, :1]) + ambient
    specular = np.zeros_like(n[:, :1])
    for direction, color, power in lights:
        light_dir = np.asarray(direction, dtype=np.float64)
        light_dir = light_dir / np.linalg.norm(light_dir)
        ndotl = np.clip(n @ light_dir, 0.0, 1.0)[:, None]
        diffuse = diffuse + ndotl * np.asarray(color, dtype=np.float64) * power
        half = light_dir[None, :] - view_dir
        half /= np.linalg.norm(half, axis=1, keepdims=True)
        ndoth = np.clip(np.einsum("ij,ij->i", n, half), 0.0, 1.0)[:, None]
        shininess = max(4.0, 2.0 / max(gloss, 0.02) ** 2)
        specular = specular + np.power(ndoth, shininess) * np.asarray(color)[None, :] * power
    base = np.asarray(base)[None, :]
    diffuse_color = base * (1.0 - metallic) + base * metallic * 0.4
    specular_color = (1.0 - metallic) * 0.35 + base * metallic
    color = diffuse_color * diffuse + specular_color * specular * (0.25 + 1.1 * gloss)
    return color


def render(verts, faces, face_mat, mat_lookup, size, ss, eye, target, fov_deg=32.0,
           ortho=False, ortho_scale=1.9, flat=False):
    width = height = size * ss
    zbuf = np.full((height, width), np.inf)
    image = np.zeros((height, width, 3), dtype=np.float64)
    image[:] = np.asarray([0.95, 0.05, 0.75] if flat else [0.055, 0.058, 0.066])

    right, up, forward = look_at(eye, target)
    rel = verts - np.asarray(eye)
    cam = np.stack([rel @ right, rel @ up, rel @ forward], axis=1)

    aspect = width / height
    if ortho:
        half_h = ortho_scale * 0.5
        half_w = half_h * aspect
        ndc = np.stack([cam[:, 0] / half_w, cam[:, 1] / half_h], axis=1)
    else:
        focal = 1.0 / math.tan(math.radians(fov_deg) * 0.5)
        half_h = 1.0
        half_w = aspect
        z = np.where(cam[:, 2] > 1e-4, cam[:, 2], 1e-4)
        ndc = np.stack([focal * cam[:, 0] / (z * half_w), focal * cam[:, 1] / (z * half_h)], axis=1)

    sx = (ndc[:, 0] * 0.5 + 0.5) * (width - 1)
    sy = (0.5 - ndc[:, 1] * 0.5) * (height - 1)
    sz = cam[:, 2]

    tri = np.stack([np.stack([sx[faces[:, k]], sy[faces[:, k]], sz[faces[:, k]]], axis=1)
                    for k in range(3)], axis=1)

    normals = vertex_normals(verts, faces)
    view_eye = np.asarray(eye, dtype=np.float64)
    center = verts.mean(axis=0)
    lights = [
        ((view_eye - center) + np.array([-1.6, 1.4, 0.6]), np.array([1.0, 0.96, 0.92]), 0.85),
        (np.array([1.5, 0.6, -1.4]), np.array([0.42, 0.52, 0.72]), 0.42),
        (np.array([-0.4, -0.5, 1.5]), np.array([0.35, 0.33, 0.42]), 0.30),
    ]
    ambient = 0.20

    # Cull triangles fully behind the camera; keep the rest.
    keep = (sz[faces] > 0.02) if not ortho else np.ones(len(faces), dtype=bool)
    # QA guard: drop extremely long thin triangles (a sweep whose samples
    # double back). They are authoring noise, not part of the silhouette.
    edges = np.stack([np.linalg.norm(tri[:, 0, :2] - tri[:, 1, :2], axis=1),
                      np.linalg.norm(tri[:, 1, :2] - tri[:, 2, :2], axis=1),
                      np.linalg.norm(tri[:, 2, :2] - tri[:, 0, :2], axis=1)], axis=1)
    edge_max = edges.max(axis=1)
    longest = edges.max(axis=1)
    shortest = np.maximum(edges.min(axis=1), 1e-6)
    keep &= ~((longest > 90.0) & (longest / shortest > 40.0))
    order = np.argsort(-tri[:, :, 2].mean(axis=1))

    for f in order:
        if not keep[f]:
            continue
        t = tri[f]
        x0 = max(int(math.floor(t[:, 0].min())), 0)
        x1 = min(int(math.ceil(t[:, 0].max())), width - 1)
        y0 = max(int(math.floor(t[:, 1].min())), 0)
        y1 = min(int(math.ceil(t[:, 1].max())), height - 1)
        if x1 < x0 or y1 < y0:
            continue
        area = ((t[1, 0] - t[0, 0]) * (t[2, 1] - t[0, 1]) -
                (t[2, 0] - t[0, 0]) * (t[1, 1] - t[0, 1]))
        if abs(area) < 1e-9:
            continue
        xs = np.arange(x0, x1 + 1) + 0.5
        ys = np.arange(y0, y1 + 1) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        w0 = ((t[1, 0] - gx) * (t[2, 1] - gy) - (t[2, 0] - gx) * (t[1, 1] - gy)) / area
        w1 = ((t[2, 0] - gx) * (t[0, 1] - gy) - (t[0, 0] - gx) * (t[2, 1] - gy)) / area
        w2 = 1.0 - w0 - w1
        eps = -1e-6 if area > 0 else 1e-6
        mask = (w0 >= eps) & (w1 >= eps) & (w2 >= eps)
        if not mask.any():
            continue
        depth = w0 * t[0, 2] + w1 * t[1, 2] + w2 * t[2, 2]
        sub_z = zbuf[y0:y1 + 1, x0:x1 + 1]
        hit = mask & (depth < sub_z)
        if not hit.any():
            continue
        sub_z[hit] = depth[hit]
        idx = np.nonzero(hit)
        px = idx[0] + y0
        py = idx[1] + x0
        n0, n1, n2 = normals[faces[f, 0]], normals[faces[f, 1]], normals[faces[f, 2]]
        w0h = w0[hit][:, None]
        w1h = w1[hit][:, None]
        w2h = w2[hit][:, None]
        nrm = w0h * n0[None, :] + w1h * n1[None, :] + w2h * n2[None, :]
        nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-9)
        pos = (w0h * verts[faces[f, 0]][None, :] + w1h * verts[faces[f, 1]][None, :] +
               w2h * verts[faces[f, 2]][None, :])
        view_dir = pos - view_eye
        view_dir /= np.maximum(np.linalg.norm(view_dir, axis=1, keepdims=True), 1e-9)
        name = mat_lookup[face_mat[f]]
        if flat:
            color = np.tile(np.asarray(name[0])[None, :], (len(px), 1)) * 0.55 + 0.06
        else:
            color = shade_fragment(nrm, view_dir, name[0], name[1], name[2], lights, ambient)
        image[px, py] = color
    # Simple gamma + tonemap for review readability.
    image = np.clip(image, 0.0, 1.0) ** (1.0 / 2.2)
    img = Image.fromarray((image * 255.0 + 0.5).astype(np.uint8), "RGB")
    if ss > 1:
        img = img.resize((size, size), Image.LANCZOS)
    return img


VIEWS = {
    # name: (eye offset (x, y, z) relative to target, target offset, ortho scale)
    "front": ((0.0, 0.05, 3.4), (0.0, 0.92, 0.0), 2.05),
    "back": ((0.0, 0.05, -3.4), (0.0, 0.92, 0.0), 2.05),
    "left": ((-3.4, 0.05, 0.0), (0.0, 0.92, 0.0), 2.05),
    "right": ((3.4, 0.05, 0.0), (0.0, 0.92, 0.0), 2.05),
    "three_quarter_front_left": ((-2.3, 0.75, 2.5), (0.0, 0.95, 0.0), 2.05),
    "three_quarter_front_right": ((2.3, 0.75, 2.5), (0.0, 0.95, 0.0), 2.05),
    "three_quarter_back_left": ((-2.3, 0.75, -2.5), (0.0, 0.95, 0.0), 2.05),
    "three_quarter_back_right": ((2.3, 0.75, -2.5), (0.0, 0.95, 0.0), 2.05),
    "high_front": ((0.0, 2.8, 2.2), (0.0, 1.2, 0.0), 2.05),
    "low_back": ((0.0, -0.6, -2.6), (0.0, 0.9, 0.0), 2.05),
    "detail_collar": ((-0.55, 0.30, 0.85), (0.0, 1.50, 0.0), 0.62),
    "detail_chest": ((-0.60, 0.05, 1.0), (0.0, 1.22, 0.0), 0.80),
    "detail_waist": ((-0.75, -0.10, 0.95), (0.0, 1.02, 0.02), 0.72),
    "detail_upper": ((-1.05, 0.45, 1.05), (0.0, 1.30, 0.02), 1.15),
    "detail_sleeve_l": ((-0.95, 0.35, 0.75), (-0.31, 1.24, 0.22), 0.80),
    "detail_shoulder_l": ((-0.75, 0.70, 0.85), (-0.18, 1.36, 0.05), 0.85),
    "detail_waist_side": ((-1.60, 0.10, 0.35), (0.0, 1.02, 0.0), 0.85),
    "detail_hand_left": ((-0.75, 0.05, 0.55), (-0.38, 0.92, 0.05), 0.46),
    "detail_boots": ((-0.85, 0.35, 0.90), (0.0, 0.22, 0.05), 0.95),
    "detail_knees": ((-1.0, 0.30, 0.85), (0.0, 0.50, 0.02), 0.95),
    "detail_back": ((0.30, 0.25, -1.15), (0.0, 1.10, 0.0), 1.10),
    "detail_hem": ((-0.9, -0.35, 0.75), (0.0, 0.60, 0.0), 1.0),
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=os.path.join(ROOT, "Docs/Protagonist"))
    parser.add_argument("--size", type=int, default=900)
    parser.add_argument("--supersample", type=int, default=2)
    parser.add_argument("--views", default=",".join(VIEWS.keys()))
    parser.add_argument("--contact", default=None, help="contact sheet path (default: <out>/contact_sheet.png)")
    parser.add_argument("--contact-scale", type=float, default=0.6,
                        help="contact-sheet tile scale, so the sheet stays small on disk")
    parser.add_argument("--scale", type=float, default=None,
                        help="QA: override the orthographic width (smaller = closer)")
    parser.add_argument("--only", default=None,
                        help="QA: comma-separated part name prefixes to keep (others hidden)")
    parser.add_argument("--ids", action="store_true",
                        help="QA: colour by material id (pairs with --flat)")
    parser.add_argument("--flat", action="store_true",
                        help="QA: unlit silhouette shading (shows missing geometry as background)")
    parser.add_argument("--solo", default=None,
                        help="QA: draw only this material in colour, everything else dim")
    args = parser.parse_args(argv)

    verts, faces, face_mat, materials = load_obj(OBJ_PATH)
    unity_mats = read_unity_materials()
    lookup = []
    for name in materials:
        entry = FALLBACK.get(name)
        if name in unity_mats:
            rgb, metal, gloss = unity_mats[name]
            # .mat colours are authored for the linear-space pipeline; the renderer
            # works in a display-ish space, so lift them a little for review.
            entry = (tuple(min(1.0, c * 1.05) for c in rgb), metal, gloss)
        elif entry is None:
            entry = ((0.5, 0.5, 0.5), 0.0, 0.2)
        lookup.append(entry)
    print(f"Loaded {len(verts)} vertices, {len(faces)} triangles, "
          f"{len(materials)} materials: {', '.join(materials)}")
    if args.only:
        csv_path = os.path.join(ROOT, "Docs/Protagonist/parts.csv")
        keep_prefixes = tuple(p.strip() for p in args.only.split(",") if p.strip())
        keep_faces = np.zeros(len(faces), dtype=bool)
        kept_parts = set()
        with open(csv_path, encoding="utf-8") as handle:
            next(handle)
            for line in handle:
                part, material, mfirst, count, ofirst, ocount = line.strip().split(",")
                if not part.startswith(keep_prefixes):
                    continue
                kept_parts.add(part)
                lo, hi = int(ofirst), int(ofirst) + int(ocount)
                keep_faces |= np.all((faces >= lo) & (faces < hi), axis=1)
        faces = faces[keep_faces]
        face_mat = face_mat[keep_faces]
        print(f"  only mode: {len(kept_parts)} parts, {len(faces)} triangles kept")
    if args.solo:
        solo_index = materials.index(args.solo)
        for index, entry in enumerate(lookup):
            if index != solo_index:
                lookup[index] = ((0.05, 0.05, 0.06), 0.0, 0.05)
            else:
                lookup[index] = ((0.85, 0.30, 0.25), 0.0, 0.3)
        print(f"  solo mode: {args.solo} highlighted")

    os.makedirs(args.out, exist_ok=True)
    wanted = [v.strip() for v in args.views.split(",") if v.strip()]
    tiles = []
    for name in wanted:
        if name not in VIEWS:
            print(f"  ! unknown view '{name}' (skipped)")
            continue
        offset, target, ortho_scale = VIEWS[name]
        if args.scale:
            ortho_scale = args.scale
        eye = (offset[0], offset[1], offset[2])
        if args.flat and args.ids:
            palette = [(0.95,0.25,0.25),(0.25,0.95,0.35),(0.30,0.45,0.98),(0.95,0.85,0.25),
                       (0.95,0.45,0.95),(0.25,0.90,0.90),(0.98,0.60,0.20),(0.60,0.55,0.95),
                       (0.55,0.35,0.20),(0.95,0.95,0.95),(0.45,0.45,0.48)]
            lookup = [(palette[i % len(palette)], 0.0, 0.05) for i in range(len(materials))]
            print("  material id colours:")
            for i, n in enumerate(materials):
                print(f"    {n:12s} rgb{palette[i % len(palette)]}")
        img = render(verts, faces, face_mat, lookup, args.size, args.supersample,
                     eye, target, ortho=True, ortho_scale=ortho_scale,
                     flat=args.flat)
        path = os.path.join(args.out, f"{name}.png")
        img.save(path, optimize=True)
        print(f"  wrote {os.path.relpath(path, ROOT)}")
        tiles.append((name, img))

    if tiles:
        cols = 4
        rows = math.ceil(len(tiles) / cols)
        tile = max(160, int(args.size * args.contact_scale))
        label = max(14, int(22 * args.contact_scale))
        sheet = Image.new("RGB", (cols * tile, rows * (tile + label)), (18, 18, 22))
        draw = ImageDraw.Draw(sheet)
        for index, (name, img) in enumerate(tiles):
            cx = (index % cols) * tile
            cy = (index // cols) * (tile + label)
            sheet.paste(img.resize((tile, tile), Image.LANCZOS), (cx, cy))
            draw.text((cx + 6, cy + tile + 4), name, fill=(190, 190, 200))
        contact = args.contact or os.path.join(args.out, "contact_sheet.png")
        sheet.save(contact, optimize=True)
        print(f"  wrote {os.path.relpath(contact, ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
