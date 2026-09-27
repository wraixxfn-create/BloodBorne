#!/usr/bin/env python3
"""Build the original Vespershade protagonist as a smooth, multi-material OBJ.

All forms are original procedural meshes in metres (1 unit = 1 m, feet at y=0).

The wardrobe is built as real layered geometry, not painted-on surfaces:
every garment piece is a closed cloth solid with an outer face, an inner
lining face and bound edge rims, so collars, cuffs, hems, belts and straps
all have measurable thickness. Folds and tension creases are displaced into
the shells around elbows, shoulders, waist, knees and ankles. The silhouette
is asymmetric by design (left-over-right closure, deeper left shoulder
mantle, single baldric, offset buckles, unequal coat tails).

Running this script writes only
Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj and its MTL.

Material order is also the order of submeshes assigned by Player.prefab;
the nine Unity materials are referenced by GUID and never change here.
"""
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Assets/Models/Characters")
os.makedirs(OUT, exist_ok=True)

# LOD support: segment counts scale with DETAIL; shapes are unchanged.
DETAIL = max(0.2, float(os.environ.get("WAYFARER_DETAIL", "1.0")))
SUFFIX = os.environ.get("WAYFARER_SUFFIX", "")
def _segs(n, lo=4):
    return max(lo, int(round(n * DETAIL)))

# Material order is also the order of submeshes assigned by Player.prefab.
MATERIALS = ["Cloth", "ClothAccent", "Trouser", "Leather", "Skin", "Hair", "AgedBrass", "BoneThread", "BootSole"]
colors = {
    "Cloth": ((0.055, 0.075, 0.105), 0.16),
    "ClothAccent": ((0.16, 0.045, 0.065), 0.16),
    "Trouser": ((0.075, 0.085, 0.10), 0.12),
    "Leather": ((0.095, 0.055, 0.038), 0.24),
    "Skin": ((0.39, 0.25, 0.19), 0.12),
    "Hair": ((0.075, 0.085, 0.105), 0.2),
    "AgedBrass": ((0.32, 0.20, 0.075), 0.58),
    "BoneThread": ((0.46, 0.38, 0.25), 0.3),
    "BootSole": ((0.035, 0.030, 0.028), 0.12),
}

# Each material has a separate vertex/face buffer and keeps OBJ groups readable.
verts = {m: [] for m in MATERIALS}
faces = {m: [] for m in MATERIALS}
groups = {m: [] for m in MATERIALS}
active_group = {m: "" for m in MATERIALS}

def vadd(a, b): return (a[0]+b[0], a[1]+b[1], a[2]+b[2])
def vsub(a, b): return (a[0]-b[0], a[1]-b[1], a[2]-b[2])
def vmul(a, s): return (a[0]*s, a[1]*s, a[2]*s)
def dot(a, b): return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]
def cross(a, b): return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])
def norm(a):
    l = math.sqrt(dot(a, a))
    return vmul(a, 1.0/l) if l > 1e-9 else (0.0, 1.0, 0.0)
def lerp(a, b, t): return vmul(a, 1.0-t) + vmul(b, t) if False else tuple(a[i]*(1.0-t)+b[i]*t for i in range(len(a)))
def clamp(x, lo, hi): return max(lo, min(hi, x))
def smoothstep(e0, e1, x):
    t = clamp((x-e0)/(e1-e0), 0.0, 1.0)
    return t*t*(3.0-2.0*t)
def gauss(x, mu, sig): return math.exp(-((x-mu)/sig)**2)

def interp_val(x, xp, fp):
    if x <= xp[0]: return fp[0]
    if x >= xp[-1]: return fp[-1]
    for i in range(len(xp) - 1):
        if xp[i] <= x <= xp[i+1]:
            t = (x - xp[i]) / (xp[i+1] - xp[i])
            return fp[i] * (1.0 - t) + fp[i+1] * t
    return fp[-1]

def add_mesh(mat, name, points, polys):
    base = len(verts[mat]) + 1
    verts[mat].extend(points)
    if active_group[mat] != name:
        groups[mat].append((len(faces[mat]), name))
        active_group[mat] = name
    faces[mat].extend(tuple(base+i for i in face) for face in polys)

# ---------------------------------------------------------------------------
# Solid-surface construction kit: every garment piece is a closed cloth solid
# (outer face + offset inner lining face + bound edge rims).
# ---------------------------------------------------------------------------

def add_quad_strip(ptsA, ptsB, closed, flip=False):
    """Stitch two equal-length point rows into triangles."""
    n = len(ptsA)
    rng = range(n) if closed else range(n-1)
    fs = []
    for i in rng:
        j = (i+1) % n
        t = (ptsA[i], ptsA[j], ptsB[j])
        fs.append(t[::-1] if flip else t)
        t2 = (ptsA[i], ptsB[j], ptsB[i])
        fs.append(t2[::-1] if flip else t2)
    return fs

def quad_grid(pts, rows, cols, closed_cols, flip=False):
    fs = []
    rng = range(cols) if closed_cols else range(cols-1)
    for r in range(rows-1):
        for c in rng:
            cn = (c+1) % cols
            t = (pts[r*cols+c], pts[r*cols+cn], pts[(r+1)*cols+cn])
            fs.append(t[::-1] if flip else t)
            t2 = (pts[r*cols+c], pts[(r+1)*cols+cn], pts[(r+1)*cols+c])
            fs.append(t2[::-1] if flip else t2)
    return fs

def shell_point(y, rx, rz, zc, a, dr, dy, dz):
    """Point on an elliptical ring plus radial/axial cloth displacement."""
    x = rx*math.sin(a)
    z = zc + rz*math.cos(a)
    r = math.hypot(x, z-zc)
    if r > 1e-9:
        ux, uz = x/r, (z-zc)/r
    else:
        ux, uz = 0.0, 1.0
    return (x + ux*dr, y + dy, z + uz*dr + dz)

def thick_ring_shell(mat, name, rows, thick, sides, a0, a1,
                     wrap=False, rim_start=True, rim_end=True, fold=None,
                     center=(0.0, 0.0, 0.0), radial_extra=None):
    """A garment slab swept over elliptical rings.

    rows: callables a -> (y, rx, rz, zc[, a0, a1])
    Builds the outer face, an inner lining face offset inward by `thick`,
    and closed rims along both vertical edges (a0/a1) and optionally the
    first/last horizontal edge (hems). `fold(a, row_idx)` -> (dr, dy, dz)
    displaces outer and lining identically so thickness stays constant.
    """
    sides = _segs(sides, 6)
    n_cols = sides if wrap else sides + 1
    outer, inner = [], []
    cx, cy, cz = center
    row_spans = []
    for ri, row_fn in enumerate(rows):
        probe = row_fn(a0)
        row_spans.append((probe[4], probe[5]) if len(probe) >= 6 else (a0, a1))
    for ri, row_fn in enumerate(rows):
        ra0, ra1 = row_spans[ri]
        orow, irow = [], []
        for cj in range(n_cols):
            a = ra0 + (ra1 - ra0) * (cj / sides)
            y, rx, rz, zc = row_fn(a)[:4]
            if radial_extra:
                extra = radial_extra(a, ri)
                rx, rz = rx + extra, rz + extra
            dr, dy, dz = fold(a, ri) if fold else (0.0, 0.0, 0.0)
            po = shell_point(y, rx, rz, zc, a, dr, dy, dz)
            po = (po[0] + cx, po[1] + cy, po[2] + cz)
            x, _, z = po[0], po[1], po[2]
            r = math.hypot(x - cx, z - (zc + cz))
            k = (r - thick) / r if r > 1e-9 else 1.0
            pi_ = (cx + (x - cx) * k, po[1], (zc + cz) + (z - (zc + cz)) * k)
            orow.append(po); irow.append(pi_)
        outer.append(orow); inner.append(irow)
    pts = [p for row in outer for p in row] + [p for row in inner for p in row]
    fs = []
    nr = len(rows)
    off = nr * n_cols
    for r in range(nr-1):
        for c in range(n_cols-1 if not wrap else n_cols):
            cn = (c+1) % n_cols
            i00 = r*n_cols+c; i01 = r*n_cols+cn
            i10 = (r+1)*n_cols+c; i11 = (r+1)*n_cols+cn
            fs.append((i00, i01, i10)); fs.append((i01, i11, i10))
            fs.append((off+i00, off+i10, off+i01)); fs.append((off+i01, off+i10, off+i11))
    for r in range(nr-1):  # vertical edge rims (bind the cut edges)
        for c in set(([0, n_cols-1] if not wrap else [])):
            o0 = r*n_cols+c; o1 = (r+1)*n_cols+c
            if c == 0:
                fs.append((off+o0, o0, o1)); fs.append((off+o0, o1, off+o1))
            else:
                fs.append((o0, off+o0, off+o1)); fs.append((o0, off+o1, o1))
    if rim_start:  # top hem rim, normal up
        for c in range(n_cols-1 if not wrap else n_cols):
            cn = (c+1) % n_cols
            fs.append((off+cn, off+c, c)); fs.append((off+cn, c, cn))
    if rim_end:    # bottom hem rim, normal down
        base = (nr-1)*n_cols
        for c in range(n_cols-1 if not wrap else n_cols):
            cn = (c+1) % n_cols
            fs.append((base+c, off+base+c, off+base+cn)); fs.append((base+c, off+base+cn, base+cn))
    add_mesh(mat, name, pts, fs)

def tube_frames(centers, preferred=(1, 0, 0)):
    """Parallel-transport frames along a polyline of centers."""
    centers = [tuple(p) for p in centers]
    frames = []
    for i, c in enumerate(centers):
        tangent = norm(vsub(centers[min(i+1, len(centers)-1)], centers[max(0, i-1)]))
        hint = preferred
        b1 = vsub(hint, vmul(tangent, dot(hint, tangent)))
        if dot(b1, b1) < 1e-6:
            hint = (0, 0, 1) if abs(tangent[2]) < 0.8 else (0, 1, 0)
            b1 = vsub(hint, vmul(tangent, dot(hint, tangent)))
        b1 = norm(b1)
        b2 = norm(cross(tangent, b1))
        frames.append((tangent, b1, b2))
    return frames

def thick_tube(mat, name, points, radii, sides, thick, fold=None,
               rim_start=False, rim_end=True, inner_mat=None):
    """Swept cloth solid around a path: outer face, lining face, open ends
    bound with rims (cuffs, trouser hems, boot shafts)."""
    sides = _segs(sides, 6)
    inner_mat = inner_mat or mat
    frames = tube_frames(points)
    rings_o, rings_i = [], []
    n = len(points)
    for i, c in enumerate(points):
        _, b1, b2 = frames[i]
        rad = radii[i]
        rw, rd = rad if isinstance(rad, (tuple, list)) else (rad, rad)
        ro, ri = [], []
        for s in range(sides):
            a = 2*math.pi*s/sides
            ca, sa = math.cos(a), math.sin(a)
            po = vadd(c, vadd(vmul(b1, rw*ca), vmul(b2, rd*sa)))
            dr = fold(i, s, a) if fold else 0.0
            if dr:
                po = vadd(po, vadd(vmul(b1, dr*ca), vmul(b2, dr*sa)))
            pi_ = vadd(c, vadd(vmul(b1, (rw-thick)*ca), vmul(b2, (rd-thick)*sa)))
            if dr:
                pi_ = vadd(pi_, vadd(vmul(b1, dr*ca), vmul(b2, dr*sa)))
            ro.append(po); ri.append(pi_)
        rings_o.append(ro); rings_i.append(ri)
    pts = [p for ring in rings_o for p in ring] + [p for ring in rings_i for p in ring]
    fs = []
    off = n * sides
    for r in range(n-1):
        for s in range(sides):
            sn = (s+1) % sides
            i00 = r*sides+s; i01 = r*sides+sn
            i10 = (r+1)*sides+s; i11 = (r+1)*sides+sn
            fs.append((i00, i01, i10)); fs.append((i01, i11, i10))
            fs.append((off+i00, off+i10, off+i01)); fs.append((off+i01, off+i10, off+i11))
    if rim_start:
        for s in range(sides):
            sn = (s+1) % sides
            fs.append((s, off+s, off+sn)); fs.append((s, off+sn, sn))
    if rim_end:
        base = (n-1)*sides
        for s in range(sides):
            sn = (s+1) % sides
            fs.append((base+s, off+base+s, off+base+sn)); fs.append((base+s, off+base+sn, base+sn))
    add_mesh(mat, name, pts, fs)

