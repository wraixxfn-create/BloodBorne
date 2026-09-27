#!/usr/bin/env python3
"""Foot, boot and lower-leg anatomy, rig and posing for the Veilbound Wayfarer.

Single source of truth shared by:
- Tools/create_original_protagonist.py (builds the boot + lower-leg meshes from
  the section tables below and tags every boot part with a rig chain id),
- Tools/verify_boots.py (re-checks the built mesh against this anatomy, poses
  the rig and validates the floor contact for idle / walk / run / dodge),
- Tools/render_boot_previews.py (renders the posed states over a floor).

Everything is deterministic, dependency-free (math only) and expressed in
metres. The boot is authored ONCE in a local frame and mirrored per side:

  local frame (RIGHT boot, all values world-scale, foot centre line at x=0):
    +x = outboard (right), +y = up (sole contact plane is y = 0),
    +z = forward (the character faces +Z).

Anatomical targets for the ~1.85 m figure (male foot ~27 cm):
  foot length  (heel back -> toe tip)            0.276 m  (~15 % of height)
  ball (MTP) line from the heel                  0.70 of the length
  ball width (widest, across the metatarsals)    0.110 m
  heel width                                     0.078 m
  toe box (ball -> tip)                          ~0.08 m
  ankle (talocrural) height above the floor      0.105 m (raised by the heel)
  heel lift (heel block)                         0.030 m
  forefoot sole thickness                        0.0135 m

Sole construction (all contact faces are exactly y = 0):
  * forefoot sole: flat contact patch from the ball to the toe-break, with a
    feathered edge, a welt bead and welt stitching,
  * toe spring: the last 25 mm of the toe curls up ~10 mm (a real last feature,
    not a floating foot) so the toe never digs into the floor,
  * waist/shank: lifted off the floor between the heel breast and the ball,
  * heel block: three stacked laminations, brass edge plate + nail heads, flat
    contact face at y = 0.

The rig is authored data for verification and future animation work: the
prefab consumes nothing from it at runtime (the player is still a static mesh
child of the CharacterController), and no movement code is involved.

Floor-contact contract (checked by Tools/verify_boots.py):
  1. the minimum vertex of the boot geometry is exactly 0.000 (idle pose) and
     nothing is below 0 (no clipping),
  2. the planted contact is a *patch* (several vertices within 1.5 mm of the
     floor spread over > 40 mm of foot length), never a single point,
  3. for walk/run/dodge the planted foot is grounded by foot IK (the usual
     engine step) and the same invariants hold, while the swing foot stays
     clear of the floor.
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hand_rig import (vadd, vsub, vmul, dot, cross, norm, lerp3, clamp,  # noqa: E402
                      smoothstep, mat_mul, mat_translate, mat_rot_axis, mat_apply)

# ===========================================================================
# Placement / skeleton anchors (RIGHT side; the left is the exact x mirror)
# ===========================================================================

FOOT_X = 0.118          # boot centre line, matches the trouser leg axis
FOOT_Z = 0.000          # local z origin == world z origin for the foot

HIP = (0.100, 0.905, 0.000)
KNEE = (0.116, 0.492, 0.008)
ANKLE = (0.118, 0.105, -0.034)      # talocrural joint centre
BALL = (0.118, 0.031, 0.112)        # metatarsophalangeal line (ball of the foot)
TOE = (0.118, 0.036, 0.176)         # toe-break pivot inside the toe box

# ===========================================================================
# Boot construction numbers
# ===========================================================================

SOLE_TOP_FORE = 0.0135      # sole top edge (leather line) at the forefoot
SOLE_TOP_HEEL = 0.0345      # sole top edge over the heel block
HEEL_BLOCK_TOP = 0.0300     # top of the stacked heel block
HEEL_BREAST = -0.030        # front face of the heel block (shank starts here)
WELT_OUT = 0.0045           # welt overhang beyond the leather
WELT_H = 0.0062             # welt bead height
WELT_PROUD = 0.0022         # extra welt overhang beyond the sole edge
SHAFT_TOP = 0.4550          # cuff rim height (boot top)
CUFF_FOLD_Y = 0.4400        # top of the folded wine cuff
FOOT_BACK = -0.076          # heel back (leather)
FOOT_TIP = 0.186            # toe tip (leather, before the sole overhang)

# Boot upper: lengthwise sections (z, half width, bottom edge, top of upper).
# b(z) is the leather's bottom edge == the sole's top edge; t(z) is the skyline.
FOOT_SECTIONS = [
    (-0.0760, 0.0085, 0.0335, 0.0885),
    (-0.0720, 0.0215, 0.0328, 0.0965),
    (-0.0660, 0.0285, 0.0318, 0.1030),
    (-0.0570, 0.0325, 0.0300, 0.1080),
    (-0.0460, 0.0352, 0.0272, 0.1115),
    (-0.0360, 0.0372, 0.0248, 0.1140),
    (-0.0260, 0.0388, 0.0222, 0.1160),
    (-0.0140, 0.0400, 0.0198, 0.1172),   # instep / ankle collar
    (-0.0020, 0.0412, 0.0174, 0.1170),
    ( 0.0120, 0.0428, 0.0152, 0.1150),
    ( 0.0260, 0.0448, 0.0140, 0.1112),
    ( 0.0400, 0.0468, 0.0136, 0.1052),
    ( 0.0540, 0.0488, 0.0135, 0.0982),
    ( 0.0680, 0.0506, 0.0135, 0.0902),
    ( 0.0820, 0.0522, 0.0135, 0.0815),
    ( 0.0960, 0.0534, 0.0135, 0.0728),   # ball line
    ( 0.1100, 0.0540, 0.0136, 0.0648),
    ( 0.1240, 0.0534, 0.0140, 0.0578),
    ( 0.1380, 0.0515, 0.0146, 0.0512),
    ( 0.1500, 0.0488, 0.0156, 0.0458),
    ( 0.1620, 0.0448, 0.0170, 0.0412),
    ( 0.1720, 0.0392, 0.0190, 0.0378),
    ( 0.1800, 0.0308, 0.0212, 0.0356),
    ( 0.1860, 0.0192, 0.0236, 0.0348),
]
FOOT_P = 2.55          # cross-section dome exponent (2 = ellipse, >2 = squarer)

# Sole underside: shank arch + toe spring (all contact at y = 0)
SOLE_BOTTOM = [
    (-0.0860, 0.0300), (-0.0600, 0.0300), (-0.0300, 0.0300), (-0.0180, 0.0286),
    (-0.0040, 0.0252), ( 0.0100, 0.0196), ( 0.0220, 0.0128), ( 0.0340, 0.0060),
    ( 0.0460, 0.0018), ( 0.0580, 0.0000), ( 0.0900, 0.0000), ( 0.1300, 0.0000),
    ( 0.1620, 0.0000), ( 0.1740, 0.0012), ( 0.1820, 0.0044), ( 0.1890, 0.0092),
    ( 0.1930, 0.0136),
]

# Shaft: horizontal sections (y, half width, front extent, back extent, z centre)
# Fitted to the lower-leg profile so the boot always clears the trouser inside
# (leather 4.5 mm + ~2 mm air) and grows smoothly out of the ankle collar.
SHAFT_SECTIONS = [
    (0.0950, 0.0230, 0.0235, 0.0235, -0.0130),   # buried inside the foot form
    (0.1100, 0.0260, 0.0260, 0.0260, -0.0120),
    (0.1180, 0.0300, 0.0330, 0.0330, -0.0110),
    (0.1300, 0.0380, 0.0390, 0.0390, -0.0090),
    (0.1500, 0.0425, 0.0490, 0.0480, -0.0040),
    (0.1800, 0.0448, 0.0560, 0.0535, -0.0010),
    (0.2200, 0.0480, 0.0600, 0.0570,  0.0015),
    (0.2600, 0.0520, 0.0635, 0.0605,  0.0040),
    (0.3000, 0.0570, 0.0670, 0.0635,  0.0058),
    (0.3400, 0.0620, 0.0705, 0.0670,  0.0068),
    (0.3800, 0.0660, 0.0745, 0.0705,  0.0074),
    (0.4200, 0.0695, 0.0785, 0.0740,  0.0078),
    (0.4550, 0.0725, 0.0820, 0.0770,  0.0080),
]
SHAFT_P = 2.15         # near-elliptical at the calf, squarer at the ankle
SHAFT_P_ANKLE = 2.45
SHAFT_GAP = [          # lacing opening: half angle (deg) per SHAFT_SECTIONS row
    0.0, 0.0, 0.0, 4.0, 6.5, 8.0, 8.7, 9.1, 9.4, 9.7, 10.0, 10.3, 10.6,
]
SHAFT_THICK = 0.0045   # leather thickness (lining offset)

# Trouser tuck: the wool leg inside the shaft (world x centre = the leg axis).
# The shaft's inner wall clears this profile by >= 2 mm everywhere below the
# cuff opening, so the tucked trouser can never poke through the boot leather;
# above the opening the legs flare back out over the cuff.
TROUSER_TUCK = [
    # (y, rx, rz, z centre): leg radius below the cuff opening
    (0.2850, 0.0395, 0.0415, 0.0130),
    (0.3650, 0.0455, 0.0475, 0.0080),
    (0.4550, 0.0510, 0.0530, 0.0089),
    (0.4850, 0.0820, 0.0860, 0.0120),   # flares back out over the cuff
]

# Hardware / trim layout along the shaft (y heights)
SLIT_Y0 = 0.118         # the lacing slit opens from here up
EYELET_Y = (0.130, 0.158, 0.188, 0.220)
HOOK_Y = (0.256, 0.298, 0.340)
LACE_BOW_Y = 0.372
CUFF_STRAP_Y = 0.408
INSTEP_STRAP_Y = 0.056   # along z on the vamp (instep strap)
TOE_CAP_SEAM = 0.126     # z where the toe cap seam crosses the centre line
COUNTER_BACK = -0.074    # z of the heel counter panel's rear edge
EYELET_FACING_W = 0.0125  # width of the eyelet facings along the opening
TONGUE_Y0, TONGUE_Y1 = 0.098, 0.318
WELT_STITCH_R = 0.0016


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def _interp(tab, x, col):
    """Piecewise-linear interpolation of column `col` of a table over column 0."""
    if x <= tab[0][0]:
        return tab[0][col]
    if x >= tab[-1][0]:
        return tab[-1][col]
    for i in range(len(tab) - 1):
        a, b = tab[i], tab[i + 1]
        if a[0] <= x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0])
            return a[col] * (1.0 - t) + b[col] * t
    return tab[-1][col]


def leather_bottom(z):
    """Lower edge of the leather upper at lengthwise station z."""
    return _interp(FOOT_SECTIONS, z, 2)


def leather_top(z):
    """Skyline (top of the leather) at station z."""
    return _interp(FOOT_SECTIONS, z, 3)


def leather_half_width(z):
    return _interp(FOOT_SECTIONS, z, 1)


def sole_bottom(z):
    """Underside of the sole: 0.0 for every ground-contact section."""
    return _interp(SOLE_BOTTOM, z, 1)


def sole_top(z):
    return max(leather_bottom(z), sole_bottom(z) + 0.0015)


def shaft_row(y):
    """(half width, df, db, zc, gap_half_angle, p) of the shaft at height y."""
    w = _interp(SHAFT_SECTIONS, y, 1)
    df = _interp(SHAFT_SECTIONS, y, 2)
    db = _interp(SHAFT_SECTIONS, y, 3)
    zc = _interp(SHAFT_SECTIONS, y, 4)
    gap = math.radians(_interp([(r[0], r[1], g) for r, g in zip(SHAFT_SECTIONS, SHAFT_GAP)],
                               y, 2))
    p = SHAFT_P + (SHAFT_P_ANKLE - SHAFT_P) * (1.0 - smoothstep(0.10, 0.24, y))
    return w, df, db, zc, gap, p


def foot_section_x(z, y):
    """Half-width of the boot upper's section at station z and height y."""
    w = leather_half_width(z)
    b = leather_bottom(z)
    t = leather_top(z)
    e = (y - b) / max(1e-6, t - b)
    if e >= 1.0:
        return 0.0
    return w * math.sqrt(max(0.0, 1.0 - e ** FOOT_P))


