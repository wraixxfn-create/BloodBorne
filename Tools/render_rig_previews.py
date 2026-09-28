#!/usr/bin/env python3
"""Posed deformation previews for the Veilbound Wayfarer rig.

The authoring environment has no Unity editor, so this is the visual half of
the rig QA: it skins the protagonist mesh through `Tools/body_rig.py` for one
of the authored poses (bind / walk / attack / dodge), then renders the result
with the same z-buffer rasterizer `Tools/render_character_previews.py` uses
for the bind-pose turntable.

Usage:
    python3 Tools/render_rig_previews.py [output_dir] [pose ...]

Requires numpy + Pillow (authoring env only; never used by the game).
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "Tools"))

import body_rig as bd                      # noqa: E402
import render_character_previews as rc     # noqa: E402
import verify_rig as vz                    # noqa: E402

W, H = 520, 640

# pose -> [(name, yaw, pitch, target_y, distance, fov, target | None)]
POSES = {
    "bind": [("front", 0, 3, 0.95, 3.1, 38, None),
             ("threeQ", 40, 3, 0.95, 3.1, 38, None),
             ("arm_R", -55, 4, 1.20, 0.85, 34, (0.36, 1.15, 0.0))],
    "walk": [("front", 0, 3, 0.95, 3.1, 38, None),
             ("threeQ", 40, 3, 0.95, 3.1, 38, None),
             ("legs", -30, 10, 0.55, 1.60, 34, (-0.05, 0.55, 0.05))],
    "attack": [("front", 0, 3, 0.95, 3.1, 38, None),
               ("threeQ", -40, 3, 0.95, 3.1, 38, None),
               ("hand_R", -40, 12, 1.05, 0.75, 34, (0.36, 1.10, 0.10))],
    "dodge": [("front", 0, 3, 0.90, 3.1, 38, None),
              ("threeQ", 40, 3, 0.90, 3.1, 38, None),
              ("knees", -25, 12, 0.50, 1.50, 34, (-0.06, 0.50, 0.06))],
}


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1] in POSES \
        else os.path.join(ROOT, "Docs/CharacterPreviews")
    wanted = [a for a in sys.argv[1:] if a in POSES] or list(POSES)
    os.makedirs(out_dir, exist_ok=True)

    verts, faces, order = rc.load_obj(rc.OBJ_PATH)
    tris, mat_ids = [], []
    for mi, m in enumerate(order):
        for tri in faces[m]:
            tris.append(tri)
            mat_ids.append(mi)
    tris = np.asarray(tris)
    mat_ids = np.asarray(mat_ids)

    rig = vz.Rig(__import__("json").load(open(vz.RIG)), verts, faces, None)
    print(f"loaded {len(verts)} verts / {len(tris)} tris, "
          f"{sum(1 for i in range(len(verts)) if rig.detail[i])} detail verts")

    for pose in wanted:
        posed = rig.pose(pose)
        skinned = np.asarray([bd.skin_vertex(verts[i], rig.weights[i], posed,
                                             rig.joints)
                              for i in range(len(verts))])
        fn = np.cross(skinned[tris[:, 1]] - skinned[tris[:, 0]],
                      skinned[tris[:, 2]] - skinned[tris[:, 0]])
        vnorm = np.zeros_like(skinned)
        for k in range(3):
            np.add.at(vnorm, tris[:, k], fn)
        ln = np.linalg.norm(vnorm, axis=1)
        ln[ln < 1e-12] = 1.0
        vnorm = vnorm / ln[:, None]

        paths = []
        for (name, yaw, pitch, ty, dist, fov, target) in POSES[pose]:
            target = target or (0.0, ty, 0.0)
            img = rc.render_view(skinned, tris, mat_ids, vnorm, yaw, pitch,
                                 target, dist, fov, W, H)
            path = os.path.join(out_dir, f"RIG_{pose}_{name}.png")
            Image.fromarray(img).save(path)
            paths.append(path)
            print(f"  wrote {path}")

        sheet = Image.new("RGB", (W * len(paths), H), (16, 16, 20))
        for i, p in enumerate(paths):
            sheet.paste(Image.open(p), (i * W, 0))
        path = os.path.join(out_dir, f"RIG_{pose}_sheet.jpg")
        sheet.resize((W * len(paths) // 2, H // 2)).save(path, quality=88)
        print(f"  wrote {path}")


if __name__ == "__main__":
    main()
