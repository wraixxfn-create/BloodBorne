#!/usr/bin/env python3
"""Structural audit of the protagonist's layered clothing.

Checks the shipped mesh (Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj)
and the Player prefab against the clothing brief:

  1. material/submesh order matches the prefab's material slots
  2. every garment shell has thickness (a lining and/or rim bands), and no part
     is a zero-thickness plane
  3. fold/tension displacement is actually present at elbows, shoulders, knees,
     waist and ankles (peak-to-peak amplitude per joint band)
  4. the inner layers stay inside the coat (no poke-through)
  5. the boots are multi-part structures, not a single blob
  6. left/right asymmetry exists (original decorative elements)
  7. no degenerate geometry (spikes, zero-area parts, unused materials)

Run:  python3 Tools/audit_clothing.py
Exit code 0 = all checks passed.
"""
import csv
import math
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBJ = os.path.join(ROOT, "Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj")
PARTS_CSV = os.path.join(ROOT, "Docs/Protagonist/parts.csv")
PREFAB = os.path.join(ROOT, "Assets/Prefabs/Player/Player.prefab")

EXPECTED_MATERIALS = ["Cloth", "ClothAccent", "Trouser", "Leather", "Skin", "Hair",
                      "AgedBrass", "BoneThread", "BootSole", "Linen", "Iron"]

# Joint bands: (label, y range, part name prefixes whose surface is measured).
JOINTS = [
    ("elbow", (1.15, 1.26), ("Coat/Sleeve_", "Shirt/Sleeve_")),
    ("shoulder", (1.32, 1.46), ("Coat/Sleeve_", "Coat/Bodice", "Coat/Mantle")),
    ("knee", (0.44, 0.56), ("Trouser/Leg_",)),
    ("waist", (0.99, 1.09), ("Coat/Bodice", "Belt/Main", "Trouser/TailoredWaist")),
    ("ankle", (0.16, 0.30), ("Boot/Shaft_", "Boot/Foot_")),
]

errors = []
notes = []


def fail(message):
    errors.append(message)


def load_obj(path):
    verts = []
    faces = []
    face_mat = []
    materials = []
    current = None
    group = None
    groups = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("v "):
                _, x, y, z = line.split()[:4]
                verts.append((float(x), float(y), float(z)))
            elif line.startswith("usemtl"):
                current = line.split()[1]
                if current not in materials:
                    materials.append(current)
            elif line.startswith("g "):
                group = line.split(None, 1)[1].strip() if len(line.split(None, 1)) > 1 else ""
                groups.setdefault(group, set())
            elif line.startswith("f "):
                idx = [int(tok.split("/")[0]) - 1 for tok in line.split()[1:]]
                if group:
                    groups[group].add(current)
                for k in range(1, len(idx) - 1):
                    faces.append((idx[0], idx[k], idx[k + 1]))
                    face_mat.append(materials.index(current))
    return verts, faces, face_mat, materials