def foot_section_s(z, y):
    """The section parameter s in [-1, 1] at station z and height y."""
    b = leather_bottom(z)
    t = leather_top(z)
    e = clamp((y - b) / max(1e-6, t - b), 0.0, 1.0)
    ang = math.asin(min(1.0, e ** (FOOT_P / 2.0)))
    return -1.0 + 2.0 * ang / math.pi


def foot_section_point(z, s, off=0.0):
    """A point on (or offset from) the boot upper's surface.

    z   station along the foot, s in [-1, 1] sweeping the section from the
    inboard bottom edge (s = -1) over the top (s = 0) to the outboard bottom
    edge (s = +1); `off` offsets along the local outward normal.
    """
    w = leather_half_width(z)
    b = leather_bottom(z)
    t = leather_top(z)
    u = 0.5 + 0.5 * s                       # 0 inboard edge -> 1 outboard edge
    ang = math.pi * u                       # 0..pi across the upper
    sa = max(1e-6, math.sin(ang))
    x = -w * math.cos(ang)
    y = b + (t - b) * sa ** (2.0 / FOOT_P)
    # outward normal from the section gradient (in the x-y plane)
    dx = w * sa
    dy = (t - b) * (2.0 / FOOT_P) * sa ** (2.0 / FOOT_P - 1.0) * math.cos(ang)
    ln = math.hypot(dx, dy)
    nx, ny = (-dy / ln, dx / ln) if ln > 1e-9 else (0.0, 1.0)
    return (x + nx * off, y + ny * off, z)


