#!/usr/bin/env python3
"""Original layered gothic clothing for the Vespershade protagonist.

Design notes (all original work, nothing traced from any existing game)
----------------------------------------------------------------------
Silhouette: a tall, narrow "Veilbound Wayfarer" in a storm-slate siege coat with
a wine-black lining, a shoulder mantle, a stiff standing collar and a leather
field harness worn over everything.

Layer stack, outermost first, with real offsets in metres:

    0. denim-dark trousers (tucked into the boots)
    1. bone-grey linen shirt   ~+0.014 off the body, 5 mm thick, V neckline
    2. body vest (wine cloth)  shirt +13 mm, 8 mm thick, front bib only
    3. siege coat (slate)      body +30..+50 mm, 14 mm thick shell
    4. mantle + collar         10-13 mm thick, sitting over the coat
    5. belt / baldric / straps over the coat, 6-15 mm thick

Every layer's surface is an explicit table, so the layers nest instead of
interpenetrating; each is authored as a shell (outer face, inner lining, rim
bands) and displaced by fold/tension functions around elbows, shoulders, knees,
waist and ankles.

Original motifs (not from any existing game):
  * "Gauged charter" - a descending row of brass gauge-ticks riveted down the
    right coat front, like the sighting marks on a surveying instrument.
  * "Vigil disc" - a layered iron/brass/thread roundel clasping the chest strap.
  * "Vigil chain" - five oval bone-thread links from the belt to the satchel.
  * "Mud spurs" - three bone-thread wedges on the outer face of the right boot.
  * "Quill and measure" - a rolled chart case and a flat rule strapped to the
    belt, with a wine thread tassel on the left hip and a brass toggle on the
    left shoulder: deliberate left/right asymmetry.
"""
import math

import clothing_kernel as kk
from clothing_kernel import TAU

MATERIALS = ["Cloth", "ClothAccent", "Trouser", "Leather", "Skin", "Hair",
             "AgedBrass", "BoneThread", "BootSole", "Linen", "Iron"]

# ---------------------------------------------------------------- body tables
# Outer surface of the base body (the torso skin is not modelled: the layers
# below stack straight onto these numbers, which the body mesh matches).
BODY_Y = [0.30, 0.42, 0.60, 0.72, 0.86, 0.95, 1.02, 1.10, 1.18, 1.26, 1.34, 1.42, 1.49]
BODY_RX = [0.200, 0.196, 0.196, 0.196, 0.219, 0.214, 0.203, 0.200, 0.212, 0.246, 0.276, 0.288, 0.256]
BODY_RZ = [0.130, 0.126, 0.126, 0.126, 0.138, 0.134, 0.126, 0.122, 0.126, 0.130, 0.133, 0.137, 0.120]


def body_rx(y):
    return kk.table(y, BODY_Y, BODY_RX)


def body_rz(y):
    return kk.table(y, BODY_Y, BODY_RZ)


def super_point(u, y, rx, rz, n=2.4):
    """Point on a super-ellipse section; n=2 is an ellipse, higher is boxier."""
    c, s = math.cos(u), math.sin(u)
    e = 2.0 / n
    return (rx * math.copysign(abs(c) ** e, c), y, rz * math.copysign(abs(s) ** e, s))


class Surface:
    """Piecewise-linear body-shaped surface: rows of (y, rx, rz, n)."""

    def __init__(self, rows):
        self.rows = rows
        self.ys = [row[0] for row in rows]

    def at(self, v):
        rows = self.rows
        v = kk.clamp(v)
        if v <= 0.0:
            return rows[0]
        if v >= 1.0:
            return rows[-1]
        span = 1.0 / (len(rows) - 1)
        index = min(int(v / span), len(rows) - 2)
        local = (v - index * span) / span
        a, b = rows[index], rows[index + 1]
        return tuple(a[i] + (b[i] - a[i]) * local for i in range(len(a)))

    def v_of_y(self, y):
        ys = self.ys
        if y <= ys[0]:
            return 0.0
        if y >= ys[-1]:
            return 1.0
        for i in range(len(ys) - 1):
            if ys[i] <= y <= ys[i + 1]:
                return (i + (y - ys[i]) / (ys[i + 1] - ys[i])) / (len(ys) - 1)
        return 1.0

    def point(self, u, v, extra=0.0):
        y, rx, rz, n = self.at(v)
        x, _, z = super_point(u, 0.0, rx + extra, rz + extra, n)
        return (x, y, z)

    def point_y(self, u, y, extra=0.0):
        return self.point(u, self.v_of_y(y), extra)

    def normal(self, u, v, extra=0.0):
        a = self.point(u - 0.012, v, extra)
        b = self.point(u + 0.012, v, extra)
        c = self.point(u, max(0.0, v - 0.02), extra)
        d = self.point(u, min(1.0, v + 0.02), extra)
        normal = kk.vnorm(kk.vcross(kk.vsub(b, a), kk.vsub(d, c)))
        centre = self.point(0.0, v, extra)
        if kk.vdot(normal, kk.vsub(self.point(u, v, extra), (0.0, centre[1], 0.0))) < 0.0:
            normal = kk.vmul(normal, -1.0)
        return normal

    def normal_y(self, u, y, extra=0.0):
        return self.normal(u, self.v_of_y(y), extra)


# ------------------------------------------------------------------ surfaces
SHIRT = Surface([
    # (y, rx, rz, superellipse power)
    (0.800, 0.192, 0.128, 2.4),
    (0.860, 0.196, 0.130, 2.4),
    (0.900, 0.204, 0.132, 2.4),
    (1.010, 0.203, 0.130, 2.4),
    (1.090, 0.209, 0.134, 2.4),
    (1.170, 0.214, 0.139, 2.4),
    (1.250, 0.240, 0.148, 2.35),
    (1.320, 0.256, 0.152, 2.3),
    (1.380, 0.268, 0.154, 2.3),
    (1.420, 0.258, 0.148, 2.3),
    (1.450, 0.220, 0.130, 2.3),
    (1.472, 0.150, 0.110, 2.3),
    (1.492, 0.104, 0.090, 2.3),
    (1.524, 0.101, 0.088, 2.3),
])

# The vest hugs the shirt: the bib narrows toward the collar so it can never
# cross the coat's lining at the shoulders.
VEST = Surface([(y, rx + 0.010 - 0.006 * kk.smoothstep(1.16, 1.36, y),
                 rz + 0.010 - 0.006 * kk.smoothstep(1.16, 1.36, y), n)
                for (y, rx, rz, n) in SHIRT.rows])

COAT = Surface([
    (0.430, 0.232, 0.152, 2.9),
    (0.620, 0.236, 0.155, 2.8),
    (0.820, 0.230, 0.152, 2.7),
    (1.000, 0.234, 0.156, 2.7),
    (1.055, 0.236, 0.158, 2.6),
    (1.100, 0.242, 0.160, 2.6),
    (1.160, 0.249, 0.164, 2.6),
    (1.220, 0.258, 0.170, 2.5),
    (1.275, 0.268, 0.174, 2.4),
    (1.330, 0.280, 0.178, 2.4),
    (1.380, 0.292, 0.180, 2.3),
    (1.420, 0.298, 0.180, 2.2),
    (1.444, 0.286, 0.172, 2.2),
    (1.466, 0.244, 0.156, 2.2),
    (1.482, 0.188, 0.136, 2.2),
    (1.494, 0.150, 0.120, 2.2),
])
COAT_INNER = 0.015      # lining offset below the coat's outer surface
COAT_BODY_GAP = 0.030   # the coat's inner face sits this far off the body

MANTLE = Surface([
    (1.286, 0.344, 0.196, 3.0),
    (1.322, 0.340, 0.196, 2.9),
    (1.358, 0.328, 0.192, 2.8),
    (1.398, 0.302, 0.186, 2.6),
    (1.432, 0.276, 0.178, 2.5),
    (1.462, 0.248, 0.168, 2.4),
    (1.486, 0.194, 0.144, 2.2),
    (1.502, 0.130, 0.114, 2.1),
])