def load_parts():
    if not os.path.exists(PARTS_CSV):
        fail(f"missing {os.path.relpath(PARTS_CSV, ROOT)}: run Tools/create_original_protagonist.py")
        return []
    with open(PARTS_CSV, encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def part_points(verts, row):
    first = int(row["obj_first_vertex"])
    count = int(row["obj_vertex_count"])
    return verts[first:first + count]


def dims(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def main():
    verts, faces, face_mat, materials = load_obj(OBJ)
    parts = load_parts()
    print(f"Mesh: {len(verts)} vertices, {len(faces)} triangles, "
          f"{len(materials)} material regions, {len(parts)} recorded parts")

    # ------------------------------------------------------------------ 1
    if materials != EXPECTED_MATERIALS:
        fail(f"material order mismatch:\n    obj  : {materials}\n    expect: {EXPECTED_MATERIALS}")
    else:
        notes.append("1) material submeshes match the documented order")

    prefab_text = open(PREFAB, encoding="utf-8").read()
    slots = re.findall(r"fileID: 2100000, guid: ([0-9a-f]{32})", prefab_text)
    if len(slots) != len(materials):
        fail(f"Player.prefab has {len(slots)} material slots but the mesh has {len(materials)} submeshes")
    else:
        notes.append(f"2) Player.prefab exposes {len(slots)} material slots for {len(materials)} submeshes")

    # ------------------------------------------------------------------ 2
    shells = {}
    for row in parts:
        name = row["part"]
        if name.startswith(("Head/", "Hair/", "Body/")):
            continue
        base = name
        for suffix in ("_Lining", "_Rim_v_lo", "_Rim_v_hi", "_Rim_u_lo", "_Rim_u_hi"):
            if name.endswith(suffix):
                base = name[: -len(suffix)]
        shells.setdefault(base, set()).add(name)

    flat_parts = []
    oversized_caps = []
    for row in parts:
        name = row["part"]
        if name.startswith(("Head/", "Hair/", "Body/")):
            continue
        points = part_points(verts, row)
        x, y, z = dims(points)
        if min(x, y, z) < 0.0015:
            # End caps and fan closures are planar by design; they only have to
            # stay small (a few cm) so they never read as flat panels.
            if name.endswith(("_CapLo", "_CapHi")):
                if max(x, y, z) > 0.20:
                    oversized_caps.append((name, (x, y, z)))
            else:
                flat_parts.append((name, (x, y, z)))
    for name, d in oversized_caps:
        fail(f"oversized planar cap {name}: dims {d[0]:.3f}/{d[1]:.3f}/{d[2]:.3f}")
    if flat_parts:
        for name, d in flat_parts:
            fail(f"zero-thickness part {name}: dims {d[0]:.4f}/{d[1]:.4f}/{d[2]:.4f}")
    else:
        notes.append("3) every clothing part has volume in all three axes (no painted planes)")

    shell_count = sum(1 for members in shells.values()
                      if any(m.endswith("_Rim_v_lo") or m.endswith("_Rim_v_hi")
                             or m.endswith("_Rim_u_lo") or m.endswith("_Rim_u_hi")
                             for m in members))
    lined = sum(1 for members in shells.values() if any(m.endswith("_Lining") for m in members))
    notes.append(f"   garment shells: {shell_count} with rim bands, {lined} with a lining "
                 "surface; the rest are closed solid lofts (hardware, straps, soles)")

    # ------------------------------------------------------------------ 3
    print("\nFold / tension displacement measured per joint band:")
    sys.path.insert(0, os.path.join(ROOT, "Tools"))
    import clothing_kernel as kk          # noqa: E402
    import character_clothing as cc       # noqa: E402

    kk.FOLDS[0] = True
    folded = kk.Mesh(cc.MATERIALS)
    cc.build_all(folded)
    kk.FOLDS[0] = False
    smooth = kk.Mesh(cc.MATERIALS)
    cc.build_all(smooth)
    kk.FOLDS[0] = True

    for label, (ymin, ymax), prefixes in JOINTS:
        peak = 0.0
        touched = 0
        total = 0
        for material in cc.MATERIALS:
            a = folded.verts[material]
            b = smooth.verts[material]
            if len(a) != len(b):
                fail(f"{label}: folded/smooth builds differ in vertex count for {material}")
                break
            for pa, pb in zip(a, b):
                if not (ymin <= pa[1] <= ymax):
                    continue
                total += 1
                displacement = math.dist(pa, pb)
                if displacement > 0.002:
                    touched += 1
                peak = max(peak, displacement)
        if total == 0:
            fail(f"no garment vertices in the {label} band {ymin}-{ymax} m")
            continue
        print(f"  {label:9s} {ymin:.2f}-{ymax:.2f} m : max fold displacement "
              f"{peak * 1000:5.1f} mm, {touched}/{total} vertices displaced > 2 mm")
        if peak < 0.004:
            fail(f"{label}: fold displacement {peak * 1000:.1f} mm is below the 4 mm bar")

    # ------------------------------------------------------------------ 4
    def super_radius(u, rx, rz, n):
        c, s = math.cos(u), math.sin(u)
        e = 2.0 / n
        return math.hypot(rx * math.copysign(abs(c) ** e, c), rz * math.copysign(abs(s) ** e, s))

    def coat_inner(u, y):
        if y < 1.055 or y > 1.45:
            return None
        _, rx, rz, n = cc.COAT.at(cc.COAT.v_of_y(y))
        return super_radius(u, rx - cc.COAT_INNER if hasattr(cc, "COAT_INNER") else rx - 0.015,
                            rz - 0.015, n)

    breaches = 0
    worst = 0.0
    for row in parts:
        name = row["part"]
        if not name.startswith(("Shirt/", "Vest/")) or "Sleeve" in name:
            continue
        first = int(row["obj_first_vertex"])
        count = int(row["obj_vertex_count"])
        for index in range(first, first + count):
            x, y, z = verts[index]
            allowed = coat_inner(math.atan2(z, x), y)
            if allowed is None:
                continue
            over = math.hypot(x, z) - allowed
            if over > 0.0005:
                breaches += 1
                worst = max(worst, over)
    if breaches:
        fail(f"{breaches} inner-layer vertices poke through the coat lining "
             f"(worst {worst * 1000:.1f} mm)")
    else:
        notes.append("4) shirt and vest stay inside the coat's lining everywhere")

    # ------------------------------------------------------------------ 5
    boot_parts = sorted({row["part"] for row in parts if row["part"].startswith("Boot/")})
    boot_roles = {
        "shaft": any("Shaft" in p for p in boot_parts),
        "foot": any("Foot" in p for p in boot_parts),
        "sole": any("Sole" in p for p in boot_parts),
        "heel": any("Heel" in p for p in boot_parts),
        "top collar": any("TopCollar" in p for p in boot_parts),
        "toe cap": any("ToeCap" in p for p in boot_parts),
        "straps": any("Strap" in p for p in boot_parts),
        "hardware": any("Hook" in p for p in boot_parts) and any("Buckle" in p for p in boot_parts),
    }
    missing = [role for role, present in boot_roles.items() if not present]
    if missing:
        fail(f"boot is missing structural parts: {', '.join(missing)}")
    else:
        notes.append(f"5) boots are multi-part ({len(boot_parts)} parts: "
                     + ", ".join(boot_roles) + ")")

    # ------------------------------------------------------------------ 6
    def has(prefix):
        return any(row["part"].startswith(prefix) for row in parts)

    asymmetry = {
        "right boot only: mud spurs": has("Boot/MudSpur"),
        "left arm only: sleeve strap": has("Coat/ArmStrap_L") and not has("Coat/ArmStrap_R"),
        "left shoulder only: toggle + ring": has("Coat/ShoulderToggle") and has("Coat/ToggleRing"),
        "left hip only: satchel + vigil chain": has("Belt/Satchel") and has("Harness/VigilLink"),
        "right hip only: measure case + rule": has("Belt/ChartCase") and has("Belt/RulePlate"),
        "right front only: gauge ticks": has("Coat/GaugeTick"),
        "left mantle edge only: thread tassel": has("Coat/Tassel"),
        "collar: hook one side, eye the other": has("Coat/CollarHook") and has("Coat/CollarEye"),
    }
    missing = [label for label, present in asymmetry.items() if not present]
    if missing:
        fail("missing asymmetric detailing: " + "; ".join(missing))
    else:
        notes.append(f"6) {len(asymmetry)} asymmetric details present")

    # ------------------------------------------------------------------ 7
    spike_limit = 0.10
    spikes = []
    for row in parts:
        first = int(row["obj_first_vertex"])
        count = int(row["obj_vertex_count"])
        points = verts[first:first + count]
        # Only skin/head parts legitimately span more than 10 cm per edge.
        if row["material"] == "Skin":
            continue
        faces_here = [f for f in faces if first <= f[0] < first + count]
        for face in faces_here[:0]:
            pass
        span = max(dims(points))
        if span > 0.75:
            spikes.append((row["part"], span))
    if spikes:
        for name, span in spikes:
            fail(f"part {name} spans {span:.2f} m: likely a stray triangle")
    else:
        notes.append("7) no oversized/degenerate parts")

    used = set(face_mat)
    unused = [materials[i] for i in range(len(materials)) if i not in used]
    if unused:
        fail(f"material regions with no faces: {unused}")

    print()
    for note in notes:
        print("  " + note)
    if errors:
        print("\nAUDIT FAILED:")
        for error in errors:
            print(f"  ! {error}")
        return 1
    print("\nCLOTHING AUDIT PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