def foot_ring(z, n_side=None, n_flat=5):
    """Closed ring (upper surface + flat insole) at station z, ordered +x first."""
    if n_side is None:
        n_side = 22
    b = leather_bottom(z)
    w = leather_half_width(z)
    pts = []
    for k in range(n_side):                 # upper: inboard edge -> top -> outboard
        pts.append(foot_section_point(z, -1.0 + 2.0 * k / (n_side - 1.0)))
    for k in range(1, n_flat):              # flat insole back to the inboard edge
        pts.append((w - 2.0 * w * k / float(n_flat), b, z))
    return pts


def worn_out(z, depth=0.0011, z_peak=0.104, width=0.055):
    """Local extra wear on the outboard sole edge (ground drag at the ball)."""
    return depth * math.exp(-((z - z_peak) / width) ** 2)


def sole_half_width(z, worn=True):
    """Half width of the sole / welt footprint at station z.

    The sole edge overhangs the leather by WELT_OUT (the welt bead), plus the
    measured outboard wear flat - so the slab and the welt below always agree
    and the boot reads as walked-in rather than mint.
    """
    w = leather_half_width(clamp(z, FOOT_BACK, FOOT_TIP)) + WELT_OUT
    if worn:
        w -= worn_out(z)
    return max(0.0045, w)