# ============================================================================
# Trousers
# ============================================================================
def build_trousers(mesh):
    """Fuller tailored trousers: knee break, hanging thigh, gathered ankle."""
    for side, label in ((-1, "L"), (1, "R")):
        spec = [
            (0.97, 0.104, 0.000, 0.116, 0.126),
            (0.90, 0.106, 0.004, 0.114, 0.124),
            (0.80, 0.109, 0.009, 0.110, 0.120),
            (0.70, 0.112, 0.013, 0.104, 0.114),
            (0.62, 0.114, 0.015, 0.098, 0.107),
            (0.55, 0.116, 0.016, 0.093, 0.101),
            (0.50, 0.117, 0.017, 0.090, 0.098),
            (0.45, 0.118, 0.018, 0.088, 0.096),
            (0.40, 0.119, 0.019, 0.085, 0.093),
            (0.35, 0.120, 0.021, 0.081, 0.089),
            (0.31, 0.120, 0.022, 0.078, 0.086),
            (0.275, 0.120, 0.023, 0.076, 0.084),
        ]
        stations = [((side * x, y, z), rx, rz) for (y, x, z, rx, rz) in spec]

        def fold(u, v):
            # Compression break across the knee, heaviest at the front.
            knee = kk.fold_accordion(v, 0.62, 0.085, 3.0, 0.0075) * \
                (0.45 + 0.55 * math.cos(u - math.pi * 0.5))
            # Cloth pulled off the hip and left to hang in long soft creases.
            drape = (kk.fold_slant(u, v, 0.15, 0.28, 0.5, 0.4, 0.005) +
                     kk.fold_space(u, v, 5.0, 0.004, 0.05, 0.6))
            ankle = kk.fold_gather(v, 0.94, 0.05, 4.0, 0.0058)
            return knee + drape + ankle

        kk.sweep_shell(mesh, f"Trouser/Leg_{label}", stations, 26, "Trouser",
                       lambda tu, tv: 0.012 - 0.003 * tv,
                       material_in="Trouser", material_rim="Trouser",
                       fold=kk.angle_fold(fold), v_lo_rim=False, v_hi_rim=True,
                       inner="edges", inner_band=(2, 2))

    waist_rows = [
        (0.760, 0.196, 0.128, 2.4),
        (0.860, 0.214, 0.138, 2.4),
        (0.940, 0.212, 0.134, 2.4),
        (1.010, 0.203, 0.127, 2.4),
        (1.060, 0.196, 0.124, 2.4),
    ]
    grid = [[super_point(TAU * j / 44, row[0], row[1], row[2], row[3]) for j in range(44)]
            for row in waist_rows]

    def waist_fold(u, v):
        return (kk.fold_accordion(v, 0.9, 0.2, 5.0, 0.004, 0.6) +
                kk.fold_slant(u, v, math.pi, 0.25, 0.5, 0.3, 0.004))

    kk.build_shell(mesh, "Trouser/TailoredWaist", grid, 0.008, "Trouser",
                   material_in="Trouser", material_rim="Trouser", close_u=True,
                   inside=lambda p: (0.0, p[1], 0.0),
                   v_lo_rim=False, v_hi_rim=True, inner="edges", inner_band=(2, 2),
                   fold=kk.angle_fold(waist_fold))
    kk.ellipsoid(mesh, "Trouser/Seat", "Trouser", (0.0, 0.87, -0.012),
                 (0.216, 0.150, 0.132), 16, 28)
    kk.ellipsoid(mesh, "Trouser/UpperThigh", "Trouser", (0.0, 0.85, 0.012),
                 (0.196, 0.120, 0.116), 12, 20)


# ============================================================================
# Layer 1: linen shirt
# ============================================================================
def build_shirt(mesh):
    cols = 44
    neck_rows = 4
    total = len(SHIRT.rows) + neck_rows
    grid = []
    for i in range(total):
        v = i / (total - 1)
        row = []
        for j in range(cols):
            u = TAU * j / cols
            # Front V neckline: plunges at the centre, rides high at the sides.
            delta = abs(kk.angle_delta(u, math.pi * 0.5))
            front = max(0.0, 1.0 - kk.clamp((delta - 0.05) / 0.40)) ** 1.4
            if i < len(SHIRT.rows):
                y, rx, rz, n = SHIRT.rows[i]
                row.append(super_point(u, y, rx, rz, n))
            else:
                # Yoke: gather from the neckline in to the standing neck ring.
                t = (i - len(SHIRT.rows) + 1) / neck_rows
                t *= (1.0 - 0.92 * front)
                base = super_point(u, 1.492, 0.104, 0.090, 2.3)
                target = super_point(u, 1.524, 0.101, 0.088, 2.3)
                row.append(kk.vlerp(base, target, t))
        # Deepen the front V a little beyond the fitted neckline.
        grid.append(row)
    # Carve the V by pulling the front edge rows down along y (the neckline).
    v_shift = {}
    for i in range(total):
        v = i / (total - 1)
        for j in range(cols):
            u = TAU * j / cols
            delta = abs(kk.angle_delta(u, math.pi * 0.5))
            front = max(0.0, 1.0 - kk.clamp((delta - 0.05) / 0.40)) ** 1.4
            if front > 0.0 and v > 0.78:
                drop = 0.062 * front * kk.smoothstep(0.78, 1.0, v)
                point = grid[i][j]
                grid[i][j] = (point[0], point[1] - drop, point[2])

    def fold(u, v):
        return (kk.fold_accordion(v, 0.10, 0.10, 4.0, 0.0045) +
                kk.fold_slant(u, v, 0.30, 0.45, 0.45, 0.5, 0.004) +
                kk.fold_slant(u, v, TAU - 0.30, 0.45, 0.45, 0.5, 0.004))

    kk.build_shell(mesh, "Shirt/Body", grid, 0.005, "Linen", material_in="Linen",
                   material_rim="Linen", close_u=True,
                   inside=lambda p: (0.0, p[1], 0.0), v_lo_rim=True, v_hi_rim=True,
                   inner="edges", inner_band=(2, 3), fold=kk.angle_fold(fold))
    build_shirt_sleeves(mesh)


def build_shirt_sleeves(mesh):
    """Thin under-sleeves: the cuff shows between coat sleeve and glove."""
    for side, label in ((-1, "L"), (1, "R")):
        stations = [
            ((side * 0.150, 1.432, -0.006), 0.058, 0.086),
            ((side * 0.210, 1.402, 0.000), 0.074, 0.088),
            ((side * 0.270, 1.348, 0.008), 0.081, 0.083),
            ((side * 0.310, 1.288, 0.016), 0.077, 0.076),
            ((side * 0.334, 1.224, 0.022), 0.071, 0.070),
            ((side * 0.354, 1.168, 0.027), 0.066, 0.066),
            ((side * 0.370, 1.108, 0.032), 0.061, 0.061),
            ((side * 0.379, 1.048, 0.035), 0.057, 0.057),
            ((side * 0.383, 1.000, 0.037), 0.056, 0.056),
            ((side * 0.384, 0.952, 0.038), 0.058, 0.057),
        ]

        def fold(u, v):
            return (kk.fold_accordion(v, 0.60, 0.10, 3.0, 0.004) +
                    kk.fold_gather(v, 0.96, 0.05, 5.0, 0.005) +
                    kk.fold_slant(u, v, math.pi * 0.5, 0.12, 0.6, 0.2, 0.004))

        kk.sweep_shell(mesh, f"Shirt/Sleeve_{label}", stations, 18, "Linen",
                       lambda tu, tv: 0.004, material_in="Linen", material_rim="Linen",
                       fold=kk.angle_fold(fold), v_lo_rim=False, v_hi_rim=True,
                       inner="edges", inner_band=(2, 2), ref_a=(1.0, 0.0, 0.0))


# ============================================================================
# Layer 2: body vest (front bib, wine cloth)
# ============================================================================
def build_vest(mesh):
    cols = 32
    rows = 12
    grid = []
    for i in range(rows):
        v = i / (rows - 1)
        row = []
        for j in range(cols):
            t = j / (cols - 1)
            u = math.pi * 0.5 + (t - 0.5) * 1.86      # 107 degrees of front arc
            top = 1.432 - 0.055 * (abs(t - 0.5) * 2.0) ** 1.7
            y = kk.lerp(1.100, top, v)
            point = VEST.point(u, VEST.v_of_y(y))
            row.append(point)
        grid.append(row)

    def fold(u, v):
        return (kk.fold_slant(u, v, math.pi * 0.5, 0.55, 0.5, 0.5, 0.0035) +
                kk.fold_accordion(v, 0.08, 0.08, 3.0, 0.003))

    kk.build_shell(mesh, "Vest/FrontBib", grid, 0.008, "ClothAccent",
                   material_in="Linen", material_rim="ClothAccent", close_u=False,
                   inside=lambda p: (0.0, p[1], 0.0), fold=fold,
                   v_lo_rim=False, v_hi_rim=True, u_lo_rim=True, u_hi_rim=True,
                   inner="edges", inner_band=(3, 2))
    # Side seam tapes: the bib reads as a garment, not a decal.
    for sign, label in ((-1, "L"), (1, "R")):
        path = []
        for index in range(6):
            y = kk.lerp(1.05, 1.40, index / 5.0)
            u = math.pi * 0.5 + sign * 0.88
            path.append(VEST.point_y(u, y, 0.006))
        kk.tube(mesh, f"Vest/SeamTape_{label}", path, "ClothAccent", 0.0022, 8)