def tube(mat, name, points, radii, sides=16, preferred=(1, 0, 0), depth_scale=1.0):
    """Smooth solid swept form (round trim, cords, fingers, hardware)."""
    sides = _segs(sides, 4)
    centers = [tuple(p) for p in points]
    if len(radii) != len(centers):
        raise ValueError("one radius per tube point")
    rings = []
    for i, c in enumerate(centers):
        tangent = norm(vsub(centers[min(i+1, len(centers)-1)], centers[max(0, i-1)]))
        hint = preferred
        b1 = vsub(hint, vmul(tangent, dot(hint, tangent)))
        if dot(b1, b1) < 1e-6:
            hint = (0, 0, 1) if abs(tangent[2]) < 0.8 else (0, 1, 0)
            b1 = vsub(hint, vmul(tangent, dot(hint, tangent)))
        b1 = norm(b1); b2 = norm(cross(tangent, b1))
        rad = radii[i]
        rw, rd = (rad, rad*depth_scale) if isinstance(rad, (float, int)) else rad
        ring = []
        for s in range(sides):
            a = 2*math.pi*s/sides
            ring.append(vadd(c, vadd(vmul(b1, rw*math.cos(a)), vmul(b2, rd*math.sin(a)))))
        rings.append(ring)
    fs = []
    for r in range(len(centers)-1):
        for s in range(sides):
            a = r*sides+s; an = r*sides+(s+1) % sides
            b = (r+1)*sides+s; bn = (r+1)*sides+(s+1) % sides
            fs.extend(((a, an, b), (an, bn, b)))
    for end, reverse in ((0, True), (len(centers)-1, False)):
        center_idx = len(rings); rings.append([centers[end]]); base = end*sides
        for s in range(sides):
            tri = (center_idx, base+(s+1) % sides, base+s) if reverse else (center_idx, base+s, base+(s+1) % sides)
            fs.append(tri)
    pts = [p for ring in rings for p in ring]
    add_mesh(mat, name, pts, fs)

def ellipsoid(mat, name, center, scale, rings=18, sides=28, rotation=None):
    # Smooth UV surface with shared ring vertices; poles are merged to avoid pinched fans.
    rings = _segs(rings, 6); sides = _segs(sides, 6)
    rot = rotation or ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    def transform(p):
        return (center[0]+rot[0][0]*p[0]+rot[0][1]*p[1]+rot[0][2]*p[2],
                center[1]+rot[1][0]*p[0]+rot[1][1]*p[1]+rot[1][2]*p[2],
                center[2]+rot[2][0]*p[0]+rot[2][1]*p[1]+rot[2][2]*p[2])
    pts = [transform((0, scale[1], 0))]
    for r in range(1, rings):
        lat = math.pi*r/rings
        for s in range(sides):
            lon = 2*math.pi*s/sides
            pts.append(transform((scale[0]*math.sin(lat)*math.cos(lon), scale[1]*math.cos(lat), scale[2]*math.sin(lat)*math.sin(lon))))
    bottom = len(pts)
    pts.append(transform((0, -scale[1], 0)))
    fs = []
    for s in range(sides): fs.append((0, 1+(s+1) % sides, 1+s))
    for r in range(rings-2):
        a = 1+r*sides; b = a+sides
        for s in range(sides):
            n = (s+1) % sides
            fs.extend(((a+n, b+s, a+s), (b+n, b+s, a+n)))
    last = 1+(rings-2)*sides
    for s in range(sides): fs.append((last+(s+1) % sides, bottom, last+s))
    add_mesh(mat, name, pts, fs)

def ring_surface(mat, name, profile, sides=48, front_split=0.0):
    """Closed/open smooth single-surface ring (under-layers, base body)."""
    sides = _segs(sides, 6)
    pts = []
    for y, rx, rz, zc in profile:
        for s in range(sides):
            a = 2*math.pi*s/sides
            x = rx*math.cos(a); z = zc+rz*math.sin(a)
            if front_split and z > 0 and abs(x) < front_split:
                x = math.copysign(front_split, x if x else 1)
            pts.append((x, y, z))
    fs = []
    for r in range(len(profile)-1):
        for s in range(sides):
            a = r*sides+s; an = r*sides+(s+1) % sides
            b = (r+1)*sides+s; bn = (r+1)*sides+(s+1) % sides
            fs.extend(((b, an, a), (b, bn, an)))
    add_mesh(mat, name, pts, fs)

def sweep_rect(mat, name, corners_per_station, closed):
    """Swept rectangular solid: each station supplies 4 corners
    (outerL, outerR, innerR, innerL); builds 4 faces + end caps if open."""
    n = len(corners_per_station)
    fs = []
    rng = range(n) if closed else range(n-1)
    for i in rng:
        j = (i+1) % n
        b0, b1 = i*4, j*4
        # outer face, inner face, two side faces
        fs.append((b0, b1, b1+1)); fs.append((b0, b1+1, b0+1))
        fs.append((b0+2, b1+2, b1+3)); fs.append((b0+2, b1+3, b0+3))
        fs.append((b0+1, b1+1, b1+2)); fs.append((b0+1, b1+2, b0+2))
        fs.append((b0+3, b1+3, b1));   fs.append((b0+3, b1, b0))
    if not closed:
        for i in (0, n-1):
            b = i * 4
            fs.append((b, b+1, b+2)); fs.append((b, b+2, b+3))
    pts = [c for st in corners_per_station for c in st]
    add_mesh(mat, name, pts, fs)

def strap_band(mat, name, points, width, thick, normal_fn, closed=False):
    """Flat strap/belt solid following a path; normal_fn(p, tangent)->outward."""
    stations = []
    pts = [tuple(p) for p in points]
    n = len(pts)
    for i, p in enumerate(pts):
        tangent = norm(vsub(pts[min(i+1, n-1)], pts[max(0, i-1)]))
        nrm = normal_fn(p, tangent)
        side = norm(cross(nrm, tangent))
        ol = vadd(vadd(p, vmul(nrm, thick*0.5)), vmul(side, width*0.5))
        orr = vadd(vadd(p, vmul(nrm, thick*0.5)), vmul(side, -width*0.5))
        irr = vadd(vadd(p, vmul(nrm, -thick*0.5)), vmul(side, -width*0.5))
        ill = vadd(vadd(p, vmul(nrm, -thick*0.5)), vmul(side, width*0.5))
        stations.append((ol, orr, irr, ill))
    sweep_rect(mat, name, stations, closed)

def torus_arc(mat, name, center, R, r, sides, segs, axis=(0, 1, 0), arc=2*math.pi, rot=None):
    """Ring/chain-link solid; optional partial arc."""
    sides = _segs(sides, 4); segs = _segs(segs, 4)
    ax = norm(axis)
    ref = (0, 1, 0) if abs(ax[1]) < 0.9 else (1, 0, 0)
    u = norm(vsub(ref, vmul(ax, dot(ref, ax))))
    w = cross(ax, u)
    pts = []
    for i in range(segs):
        t = arc*i/segs
        cx = center[0] + (u[0]*math.cos(t) + w[0]*math.sin(t))*R
        cy = center[1] + (u[1]*math.cos(t) + w[1]*math.sin(t))*R
        cz = center[2] + (u[2]*math.cos(t) + w[2]*math.sin(t))*R
        for s in range(sides):
            b = 2*math.pi*s/sides
            rr = r*math.cos(b)
            hh = r*math.sin(b)
            px = cx + (u[0]*math.cos(t) + w[0]*math.sin(t))*rr + ax[0]*hh
            py = cy + (u[1]*math.cos(t) + w[1]*math.sin(t))*rr + ax[1]*hh
            pz = cz + (u[2]*math.cos(t) + w[2]*math.sin(t))*rr + ax[2]*hh
            pts.append((px, py, pz))
    fs = []
    for i in range(segs):
        i2 = (i+1) % segs
        for s in range(sides):
            sn = (s+1) % sides
            a = i*sides+s; an = i*sides+sn
            b = i2*sides+s; bn = i2*sides+sn
            fs.extend(((a, an, b), (an, bn, b)))
    add_mesh(mat, name, pts, fs)

def stitch_dashes(mat, name, path_pts, count, r=0.0028, length=0.013):
    """Dashed saddle-stitch trim following a path (original decorative seam)."""
    count = max(2, int(round(count * DETAIL)))
    pts = [tuple(p) for p in path_pts]
    n = len(pts)
    for k in range(count):
        t = (k + 0.5) / count
        f = t * (n - 1)
        i = min(int(f), n - 2)
        frac = f - i
        c = lerp(pts[i], pts[i+1], frac)
        tangent = norm(vsub(pts[i+1], pts[i]))
        mid = vmul(tangent, length*0.5)
        tube(mat, f"{name}_d{k}", (vsub(c, mid), vadd(c, mid)), [r, r], 6, (0, 1, 0))

# =========================================================================
# VESPERSHADE PROTAGONIST: ORIGINAL SCULPTED HEAD, FACE, EARS, EYES & HAIR
# =========================================================================