def foot_outline(n_fn=34, overhang=WELT_OUT, cap_extent=0.0100, worn=True):
    """Closed (x, z) outline of the sole footprint (welt edge).

    Ordered: heel back -> toe tip along the outboard (+x) side, around the toe,
    toe -> heel along the inboard side, around the heel. The outboard edge of
    the ball carries a measured wear flat (`worn_out`) - the boots are broken
    in on the outside, like a real pair that has been walked in.
    """
    z0, z1 = FOOT_BACK, FOOT_TIP
    zs = [z0 + (z1 - z0) * k / (n_fn - 1.0) for k in range(n_fn)]
    def w_out(z):
        return max(0.0045, sole_half_width(z, worn) + (overhang - WELT_OUT))
    pts = [(w_out(z), z) for z in zs]
    w_tip = w_out(z1)
    for k in range(1, 6):                       # toe cap arc
        u = k / 6.0
        pts.append((w_tip * math.cos(math.pi * u), z1 + cap_extent * math.sin(math.pi * u)))
    pts += [(-(leather_half_width(z) + overhang), z) for z in reversed(zs)]
    w_heel = leather_half_width(z0) + overhang
    for k in range(1, 6):                       # heel cap arc
        u = k / 6.0
        pts.append((-w_heel * math.cos(math.pi * u), z0 - cap_extent * math.sin(math.pi * u)))
    return pts


def _skyline_cross(y, n=160):
    """(z_back, z_front) where the upper's skyline reaches height y.

    The skyline of the fitting (leather_top over the foot form) is unimodal, so
    the set {z : skyline(z) >= y} is one interval; the ends are the heel cap and
    the toe cap when the cap itself stands above y. Returns None above the
    ankle collar, where the boot upper is the shaft and not the foot form.
    """
    zs = [FOOT_BACK + (FOOT_TIP - FOOT_BACK) * k / n for k in range(n + 1)]
    tops = [leather_top(z) for z in zs]
    if max(tops) < y:
        return None
    above = [t >= y for t in tops]
    i0 = above.index(True)
    i1 = n - above[::-1].index(True)

    def cross(i, j):
        if abs(tops[j] - tops[i]) < 1e-12:
            return zs[i]
        return zs[i] + (zs[j] - zs[i]) * (y - tops[i]) / (tops[j] - tops[i])

    return (FOOT_BACK if i0 == 0 else cross(i0 - 1, i0),
            FOOT_TIP if i1 == n else cross(i1, i1 + 1))