# ============================================================================
# Layer 3: the siege coat
# ============================================================================
def _front_gap(v, gap_waist, gap_chest, gap_neck, mid=0.62):
    """Half-angle of the coat's front opening at normalised height v."""
    if v < mid:
        return kk.lerp(gap_waist, gap_chest, v / mid)
    return kk.lerp(gap_chest, gap_neck, (v - mid) / (1.0 - mid))


def coat_surface_point(u, y, extra=0.0):
    return COAT.point_y(u, y, extra)


def build_coat(mesh):
    build_coat_bodice(mesh)
    build_coat_skirt(mesh)
    build_coat_sleeves(mesh)
    build_mantle(mesh)
    build_collar(mesh)


def build_coat_bodice(mesh):
    """Chest/torso of the coat: thick shell, open front, tailored yoke."""
    cols = 46
    rows = [row[:3] for row in COAT.rows if row[0] >= 1.055]
    rows = sorted(rows, key=lambda r: r[0])
    total = len(rows)
    grid = []
    for i in range(total):
        v = i / (total - 1)
        gap = _front_gap(v, 0.085, 0.105, 0.150, mid=0.66)
        u0 = math.pi * 0.5 + gap
        span = TAU - 2.0 * gap
        y, rx, rz = rows[i]
        n = kk.table(y, [r[0] for r in COAT.rows], [r[3] for r in COAT.rows])
        row = [super_point(u0 + span * (j / (cols - 1)), y, rx, rz, n) for j in range(cols)]
        grid.append(row)

    def fold(t_u, t_v):
        angle = math.pi * 0.5 + 0.085 + (TAU - 0.17) * t_u
        out = 0.0
        # Shoulder-blade tension creases, one per side.
        out += kk.fold_slant(angle, t_v, math.pi * 1.35, 0.80, 0.30, 0.16, 0.0055, tilt=0.5)
        out += kk.fold_slant(angle, t_v, math.pi * 0.65, 0.80, 0.30, 0.16, 0.0055, tilt=-0.5)
        # Waist compression under the belt.
        out += kk.fold_accordion(t_v, 0.10, 0.09, 4.0, 0.005)
        # Creases pulled from the front opening.
        out += kk.fold_slant(angle, t_v, math.pi * 0.5 + 0.22, 0.72, 0.22, 0.35, 0.005)
        out += kk.fold_slant(angle, t_v, math.pi * 0.5 - 0.22, 0.72, 0.22, 0.35, 0.005)
        return out

    kk.build_shell(mesh, "Coat/Bodice", grid, 0.014, "Cloth",
                   material_in="ClothAccent", material_rim="ClothAccent", close_u=False,
                   inside=lambda p: (0.0, p[1], 0.0), fold=fold,
                   v_lo_rim=True, v_hi_rim=False, u_lo_rim=True, u_hi_rim=True,
                   inner="full")
    build_lapels(mesh)
    build_bodice_details(mesh)


def build_lapels(mesh):
    """Folded-back lapels with thickness; the right leaf laps wider."""
    for sign, label, reach, roll in ((-1, "L", 0.30, 0.012), (1, "R", 0.44, 0.017)):
        cols = 12
        rows = 10
        grid = []
        for i in range(rows):
            v = i / (rows - 1)
            y = kk.lerp(1.494, 1.318, v ** 0.9)
            gap = _front_gap(kk.lerp(1.0, 0.62, v), 0.085, 0.105, 0.150, mid=0.66)
            row = []
            for j in range(cols):
                t = j / (cols - 1)
                spread = (reach * (1.0 - 0.55 * v) + 0.045)
                attach_u = math.pi * 0.5 + sign * gap
                u = attach_u - sign * spread * t
                y_pt = y - 0.040 * t * (1.0 - 0.5 * v)
                offset = 0.014 + roll * t + 0.004 * math.sin(t * math.pi)
                row.append(COAT.point_y(u, y_pt, offset))
            grid.append(row)
        kk.build_shell(mesh, f"Coat/Lapel_{label}", grid, 0.011, "Cloth",
                       material_in="ClothAccent", material_rim="ClothAccent",
                       close_u=False, inside=lambda p: (0.0, p[1], -0.06),
                       v_lo_rim=True, v_hi_rim=True, u_lo_rim=False, u_hi_rim=True,
                       inner="full")


def build_bodice_details(mesh):
    """Chest tie, shoulder toggle, gauge ticks and pocket chevrons."""
    # Cloth frog knot closing the coat at the sternum: a doubled loop with a
    # brass stud, one of the garment's few soft-format fasteners.
    knot = COAT.point_y(math.pi * 0.5 - 0.050, 1.380, 0.018)
    kk.ellipsoid(mesh, "Coat/Knot", "Leather", knot, (0.022, 0.014, 0.011), 10, 14)
    kk.ellipsoid(mesh, "Coat/KnotStud", "AgedBrass", kk.vadd(knot, (0.0, 0.003, 0.013)),
                 (0.0085, 0.0085, 0.005), 8, 12)
    # Left shoulder: brass toggle on a leather thong (deliberate asymmetry).
    u_toggle = math.pi * 0.5 + 1.05
    base = COAT.point_y(u_toggle, 1.436, 0.026)
    kk.ellipsoid(mesh, "Coat/ShoulderToggle", "AgedBrass", base,
                 (0.017, 0.019, 0.012), 10, 14)
    kk.ring_torus(mesh, "Coat/ToggleRing", "AgedBrass",
                  kk.vadd(base, (0.004, -0.018, 0.0)), 0.010, 0.0026, sides=12,
                  ring_sides=6, axis=(0.35, 0.94, 0.0))
    # Original motif: descending gauge ticks down the right coat front.
    for index in range(7):
        t = index / 6.0
        y = kk.lerp(1.344, 1.118, t)
        gap = _front_gap(kk.clamp((y - 1.055) / 0.44), 0.085, 0.105, 0.150, mid=0.66)
        u = math.pi * 0.5 - gap + 0.052
        scale = 1.0 - 0.35 * t
        point = COAT.point_y(u, y, 0.016)
        kk.ellipsoid(mesh, f"Coat/GaugeTick_{index}", "AgedBrass", point,
                     (0.0045 * scale, 0.0125 * scale, 0.0035), 6, 10)
    # Pocket chevrons: raised bone-thread stitching, one per panel.
    for sign, label in ((-1, "L"), (1, "R")):
        path = []
        for index in range(9):
            t = index / 8.0
            y = kk.lerp(1.150, 1.088, abs(t * 2.0 - 1.0) * 0.5 + t * 0.5)
            u = math.pi * 0.5 + sign * (0.30 + 0.34 * t)
            path.append(COAT.point_y(u, y, 0.016))
        kk.tube(mesh, f"Coat/PocketTrim_{label}", path, "Cloth", 0.0026, 8)


def build_coat_skirt(mesh):
    """Two skirt panels: front overlap, split back, thick rimmed edges."""
    for sign, label in ((-1, "L"), (1, "R")):
        cols = 26
        rows = 20
        grid = []
        for i in range(rows):
            v = i / (rows - 1)
            y = kk.lerp(1.115, 0.398, v ** 0.98)
            front_gap = kk.lerp(0.070, 0.46, v ** 0.85) * (1.0 if sign > 0 else 1.18)
            back_gap = kk.lerp(0.050, 0.30, v ** 0.9)
            span = math.pi - front_gap - back_gap
            if sign > 0:
                u0, u1 = math.pi * 0.5 - front_gap, math.pi * 0.5 - front_gap - span
            else:
                u0, u1 = math.pi * 0.5 + front_gap, math.pi * 0.5 + front_gap + span
            row = []
            for j in range(cols):
                t = j / (cols - 1)
                u = u0 + (u1 - u0) * t
                # Hem lifts slightly at the sides so the coat reads tailored.
                y_pt = y + 0.038 * math.sin(math.pi * t) * v ** 2
                # The panel starts tucked inside the bodice, then flares.
                flare = kk.lerp(0.024, 0.078, v ** 1.25)
                rx = body_rx(y_pt) + flare
                rz = body_rz(y_pt) + flare
                n = kk.lerp(2.7, 3.1, v)
                row.append(super_point(u, y_pt, rx, rz, n))
            grid.append(row)

        def fold(u, v, sign=sign):
            # Wide vertical drape folds, deepening toward the hem.
            ribs = kk.fold_space(u, v, 4.2, 0.010, 0.30, 1.0)
            side = kk.fold_slant(u, v, math.pi * 0.5 + sign * 1.35, 0.35, 0.55, 0.35, 0.006)
            front = kk.fold_slant(u, v, math.pi * 0.5 + sign * 0.02, 0.55, 0.22, 0.4, 0.005)
            back = kk.fold_slant(u, v, math.pi * 1.5 - sign * 0.02, 0.5, 0.22, 0.4, 0.006)
            return ribs + side + front + back

        kk.build_shell(mesh, f"Coat/Skirt_{label}", grid,
                       lambda tu, tv: 0.012 + 0.005 * tv,
                       "Cloth", material_in="ClothAccent", material_rim="ClothAccent",
                       close_u=False, inside=lambda p: (0.0, p[1], 0.0), fold=fold,
                       v_lo_rim=False, v_hi_rim=True, u_lo_rim=True, u_hi_rim=True,
                       inner="full")
        build_hem_strap(mesh, sign, label)