# 1. Seamless Anatomically Proportioned Head, Face, and Neck
def generate_unified_head(rings=110, sides=64):
    pts = []
    y_vals = [1.440 + i * (1.815 - 1.440) / (rings - 1) for i in range(rings)]
    
    spline_y        = [1.440, 1.490, 1.530, 1.555, 1.580, 1.605, 1.635, 1.665, 1.695, 1.718, 1.745, 1.772, 1.792, 1.808, 1.815]
    spline_rx       = [0.076, 0.068, 0.064, 0.065, 0.060, 0.068, 0.078, 0.086, 0.084, 0.082, 0.080, 0.074, 0.062, 0.038, 0.006]
    spline_rz_back  = [0.072, 0.066, 0.066, 0.072, 0.082, 0.092, 0.102, 0.108, 0.112, 0.112, 0.108, 0.098, 0.082, 0.052, 0.010]
    spline_rz_front = [0.076, 0.068, 0.064, 0.068, 0.074, 0.078, 0.082, 0.086, 0.084, 0.082, 0.078, 0.068, 0.056, 0.035, 0.006]
    spline_cz       = [0.000, 0.002, 0.004, 0.005, 0.004, 0.000,-0.006,-0.010,-0.014,-0.016,-0.018,-0.018,-0.018,-0.018,-0.018]
    
    def g2(x_val, y_val, mx, my, sx, sy):
        return math.exp(-(((x_val - mx)/sx)**2 + ((y_val - my)/sy)**2)/2.0)

    for r_idx, y in enumerate(y_vals):
        rx = interp_val(y, spline_y, spline_rx)
        rz_back = interp_val(y, spline_y, spline_rz_back)
        rz_front = interp_val(y, spline_y, spline_rz_front)
        cz = interp_val(y, spline_y, spline_cz)
        
        ring = []
        for s in range(sides):
            a = 2.0 * math.pi * s / sides
            cos_a = math.cos(a)
            sin_a = math.sin(a)
            
            blend_t = 0.5 * (cos_a + 1.0)
            rz = rz_back * (1.0 - blend_t) + rz_front * blend_t
            
            px = rx * sin_a
            pz = cz + rz * cos_a
            py = y
            
            if cos_a > 0.0:
                front_blend = cos_a ** 1.5
                
                # Chin definition
                chin = g2(px, y, 0.0, 1.588, 0.018, 0.014) * 0.018
                chin_tub = (g2(px, y, 0.012, 1.588, 0.010, 0.012) + g2(px, y, -0.012, 1.588, 0.010, 0.012)) * 0.007
                mento = g2(px, y, 0.0, 1.606, 0.024, 0.007) * -0.0055
                
                # Lips and philtrum
                l_lip = g2(px, y, 0.0, 1.618, 0.018, 0.007) * 0.011
                u_lip_mid = g2(px, y, 0.0, 1.632, 0.008, 0.006) * 0.009
                u_lip_peaks = (g2(px, y, 0.008, 1.633, 0.006, 0.006) + g2(px, y, -0.008, 1.633, 0.006, 0.006)) * 0.0095
                fissure = g2(px, y, 0.0, 1.625, 0.022, 0.0035) * -0.006
                corners = (g2(px, y, 0.022, 1.624, 0.006, 0.006) + g2(px, y, -0.022, 1.624, 0.006, 0.006)) * -0.006
                phil_trough = g2(px, y, 0.0, 1.644, 0.004, 0.007) * -0.0028
                phil_cols = (g2(px, y, 0.0045, 1.644, 0.0025, 0.007) + g2(px, y, -0.0045, 1.644, 0.0025, 0.007)) * 0.0025
                
                # Nose bridge, tip, alar wings
                tip = g2(px, y, 0.0, 1.660, 0.011, 0.011) * 0.024
                bridge = g2(px, y, 0.0, 1.682, 0.007, 0.016) * 0.018
                hump = g2(px, y, 0.0, 1.674, 0.006, 0.009) * 0.004
                alar = (g2(px, y, 0.013, 1.652, 0.006, 0.008) + g2(px, y, -0.013, 1.652, 0.006, 0.008)) * 0.008
                nasion = g2(px, y, 0.0, 1.702, 0.010, 0.008) * -0.0055
                columella = g2(px, y, 0.0, 1.650, 0.005, 0.006) * 0.007
                
                # Zygomatic arches & cheek definition
                zygoma = (g2(px, y, 0.052, 1.675, 0.018, 0.018) + g2(px, y, -0.052, 1.675, 0.018, 0.018)) * 0.011
                buccal = (g2(px, y, 0.038, 1.644, 0.016, 0.018) + g2(px, y, -0.038, 1.644, 0.016, 0.018)) * -0.006
                canine_fossa = (g2(px, y, 0.018, 1.656, 0.007, 0.012) + g2(px, y, -0.018, 1.656, 0.007, 0.012)) * -0.004
                
                # Eye sockets & brow ridge
                socket = (g2(px, y, 0.033, 1.692, 0.013, 0.010) + g2(px, y, -0.033, 1.692, 0.013, 0.010)) * -0.012
                glabella = g2(px, y, 0.0, 1.714, 0.011, 0.010) * 0.007
                brow = (g2(px, y, 0.030, 1.716, 0.016, 0.009) + g2(px, y, -0.030, 1.716, 0.016, 0.009)) * 0.009
                boss = (g2(px, y, 0.026, 1.742, 0.018, 0.014) + g2(px, y, -0.026, 1.742, 0.018, 0.014)) * 0.004
                
                # Subtle gothic asymmetry
                asym = g2(px, y, 0.030, 1.716, 0.016, 0.009) * 0.0014 + g2(px, y, 0.012, 1.588, 0.010, 0.012) * 0.0010
                
                pz += (chin + chin_tub + mento + l_lip + u_lip_mid + u_lip_peaks + fissure + corners + 
                       phil_trough + phil_cols + tip + bridge + hump + alar + nasion + columella + 
                       zygoma + buccal + canine_fossa + socket + glabella + brow + boss + asym) * front_blend
                
            if y < 1.555:
                scm = (math.exp(-((a - math.radians(40))**2)/0.08) + math.exp(-((a - (2*math.pi - math.radians(40)))**2)/0.08)) * 0.006 * (1.0 - (y-1.44)/0.15)
                larynx = math.exp(-(a**2)/0.06) * math.exp(-((y - 1.520)/0.018)**2) * 0.007
                nape = math.exp(-((a - math.pi)**2)/0.06) * -0.004
                pz += scm * cos_a + larynx + nape
                px += scm * sin_a

            ring.append((px, py, pz))
        pts.append(ring)
        
    flat_pts = [p for r in pts for p in r]
    polys = []
    for r in range(rings - 1):
        for s in range(sides):
            p0 = r * sides + s
            p1 = r * sides + (s + 1) % sides
            p2 = (r + 1) * sides + s
            p3 = (r + 1) * sides + (s + 1) % sides
            polys.append((p0, p1, p2))
            polys.append((p1, p3, p2))
            
    top_pole = len(flat_pts)
    flat_pts.append((0.0, 1.815, spline_cz[-1]))
    top_ring = (rings - 1) * sides
    for s in range(sides):
        polys.append((top_ring + (s + 1) % sides, top_ring + s, top_pole))
        
    return flat_pts, polys

head_pts, head_polys = generate_unified_head()
add_mesh("Skin", "Head/FaceAndNeck", head_pts, head_polys)

# 2. Detailed Sculpted Anatomical Ears
def generate_detailed_ears():
    ear_verts = []
    ear_polys = []
    
    for side in (1, -1):
        cx = side * 0.080
        cy = 1.660
        cz = -0.014
        
        num_rim = 16
        rim_pts = []
        inner_pts = []
        concha_pts = []
        
        for i in range(num_rim):
            t = i / (num_rim - 1)
            theta = 0.15 * math.pi + t * 1.25 * math.pi
            
            ry = 0.026
            rz = 0.016
            ey = cy + ry * math.cos(theta)
            ez = cz - rz * math.sin(theta)
            ex = cx + side * (0.012 * math.sin(t * math.pi) + 0.004)
            rim_pts.append((ex, ey, ez))
            
            iy = cy + ry * 0.70 * math.cos(theta)
            iz = cz - rz * 0.65 * math.sin(theta)
            ix = cx + side * (0.007 * math.sin(t * math.pi) + 0.002)
            inner_pts.append((ix, iy, iz))
            
            cy_pt = cy + ry * 0.35 * math.cos(theta) - 0.003
            cz_pt = cz - rz * 0.30 * math.sin(theta)
            cx_pt = cx + side * 0.001
            concha_pts.append((cx_pt, cy_pt, cz_pt))
            
        base = len(ear_verts)
        ear_verts.extend(rim_pts + inner_pts + concha_pts)
        
        for i in range(num_rim - 1):
            p0 = base + i
            p1 = base + i + 1
            p2 = base + num_rim + i
            p3 = base + num_rim + i + 1
            if side > 0:
                ear_polys.extend(((p0, p1, p2), (p1, p3, p2)))
            else:
                ear_polys.extend(((p0, p2, p1), (p1, p2, p3)))
                
        for i in range(num_rim - 1):
            p0 = base + num_rim + i
            p1 = base + num_rim + i + 1
            p2 = base + 2 * num_rim + i
            p3 = base + 2 * num_rim + i + 1
            if side > 0:
                ear_polys.extend(((p0, p1, p2), (p1, p3, p2)))
            else:
                ear_polys.extend(((p0, p2, p1), (p1, p2, p3)))
                
        tragus_idx = len(ear_verts)
        ear_verts.append((cx + side * 0.008, cy - 0.002, cz + 0.006))
        ear_verts.append((cx + side * 0.006, cy - 0.028, cz - 0.008))
        
        if side > 0:
            ear_polys.append((base, base + num_rim, tragus_idx))
            ear_polys.append((base + num_rim - 1, tragus_idx + 1, base + 2*num_rim - 1))
        else:
            ear_polys.append((base, tragus_idx, base + num_rim))
            ear_polys.append((base + num_rim - 1, base + 2*num_rim - 1, tragus_idx + 1))
            
    return ear_verts, ear_polys

ear_pts, ear_polys = generate_detailed_ears()
add_mesh("Skin", "Head/DetailedEars", ear_pts, ear_polys)

# 3. Eyeballs Inset into Anatomical Orbits (BoneThread material)
def generate_eyeballs():
    eye_verts = []
    eye_polys = []
    for side in (-1, 1):
        cx = side * 0.033
        cy = 1.692
        cz = 0.052
        r = 0.0105
        
        rings = 10
        sides = 16
        base = len(eye_verts)
        pts = [(cx, cy + r, cz)]
        for ri in range(1, rings):
            lat = math.pi * ri / rings
            y = cy + r * math.cos(lat)
            rr = r * math.sin(lat)
            for si in range(sides):
                lon = 2.0 * math.pi * si / sides
                x = cx + rr * math.sin(lon)
                z = cz + rr * math.cos(lon)
                pts.append((x, y, z))
        bot = len(pts)
        pts.append((cx, cy - r, cz))
        
        fs = []
        for si in range(sides):
            fs.append((0, 1 + si, 1 + (si + 1) % sides))
        for ri in range(rings - 2):
            for si in range(sides):
                p0 = 1 + ri * sides + si
                p1 = 1 + ri * sides + (si + 1) % sides
                p2 = 1 + (ri + 1) * sides + si
                p3 = 1 + (ri + 1) * sides + (si + 1) % sides
                fs.extend(((p0, p2, p1), (p1, p2, p3)))
        last = 1 + (rings - 2) * sides
        for si in range(sides):
            fs.append((bot, last + (si + 1) % sides, last + si))
            
        eye_verts.extend(pts)
        eye_polys.extend([(base + f[0], base + f[1], base + f[2]) for f in fs])
    return eye_verts, eye_polys

eye_pts, eye_polys = generate_eyeballs()
add_mesh("BoneThread", "Head/Eyes", eye_pts, eye_polys)

# 4. Sculpted Arched Eyebrows (Hair material)
def generate_eyebrows():
    brow_verts = []
    brow_polys = []
    for side in (-1, 1):
        asym_y = 0.0018 if side < 0 else 0.0
        pts = [
            (side * 0.014, 1.712 + asym_y, 0.068),
            (side * 0.024, 1.719 + asym_y, 0.066),
            (side * 0.038, 1.722 + asym_y, 0.061),
            (side * 0.052, 1.718 + asym_y, 0.052),
            (side * 0.064, 1.710 + asym_y, 0.040)
        ]
        radii = [(0.0045, 0.003), (0.0055, 0.0035), (0.0050, 0.0032), (0.0035, 0.0025), (0.0015, 0.0015)]
        
        sides = 8
        n_pts = len(pts)
        ring_pts = []
        for i, c in enumerate(pts):
            p_next = pts[min(i+1, n_pts-1)]
            p_prev = pts[max(0, i-1)]
            tangent = norm(vsub(p_next, p_prev))
            if dot(tangent, tangent) < 1e-6: tangent = (side, 0.0, 0.0)
            hint = (0.0, 1.0, 0.0)
            b1 = norm(vsub(hint, vmul(tangent, dot(hint, tangent))))
            b2 = cross(tangent, b1)
            rx, rz = radii[i]
            for s in range(sides):
                a = 2.0 * math.pi * s / sides
                off = vadd(vmul(b1, rx * math.cos(a)), vmul(b2, rz * math.sin(a)))
                ring_pts.append(vadd(c, off))
                
        base = len(brow_verts)
        brow_verts.extend(ring_pts)
        for r in range(n_pts - 1):
            for s in range(sides):
                a = base + r * sides + s
                an = base + r * sides + (s + 1) % sides
                b = base + (r + 1) * sides + s
                bn = base + (r + 1) * sides + (s + 1) % sides
                brow_polys.extend(((a, an, b), (an, bn, b)))
    return brow_verts, brow_polys