def foot_contour(y, n=48, off=0.0):
    """Closed horizontal section of the boot upper at height y.

    Ordered front centre -> outboard side -> back centre -> inboard side, so the
    loop can be sliced by z to build vertical bands (the heel counter).
    """
    cross = _skyline_cross(y)
    if cross is None:
        return []
    z_back, z_front = cross
    raw = []
    nside = max(6, n // 2)
    for k in range(nside + 1):
        z = z_front + (z_back - z_front) * k / nside
        raw.append((foot_section_x(z, y), y, z))
    for k in range(1, nside):
        z = z_back + (z_front - z_back) * k / nside
        raw.append((-foot_section_x(z, y), y, z))
    # resample by arc length for an even parameterisation
    lens = [0.0]
    for i in range(1, len(raw)):
        lens.append(lens[-1] + math.dist(raw[i-1], raw[i]))
    total = lens[-1] + math.dist(raw[-1], raw[0])
    out = []
    for k in range(n):
        s = total * k / n
        for i in range(len(raw)):
            a = lens[i]
            b = lens[i+1] if i + 1 < len(raw) else total
            if a <= s <= b and b > a:
                t = (s - a) / (b - a)
                q = lerp3(raw[i], raw[(i+1) % len(raw)], t)
                out.append(vadd(q, vmul(norm((q[0], 0.0, q[2] - 0.004)), off)))
                break
    return out


def heel_outline(n_fn=16, inset=0.0):
    """Closed (x, z) outline of the heel block (flush with the sole edge)."""
    z0, z1 = -0.0860, HEEL_BREAST - 0.0035
    pts = []
    zs = [z0 + (z1 - z0) * k / (n_fn - 1.0) for k in range(n_fn)]
    for z in zs:
        pts.append((max(0.004, leather_half_width(z) + WELT_OUT - inset), z))
    w_heel = max(0.004, leather_half_width(z0) + WELT_OUT - inset)
    for k in range(1, 5):
        u = k / 5.0
        pts.append((w_heel * math.cos(math.pi * u), z0 - 0.0090 * math.sin(math.pi * u)))
    for z in reversed(zs):
        pts.append((-max(0.004, leather_half_width(z) + WELT_OUT - inset), z))
    for k in range(1, 5):
        u = k / 5.0
        pts.append((-w_heel * math.cos(math.pi * u), z0 - 0.0090 * math.sin(math.pi * u)))
    return pts


def shaft_ring(y, n=None, gap=None, thick=0.0):
    """Ring of the shaft at height y. Positive gap -> open C (lacing slit).

    Returns (points, open_span) where points run clockwise seen from above
    starting at the outboard edge of the slit (+z front is the slit centre).
    """
    w, df, db, zc, gap_a, p = shaft_row(y)
    if gap is not None:
        gap_a = gap
    if n is None:
        n = 26
    pts = []
    if gap_a <= 1e-6:
        for k in range(n):
            t = 2.0 * math.pi * k / n
            pts.append(_shaft_pt(y, w, df, db, zc, p, t, thick))
        return pts, None
    for k in range(n):
        t = gap_a + (2.0 * math.pi - 2.0 * gap_a) * k / (n - 1.0)
        pts.append(_shaft_pt(y, w, df, db, zc, p, t, thick))
    return pts, (gap_a, 2.0 * math.pi - gap_a)


def _shaft_pt(y, w, df, db, zc, p, t, thick=0.0):
    """One shaft contour point at polar angle t (0 = front, +z)."""
    s, c = math.sin(t), math.cos(t)
    wgt = 0.5 + 0.5 * c
    W = w
    D = df * wgt + db * (1.0 - wgt)
    e = 2.0 / p
    x = W * math.copysign(abs(s) ** e, s)
    z = zc + D * math.copysign(abs(c) ** e, c)
    if thick:
        r = math.hypot(x, z - zc)
        if r > 1e-9:
            k = max(0.0, (r - thick)) / r
            x, z = x * k, zc + (z - zc) * k
    return (x, y, z)


def _shaft_pt_at(y, t):
    r = shaft_row(y)
    return _shaft_pt(y, r[0], r[1], r[2], r[3], r[5], t)


def shaft_outer_normal(y, t):
    """Outward horizontal normal of the shaft surface at (y, t)."""
    a = _shaft_pt_at(y, t - 0.02)
    b = _shaft_pt_at(y, t + 0.02)
    tang = norm(vsub(b, a))
    n = cross(tang, (0.0, 1.0, 0.0))
    if dot(n, (a[0], 0.0, a[2])) < 0:
        n = vmul(n, -1.0)
    return norm(n)


def shaft_point(y, t, off=0.0):
    """Point on the shaft surface at height y, polar angle t, offset outward."""
    p = _shaft_pt_at(y, t)
    if off:
        p = vadd(p, vmul(shaft_outer_normal(y, t), off))
    return p


# ===========================================================================
# Rig: joints, axes, skin weights, poses, forward kinematics
# ===========================================================================

def joint_list():
    """[(name, parent, world_head, axes)] for Root + both legs.

    Axis conventions (mirrored per side where the motion is lateral):
      Hip   flex + = thigh swings forward, abd + = thigh swings outboard,
            twist + = toes turn outward
      Knee  flex + = shin folds backwards (normal knee flexion)
      Ankle flex + = dorsiflexion (toes up), transfer = shin roll
      Ball  flex + = toe box rotates up (MTP dorsiflexion, the roll at the ball)
      Toe   flex + = toe tip rotates up
    """
    joints = [("Root", None, (0.0, 0.0, 0.0), None)]
    for side, pre in ((1, "R"), (-1, "L")):
        mir = (lambda v: (v[0] * side, v[1], v[2]))
        joints.append((f"{pre}Hip", "Root", mir(HIP),
                       {"flex": (-1, 0, 0), "abd": (0, 0, side), "twist": (0, side, 0)}))
        joints.append((f"{pre}Knee", f"{pre}Hip", mir(KNEE),
                       {"flex": (1, 0, 0), "abd": (0, 0, side), "twist": (0, side, 0)}))
        joints.append((f"{pre}Ankle", f"{pre}Knee", mir(ANKLE),
                       {"flex": (-1, 0, 0), "abd": (0, 0, side), "twist": (0, side, 0)}))
        joints.append((f"{pre}Ball", f"{pre}Ankle", mir(BALL),
                       {"flex": (-1, 0, 0), "abd": (0, 0, side), "twist": (0, side, 0)}))
        joints.append((f"{pre}Toe", f"{pre}Ball", mir(TOE),
                       {"flex": (-1, 0, 0), "abd": (0, 0, side), "twist": (0, side, 0)}))
    return joints


def _mirror_point(p, side):
    return (p[0] * side, p[1], p[2])


def part_axis(part, side):
    """Axis of a mesh part -> mirror per side ('R'/'L')."""
    pre = "R" if side > 0 else "L"
    return pre + part


# ---- skin weights ----------------------------------------------------------

def _prune_top4(w):
    items = sorted(w.items(), key=lambda kv: -kv[1])
    out = {k: v for k, v in items[:4] if v > 1e-5}
    tot = sum(out.values())
    return {k: v / tot for k, v in out.items()} if tot > 1e-9 else {"Root": 1.0}


def foot_weights(side, p):
    """Boot geometry: foot form / sole / heel / toe cap / counter / straps.

    The ball-to-toe blend lets the boot roll at the MTP joint, the shaft blend
    (0.09 -> 0.18) hands the ankle collar over to the shin so a stiff boot does
    not shear at the ankle.
    """
    pre = "R" if side > 0 else "L"
    y = p[1]
    s = (p[2] - ANKLE[2]) / (BALL[2] - ANKLE[2])
    k_shaft = smoothstep(0.092, 0.185, y)
    k_ball = smoothstep(0.60, 1.02, s)
    k_toe = smoothstep(1.22, 1.62, s)
    w = {}
    foot = 1.0 - k_shaft
    w[f"{pre}Ankle"] = foot * (1.0 - k_ball)
    w[f"{pre}Ball"] = foot * k_ball * (1.0 - k_toe)
    w[f"{pre}Toe"] = foot * k_toe
    sh = k_shaft
    u = (y - ANKLE[1]) / (KNEE[1] - ANKLE[1])
    up = smoothstep(0.18, 0.62, u)
    w[f"{pre}Knee"] = sh * up
    w[f"{pre}Ankle"] = w.get(f"{pre}Ankle", 0.0) + sh * (1.0 - up)
    return _prune_top4(w)


def shaft_weights(side, p):
    """Shaft shell, tongue, facings, laces, calf strap, cuff: follows the shin."""
    pre = "R" if side > 0 else "L"
    y = p[1]
    u = (y - ANKLE[1]) / (KNEE[1] - ANKLE[1])
    up = smoothstep(0.10, 0.55, u)
    w = {f"{pre}Knee": up, f"{pre}Ankle": 1.0 - up}
    return _prune_top4(w)


def leg_weights(side, p):
    """Trousers: Hip above the knee, Knee down the shin, Ankle at the ankle."""
    pre = "R" if side > 0 else "L"
    y = p[1]
    u = (y - ANKLE[1]) / (KNEE[1] - ANKLE[1])          # 0 ankle, 1 knee
    v = (y - KNEE[1]) / (HIP[1] - KNEE[1])             # 0 knee, 1 hip
    above_ankle = smoothstep(-0.05, 0.18, u)
    hip = above_ankle * smoothstep(0.55, 1.05, v)
    knee = max(0.0, above_ankle - hip)
    w = {f"{pre}Ankle": 1.0 - above_ankle, f"{pre}Knee": knee, f"{pre}Hip": hip}
    return _prune_top4(w)


CHAIN_WEIGHT_FN = {
    "foot": foot_weights,
    "shaft": shaft_weights,
    "leg": leg_weights,
}


def weights_for(side, chain, p_world):
    """Dispatch a mesh part chain id to its weight function (world point)."""
    fn = CHAIN_WEIGHT_FN.get(chain)
    if fn is None:
        raise KeyError(f"unknown boot rig chain '{chain}'")
    local = (p_world[0] - side * FOOT_X, p_world[1], p_world[2] - FOOT_Z)
    return fn(side, local)


# ---- poses -----------------------------------------------------------------

POSES = {
    # Standing at ease: both boots flat on the floor, zero solver offset.
    "idle": {
        "R": {"sole_tilt": 0.0},
        "L": {"sole_tilt": 0.0},
    },
    # Walk, double support: right heel strike (sole 14 deg toes-up, only the
    # heel patch down) and left toe-off (heel raised 22 deg, toe pad flat on
    # the floor - the MTP joint extends by exactly the heel lift).
    "walk": {
        "R": {"Hip": {"flex": 20.0}, "Knee": {"flex": 6.0},
              "sole_tilt": 14.0},
        #   the trailing knee angle is solved so the toe pad lands exactly on
        #   the floor once the heel-strike boot is grounded (Tools/verify_boots)
        "L": {"Hip": {"flex": -14.5}, "Knee": {"flex": 11.5},
              "sole_tilt": -22.0, "forefoot_tilt": 0.0},
    },
    # Run, right ball strike: the forefoot pad lands flat while the heel stays
    # up (sole 16 deg), the left leg swings through with the knee folded.
    "run": {
        "R": {"Hip": {"flex": 12.0}, "Knee": {"flex": 20.0},
              "sole_tilt": -16.0, "forefoot_tilt": 0.0},
        #   swing leg: knee folded, picked so the boot passes ~135 mm clear
        "L": {"Hip": {"flex": -6.0}, "Knee": {"flex": 52.7},
              "sole_tilt": -58.0, "forefoot_tilt": -18.0},
    },
    # Dodge: lateral lunge - the left boot is planted flat outboard (hip
    # abducted 30 deg, the ankle solver rolls the sole back to the floor), the
    # right boot trails on its toe with the ankle extended.
    "dodge": {
        #   trailing knee solved so the toe pad rests on the floor
        "R": {"Hip": {"flex": -10.0, "abd": 16.0, "twist": -8.0}, "Knee": {"flex": 36.4},
              "sole_tilt": -30.0, "forefoot_tilt": 0.0},
        "L": {"Hip": {"flex": 4.0, "abd": 30.0, "twist": 12.0}, "Knee": {"flex": 26.0},
              "sole_tilt": 0.0},
    },
}

POSES_ORDER = ("idle", "walk", "run", "dodge")


def _rot3(m):
    return (m[0][:3], m[1][:3], m[2][:3])


def _mat3(m):
    return ((m[0][0], m[0][1], m[0][2], 0.0), (m[1][0], m[1][1], m[1][2], 0.0),
            (m[2][0], m[2][1], m[2][2], 0.0), (0.0, 0.0, 0.0, 1.0))


def _rot_about(axis, deg):
    return mat_rot_axis(axis, deg)


def _rot_err(a, b):
    """Frobenius error between two rotation matrices (identical -> 0)."""
    e = 0.0
    for i in range(3):
        for j in range(3):
            e += (a[i][j] - b[i][j]) ** 2
    return e


def _solve_ankle(m_parent, target, axes, start=(0.0, 0.0, 0.0)):
    """Solve the ankle's flex/abd/twist so the foot's world rotation == target.

    The foot form is rigidly attached to the ankle bone, so its orientation in
    the world is exactly the ankle's world rotation. Three joints give three
    degrees of freedom, which is what a foot-IK pass uses to keep a planted sole
    flat (e.g. when the hip is abducted during a lateral lunge). Deterministic
    coordinate descent, 3 sweeps of a bisection-style refinement.
    """
    parent = _rot3(m_parent)
    best = list(start)
    span = 60.0

    def err(v):
        r = ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0), (0.0, 0.0, 1.0, 0.0),
             (0.0, 0.0, 0.0, 1.0))
        r = mat_mul(r, _rot_about(axes["flex"], v[0]))
        r = mat_mul(r, _rot_about(axes["abd"], v[1]))
        r = mat_mul(r, _rot_about(axes["twist"], v[2]))
        world = mat_mul(_mat3(m_parent), r)
        return _rot_err(_rot3(world), target)

    for _ in range(24):
        for k in range(3):
            base = err(best)
            improved = False
            for d in (span, -span):
                cand = list(best)
                cand[k] += d
                if err(cand) < base - 1e-14:
                    best, improved = cand, True
                    break
            if not improved:
                pass
        span *= 0.5
    return best