def _skirt_surface(y):
    """Approximate skirt shell radius at a given height (for straps/keepers)."""
    v = kk.clamp((1.115 - y) / 0.717)
    flare = kk.lerp(0.024, 0.078, v ** 1.25)
    return lambda u: super_point(u, y, body_rx(y) + flare, body_rz(y) + flare,
                                 kk.lerp(2.7, 3.1, v))


def build_hem_strap(mesh, sign, label):
    """Leather strap and iron buckle cinching each front skirt panel."""
    y_strap = 0.640
    surface = _skirt_surface(y_strap)
    u_front = math.pi * 0.5 + sign * 0.30
    path, normals = [], []
    for index in range(7):
        t = index / 6.0
        u = u_front + sign * t * 0.62
        y = y_strap - 0.02 * t
        point = kk.vadd(surface(u), (0.0, 0.0, 0.0))
        point = (point[0], y, point[2])
        path.append(point)
        normals.append(kk.vnorm((math.cos(u), 0.0, math.sin(u))))
    kk.strap(mesh, f"Coat/HemStrap_{label}", path, normals, "Leather", 0.024, 0.007)
    mid = 3
    end, normal = path[mid], normals[mid]
    side = kk.vnorm(kk.vcross(kk.vsub(path[mid + 1], path[mid - 1]), normal))
    for bar in (-1, 1):
        a = kk.vadd(end, kk.vmul(side, bar * 0.022))
        b = kk.vadd(kk.vadd(a, kk.vmul(normal, 0.006)), kk.vmul(side, bar * 0.006))
        kk.tube(mesh, f"Coat/HemBuckle_{label}_{bar}", [a, b], "Iron", 0.0045, 8)
    kk.tube(mesh, f"Coat/HemBucklePin_{label}",
            [kk.vadd(end, kk.vmul(side, -0.022)), kk.vadd(end, kk.vmul(side, 0.028))],
            "Iron", 0.0032, 8)


def build_coat_sleeves(mesh):
    """Sleeves with a filled shoulder head, elbow break and turned-back cuff."""
    for side, label in ((-1, "L"), (1, "R")):
        stations = [
            ((side * 0.128, 1.430, -0.008), 0.070, 0.098),
            ((side * 0.196, 1.406, -0.002), 0.086, 0.100),
            ((side * 0.262, 1.352, 0.006), 0.092, 0.094),
            ((side * 0.305, 1.290, 0.014), 0.088, 0.087),
            ((side * 0.331, 1.226, 0.020), 0.081, 0.080),
            ((side * 0.352, 1.170, 0.026), 0.076, 0.076),
            ((side * 0.368, 1.110, 0.031), 0.071, 0.071),
            ((side * 0.378, 1.048, 0.034), 0.067, 0.067),
            ((side * 0.382, 1.000, 0.036), 0.066, 0.066),
        ]

        def fold(u, v):
            out = 0.0
            # Elbow: ridges wrap the joint, heaviest behind the arm.
            out += kk.fold_accordion(v, 0.62, 0.10, 3.0, 0.0062) * \
                (0.45 + 0.55 * math.cos(u - math.pi * 1.5))
            # Sleeve head gathered where the arm enters the shoulder.
            out += kk.fold_gather(v, 0.05, 0.06, 4.0, 0.0060)
            # Shoulder pull creases at the front and back of the armhole.
            out += kk.fold_slant(u, v, math.pi * 0.5, 0.20, 0.55, 0.16, 0.0048)
            out += kk.fold_slant(u, v, math.pi * 1.5, 0.20, 0.55, 0.16, 0.0048)
            # Forearm crushing toward the cuff.
            out += kk.fold_accordion(v, 0.90, 0.08, 3.0, 0.0045)
            return out

        kk.sweep_shell(mesh, f"Coat/Sleeve_{label}", stations, 24, "Cloth",
                       lambda tu, tv: 0.013 - 0.002 * tv,
                       material_in="ClothAccent", material_rim="ClothAccent",
                       fold=kk.angle_fold(fold), v_lo_rim=False, v_hi_rim=True,
                       inner="full", ref_a=(1.0, 0.0, 0.0))
        cuff_stations = [
            ((side * 0.380, 1.030, 0.035), 0.069, 0.069),
            ((side * 0.383, 1.008, 0.036), 0.073, 0.072),
            ((side * 0.385, 0.986, 0.037), 0.074, 0.073),
            ((side * 0.386, 0.972, 0.038), 0.071, 0.070),
        ]

        def cuff_fold(u, v):
            return (kk.fold_gather(v, 0.5, 0.3, 3.0, 0.0035) +
                    kk.fold_slant(u, v, math.pi * 1.5, 0.5, 0.5, 0.5, 0.003))

        kk.sweep_shell(mesh, f"Coat/Cuff_{label}", cuff_stations, 24, "Leather",
                       lambda tu, tv: 0.007, material_in="Leather",
                       material_rim="Leather", fold=kk.angle_fold(cuff_fold),
                       v_lo_rim=True, v_hi_rim=True, inner="full",
                       ref_a=(1.0, 0.0, 0.0))
        ring = [(side * 0.383 + 0.0755 * math.cos(TAU * j / 20), 0.981,
                 0.0365 + 0.0745 * math.sin(TAU * j / 20)) for j in range(20)]
        kk.tube(mesh, f"Coat/CuffPiping_{label}", ring, "BoneThread", 0.0028, 8,
                close=True, ref_a=(0.0, 1.0, 0.0))
        for index, angle in enumerate((math.pi * 1.35, math.pi * 0.65)):
            point = (side * 0.383 + 0.078 * math.cos(angle), 0.999,
                     0.036 + 0.076 * math.sin(angle))
            kk.ellipsoid(mesh, f"Coat/CuffStud_{label}{index}", "AgedBrass", point,
                         (0.006, 0.006, 0.006), 8, 10)
    # Left arm only: upper-arm strap with a small keeper (asymmetry).
    path, normals = [], []
    for index in range(9):
        angle = TAU * index / 9
        path.append((-0.296 + 0.098 * math.cos(angle), 1.288,
                     0.012 + 0.094 * math.sin(angle)))
        normals.append((math.cos(angle), 0.0, math.sin(angle)))
    kk.strap(mesh, "Coat/ArmStrap_L", path, normals, "Leather", 0.026, 0.007, close=True)


def build_mantle(mesh):
    """Storm mantle: a short shoulder cape with a thick rimmed hem."""
    cols = 48
    rows = MANTLE.rows
    total = len(rows)
    grid = []
    for i in range(total):
        v = i / (total - 1)
        # Opens at the front so the lapels and chest read through it.
        front_gap = kk.lerp(0.13, 0.60, (1.0 - v) ** 1.15)
        u0 = math.pi * 0.5 + front_gap
        span = TAU - 2.0 * front_gap
        y, rx, rz, n = rows[i]
        row = []
        for j in range(cols):
            t = j / (cols - 1)
            u = u0 + span * t
            # Keel-shaped hem: lowest at the sides, lifted front and back.
            y_pt = y + 0.056 * (1.0 - v) ** 1.4 * (math.cos(u * 2.0) * 0.5 + 0.5)
            row.append(super_point(u, y_pt, rx, rz, n))
        grid.append(row)

    def fold(u, v):
        ribs = kk.fold_space(u, v, 6.4, 0.011, 0.25, 1.0)
        shoulder = (kk.fold_slant(u, v, math.pi * 0.5 + 0.85, 0.45, 0.35, 0.35, 0.006) +
                    kk.fold_slant(u, v, math.pi * 0.5 - 0.85, 0.45, 0.35, 0.35, 0.006))
        return ribs + shoulder

    def mantle_hidden(p):
        # Everything above the mantle's own surface is air: the inside reference
        # for winding is the vertical body axis.
        return (0.0, p[1], 0.0)

    kk.build_shell(mesh, "Coat/Mantle", grid, 0.013, "Cloth",
                   material_in="ClothAccent", material_rim="ClothAccent", close_u=False,
                   inside=mantle_hidden, fold=fold,
                   v_lo_rim=False, v_hi_rim=True, u_lo_rim=True, u_hi_rim=True,
                   inner="full")
    # Stitched panel seams across each shoulder.
    for sign, label in ((-1, "L"), (1, "R")):
        path = []
        for index in range(8):
            t = index / 7.0
            u = math.pi * 0.5 + sign * (0.72 + t * 0.78)
            row = MANTLE.at(kk.lerp(0.42, 0.95, t))
            point = super_point(u, row[0] + 0.02, row[1] + 0.006, row[2] + 0.006, row[3])
            path.append(point)
        kk.tube(mesh, f"Coat/MantleSeam_{label}", path, "Cloth", 0.0024, 8)
    # Wine thread tassel hanging from the mantle's front-left edge.
    row = MANTLE.at(0.0)
    anchor = super_point(math.pi * 0.5 + 0.62, row[0] + 0.016, row[1] - 0.004,
                         row[2] - 0.004, row[3])
    for index in range(3):
        drift = (index - 1) * 0.009
        kk.tube(mesh, f"Coat/Tassel_{index}",
                [(anchor[0] + drift * 0.4, anchor[1], anchor[2]),
                 (anchor[0] + drift, anchor[1] - 0.038, anchor[2] + 0.003),
                 (anchor[0] + drift * 1.4, anchor[1] - 0.072, anchor[2] + 0.005)],
                "ClothAccent", lambda t: 0.0038 * (1.0 - 0.7 * t), 8)