brow_pts, brow_polys = generate_eyebrows()
add_mesh("Hair", "Head/Eyebrows", brow_pts, brow_polys)

# 5. Volumetric Layered Gothic Hairstyle
def generate_gothic_hair():
    hair_verts = []
    hair_polys = []

    def add_mesh_hair(points, faces):
        base = len(hair_verts)
        hair_verts.extend(points)
        hair_polys.extend([(base + f[0], base + f[1], base + f[2]) for f in faces])

    spline_y        = [1.440, 1.490, 1.530, 1.555, 1.580, 1.605, 1.635, 1.665, 1.695, 1.718, 1.745, 1.772, 1.792, 1.808, 1.815]
    spline_rx       = [0.076, 0.068, 0.064, 0.065, 0.060, 0.068, 0.078, 0.086, 0.084, 0.082, 0.080, 0.074, 0.062, 0.038, 0.006]
    spline_rz_back  = [0.072, 0.066, 0.066, 0.072, 0.082, 0.092, 0.102, 0.108, 0.112, 0.112, 0.108, 0.098, 0.082, 0.052, 0.010]
    spline_rz_front = [0.076, 0.068, 0.064, 0.068, 0.074, 0.078, 0.082, 0.086, 0.084, 0.082, 0.078, 0.068, 0.056, 0.035, 0.006]
    spline_cz       = [0.000, 0.002, 0.004, 0.005, 0.004, 0.000,-0.006,-0.010,-0.014,-0.016,-0.018,-0.018,-0.018,-0.018,-0.018]

    # Full Solid Cap Base
    cap_rings = 36
    cap_sides = 48
    pts = []
    fs = []
    
    top_pole = (0.0, 1.824, -0.018)
    pts.append(top_pole)
    
    y_levels = [1.816 - i * (1.816 - 1.560) / (cap_rings - 2) for i in range(cap_rings - 1)]
    
    for r_idx, y_ring in enumerate(y_levels):
        rx_skull = interp_val(y_ring, spline_y, spline_rx)
        rz_b_skull = interp_val(y_ring, spline_y, spline_rz_back)
        rz_f_skull = interp_val(y_ring, spline_y, spline_rz_front)
        cz_skull = interp_val(y_ring, spline_y, spline_cz)
        
        hair_offset = 0.0065
        rx_h = rx_skull + hair_offset
        rz_b_h = rz_b_skull + hair_offset + 0.002
        rz_f_h = rz_f_skull + hair_offset
        
        for s in range(cap_sides):
            lon = 2.0 * math.pi * s / cap_sides
            cos_lon = math.cos(lon)
            sin_lon = math.sin(lon)
            
            blend_t = 0.5 * (cos_lon + 1.0)
            rz = rz_b_h * (1.0 - blend_t) + rz_f_h * blend_t
            
            px = rx_h * sin_lon
            pz = cz_skull + rz * cos_lon
            py = y_ring
            
            if cos_lon > 0.0:
                hairline_y = 1.738 + 0.008 * math.cos(lon * 2.0)
                if py < hairline_y:
                    py = hairline_y
                    
            pts.append((px, py, pz))
            
    for s in range(cap_sides):
        p1 = 1 + s
        p2 = 1 + (s + 1) % cap_sides
        fs.append((0, p1, p2))
        
    for r in range(cap_rings - 2):
        for s in range(cap_sides):
            p0 = 1 + r * cap_sides + s
            p1 = 1 + r * cap_sides + (s + 1) % cap_sides
            p2 = 1 + (r + 1) * cap_sides + s
            p3 = 1 + (r + 1) * cap_sides + (s + 1) % cap_sides
            fs.extend(((p0, p2, p1), (p1, p2, p3)))
            
    add_mesh_hair(pts, fs)

    # Swept volume locks
    def swept_lock(spline, radii, sides=10, twist=0.0):
        sides = _segs(sides, 6)
        centers = spline
        n = len(centers)
        ring_pts = []
        ring_fs = []
        for i, c in enumerate(centers):
            p_next = centers[min(i+1, n-1)]
            p_prev = centers[max(0, i-1)]
            tangent = norm(vsub(p_next, p_prev))
            if dot(tangent, tangent) < 1e-6: tangent = (0.0, 1.0, 0.0)
            hint = (1.0, 0.0, 0.0)
            b1 = norm(vsub(hint, vmul(tangent, dot(hint, tangent))))
            if dot(b1, b1) < 0.2:
                hint = (0.0, 0.0, 1.0)
                b1 = norm(vsub(hint, vmul(tangent, dot(hint, tangent))))
            b2 = cross(tangent, b1)
            
            angle_rot = twist * (i / (n - 1))
            cr, sr = math.cos(angle_rot), math.sin(angle_rot)
            rb1 = vadd(vmul(b1, cr), vmul(b2, sr))
            rb2 = vadd(vmul(b1, -sr), vmul(b2, cr))
            
            rx, ry = radii[i] if isinstance(radii[i], (list, tuple)) else (radii[i], radii[i]*0.6)
            for s in range(sides):
                a = 2.0 * math.pi * s / sides
                off = vadd(vmul(rb1, rx * math.cos(a)), vmul(rb2, ry * math.sin(a)))
                ring_pts.append(vadd(c, off))
                
        for r in range(n - 1):
            for s in range(sides):
                a = r * sides + s
                an = r * sides + (s + 1) % sides
                b = (r + 1) * sides + s
                bn = (r + 1) * sides + (s + 1) % sides
                ring_fs.extend(((a, an, b), (an, bn, b)))
                
        tc = len(ring_pts); ring_pts.append(centers[0])
        bc = len(ring_pts); ring_pts.append(centers[-1])
        for s in range(sides):
            ring_fs.append((tc, (s+1)%sides, s))
            base_bot = (n - 1) * sides
            ring_fs.append((bc, base_bot + s, base_bot + (s+1)%sides))
            
        add_mesh_hair(ring_pts, ring_fs)

    locks = [
        ([(0.025, 1.775, 0.082), (0.005, 1.755, 0.088), (-0.022, 1.730, 0.086), (-0.045, 1.700, 0.078)],
         [(0.022, 0.014), (0.020, 0.012), (0.015, 0.009), (0.004, 0.003)], 0.2),
        ([(-0.040, 1.765, 0.072), (-0.068, 1.728, 0.076), (-0.082, 1.675, 0.066), (-0.080, 1.620, 0.048), (-0.068, 1.575, 0.035)],
         [(0.020, 0.013), (0.018, 0.012), (0.014, 0.010), (0.009, 0.006), (0.003, 0.003)], -0.25),
        ([(-0.055, 1.760, 0.055), (-0.078, 1.710, 0.050), (-0.085, 1.650, 0.032), (-0.078, 1.595, 0.018)],
         [(0.018, 0.012), (0.016, 0.010), (0.011, 0.007), (0.003, 0.003)], -0.15),
        ([(0.038, 1.765, 0.068), (0.065, 1.735, 0.058), (0.082, 1.695, 0.035), (0.084, 1.650, 0.005), (0.078, 1.605, -0.018)],
         [(0.018, 0.012), (0.016, 0.011), (0.012, 0.008), (0.008, 0.005), (0.003, 0.003)], 0.25),
        ([(0.000, 1.822, 0.020), (-0.005, 1.832, -0.018), (-0.010, 1.822, -0.060), (-0.008, 1.785, -0.098)],
         [(0.024, 0.016), (0.026, 0.018), (0.022, 0.014), (0.006, 0.005)], 0.1),
        ([(0.035, 1.815, 0.010), (0.068, 1.800, -0.015), (0.082, 1.760, -0.045), (0.084, 1.705, -0.070)],
         [(0.020, 0.014), (0.022, 0.015), (0.016, 0.011), (0.005, 0.004)], 0.15),
        ([(-0.035, 1.815, 0.010), (-0.068, 1.800, -0.015), (-0.082, 1.760, -0.045), (-0.084, 1.705, -0.070)],
         [(0.020, 0.014), (0.022, 0.015), (0.016, 0.011), (0.005, 0.004)], -0.15),
        ([(-0.035, 1.730, -0.095), (-0.038, 1.675, -0.108), (-0.030, 1.620, -0.098), (-0.018, 1.565, -0.082)],
         [(0.020, 0.014), (0.018, 0.012), (0.012, 0.008), (0.004, 0.003)], -0.1),
        ([(0.035, 1.730, -0.095), (0.038, 1.675, -0.108), (0.030, 1.620, -0.098), (0.018, 1.565, -0.082)],
         [(0.020, 0.014), (0.018, 0.012), (0.012, 0.008), (0.004, 0.003)], 0.1),
        ([(0.000, 1.725, -0.100), (0.000, 1.665, -0.112), (0.000, 1.610, -0.102), (0.000, 1.555, -0.084)],
         [(0.022, 0.016), (0.020, 0.014), (0.014, 0.010), (0.004, 0.003)], 0.0),
        ([(0.012, 1.765, 0.084), (-0.004, 1.735, 0.090), (-0.018, 1.705, 0.085)],
         [(0.012, 0.008), (0.009, 0.006), (0.003, 0.002)], 0.2)
    ]
    
    for spline, radii, twist in locks:
        swept_lock(spline, radii, sides=10, twist=twist)
        
    return hair_verts, hair_polys

hair_pts, hair_polys = generate_gothic_hair()
add_mesh("Hair", "Hair/WayfarerHairstyle", hair_pts, hair_polys)

# =========================================================================
# BODY UNDER-LAYERS (kept minimal: only what garments can reveal)
# =========================================================================

# Anatomically tapered torso (visible above the waistcoat neckline and at the
# collar V); forearms remain as the layer inside the coat sleeves.
ring_surface("Skin", "Body/Torso", [(1.00,.18,.105,0),(1.10,.205,.115,0),(1.25,.25,.13,0),(1.39,.29,.135,0),(1.49,.255,.115,0)],36)
for side, label in ((-1,"L"),(1,"R")):
    x=side
    tube("Skin",f"Body/Forearm_{label}",[(x*.27,1.27,.005),(x*.34,1.10,.018),(x*.365,.97,.035),(x*.37,.88,.04)],[(.075,.075),(.065,.065),(.052,.052),(.047,.05)],20,(1,0,0))

# =========================================================================
# TROUSERS: fitted wool with a yoked waistband, knee creases, ankle wrinkles;
# hems tuck into the boot shafts so no loose hem ever clips the boots.
# =========================================================================
thick_ring_shell("Trouser","LowerBody/TrouserYoke",
    [ (lambda a, y=y, rx=rx, rz=rz, zc=zc: (y, rx, rz, zc)) for y, rx, rz, zc in
      ((1.005,.256,.152,0.0),(.955,.247,.147,0.0),(.905,.242,.144,0.0)) ],
    thick=.007, sides=26, a0=0.0, a1=2*math.pi, wrap=True,
    rim_start=False, rim_end=False)
ellipsoid("Trouser","LowerBody/Seat",(0,.895,0),(.225,.130,.138),12,20)
def trouser_fold(i, s_idx, a):
    # tension creases across the back of each knee, fine wrinkles at the ankle
    back = 0.5 + 0.5*math.cos(a - 1.5*math.pi)
    knee = -0.0055 * math.exp(-((i-1.95)/0.45)**2) * back
    ankle = 0.0028 * math.sin(5*a) * math.exp(-((i-3.5)/0.5)**2)
    return knee + ankle