def _solve_ball(m_ankle, axes, target):
    """Ball flex angle that puts the toe box at the world tilt `target`."""
    lo, hi = -120.0, 120.0
    for _ in range(48):
        mid = 0.5 * (lo + hi)
        e0 = _rot_err(_rot3(mat_mul(m_ankle, _rot_about(axes["flex"], mid))), target)
        e1 = _rot_err(_rot3(mat_mul(m_ankle, _rot_about(axes["flex"], mid + 1e-3))), target)
        if e1 < e0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def pose_matrices(pose_name, root_shift=(0.0, 0.0, 0.0)):
    """{joint: world 4x4 posed matrix} for a named pose (both legs)."""
    joints = {j[0]: j for j in joint_list()}
    posed = {"Root": mat_translate(root_shift)}
    spec = POSES[pose_name]
    todo = [n for n in joints if n != "Root"]
    while todo:
        pending = []
        for name in list(todo):
            parent = joints[name][1]
            if parent not in posed:
                pending.append(name)
                continue
            pre, part = name[0], name[1:]
            side_spec = spec.get(pre, {})
            p = dict(side_spec.get(part, {}))
            # foot IK: the ankle solve runs once its parent (the knee) is posed,
            # the ball solve once the ankle is - so a planted sole is flat on
            # the floor whatever the hip and knee are doing
            if part == "Ankle" and "sole_tilt" in side_spec:
                # + sole_tilt = toes up (dorsiflexion); a +x world rotation
                # tips the toes down, hence the negated target
                target = _rot3(mat_rot_axis((1.0, 0.0, 0.0), -side_spec["sole_tilt"]))
                f, a, t = _solve_ankle(posed[f"{pre}Knee"], target,
                                       joints[name][3],
                                       (p.get("flex", 0.0), p.get("abd", 0.0),
                                        p.get("twist", 0.0)))
                p.update({"flex": f, "abd": a, "twist": t})
            elif part == "Ball" and "forefoot_tilt" in side_spec:
                target = _rot3(mat_rot_axis((1.0, 0.0, 0.0), -side_spec["forefoot_tilt"]))
                p["flex"] = _solve_ball(posed[f"{pre}Ankle"], joints[name][3], target)
            axes = joints[name][3]
            rot = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))
            for key in ("flex", "abd", "twist"):
                ang = p.get(key, 0.0)
                if abs(ang) > 1e-9:
                    rot = mat_mul(rot, mat_rot_axis(axes[key], ang))
            m_local = mat_mul(mat_translate(vsub(joints[name][2], joints[parent][2])), rot)
            posed[name] = mat_mul(posed[parent], m_local)
        todo = pending
    return posed