def build_collar(mesh):
    """Stiff standing collar rising off the coat's neck opening."""
    cols = 40
    rows = 10
    grid = []
    for i in range(rows):
        v = i / (rows - 1)
        row = []
        for j in range(cols):
            t = j / (cols - 1)
            gap_low, gap_high = 0.125, 0.165
            gap = kk.lerp(gap_low, gap_high, v)
            u0 = math.pi * 0.5 + gap
            span = TAU - 2.0 * gap
            u = u0 + span * t
            back = 0.5 + 0.5 * math.cos(u - math.pi * 1.5)
            front = abs(kk.angle_delta(u, math.pi * 0.5)) / math.pi
            top = 1.662 - 0.052 * (front * 2.0) ** 1.25 - 0.012 * (1.0 - back)
            base = 1.488
            y = kk.lerp(base, top, v ** 0.9)
            # Flares outward as it rises, most at the back.
            flare = 1.0 + 0.10 * v + 0.05 * v * back
            rx, rz = 0.150 * flare, 0.128 * flare
            row.append(super_point(u, y, rx, rz, 2.2))
        grid.append(row)

    def fold(u, v):
        waves = 0.0035 * v * math.cos(u * 5.0)
        roll = kk.fold_slant(u, v, math.pi * 1.15, 0.62, 0.45, 0.45, 0.010)
        return waves + roll

    kk.build_shell(mesh, "Coat/Collar", grid, 0.012, "Cloth",
                   material_in="ClothAccent", material_rim="ClothAccent", close_u=False,
                   inside=lambda p: (0.0, p[1], 0.0), fold=fold,
                   v_lo_rim=True, v_hi_rim=True, u_lo_rim=True, u_hi_rim=True,
                   inner="full")
    path = [kk.vadd(grid[rows - 1][j], (0.0, 0.0035, 0.0)) for j in range(0, cols, 2)]
    kk.tube(mesh, "Coat/CollarStitch", path, "BoneThread", 0.0026, 8)
    # Brass hook on the right leaf, eye and cord on the left (asymmetry).
    right_leaf = grid[rows - 2][0]
    left_leaf = grid[rows - 2][cols - 1]
    kk.tube(mesh, "Coat/CollarHook",
            [kk.vadd(right_leaf, (0.008, -0.028, -0.002)),
             kk.vadd(right_leaf, (0.016, -0.006, 0.004))], "AgedBrass", 0.0038, 8)
    kk.ring_torus(mesh, "Coat/CollarEye", "AgedBrass",
                  kk.vadd(left_leaf, (-0.014, -0.014, 0.002)), 0.008, 0.0022,
                  sides=12, ring_sides=6)
    kk.tube(mesh, "Coat/CollarCord",
            [kk.vadd(left_leaf, (-0.016, -0.016, 0.002)),
             kk.vadd(left_leaf, (-0.022, -0.060, 0.006)),
             kk.vadd(left_leaf, (-0.016, -0.096, 0.004))],
            "BoneThread", lambda t: 0.0032 * (1.0 - 0.5 * t), 8)


# ============================================================================
# Belt, pouches and harness
# ============================================================================
def build_belt(mesh):
    cols = 52
    rows = 6
    grid = []
    for i in range(rows):
        v = i / (rows - 1)
        row = []
        for j in range(cols):
            u = TAU * j / cols
            y = kk.lerp(0.988, 1.082, v)
            # The belt sags a little at the front under its own weight.
            y += 0.012 * math.cos(u - math.pi * 0.5) * (1.0 - abs(v - 0.5) * 2.0)
            row.append(COAT.point_y(u, y, 0.008))
        grid.append(row)

    def fold(u, v):
        return 0.0022 * math.cos(u * 7.0) + kk.fold_accordion(v, 0.5, 0.6, 2.0, 0.0025)

    kk.build_shell(mesh, "Belt/Main", grid, 0.015, "Leather", material_in="Leather",
                   material_rim="Leather", close_u=True,
                   inside=lambda p: (0.0, p[1], 0.0), fold=fold,
                   v_lo_rim=True, v_hi_rim=True, inner="edges", inner_band=(2, 3))
    lower = [COAT.point_y(TAU * j / cols, 0.974, 0.012) for j in range(cols)]
    kk.tube(mesh, "Belt/UnderStrap", lower, "Leather", 0.008, 8, close=True,
            ref_a=(0.0, 1.0, 0.0), squash=lambda r, a: (r * 1.6, r * 0.75))

    front_u = math.pi * 0.5
    centre = COAT.point_y(front_u, 1.036, 0.026)
    normal = kk.vnorm((0.0, 0.0, 1.0))
    side = (1.0, 0.0, 0.0)
    up = (0.0, 1.0, 0.0)
    for sign in (-1, 1):
        a = kk.vadd(centre, kk.vmul(side, sign * 0.036))
        kk.tube(mesh, f"Belt/BuckleSide_{sign}",
                [kk.vadd(a, kk.vmul(up, -0.030)), kk.vadd(a, kk.vmul(up, 0.030))],
                "Iron", 0.0062, 10)
        b = kk.vadd(centre, kk.vmul(up, sign * 0.030))
        kk.tube(mesh, f"Belt/BuckleBar_{sign}",
                [kk.vadd(b, kk.vmul(side, -0.036)), kk.vadd(b, kk.vmul(side, 0.036))],
                "Iron", 0.0062, 10)
    kk.tube(mesh, "Belt/BuckleTongue",
            [kk.vadd(centre, kk.vmul(side, -0.030)),
             kk.vadd(kk.vadd(centre, kk.vmul(side, 0.030)), kk.vmul(normal, 0.002))],
            "AgedBrass", 0.0042, 10)
    kk.ellipsoid(mesh, "Belt/BuckleProng", "AgedBrass",
                 kk.vadd(centre, kk.vmul(up, 0.012)), (0.007, 0.026, 0.006), 8, 12)
    for index, angle in enumerate((math.pi * 0.5 + 0.55, math.pi * 0.5 - 0.55,
                                   math.pi * 1.5 + 0.42, math.pi * 1.5 - 0.42)):
        path, normals = [], []
        for step in range(7):
            y = kk.lerp(0.994, 1.076, step / 6.0)
            path.append(COAT.point_y(angle, y, 0.017))
            normals.append(kk.vnorm((math.cos(angle), 0.0, math.sin(angle))))
        kk.strap(mesh, f"Belt/Keeper_{index}", path, normals, "Leather", 0.030, 0.0055,
                 chamfer=0.45, section_scale=0.6)
    for index in range(6):
        angle = math.pi * 0.5 + (index - 2.5) * 0.30
        point = COAT.point_y(angle, 1.026, 0.025)
        kk.ellipsoid(mesh, f"Belt/Rivet_{index}", "AgedBrass", point,
                     (0.0062, 0.0062, 0.0042), 8, 10,
                     rotation=(kk.vnorm((math.cos(angle), 0.0, math.sin(angle))),
                               (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)))
    build_belt_kit(mesh)