for side, label in ((-1,"L"),(1,"R")):
    x=side
    thick_tube("Trouser",f"LowerBody/Leg_{label}",
        [(x*.113,.915,-.002),(x*.117,.660,-.004),(x*.116,.485,.012),(x*.111,.365,.008),(x*.113,.302,.013)],
        [(.102,.106),(.084,.088),(.066,.070),(.069,.073),(.061,.065)],
        sides=18, thick=.006, fold=trouser_fold, rim_start=True, rim_end=False)

# =========================================================================
# BOOTS: multi-part field boots - welted sole, separate heel block, toe cap
# with saddle stitching, heel counter, laced shaft with folded cuff, pull
# tab, instep straps (buckled on the right boot only).
# =========================================================================
def boot_normal(side):
    def fn(p, tangent):
        return norm(((p[0]-side*.118)*1.25, 0.0, (p[2]-0.05)*0.8))
    return fn
def strap_up_normal(side):
    def fn(p, tangent):
        n = norm(((p[0]-side*.118)*1.25, 0.0, (p[2]-0.05)*0.8))
        return n
    return fn
for side, label in ((-1,"L"),(1,"R")):
    x=side
    # sole, heel and welt
    ellipsoid("BootSole",f"Boots/Sole_{label}",(x*.118,.048,.058),(.100,.033,.185),10,22)
    ellipsoid("BootSole",f"Boots/Heel_{label}",(x*.118,.050,-.062),(.060,.047,.068),8,14)
    welt_pts=[(x*.118+.104*math.cos(2*math.pi*k/12),.075,.058+.188*math.sin(2*math.pi*k/12)) for k in range(12)]
    welt_pts.append(welt_pts[0])
    tube("Leather",f"Boots/Welt_{label}",welt_pts,[.006]*13,8,(0,1,0))
    # vamp and stitched toe cap
    ellipsoid("Leather",f"Boots/Vamp_{label}",(x*.118,.115,.085),(.092,.072,.142),12,22)
    ellipsoid("Leather",f"Boots/ToeCap_{label}",(x*.118,.103,.168),(.088,.062,.072),10,18)
    cap_st=[(x*.118+.080,.092,.150),(x*.118+.062,.118,.196),(x*.118,.132,.215),(x*.118-.062,.118,.196),(x*.118-.080,.092,.150)]
    stitch_dashes("BoneThread",f"Boots/ToeCapStitch_{label}",cap_st,7)
    # heel counter (bound top edge)
    thick_ring_shell("Leather",f"Boots/Counter_{label}",
        [ (lambda a, y=y, rx=rx, rz=rz: (y, rx, rz, zc)) for y, rx, rz, zc in
          ((.095,.098,.100,.010),(.170,.095,.098,.008),(.245,.097,.100,.006)) ],
        thick=.006, sides=14, a0=math.pi-1.05, a1=math.pi+1.05,
        rim_start=True, rim_end=False, center=(x*.116,0,0))
    # shaft with slouch wrinkles and folded top cuff
    def shaft_fold(i, s_idx, a, side=side):
        return .004*math.sin(4*a+.7)*math.exp(-((i-0.8)/0.5)**2)
    thick_tube("Leather",f"Boots/Shaft_{label}",
        [(x*.115,.285,.012),(x*.116,.360,.008),(x*.117,.432,.004)],
        [(.096,.100),(.099,.104),(.103,.113)], sides=20, thick=.007,
        fold=shaft_fold, rim_start=True, rim_end=True)
    thick_tube("ClothAccent",f"Boots/CuffFold_{label}",
        [(x*.117,.432,.004),(x*.118,.452,.002)],
        [(.113,.123),(.110,.121)], sides=20, thick=.005, rim_start=False, rim_end=True)
    thick_ring_shell("ClothAccent",f"Boots/CuffLining_{label}",
        [ (lambda a, y=y, rx=rx, rz=rz: (y, rx, rz, zc)) for y, rx, rz, zc in
          ((.444,.100,.110,.002),(.450,.102,.112,.002)) ],
        thick=.003, sides=16, a0=0.0, a1=2*math.pi, wrap=True,
        rim_start=False, rim_end=True, center=(x*.118,0,0))
    # back pull tab
    strap_band("Leather",f"Boots/PullTab_{label}",
        [(x*.116,.452,-.100),(x*.116,.472,-.110),(x*.116,.452,-.118)],
        width=.014, thick=.003, normal_fn=lambda p,t:(0,0,-1.0))
    # crossed instep straps; right boot carries the buckle
    strap_band("Leather",f"Boots/InstepStrapA_{label}",
        [(x*.150,.155,.030),(x*.120,.128,.120),(x*.088,.150,.208)],
        width=.015, thick=.003, normal_fn=boot_normal(side))
    strap_band("Leather",f"Boots/InstepStrapB_{label}",
        [(x*.092,.128,.028),(x*.122,.102,.118),(x*.152,.126,.205)],
        width=.015, thick=.003, normal_fn=boot_normal(side))
    if side > 0:
        bx,by,bz = x*.155,.158,.024
        tube("AgedBrass",f"Boots/StrapBuckleSide_{label}",[(bx,by-.011,bz),(bx,by+.011,bz)],[.004,.004],8,(1,0,0))
        tube("AgedBrass",f"Boots/StrapBuckleBar_{label}",[(bx,by-.011,bz),(bx,by+.011,bz)],[.004,.004],8,(0,0,1))
        tube("AgedBrass",f"Boots/StrapBuckleBar2_{label}",[(bx-.008,by-.011,bz),(bx-.008,by+.011,bz)],[.0035,.0035],8,(0,0,1))
        tube("AgedBrass",f"Boots/StrapProng_{label}",[(bx,by,bz),(bx-x*.009,by,bz+.006)],[.0026,.0026],6,(0,1,0))
    else:
        stitch_dashes("BoneThread",f"Boots/StrapStitch_{label}",
            [(x*.146,.153,.038),(x*.120,.127,.120),(x*.092,.148,.200)],6)

# =========================================================================
# GLOVES: gauntlet cuffs with bound openings, reinforced knuckle band,
# articulated fingers with knuckle creases; wrist strap on the right hand.
# =========================================================================
for side, label in ((-1,"L"),(1,"R")):
    x=side
    thick_tube("Leather",f"Accessories/Gauntlet_{label}",
        [(x*.387,1.055,.034),(x*.383,1.005,.040)],
        [(.066,.070),(.061,.065)], sides=18, thick=.005, rim_start=True, rim_end=True)
    ellipsoid("Leather",f"Accessories/GloveHand_{label}",(x*.385,.950,.054),(.048,.066,.058),10,16)
    ellipsoid("Leather",f"Accessories/KnuckleBand_{label}",(x*.402,.965,.056),(.010,.022,.030),8,12)
    for j in range(4):
        fz=.054+(1.5-j)*.021
        length=(.052,.058,.054,.042)[j]
        tube("Leather",f"Accessories/Glove_{label}_Finger{j+1}",
            [(x*.387,.914,fz),(x*.388,.886,fz+.004),(x*.388,.872,fz+.009),(x*.390,.914-length,fz+.014)],
            [(.0115,.0115),(.0092,.0092),(.0099,.0099),(.0068,.0070)],10,(1,0,0))
    tube("Leather",f"Accessories/Glove_{label}_Thumb",
        [(x*.360,.928,.082),(x*.344,.898,.096),(x*.336,.872,.102)],
        [(.016,.016),(.0125,.0125),(.0085,.0085)],10,(1,0,0))
    if side > 0:
        ring_pts=[(x*.386+.063*math.cos(2*math.pi*k/10),1.030,.036+.063*math.sin(2*math.pi*k/10)*0.9) for k in range(10)]
        ring_pts.append(ring_pts[0])
        tube("Leather",f"Accessories/WristStrap_{label}",ring_pts,[.0035]*11,6,(0,1,0))
        tube("AgedBrass",f"Accessories/WristBuckle_{label}",[(x*.452,1.030,.036),(x*.452,1.030,.036)], [.001,.001],4,(0,1,0))
        tube("AgedBrass",f"Accessories/WristBuckleFrame_{label}",[(x*.449,1.021,.036),(x*.449,1.039,.036)],[.0035,.0035],8,(1,0,0))
    else:
        ellipsoid("AgedBrass",f"Accessories/GauntletButton_{label}",(x*.452,1.040,.034),(.007,.007,.005),8,10)


# =========================================================================
# WAISTCOAT: fitted wine wool visible inside the coat's front opening;
# V-necked front panel with bound armhole edges, bone buttons on an offset
# placket, two pocket welts, bound hem. Sits clear inside the coat shell.
# =========================================================================
WC_ROWS = [(0.985,.250,.147,-0.12,0.06),(1.05,.238,.141,-0.13,0.07),
           (1.13,.230,.138,-0.16,0.10),(1.21,.238,.141,-0.24,0.18),
           (1.29,.262,.146,-0.40,0.34),(1.37,.300,.152,-0.50,0.44),
           (1.43,.306,.146,-0.54,0.48),(1.468,.292,.128,-0.56,0.50)]
def wc_rows():
    return [(lambda a, y=y, rx=rx, rz=rz, a0=a0, a1=a1: (y, rx, rz, 0.0, a0, a1))
            for y, rx, rz, a0, a1 in WC_ROWS]
def wc_fold(a, ri):
    y = WC_ROWS[ri][0]
    return (0.0028*math.sin(7*a+1.0)*smoothstep(1.05,1.15,y)*(1.0-smoothstep(1.30,1.40,y)), 0.0, 0.0)
thick_ring_shell("ClothAccent", "UpperClothing/Waistcoat", wc_rows(),
    thick=.008, sides=18, a0=-0.70, a1=0.66, rim_start=True, rim_end=True, fold=wc_fold)
# offset button placket line (asymmetric, left of centre) with bone buttons
wc_y = [r[0] for r in WC_ROWS]; wc_rx = [r[1] for r in WC_ROWS]; wc_rz = [r[2] for r in WC_ROWS]
for i in range(5):
    y = 1.40 - .085*i
    ry = interp_val(y, wc_y, wc_rx); rzv = interp_val(y, wc_y, wc_rz)
    p = shell_point(y, ry, rzv, 0.0, -0.06, 0.004, 0, 0)
    ellipsoid("BoneThread", f"Accessories/WaistcoatButton_{i+1}", (p[0], p[1], p[2]), (.0085, .0085, .005), 8, 10)
for wi, wy in ((1, 1.14), (2, 1.23)):
    ry = interp_val(wy, wc_y, wc_rx); rzv = interp_val(wy, wc_y, wc_rz)
    p0 = shell_point(wy, ry, rzv, 0.0, -0.16, 0.005, 0, 0)
    p1 = shell_point(wy, ry, rzv, 0.0, 0.13, 0.005, 0, 0)
    tube("BoneThread", f"Accessories/WaistcoatWelt_{wi}", [p0, vadd(lerp(p0, p1, .5), (0, .002, 0)), p1], [.003]*3, 6, (0, 1, 0))

# =========================================================================
# SHIRT + CRACVAT: ivory standing collar band hugging the neck, cuffs at
# the wrists; wrapped neckcloth with an off-center knot and two unequal
# tails falling over the waistcoat.
# =========================================================================
thick_ring_shell("BoneThread", "UpperClothing/ShirtCollar",
    [ (lambda a, y=y, rx=rx, rz=rz: (y, rx, rz, -0.011)) for y, rx, rz in
      ((1.477,.0675,.0715),(1.522,.0705,.0745)) ],
    thick=.0035, sides=22, a0=0.0, a1=2*math.pi, wrap=True, rim_start=False, rim_end=True)