def skin_vertex(p_world, weights, posed, joints):
    """Linear-blend-skin one world vertex. weights = {joint_name: w}."""
    acc = [0.0, 0.0, 0.0]
    for name, w in weights.items():
        j = joints[name]
        m = posed[name]
        rigid = mat_mul(m, mat_translate(vmul(j[2], -1.0)))
        q = mat_apply(rigid, p_world)
        acc[0] += w * q[0]
        acc[1] += w * q[1]
        acc[2] += w * q[2]
    return (acc[0], acc[1], acc[2])


def ground_shift(pose_name, planted_points):
    """Foot-IK style grounding: the dy that puts the lowest planted vertex at 0."""
    joints = {j[0]: j for j in joint_list()}
    posed = pose_matrices(pose_name)
    lo = min(skin_vertex(p, weights_for(1 if p[0] > 0 else -1,
                                        "foot" if p[1] < 0.20 else "shaft", p),
                         posed, joints)[1] for p in planted_points)
    return -lo


def metrics():
    """Key design dimensions (used by the verification tool)."""
    zs = [s[0] for s in FOOT_SECTIONS]
    widths = [s[1] for s in FOOT_SECTIONS]
    return {
        "foot_length": FOOT_TIP + 0.010 - (FOOT_BACK - 0.010),
        "leather_length": FOOT_TIP - FOOT_BACK,
        "ball_width": 2.0 * max(widths),
        "heel_width": 2.0 * max(leather_half_width(z) + WELT_OUT
                                for z in (-0.0620, -0.0570, -0.0460)),
        "ball_from_heel": (BALL[2] - FOOT_BACK) / (FOOT_TIP - FOOT_BACK),
        "ankle_height": ANKLE[1],
        "heel_lift": HEEL_BLOCK_TOP,
        "sole_thickness": SOLE_TOP_FORE - 0.0,
        "shaft_top": SHAFT_TOP,
        "cuff_diameter": 2.0 * _interp(SHAFT_SECTIONS, SHAFT_TOP, 1),
        "ankle_diameter": 2.0 * _interp(SHAFT_SECTIONS, 0.150, 1),
        "section_count": len(FOOT_SECTIONS),
        "z_range": (min(zs), max(zs)),
    }