def _hip_frame(u, y, extra=0.0):
    """Local frame on the body at (angle u, height y): outward, side, up.

    Everything on the belt (satchel, chart case, rule) is built in this frame so
    parts sit flat against the hip instead of floating off it.
    """
    point = COAT.point_y(u, y, extra)
    outward = kk.vnorm((COAT.point_y(u + 0.02, y, extra)[0] - COAT.point_y(u - 0.02, y, extra)[0],
                        0.0,
                        COAT.point_y(u + 0.02, y, extra)[2] - COAT.point_y(u - 0.02, y, extra)[2]))
    up = (0.0, 1.0, 0.0)
    side = kk.vnorm(kk.vcross(up, outward))
    return point, outward, side, up


def build_belt_kit(mesh):
    """Satchel on the left hip, measure case and rule on the right (asymmetry)."""
    # ---------------- left hip: field satchel ---------------------------------
    point, out, side, up = _hip_frame(math.pi * 0.5 + 1.00, 0.982, 0.014)

    def local(depth, along, height, depth_scale=1.0):
        return kk.vadd(point, kk.vadd(kk.vmul(out, depth * depth_scale),
                                      kk.vadd(kk.vmul(side, along), kk.vmul(up, height))))

    # Body: four diminishing rounded plates from the hip outward, so the satchel
    # is a solid box with a flat back pressed against the coat.
    kk.solid_loft(mesh, "Belt/Satchel", [
        [local(0.000, sx * 0.040, sy * 0.050) for (sx, sy) in _rounded_square(1.0)],
        [local(0.018, sx * 0.045, sy * 0.056) for (sx, sy) in _rounded_square(1.0)],
        [local(0.038, sx * 0.043, sy * 0.054) for (sx, sy) in _rounded_square(0.98)],
        [local(0.050, sx * 0.036, sy * 0.045) for (sx, sy) in _rounded_square(0.9)],
    ], "Leather", inside=lambda p: kk.vsub(point, kk.vmul(out, 0.05)))
    # Flap: a thin curved lid over the top third, hinged at the back.
    flap = []
    for (depth, along_scale, height, thick) in ((0.054, 0.98, 0.046, 0.0),
                                                (0.058, 1.0, 0.012, 0.0),
                                                (0.048, 0.98, -0.018, 0.0)):
        flap.append([local(depth, sx * 0.044 * along_scale, height + sy * 0.011)
                     for (sx, sy) in _rounded_square(1.0)])
    kk.solid_loft(mesh, "Belt/SatchelFlap", flap, "Leather",
                  inside=lambda p: kk.vsub(point, kk.vmul(out, 0.02)))
    # Buckle strap down the flap face and two brass studs.
    kk.strap(mesh, "Belt/SatchelStrap",
             [local(0.060, 0.0, 0.040), local(0.064, 0.0, 0.012),
              local(0.054, 0.0, -0.010)], [out, out, out],
             "Leather", 0.018, 0.0045)
    for index, along in enumerate((-0.022, 0.022)):
        kk.ellipsoid(mesh, f"Belt/SatchelStud{index}", "AgedBrass",
                     local(0.054, along, 0.040), (0.0045, 0.0045, 0.0035), 8, 10,
                     rotation=(out, up, side))
    # Buckle frame on the strap end.
    kk.tube(mesh, "Belt/SatchelBuckle",
            [local(0.060, -0.012, -0.006), local(0.060, 0.012, -0.006)], "Iron", 0.0032, 8)

    # ---------------- right hip: measure case + rule ---------------------------
    point_r, out_r, side_r, up_r = _hip_frame(math.pi * 0.5 - 1.06, 0.995, 0.026)

    def local_r(depth, along, height):
        return kk.vadd(point_r, kk.vadd(kk.vmul(out_r, depth),
                                        kk.vadd(kk.vmul(side_r, along), kk.vmul(up_r, height))))

    case_path = [local_r(0.024, 0.0, 0.048 - index * 0.024) for index in range(5)]
    kk.tube(mesh, "Belt/ChartCase", case_path, "Leather", 0.020, 12)
    for index, end in enumerate((0, 4)):
        kk.ellipsoid(mesh, f"Belt/ChartCaseCap{index}", "AgedBrass", case_path[end],
                     (0.015, 0.007, 0.015), 8, 12,
                     rotation=(kk.vnorm((0.0, 1.0, 0.0)), out_r, side_r))
    # Flat brass rule lashed across the case: a rectangular plate with thickness.
    rule = []
    for (depth, scale) in ((0.040, 1.0), (0.046, 1.0)):
        rule.append([local_r(depth, sx * 0.024 * scale, sz * 0.013 * scale)
                     for (sx, sz) in _rounded_square(1.0)])
    kk.solid_loft(mesh, "Belt/RulePlate", rule, "Iron",
                  inside=lambda p: local_r(0.02, 0.0, 0.0))


def _rounded_square(scale):
    points = []
    for index in range(12):
        angle = TAU * index / 12
        c, s = math.cos(angle), math.sin(angle)
        limit = min(1.0, 1.0 / max(abs(c), abs(s), 1e-6)) ** 0.55
        points.append((c * limit * scale, s * limit * scale))
    return points


def build_harness(mesh):
    """Field harness: baldric over the right shoulder, cross strap, vigil disc."""
    # --- baldric: an explicit 3D loop so it lies on the coat, not in the air.
    keys = [
        ((0.196, 1.446, -0.052), (0.55, 0.83, -0.10)),
        ((0.196, 1.404, 0.086), (0.72, 0.42, 0.55)),
        ((0.150, 1.320, 0.150), (0.52, 0.05, 0.85)),
        ((0.062, 1.240, 0.176), (0.24, 0.0, 0.97)),
        ((-0.052, 1.170, 0.170), (-0.24, 0.0, 0.97)),
        ((-0.150, 1.104, 0.146), (-0.54, 0.0, 0.84)),
        ((-0.226, 1.026, 0.078), (-0.86, -0.14, 0.49)),
        ((-0.238, 1.010, -0.040), (-0.95, -0.28, -0.14)),
        ((-0.206, 1.108, -0.148), (-0.76, 0.0, -0.65)),
        ((-0.132, 1.216, -0.190), (-0.44, 0.0, -0.90)),
        ((-0.032, 1.308, -0.208), (-0.12, 0.10, -0.99)),
        ((0.086, 1.382, -0.184), (0.30, 0.34, -0.89)),
        ((0.170, 1.432, -0.104), (0.52, 0.68, -0.52)),
        ((0.196, 1.446, -0.052), (0.55, 0.83, -0.10)),
    ]
    path = kk.smooth_path([p for (p, n) in keys], 46)
    normals = kk.smooth_path([n for (p, n) in keys], 46)
    normals = [kk.vnorm(n) for n in normals]
    kk.strap(mesh, "Harness/Baldric", path, normals, "Leather", 0.050, 0.010, chamfer=0.35)
    for index, t in enumerate((0.12, 0.30, 0.62, 0.82)):
        point = path[int(t * (len(path) - 1))]
        normal = normals[int(t * (len(path) - 1))]
        kk.ellipsoid(mesh, f"Harness/BaldricRivet{index}", "AgedBrass", point,
                     (0.0075, 0.0075, 0.005), 8, 12,
                     rotation=(normal, (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)))
    # Harness plate riding on the baldric itself, where it crosses the chest.
    plate = path[int(0.46 * (len(path) - 1))]
    plate_normal = normals[int(0.46 * (len(path) - 1))]
    build_vigil_disc(mesh, kk.vadd(plate, kk.vmul(plate_normal, 0.004)), plate_normal)
    # --- vigil chain: five oval thread links from the belt to the satchel
    link_path = [COAT.point_y(math.pi * 0.5 + 0.86 + index * 0.035,
                              0.968 - index * 0.009, 0.030) for index in range(6)]
    for index in range(5):
        a, b = link_path[index], link_path[index + 1]
        mid = kk.vmul(kk.vadd(a, b), 0.5)
        kk.ring_torus(mesh, f"Harness/VigilLink{index}", "BoneThread", mid, 0.0115,
                      0.0024, sides=10, ring_sides=6,
                      axis=kk.vnorm(kk.vsub(b, a)),
                      ref=kk.vnorm(kk.vcross(kk.vsub(b, a), (0.0, 1.0, 0.0))))