for side, label in ((-1,"L"),(1,"R")):
    x=side
    thick_ring_shell("BoneThread", f"UpperClothing/ShirtCuff_{label}",
        [ (lambda a, y=y, rx=rx, rz=rz: (y, rx, rz, .037)) for y, rx, rz in
          ((.958,.050,.047),(0.982,.053,.050)) ],
        thick=.003, sides=14, a0=0.0, a1=2*math.pi, wrap=True,
        rim_start=False, rim_end=True, center=(x*.390, 0, 0))
neck_pts = []
for k in range(7):
    a = -0.95 + 1.9*k/6
    neck_pts.append((0.083*math.sin(a), 1.494 - 0.006*(k/6.0), -0.011 + 0.082*math.cos(a)))
strap_band("BoneThread", "Accessories/CravatBand", neck_pts, width=.034, thick=.006,
    normal_fn=lambda p, t: norm((p[0], 0.15, p[2])))
ellipsoid("BoneThread", "Accessories/CravatKnot", (.014, 1.488, .108), (.026, .021, .017), 8, 12)
def front_normal(p, t):
    return norm((p[0]*0.35, 0, 1.0))
strap_band("BoneThread", "Accessories/CravatTailL",
    [(.026, 1.478, .114), (.042, 1.410, .122), (.050, 1.340, .116), (.054, 1.324, .114)],
    width=.026, thick=.004, normal_fn=front_normal)
strap_band("BoneThread", "Accessories/CravatTailR",
    [(.004, 1.480, .115), (-.004, 1.435, .123), (-.012, 1.404, .118)],
    width=.024, thick=.004, normal_fn=front_normal)

# =========================================================================
# THE WAYFARER'S GREATCOAT - original design.
# A heavy, layered greatcoat built as true cloth solids. The front closes
# left-over-right with a deep V opening over the waistcoat; the standing
# collar and the asymmetric shoulder mantle wrap the back; sleeves carry
# gathered heads, elbow creases and bound cuffs. Every cut edge is bound
# with a rim so the cloth reads with real thickness. Layers stack:
# shirt > waistcoat > coat bodice > belt > coat skirt > boots.
# Character faces +Z; a=0 is front centre, wearer's left is +X (a=+pi/2).
# =========================================================================

# Inner-surface radii of the coat bodice (y, rx, rz). Outer face adds COAT_T.
BODICE_ROWS = [(1.00,.272,.168),(1.03,.254,.157),
               (1.16,.262,.158),(1.28,.290,.162),(1.38,.312,.160),
               (1.455,.302,.148),(1.495,.266,.125)]
COAT_T = 0.011          # cloth thickness of the coat body

def coat_inner(y):
    return (interp_val(y, [r[0] for r in BODICE_ROWS], [r[1] for r in BODICE_ROWS]),
            interp_val(y, [r[0] for r in BODICE_ROWS], [r[2] for r in BODICE_ROWS]))

def coat_surf(a, y, out=0.0):
    rx, rz = coat_inner(y)
    return shell_point(y, rx + COAT_T + out, rz + COAT_T + out, 0.0, a, 0.0, 0.0, 0.0)

# Front-opening edges: the V gapes wide at the collar and closes below the
# chest; the left panel overlaps past centre (left-over-right closure).
def edge_left(y):    # V half-width on the wearer's left of centre (+angle)
    return 0.50 * smoothstep(1.20, 1.47, y) + 0.10 * (1 - smoothstep(1.20, 1.47, y))
def edge_right(y):   # V half-width on the wearer's right of centre (+angle)
    return 0.42 * smoothstep(1.18, 1.45, y) + 0.06 * (1 - smoothstep(1.18, 1.45, y))

def bodice_rows_factory(which):
    rows = []
    for y, rx, rz in BODICE_ROWS:
        def fn(a, y=y, rx=rx, rz=rz, which=which):
            # left panel: +edge -> left side -> back; right panel: back -> right side -> -edge
            if which == "L":
                return (y, rx, rz, 0.0, edge_left(y), math.pi)
            return (y, rx, rz, 0.0, math.pi, 2*math.pi - edge_right(y))
        rows.append(fn)
    return rows

def bodice_fold_factory(panel):
    def fold(a, ri):
        am = a % (2*math.pi)
        y = BODICE_ROWS[min(ri, len(BODICE_ROWS)-1)][0]
        dr = 0.0
        w = smoothstep(1.40, 1.475, y)                      # structured shoulders
        dr += 0.005 * w * (gauss(am, math.pi/2, .50) + gauss(am, 1.5*math.pi, .50))
        dr += 0.004 * math.sin(9*a + 0.8) * smoothstep(.94, 1.02, y) * (1 - smoothstep(1.08, 1.22, y))
        dr -= 0.004 * gauss(am, math.pi, 0.45) * (1 - smoothstep(1.18, 1.34, y))
        if panel == "L":
            dr += 0.005 * max(0.0, math.cos(am))            # overlap lift near front only
        return (dr, 0.0, 0.0)
    return fold

thick_ring_shell("Cloth", "UpperClothing/CoatBodice_L",
    bodice_rows_factory("L"), thick=COAT_T, sides=40,
    a0=0.10, a1=math.pi, rim_start=False, rim_end=True,
    fold=bodice_fold_factory("L"))
thick_ring_shell("Cloth", "UpperClothing/CoatBodice_R",
    bodice_rows_factory("R"), thick=COAT_T, sides=40,
    a0=math.pi, a1=2*math.pi - 0.06, rim_start=False, rim_end=True,
    fold=bodice_fold_factory("R"))

def thick_panel(mat, name, grid, thick):
    """Cloth solid from a point grid: front face, offset back face, rims."""
    rows, cols = len(grid), len(grid[0])
    pts = [p for row in grid for p in row]
    # back face: offset each point inward along its radial direction
    back = []
    for p in grid:
        brow = []
        for x, y, z in p:
            r = math.hypot(x, z)
            if r > 1e-9:
                k = (r - thick) / r
                brow.append((x*k, y, z*k))
            else:
                brow.append((x, y, z - thick))
        back.append(brow)
    pts += [p for row in back for p in row]
    fs = []
    for r in range(rows-1):
        for c in range(cols-1):
            i00=r*cols+c; i01=r*cols+c+1; i10=(r+1)*cols+c; i11=(r+1)*cols+c+1
            o=rows*cols
            fs.append((i00, i10, i11)); fs.append((i00, i11, i01))          # front
            fs.append((o+i00, o+i11, o+i10)); fs.append((o+i00, o+i01, o+i11))  # back
            fs.append((i01, i11, o+i11)); fs.append((i01, o+i11, o+i01))    # outer edge
    for r in range(rows-1):                                                 # inner edge rim
        i0=r*cols; i1=(r+1)*cols; o=rows*cols
        fs.append((i0, o+i0, o+i1)); fs.append((i0, o+i1, i1))
    for c in range(cols-1):                                                 # top/bottom rims
        i0=c; i1=c+1; o=rows*cols; b=(rows-1)*cols
        fs.append((i0, i1, o+i1)); fs.append((i0, o+i1, o+i0))
        fs.append((b+c, o+b+c, o+b+c+1)); fs.append((b+c, o+b+c+1, b+c+1))
    add_mesh(mat, name, pts, fs)



def coat_edge_point(y, panel, out=0.0):
    """Point exactly on the *displaced* bodice surface at a front edge."""
    if panel == "L":
        a = edge_left(y); fold = bodice_fold_factory("L")
    else:
        a = edge_right(y); fold = bodice_fold_factory("R")
    ri = min(range(len(BODICE_ROWS)), key=lambda i: abs(BODICE_ROWS[i][0] - y))
    dr, _, _ = fold(a, ri)
    p = coat_surf(a, y, out=0.0)
    return (p[0] * (1.0 + dr / max(math.hypot(p[0], p[2]), 1e-6)), p[1],
            p[2] * (1.0 + dr / max(math.hypot(p[0], p[2]), 1e-6)))

# Folded-back lapels: wide wine panels lying on the chest beside the open V,
# narrow at the collar and widening as they descend, ending mid-chest where
# the closure takes over. The left (over) lapel is broader by design.
for panel, label, spread_top, spread_bot, y0, y1 in (("L", "L", 0.15, 0.30, 1.22, 1.496),
                                                     ("R", "R", 0.13, 0.26, 1.24, 1.464)):
    sgn = 1.0 if panel == "L" else -1.0
    edge_fn = edge_left if panel == "L" else edge_right
    grid = []
    for k in range(9):
        t = k / 8.0
        y = y0 + (y1-y0)*t
        row = []
        for j in range(4):
            u = j / 3.0
            spread = spread_bot + (spread_top - spread_bot) * t   # wide chest, narrow collar
            a = sgn * (edge_fn(y) + spread * u)
            p = coat_surf(a, y, out=0.002 + 0.002*u)
            row.append(p)
        grid.append(row)
    thick_panel("ClothAccent", f"UpperClothing/Lapel_{label}", grid, thick=.006)

# Brass hook fasteners along the closed overlap below the lapels.
for hi, hy in enumerate((1.02, 1.10, 1.18, 1.26)):
    p = coat_edge_point(hy, "L", out=0.003)
    a = edge_left(hy)
    tdir = (math.cos(a), 0.0, -math.sin(a))
    tube("AgedBrass", f"Accessories/CoatHook_{hi+1}",
         [vadd(p, vmul(tdir, .010)), p, vadd(p, (0, -.011, 0))], [.0032]*3, 6, (0, 1, 0))
    stud = coat_edge_point(hy + 0.004, "R", out=0.0)
    ellipsoid("AgedBrass", f"Accessories/CoatHookStud_{hi+1}", stud, (.006, .006, .004), 8, 10)

# -------------------------------------------------------------------------
# Coat skirt: continues from under the belt to an asymmetric split hem,
# swept back below the waist, deep sway folds front-to-back.
# -------------------------------------------------------------------------
def skirt_rows(front_edge, span_a0, span_a1, hem_back_y, hem_front_lift, flare_rx, flare_rz):
    rows = []
    depths = [0.0, .07, .19, .34, .47, 1.00 - hem_back_y]
    n = len(depths)
    for i, d in enumerate(depths):
        t = i / (n - 1)
        y_back = 1.00 - d
        lift = hem_front_lift * t
        def row_fn(a, y_back=y_back, lift=lift, t=t, front_edge=front_edge,
                   flare_rx=flare_rx, flare_rz=flare_rz, span_a0=span_a0, span_a1=span_a1):
            ang = abs((front_edge - a) % (2*math.pi))
            if ang > math.pi: ang = 2*math.pi - ang
            f = clamp(1.0 - ang / math.pi, 0.0, 1.0) ** 1.15
            rx0, rz0 = 0.272, 0.168
            rx = rx0 + (flare_rx - rx0) * t + 0.030 * (1 - f) * t
            rz = rz0 + (flare_rz - rz0) * t
            y = y_back + lift * f
            zc = -0.095 * (1 - f) * t
            return (y, rx, rz, zc, span_a0, span_a1)
        rows.append(row_fn)
    return rows

def skirt_fold(front_edge, phase):
    def fold(a, ri):
        ang = (front_edge - a) % (2*math.pi)
        t = ri / 5.0
        dr = (0.004 + 0.017 * t) * math.sin((ang/math.pi) * 3*math.pi + phase)
        dy = -0.012 * t * math.sin((ang/math.pi) * 3*math.pi + phase + 1.4)
        return (dr, dy, 0.0)
    return fold