def build_vigil_disc(mesh, centre, normal):
    """Layered iron/brass/thread roundel: the harness clasp and its motif."""
    side = kk.vnorm(kk.vcross(normal, (0.0, 1.0, 0.0)))
    up = kk.vnorm(kk.vcross(side, normal))
    rings = []
    for (radius, depth) in ((0.001, 0.0), (0.030, 0.010), (0.038, 0.012), (0.034, -0.002)):
        rings.append([kk.vadd(centre, kk.vadd(kk.vmul(side, radius * math.cos(TAU * i / 16)),
                                              kk.vadd(kk.vmul(up, radius * math.sin(TAU * i / 16)),
                                                      kk.vmul(normal, depth))))
                      for i in range(16)])
    kk.solid_loft(mesh, "Harness/VigilDiscFrame", rings, "Iron",
                  inside=lambda p: kk.vsub(centre, kk.vmul(normal, 0.05)),
                  cap_lo=True, cap_hi=True)
    kk.ellipsoid(mesh, "Harness/VigilDiscCore", "ClothAccent",
                 kk.vadd(centre, kk.vmul(normal, 0.006)), (0.026, 0.026, 0.008), 8, 16,
                 rotation=(normal, up, side))
    kk.ring_torus(mesh, "Harness/VigilDiscRing", "AgedBrass",
                  kk.vadd(centre, kk.vmul(normal, 0.014)), 0.020, 0.0035, sides=16,
                  ring_sides=6, axis=normal, ref=side)
    for index in range(3):
        angle = math.pi * (0.25 + index * 0.25)
        start = kk.vadd(centre, kk.vadd(kk.vmul(side, 0.013 * math.cos(angle)),
                                        kk.vadd(kk.vmul(up, 0.013 * math.sin(angle)),
                                                kk.vmul(normal, 0.013))))
        end = kk.vadd(centre, kk.vadd(kk.vmul(side, 0.026 * math.cos(angle)),
                                      kk.vadd(kk.vmul(up, 0.026 * math.sin(angle)),
                                              kk.vmul(normal, 0.011))))
        kk.tube(mesh, f"Harness/VigilTick{index}", [start, end], "BoneThread", 0.0022, 6)


# ============================================================================
# Gloves
# ============================================================================
def build_gloves(mesh):
    for side, label in ((-1, "L"), (1, "R")):
        build_glove(mesh, side, label)


def build_glove(mesh, side, label):
    # Gauntlet cuff flaring over the coat cuff.
    cuff_stations = [
        ((side * 0.380, 1.030, 0.034), 0.074, 0.073),
        ((side * 0.382, 1.006, 0.036), 0.079, 0.077),
        ((side * 0.384, 0.982, 0.037), 0.076, 0.074),
    ]
    kk.sweep_shell(mesh, f"Glove/Cuff_{label}", cuff_stations, 22, "Leather",
                   lambda tu, tv: 0.008, material_in="Leather", material_rim="Leather",
                   v_lo_rim=True, v_hi_rim=True, inner="full", ref_a=(1.0, 0.0, 0.0))
    # Hand: flat palm shell; ra is lateral thickness, rb the front-back width.
    hand_stations = [
        ((side * 0.384, 0.982, 0.038), 0.030, 0.044),
        ((side * 0.388, 0.950, 0.044), 0.028, 0.049),
        ((side * 0.391, 0.916, 0.050), 0.027, 0.051),
        ((side * 0.393, 0.888, 0.054), 0.026, 0.048),
        ((side * 0.394, 0.868, 0.056), 0.023, 0.040),
    ]

    def hand_fold(u, v):
        # Tension across the back of the hand, compression in the palm.
        return (kk.fold_slant(u, v, 0.0, 0.55, 0.7, 0.35, 0.0028) +
                kk.fold_accordion(v, 0.06, 0.10, 2.0, 0.0025))

    kk.sweep_shell(mesh, f"Glove/Hand_{label}", hand_stations, 20, "Leather",
                   lambda tu, tv: 0.006, material_in="Leather", material_rim="Leather",
                   fold=kk.angle_fold(hand_fold), v_lo_rim=True, v_hi_rim=False,
                   inner="full", ref_a=(1.0, 0.0, 0.0))
    # Four fingers spread front-to-back, curling toward the palm (inward).
    for index in range(4):
        z_off = (1.5 - index) * 0.0235
        length = (0.068, 0.076, 0.072, 0.056)[index]
        curl = (0.014, 0.018, 0.017, 0.011)[index]
        base_z = 0.056 + z_off
        base_x = side * (0.393 - abs(z_off) * 0.10)
        path = [
            (base_x, 0.872, base_z),
            (base_x - side * curl * 0.35, 0.842, base_z + 0.004),
            (base_x - side * curl * 0.75, 0.872 - length * 0.78, base_z + 0.008),
            (base_x - side * curl, 0.872 - length, base_z + 0.010),
        ]
        radii = [0.0148, 0.0142, 0.0122, 0.0088]
        stations = [(path[i], radii[i], radii[i] * 0.95) for i in range(4)]
        kk.sweep_shell(mesh, f"Glove/Finger_{label}{index + 1}", stations, 10, "Leather",
                       lambda tu, tv: 0.0035, material_in="Leather",
                       material_rim="Leather", v_lo_rim=True, v_hi_rim=True,
                       inner="full", ref_a=(1.0, 0.0, 0.0))
    thumb_path = [
        (side * 0.360, 0.930, 0.096),
        (side * 0.342, 0.902, 0.112),
        (side * 0.336, 0.874, 0.120),
        (side * 0.340, 0.858, 0.124),
    ]
    thumb_radii = [0.019, 0.0165, 0.0135, 0.0105]
    stations = [(thumb_path[i], thumb_radii[i], thumb_radii[i]) for i in range(4)]
    kk.sweep_shell(mesh, f"Glove/Thumb_{label}", stations, 12, "Leather",
                   lambda tu, tv: 0.0035, material_in="Leather", material_rim="Leather",
                   v_lo_rim=True, v_hi_rim=True, inner="full", ref_a=(1.0, 0.0, 0.0))
    # Back-of-hand charter plate: one leather plate with three brass rivets.
    plate = []
    for (dx, scale) in ((0.0, 1.0), (0.010, 1.0)):
        plate.append([(side * (0.396 + dx), 0.906 + sy * 0.044, 0.050 + sx * 0.030)
                      for (sx, sy) in _rounded_square(scale)])
    kk.solid_loft(mesh, f"Glove/KnucklePlate_{label}", plate, "Leather",
                  inside=lambda p: (side * 0.37, 0.906, 0.050))
    for index, dz in enumerate((0.020, 0.0, -0.020)):
        kk.ellipsoid(mesh, f"Glove/PlateRivet_{label}{index}", "AgedBrass",
                     (side * 0.407, 0.906, 0.050 + dz), (0.003, 0.010, 0.010), 8, 10)
    # Wrist strap with an iron buckle on the gauntlet.
    path, normals = [], []
    for index in range(13):
        angle = TAU * index / 13
        path.append((side * 0.382 + 0.083 * math.cos(angle), 1.014,
                     0.036 + 0.082 * math.sin(angle)))
        normals.append((math.cos(angle), 0.0, math.sin(angle)))
    kk.strap(mesh, f"Glove/WristStrap_{label}", path, normals, "Leather", 0.022, 0.006,
             close=True, chamfer=0.4)
    buckle = (side * 0.382, 1.018, 0.036 + 0.084)
    kk.ellipsoid(mesh, f"Glove/Buckle_{label}", "Iron", buckle,
                 (0.011, 0.008, 0.005), 8, 10,
                 rotation=((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)))


# ============================================================================
# Boots
# ============================================================================
def build_boots(mesh):
    for side, label in ((-1, "L"), (1, "R")):
        build_boot(mesh, side, label)


def build_boot(mesh, side, label):
    """Field boot: slim officer last, tall structured shaft, thin stitched sole."""
    x = side * 0.120
    # --- shaft over the calf: taller and closer to the leg than a work boot
    shaft = [
        ((x, 0.382, 0.028), 0.083, 0.089),
        ((x, 0.350, 0.028), 0.085, 0.091),
        ((x, 0.305, 0.026), 0.088, 0.094),
        ((x, 0.255, 0.024), 0.087, 0.093),
        ((x, 0.210, 0.023), 0.083, 0.089),
        ((x, 0.172, 0.022), 0.076, 0.082),
    ]

    def shaft_fold(u, v):
        # Calf tension at the top, ankle compression where the foot hinges, and
        # the vertical pull of the leather down the shaft.
        return (kk.fold_accordion(v, 0.26, 0.18, 3.0, 0.0042) +
                kk.fold_accordion(v, 0.62, 0.10, 2.0, 0.0044) *
                (0.5 + 0.5 * math.cos(u - math.pi * 0.5)) +
                kk.fold_gather(v, 0.96, 0.10, 6.0, 0.0040) +
                kk.fold_slant(u, v, math.pi * 1.5, 0.55, 0.6, 0.35, 0.0048))

    kk.sweep_shell(mesh, f"Boot/Shaft_{label}", shaft, 22, "Leather",
                   lambda tu, tv: 0.010, material_in="Leather", material_rim="Leather",
                   fold=kk.angle_fold(shaft_fold), v_lo_rim=True, v_hi_rim=True,
                   inner="edges", inner_band=(3, 3), ref_a=(1.0, 0.0, 0.0))
    # Folded-over top edge of the shaft: a doubled band with its own rim.
    collar = [
        ((x, 0.396, 0.028), 0.086, 0.092),
        ((x, 0.386, 0.028), 0.091, 0.097),
        ((x, 0.372, 0.028), 0.090, 0.096),
        ((x, 0.362, 0.028), 0.085, 0.091),
    ]
    kk.sweep_shell(mesh, f"Boot/TopCollar_{label}", collar, 22, "Leather",
                   lambda tu, tv: 0.009, material_in="Leather", material_rim="Leather",
                   v_lo_rim=True, v_hi_rim=True, inner="full", ref_a=(1.0, 0.0, 0.0))
    # --- foot: long, narrow last with a tapered toe
    foot_stations = [
        ((x, 0.126, -0.142), 0.030, 0.046),
        ((x, 0.126, -0.126), 0.050, 0.072),
        ((x, 0.126, -0.074), 0.068, 0.080),
        ((x, 0.122, -0.014), 0.075, 0.079),
        ((x, 0.110, 0.048), 0.076, 0.070),
        ((x, 0.098, 0.112), 0.073, 0.058),
        ((x, 0.084, 0.172), 0.063, 0.045),
        ((x, 0.070, 0.218), 0.047, 0.033),
        ((x, 0.062, 0.248), 0.026, 0.018),
    ]

    def foot_fold(u, v):
        # Creases across the instep where the boot flexes over the toes.
        return (kk.fold_accordion(v, 0.62, 0.16, 3.0, 0.0036) * (0.4 + 0.6 * math.cos(u)) +
                kk.fold_accordion(v, 0.30, 0.12, 2.0, 0.0028))

    kk.sweep_shell(mesh, f"Boot/Foot_{label}", foot_stations, 24, "Leather",
                   lambda tu, tv: 0.008, material_in="Leather", material_rim="Leather",
                   fold=kk.angle_fold(foot_fold), v_lo_rim=False, v_hi_rim=False,
                   inner="edges", inner_band=(3, 3), ref_a=(1.0, 0.0, 0.0),
                   ref_b=(0.0, 1.0, 0.0), cap_lo=True, cap_hi=True,
                   cap_material="Leather")
    build_boot_sole(mesh, side, label)
    build_boot_details(mesh, side, label)


def build_boot_sole(mesh, side, label):
    """Thin stitched sole, stacked heel and a reinforced leather toe cap.

    The footprint is sampled from the foot loft so the sole follows the last
    exactly instead of reading as a platform under it.
    """
    x = side * 0.120
    footprint = [
        (-0.144, 0.024), (-0.130, 0.040), (-0.104, 0.056), (-0.064, 0.070), (-0.014, 0.077),
        (0.040, 0.078), (0.095, 0.075), (0.150, 0.068), (0.205, 0.056),
        (0.248, 0.034),
    ]
    outline = ([(x + hw, z) for (z, hw) in footprint] +
               [(x - hw, z) for (z, hw) in reversed(footprint)])
    rings = [[(x + (px - x) * scale, y, pz) for (px, pz) in outline]
             for (scale, y) in ((0.94, 0.002), (1.0, 0.010), (1.0, 0.019), (0.96, 0.026))]
    kk.solid_loft(mesh, f"Boot/Sole_{label}", rings, "BootSole",
                  inside=lambda p: (x, 0.014, 0.02), cap_lo=True, cap_hi=True)
    # Stacked heel: two tapering layers under the back of the sole.
    heel_profile = [(-0.148, 0.028), (-0.134, 0.038), (-0.108, 0.052),
                    (-0.070, 0.062), (-0.028, 0.064)]
    heel_outline = ([(x + hw, z) for (z, hw) in heel_profile] +
                    [(x - hw, z) for (z, hw) in reversed(heel_profile)])
    heel_rings = [[(x + (px - x) * scale, y, pz) for (px, pz) in heel_outline]
                  for (scale, y) in ((0.88, 0.0), (0.97, 0.014), (1.0, 0.027))]
    kk.solid_loft(mesh, f"Boot/Heel_{label}", heel_rings, "BootSole",
                  inside=lambda p: (x, 0.013, -0.06), cap_lo=True, cap_hi=True)
    # Toe cap: reinforced leather shell over the front of the last, with its own
    # top rim so the reinforcement reads as a stitched-on panel.
    cap_stations = [
        ((x, 0.098, 0.112), 0.078, 0.060),
        ((x, 0.084, 0.172), 0.068, 0.047),
        ((x, 0.070, 0.218), 0.051, 0.035),
        ((x, 0.062, 0.246), 0.030, 0.021),
    ]
    kk.sweep_shell(mesh, f"Boot/ToeCap_{label}", cap_stations, 20, "Leather",
                   lambda tu, tv: 0.005, material_in="Leather", material_rim="Leather",
                   v_lo_rim=True, v_hi_rim=False, inner="edges", inner_band=(2, 3),
                   ref_a=(1.0, 0.0, 0.0), ref_b=(0.0, 1.0, 0.0),
                   cap_hi=True, cap_material="Leather")


def build_boot_details(mesh, side, label):
    x = side * 0.120
    outward = side
    # Instep strap with an iron buckle over the vamp.
    path, normals = [], []
    for index in range(15):
        angle = TAU * index / 15
        path.append((x + 0.082 * math.cos(angle), 0.124 + 0.026 * math.cos(angle),
                     0.026 + 0.090 * math.sin(angle)))
        normals.append((math.cos(angle), 0.35 * math.cos(angle), math.sin(angle)))
    kk.strap(mesh, f"Boot/InstepStrap_{label}", path, normals, "Leather", 0.024, 0.006,
             close=True, chamfer=0.4)
    kk.ellipsoid(mesh, f"Boot/InstepBuckle_{label}", "Iron",
                 (x + outward * 0.086, 0.144, 0.026), (0.006, 0.013, 0.009), 8, 10)
    # Ankle strap above it, closing the boot over the instep.
    path2, normals2 = [], []
    for index in range(15):
        angle = TAU * index / 15
        path2.append((x + 0.082 * math.cos(angle), 0.184 + 0.008 * math.cos(angle),
                      -0.006 + 0.086 * math.sin(angle)))
        normals2.append((math.cos(angle), 0.1, math.sin(angle)))
    kk.strap(mesh, f"Boot/AnkleStrap_{label}", path2, normals2, "Leather", 0.019, 0.0055,
             close=True, chamfer=0.4)
    # Outer side panel seam: structure rather than decoration.
    panel = []
    for index in range(16):
        angle = TAU * index / 16
        panel.append((x + outward * (0.080 + 0.003 * math.cos(angle)),
                      0.238 + 0.058 * math.sin(angle),
                      0.018 + 0.062 * math.cos(angle)))
    kk.tube(mesh, f"Boot/SidePanelSeam_{label}", panel, "BoneThread", 0.0022, 6,
            close=True, ref_a=(0.0, 1.0, 0.0))
    # Four iron lace hooks up the inner quarter, with thread stays between them.
    hooks = [(x - outward * 0.082, 0.360 - index * 0.044, 0.030 + index * 0.004)
             for index in range(4)]
    for index, hook in enumerate(hooks):
        kk.ellipsoid(mesh, f"Boot/Hook_{label}{index}", "Iron",
                     (hook[0] - outward * 0.002, hook[1], hook[2]),
                     (0.0065, 0.0065, 0.009), 8, 10)
        if index < len(hooks) - 1:
            nxt = hooks[index + 1]
            mid = kk.vmul(kk.vadd(hook, nxt), 0.5)
            kk.tube(mesh, f"Boot/HookStay_{label}{index}",
                    [kk.vadd(hook, (0.0, 0.004, 0.0)), kk.vadd(mid, (0.0, 0.0, 0.004)),
                     kk.vadd(nxt, (0.0, -0.004, 0.0))], "BoneThread", 0.002, 6)
    # Bone "mud spur" wedges on the outer face of the right boot (asymmetry).
    if side > 0:
        for index in range(3):
            base = (x + 0.084, 0.150 - index * 0.032, 0.070 - index * 0.026)
            tip = (base[0] + 0.022, base[1] - 0.007, base[2] + 0.014)
            kk.tube(mesh, f"Boot/MudSpur_{index}", [base, tip], "BoneThread",
                    lambda t, r=0.0055: r * (1.0 - 0.75 * t), 6)


# ============================================================================
# Entry point
# ============================================================================
def build_all(mesh):
    build_trousers(mesh)
    build_shirt(mesh)
    build_vest(mesh)
    build_coat(mesh)
    build_belt(mesh)
    build_harness(mesh)
    build_gloves(mesh)
    build_boots(mesh)
    return mesh