skL = skirt_rows(0.14, 0.14, math.pi, hem_back_y=0.40, hem_front_lift=0.20, flare_rx=0.345, flare_rz=0.235)
skR = skirt_rows(-0.10, math.pi, 2*math.pi - 0.10, hem_back_y=0.52, hem_front_lift=0.16, flare_rx=0.330, flare_rz=0.220)
thick_ring_shell("Cloth", "LowerClothing/CoatSkirt_L", skL, thick=COAT_T, sides=34,
    a0=-0.18, a1=math.pi, rim_start=True, rim_end=True, fold=skirt_fold(-0.18, 0.6))
thick_ring_shell("Cloth", "LowerClothing/CoatSkirt_R", skR, thick=COAT_T, sides=34,
    a0=math.pi, a1=2*math.pi + 0.12, rim_start=True, rim_end=True, fold=skirt_fold(0.12, 2.9))

# -------------------------------------------------------------------------
# Standing collar: wraps the back of the neck, open at the throat; wine
# outer shell with a contrasting inner facing, an offset throat tab and a
# miniature brass buckle (asymmetric throat closure).
# -------------------------------------------------------------------------
def collar_profile(y0, h_front, h_back, rx, rz, grow, zc=-0.008):
    def fn(a):
        ang = (a + math.pi) % (2*math.pi) - math.pi   # 0 at front centre
        back_w = 1.0 - clamp(abs(ang) / math.pi, 0.0, 1.0)
        h = h_front + (h_back - h_front) * (back_w ** 1.3)
        return (y0 + h, rx + grow * h, rz + grow * h, zc)
    return fn
def blended_rows(f0, f1, ts, gap_a=0.86):
    out = []
    for t in ts:
        def fn(a, t=t, f0=f0, f1=f1):
            p0, p1 = f0(a), f1(a)
            return (p0[0] + (p1[0]-p0[0])*t, p0[1] + (p1[1]-p0[1])*t,
                    p0[2] + (p1[2]-p0[2])*t, p0[3], gap_a + t*0.02, 2*math.pi - gap_a - t*0.02)
        out.append(fn)
    return out
COLLAR_A0 = 0.86
collar_base = collar_profile(1.486, 0.0, 0.0, .0945, .1005, .16)
collar_top  = collar_profile(1.486, .030, .078, .0945, .1005, .16)
thick_ring_shell("ClothAccent", "UpperClothing/CoatCollar",
    blended_rows(collar_base, collar_top, (0.0, 0.4, 0.75, 1.0)),
    thick=.006, sides=30, a0=COLLAR_A0, a1=2*math.pi-COLLAR_A0, rim_start=False, rim_end=True)
facing_base = collar_profile(1.486, 0.0, 0.0, .0885, .0945, .16)
facing_top  = collar_profile(1.486, .024, .064, .0885, .0945, .16)
thick_ring_shell("Cloth", "UpperClothing/CollarFacing",
    blended_rows(facing_base, facing_top, (0.0, 0.55, 1.0)),
    thick=.005, sides=30, a0=COLLAR_A0, a1=2*math.pi-COLLAR_A0, rim_start=False, rim_end=True)
collar_edge = []
for k in range(15):
    t = k / 14.0
    a = (COLLAR_A0 + (2*math.pi - 2*COLLAR_A0) * t)
    p = collar_top(a)
    collar_edge.append(shell_point(p[0] + 0.002, p[1] + 0.008, p[2] + 0.008, p[3], a, 0, 0, 0))
tube("BoneThread", "Accessories/CollarPiping", collar_edge, [.0032]*15, 6, (0, 1, 0))
# throat tab: bridges from the left collar edge across the gap, buckled.
tab_pts = []
for k in range(7):
    t = k / 6.0
    a = 0.92 - (0.92 + 0.92)*t     # left edge to right edge, through front
    tab_pts.append(shell_point(1.512 + 0.004*t, .101 - .002*t, .106 + .002*t, -0.008, a, 0, 0, 0))
strap_band("Leather", "Accessories/CollarTab", tab_pts, width=.016, thick=.003,
    normal_fn=lambda p, t: norm((p[0], 0.35, p[2])))
be = tab_pts[-1]
tube("AgedBrass", "Accessories/CollarBuckleSide", [(be[0]-.0055, be[1]-.0055, be[2]+.004), (be[0]-.0055, be[1]+.0055, be[2]+.004)], [.0024, .0024], 6, (0, 0, 1))
tube("AgedBrass", "Accessories/CollarBuckleSide2", [(be[0]+.0055, be[1]-.0055, be[2]+.004), (be[0]+.0055, be[1]+.0055, be[2]+.004)], [.0024, .0024], 6, (0, 0, 1))
tube("AgedBrass", "Accessories/CollarBuckleBar", [(be[0]-.0055, be[1]+.0055, be[2]+.004), (be[0]+.0055, be[1]+.0055, be[2]+.004)], [.0024, .0024], 6, (0, 1, 0))
# small bone stud on the right collar edge where the tab points
stud_p = shell_point(1.508, .102, .107, -0.008, -0.86, 0, 0, 0)
ellipsoid("BoneThread", "Accessories/CollarStud", stud_p, (.005, .005, .004), 8, 10)

# -------------------------------------------------------------------------
# Shoulder mantle: short asymmetric half-cape wrapping the BACK and both
# shoulders, open at the chest; deepest at the left-back, ripples along the
# hem, bound hem with bone piping and a brass chain clasp at its right edge.
# -------------------------------------------------------------------------
MANTLE_A0, MANTLE_A1 = 1.95, 2*math.pi - 1.95
def mantle_row_fn(t):
    def fn(a, t=t):
        s = (a - MANTLE_A0) / (MANTLE_A1 - MANTLE_A0)      # 0 right edge, 1 left edge
        back_w = math.sin(clamp(s, 0.0, 1.0) * math.pi)     # 0 at edges, 1 at back
        depth = 0.075 + 0.105 * (back_w ** 1.4) + 0.026 * gauss(a, 2.45, 0.8)
        y0, rx0, rz0 = 1.492, .310, .168
        y1, rx1, rz1 = y0 - depth, .334 + .014*back_w, .184 + .012*back_w
        return (y0 + (y1 - y0)*t, rx0 + (rx1 - rx0)*t, rz0 + (rz1 - rz0)*t, 0.0,
                MANTLE_A0 + 0.02*t, MANTLE_A1 - 0.02*t)
    return fn
def mantle_fold(a, ri):
    t = ri / 3.0
    return (0.0035*math.sin(7*a + .3)*t, -0.006*math.sin(5*a + 1.2)*t, 0.0)
mantle_rows = [mantle_row_fn(t) for t in (0.0, 0.45, 1.0)]
thick_ring_shell("Cloth", "UpperClothing/ShoulderMantle", mantle_rows,
    thick=.008, sides=34, a0=MANTLE_A0, a1=MANTLE_A1, rim_start=True, rim_end=True,
    fold=mantle_fold)
mantle_hem = []
for k in range(23):
    a = MANTLE_A0 + (MANTLE_A1 - MANTLE_A0)*k/22
    p = mantle_row_fn(1.0)(a)
    dr, dy, _ = mantle_fold(a, 3)
    mantle_hem.append(shell_point(p[0] + dy, p[1] + dr + .002, p[2] + dr + .002, 0.0, a, 0, 0, 0))
tube("BoneThread", "Accessories/MantleHemPiping", mantle_hem, [.0032]*23, 6, (0, 1, 0))
# small brass stud pair pins the mantle edge to the shoulder seam
for si, sa in enumerate((MANTLE_A0 + 0.05, 2*math.pi - MANTLE_A0 - 0.05)):
    p = mantle_row_fn(0.02)(sa)
    ellipsoid("AgedBrass", f"Accessories/MantleStud_{si+1}",
              (p[0]*1.0, p[1], p[2]), (.007, .007, .005), 8, 10)

# -------------------------------------------------------------------------
# Coat sleeves: gathered heads, elbow creases, bound cuffs with a folded
# wine cuff band; leather cuff strap and buckle on the right sleeve only,
# stitched elbow reinforcement patch on the left.
# -------------------------------------------------------------------------
def sleeve_fold_factory(side):
    def fold(i, s_idx, a):
        dr = 0.0
        dr += 0.005 * math.sin(3*a + 1.7*side) * max(0.0, 1.0 - i)      # gathered head
        dr -= 0.0065 * math.exp(-((i - 2.05)/0.55)**2) * (0.55 + 0.45*math.cos(2*a + side))  # elbow creases
        return dr
    return fold
for side, label in ((-1, "L"), (1, "R")):
    x = side
    thick_tube("Cloth", f"UpperClothing/CoatSleeve_{label}",
        [(x*.201, 1.462, -.008), (x*.296, 1.360, .008), (x*.352, 1.185, .020),
         (x*.383, 1.065, .032), (x*.389, 1.012, .036)],
        [(.097, .100), (.080, .084), (.069, .073), (.061, .064), (.058, .061)],
        sides=22, thick=.009, fold=sleeve_fold_factory(side), rim_start=True, rim_end=True)
    thick_tube("ClothAccent", f"UpperClothing/CuffFold_{label}",
        [(x*.389, 1.010, .036), (x*.392, .982, .038)],
        [(.061, .065), (.068, .073)], sides=20, thick=.005, rim_start=False, rim_end=True)
    if side < 0:  # left: stitched elbow reinforcement patch
        ellipsoid("ClothAccent", f"UpperClothing/ElbowPatch_{label}", (x*.416, 1.185, .022), (.012, .052, .048), 8, 12)
        patch_rim = [(x*.424, 1.185 + .043*math.cos(2*math.pi*k/8), .022 + .040*math.sin(2*math.pi*k/8)) for k in range(8)]
        stitch_dashes("BoneThread", f"Accessories/ElbowPatchStitch_{label}", patch_rim, 8, r=.0024, length=.010)
    else:         # right: cuff strap with small buckle
        ring_pts = [(x*.388 + .0645*math.cos(2*math.pi*k/10), 1.048, .034 + .058*math.sin(2*math.pi*k/10)) for k in range(10)]
        ring_pts.append(ring_pts[0])
        tube("Leather", f"Accessories/CuffStrap_{label}", ring_pts, [.0032]*11, 6, (0, 1, 0))
        bxc = x*.452
        tube("AgedBrass", f"Accessories/CuffBuckleFrame_{label}", [(bxc, 1.038, .034), (bxc, 1.058, .034)], [.0035, .0035], 8, (1, 0, 0))
        tube("AgedBrass", f"Accessories/CuffBuckleBar_{label}", [(bxc - x*.008, 1.038, .034), (bxc - x*.008, 1.058, .034)], [.003, .003], 8, (1, 0, 0))

# =========================================================================
# BELT: wide leather belt cinched over the coat, with a brass frame buckle,
# prong, two keepers, a punched hanging tip, a flapped field pouch on the
# right-back hip and a left hanger strap with D-ring and mourning tassel.
# =========================================================================
BELT_Y = 1.033
def belt_ring(a):
    rx, rz = coat_inner(1.03)
    rx += COAT_T + 0.0055; rz += COAT_T + 0.0055
    rmod = 1.0 + 0.006*math.sin(3*a + 1.0)
    y = BELT_Y + 0.004*math.cos(2*a - 0.5)
    return shell_point(y, rx*rmod, rz*rmod, 0.0, a, 0, 0, 0)

belt_pts = [belt_ring(2*math.pi*k/32) for k in range(32)]
belt_pts.append(belt_pts[0])
strap_band("Leather", "Accessories/Belt", belt_pts, width=.078, thick=.009,
    normal_fn=lambda p, t: norm((p[0], 0, p[2])), closed=True)
# buckle frame, prong and keepers just left of centre-front
BA = 0.30
buck_c = belt_ring(BA)
buck_out = norm((buck_c[0], 0, buck_c[2]))
buck_t = (-buck_out[2], 0.0, buck_out[0])
buck_z = vmul(buck_out, .012)
for sgn in (-1, 1):
    tube("AgedBrass", f"Accessories/BuckleSide_{sgn}",
         [vadd(vadd(buck_c, buck_z), vmul(buck_t, sgn*.024)),
          vadd(vadd(buck_c, buck_z), vadd(vmul(buck_t, sgn*.024), (0, .052, 0)))], [.005, .005], 8, (0, 1, 0))
for yy in (0.0, .052):
    tube("AgedBrass", f"Accessories/BuckleCross_{yy}",
         [vadd(vadd(buck_c, buck_z), (0, yy, 0)),
          (buck_c[0] + buck_z[0] + buck_t[0]*.024, BELT_Y + yy, buck_c[2] + buck_z[2] + buck_t[2]*.024)],
         [.005, .005], 8, (0, 1, 0))
tube("AgedBrass", "Accessories/BuckleProng",
     [(buck_c[0] + buck_out[0]*.012, BELT_Y, buck_c[2] + buck_out[2]*.012),
      (buck_c[0] + buck_out[0]*.012 + buck_t[0]*.020, BELT_Y + .002, buck_c[2] + buck_out[2]*.012 + buck_t[2]*.020)],
     [.0035, .0035], 6, (0, 1, 0))
for ki, ka in enumerate((0.56, 0.05)):
    keep_pts = [belt_ring(ka - 0.11 + 0.22*k/7) for k in range(8)]
    keep_pts = [vadd(p, vmul(norm((p[0], 0, p[2])), .001)) for p in keep_pts]
    strap_band("Leather", f"Accessories/BeltKeeper_{ki+1}", keep_pts, width=.086, thick=.012,
        normal_fn=lambda p, t: norm((p[0], 0, p[2])))
# hanging tip beyond the buckle with three punch holes and a brass eyelet
tip_pts = [vadd(belt_ring(BA - 0.05), (0, -.015, 0)),
           vadd(belt_ring(BA - 0.09), (0, -.055, 0)),
           vadd(belt_ring(BA - 0.12), (0, -.100, 0))]
tip_pts = [vadd(p, vmul(norm((p[0], 0, p[2])), .004)) for p in tip_pts]
strap_band("Leather", "Accessories/BeltTip", tip_pts, width=.050, thick=.007,
    normal_fn=lambda p, t: norm((p[0], 0, p[2])))
for hh in range(3):
    hp = lerp(tip_pts[0], tip_pts[2], 0.35 + 0.3*hh)
    ellipsoid("BootSole", f"Accessories/BeltHole_{hh+1}", vadd(hp, vmul(norm((hp[0], 0, hp[2])), .004)),
              (.0042, .0065, .0042), 6, 8)
eye_c = lerp(tip_pts[0], tip_pts[2], 0.30)
torus_arc("AgedBrass", "Accessories/BeltEyelet", vadd(eye_c, vmul(norm((eye_c[0], 0, eye_c[2])), .006)),
          .007, .0022, 6, 10, axis=(math.cos(BA - 0.07), 0, -math.sin(BA - 0.07)))

# field pouch on the right-back hip
PA = -2.25
pc = belt_ring(PA)
pout = norm((pc[0], 0, pc[2]))
ptan = (-pout[2], 0.0, pout[0])
pouch_c = vadd(pc, (0, -.055, 0))
rot = ((ptan[0], 0, ptan[2]), (0, 1, 0), (pout[0], 0, pout[2]))
ellipsoid("Leather", "Accessories/FieldPouch", vadd(pouch_c, vmul(pout, .022)), (.054, .064, .040), 10, 16, rotation=rot)
flap_pts = []
for k in range(6):
    t = k / 5.0
    ang = PA - 0.5 + 1.0*t
    bp = belt_ring(ang)
    flap_pts.append(vadd(vadd(bp, (0, -.075, 0)), vmul(norm((bp[0], 0, bp[2])), .030 + .012*math.sin(math.pi*t))))
strap_band("Leather", "Accessories/PouchFlap", flap_pts, width=.080, thick=.005,
    normal_fn=lambda p, t: norm((p[0], 0, p[2])))
stitch_dashes("BoneThread", "Accessories/PouchFlapStitch", flap_pts[1:5], 4, r=.0024, length=.011)
ellipsoid("AgedBrass", "Accessories/PouchStud", vadd(vadd(flap_pts[2], (0, -.018, 0)), vmul(norm((flap_pts[2][0], 0, flap_pts[2][2])), .008)), (.007, .007, .004), 8, 10)

# left hip hanger strap, D-ring and braided mourning tassel (original ornament)
HA = 2.35
hang_pts = [vadd(belt_ring(HA), (0, .012, 0)),
            vadd(belt_ring(HA + .06), (0, -.062, 0)),
            vadd(belt_ring(HA + .09), (0, -.125, 0))]
hang_pts = [vadd(p, vmul(norm((p[0], 0, p[2])), .004)) for p in hang_pts]
strap_band("Leather", "Accessories/HangerStrap", hang_pts, width=.020, thick=.004,
    normal_fn=lambda p, t: norm((p[0], 0, p[2])))
dring_c = vadd(hang_pts[2], vmul(norm((hang_pts[2][0], 0, hang_pts[2][2])), .010))
torus_arc("AgedBrass", "Accessories/HangerDRing", dring_c, .016, .0032, 6, 12,
          axis=(math.cos(HA + .09), 0, -math.sin(HA + .09)))
tas_dir = norm((dring_c[0], 0, dring_c[2]))
tassel_pts = [vadd(dring_c, vmul(tas_dir, .006)),
              vadd(dring_c, (vmul(tas_dir, .010)[0], -.045, vmul(tas_dir, .010)[2])),
              vadd(dring_c, (vmul(tas_dir, .014)[0], -.085, vmul(tas_dir, .014)[2]))]
tube("ClothAccent", "Accessories/MourningTassel", tassel_pts, [.012, .009, .002], 10, (0, 1, 0), depth_scale=.6)
tube("BoneThread", "Accessories/TasselWrap",
     [vadd(dring_c, (vmul(tas_dir, .007)[0], -.012, vmul(tas_dir, .007)[2])),
      vadd(dring_c, (vmul(tas_dir, .007)[0], -.020, vmul(tas_dir, .007)[2]))], [.0045, .0045], 6, (0, 1, 0))

# =========================================================================
# BALDRIC + HOLLOW COMPASS: a single stitched leather band from the right
# shoulder to the left hip, carrying the Wayfarer's original navigational
# instrument - two nested brass rings and a balanced needle on a dark face.
# =========================================================================
bald_pts = [coat_surf(-1.50, 1.452, out=.013),
            coat_surf(-1.10, 1.375, out=.012),
            coat_surf(-0.60, 1.300, out=.011),
            coat_surf(-0.12, 1.235, out=.011),
            coat_surf(0.42, 1.175, out=.011),
            coat_surf(0.95, 1.110, out=.011),
            coat_surf(1.35, 1.062, out=.013)]
def baldric_normal(p, t):
    wr = smoothstep(1.28, 1.42, p[1])
    radial = norm((p[0], 0, p[2]))
    return norm(vadd(vmul(radial, 1.0 - wr), vmul((0, 1, 0), wr)))
strap_band("Leather", "Accessories/Baldric", bald_pts, width=.034, thick=.0045, normal_fn=baldric_normal)
stitch_dashes("BoneThread", "Accessories/BaldricStitch", bald_pts[1:6], 8, r=.0026, length=.012)
# instrument drop strap
drop_top = bald_pts[3]
drop_bot = vadd(drop_top, (0, -.030, 0))
drop_bot = vadd(drop_bot, vmul(norm((drop_bot[0], 0, drop_bot[2])), .006))
strap_band("Leather", "Accessories/CompassDrop", [drop_top, vadd(lerp(drop_top, drop_bot, .5), vmul(norm((drop_top[0], 0, drop_top[2])), .004)), drop_bot],
           width=.014, thick=.003, normal_fn=lambda p, t: norm((p[0], 0, p[2])))
comp_c = vadd(drop_bot, (0, -.036, 0))
comp_c = vadd(comp_c, vmul(norm((comp_c[0], 0, comp_c[2])), .012))
comp_dir = norm((comp_c[0], 0.15, comp_c[2]))
comp_up = (0, 1, 0)
comp_t = norm(cross(comp_up, comp_dir))
comp_b = norm(cross(comp_dir, comp_t))
face_rot = ((comp_t[0], comp_t[1], comp_t[2]), (comp_b[0], comp_b[1], comp_b[2]), (comp_dir[0], comp_dir[1], comp_dir[2]))
ellipsoid("ClothAccent", "Accessories/CompassFace", comp_c, (.030, .030, .005), 10, 16, rotation=face_rot)
torus_arc("AgedBrass", "Accessories/CompassRingOuter", comp_c, .034, .0045, 8, 24, axis=comp_dir)
tilt_axis = norm(vadd(comp_dir, vmul(comp_t, .55)))
torus_arc("AgedBrass", "Accessories/CompassRingInner", comp_c, .022, .0032, 6, 18, axis=tilt_axis)
needle_a = vadd(comp_c, vmul(comp_t, -.017))
needle_b = vadd(vadd(comp_c, vmul(comp_t, .017)), vmul(comp_dir, .002))
tube("AgedBrass", "Accessories/CompassNeedle", [needle_a, comp_c, needle_b], [.002, .0026, .002], 6, (0, 1, 0))
ellipsoid("AgedBrass", "Accessories/CompassStud", vadd(comp_c, vmul(comp_dir, .008)), (.006, .006, .004), 8, 10)
torus_arc("AgedBrass", "Accessories/CompassLoop", vadd(drop_bot, (0, .004, 0)), .008, .002, 6, 10, axis=(1, 0, 0))


# Export material buffers in stable order. Normals are generated by Unity from smooth vertex rings.
obj_path=os.path.join(OUT,f"SM_Character_VeilboundWayfarer{SUFFIX}.obj")
mtl_path=os.path.join(OUT,f"SM_Character_VeilboundWayfarer{SUFFIX}.mtl")
with open(obj_path,"w",encoding="utf-8") as f:
    f.write(f"# Veilbound Wayfarer - original Vespershade protagonist (DETAIL={DETAIL:.2f}), 1 unit = 1 metre\n")
    f.write("# Layered wardrobe: every garment is a cloth solid (outer face, lining face, bound rims).\n")
    f.write("# Logical regions: body, head, hair, upper clothing, lower clothing, boots, gloves, accessories.\n")
    f.write("mtllib SM_Character_VeilboundWayfarer.mtl\no SM_Character_VeilboundWayfarer\ng VeilboundWayfarer\n")
    offset=0
    for mat in MATERIALS:
        for x,y,z in verts[mat]: f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        f.write(f"usemtl {mat}\n")
        for a,b,c in faces[mat]: f.write(f"f {a+offset} {b+offset} {c+offset}\n")
        offset += len(verts[mat])
with open(mtl_path,"w",encoding="utf-8") as f:
    f.write("# Original tonal palette; Unity prefab uses authored Standard materials.\n")
    for mat in MATERIALS:
        rgb,shine=colors[mat]
        f.write(f"newmtl {mat}\nKa 0.03 0.03 0.03\nKd {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f}\nKs {shine:.3f} {shine:.3f} {shine:.3f}\nNs 32\n\n")
print(f"Wrote {obj_path}: {sum(map(len,verts.values()))} vertices, {sum(map(len,faces.values()))} triangles, {len(MATERIALS)} material regions")
