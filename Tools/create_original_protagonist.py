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

High-value physical details included:
- Seams: spine seam, princess seams, shoulder seams, sleeve seams, trouser seams,
  vent pleats, welt ridges.
- Stitching: double saddle-stitch dashes along lapels, mantle hem, belt borders,
  pouch flap, baldric, toe cap, boot shaft spine, elbow patch, and glove cuffs.
- Buttons: aged brass crested greatcoat tail buttons, shoulder epaulette buttons,
  waistcoat buttons with thread stitches, sleeve cuff button trios, pocket flap buttons.
- Buckles: front belt frame buckle + prong, chest baldric adjustment buckle,
  rear baldric slider, dual boot instep & calf buckles, dual wrist cinch buckles,
  and high collar throat tab buckle.
- Straps: cinched leather waist belt, cross-body baldric, compass drop strap,
  boot instep & calf straps, wrist cinch straps, shoulder epaulettes, rear martingale.
- Cloth edges: bound hem piping along coat skirts, lapels, collar, turned-back cuffs,
  and mantle hem.
- Layered collars: 4-tier collar structure (shirt collar band, cravat & brooch,
  standing greatcoat collar with facing & throat tab, and mantle cowl drape).
- Small metal fasteners: brass frog clasps down torso, mantle shoulder pins,
  belt eyelets/grommets, D-rings, boot speed hooks/eyelets, cravat brooch, compass rings.
- Subtle leather panels: shoulder yoke tabs, elbow reinforcement patch,
  multi-piece boot vamp/counter/toe cap/shaft, pocket flaps, and reinforced gauntlets.
- Small decorative elements: gothic navigational astrolabe/compass, hip mourning tassel,
  watch fob chain, rear coat tail pleat buttons.

Running this script writes
Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj, its MTL and the
hand-rig sidecar SM_Character_VeilboundWayfarer.handrig.json (skeleton joints
plus the rigged hand/glove part ranges; see Tools/hand_rig.py).

Material order is also the order of submeshes assigned by Player.prefab;
the nine Unity materials are referenced by GUID and never change here.
"""
import math
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hand_rig

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
def lerp(a, b, t):
    if isinstance(a, (int, float)):
        return a * (1.0 - t) + b * t
    return tuple(a[i]*(1.0-t)+b[i]*t for i in range(len(a)))
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
# Solid-surface construction kit
# ---------------------------------------------------------------------------

def add_quad_strip(ptsA, ptsB, closed, flip=False):
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
    for r in range(rows - 1):
        for c in rng:
            c_next = (c + 1) % cols
            i00 = r * cols + c; i01 = r * cols + c_next
            i10 = (r + 1) * cols + c; i11 = (r + 1) * cols + c_next
            t1 = (i00, i10, i11); t2 = (i00, i11, i01)
            fs.append(t1[::-1] if flip else t1)
            fs.append(t2[::-1] if flip else t2)
    return fs

def shell_point(y, rx, rz, zc, a, dr, dy, dz):
    x = rx * math.sin(a)
    z = zc + rz * math.cos(a)
    r = math.hypot(x, z - zc)
    if r > 1e-9:
        ux, uz = x/r, (z-zc)/r
    else:
        ux, uz = 0.0, 1.0
    return (x + ux*dr, y + dy, z + uz*dr + dz)

def thick_ring_shell(mat, name, rows, thick, sides, a0, a1,
                     wrap=False, rim_start=True, rim_end=True, fold=None,
                     center=(0.0, 0.0, 0.0), radial_extra=None):
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
            a = ra0 + (ra1 - ra0) * (cj / float(sides))
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
            fs.append((i00, i10, i11)); fs.append((i00, i11, i01))
    for r in range(nr-1):
        for c in range(n_cols-1 if not wrap else n_cols):
            cn = (c+1) % n_cols
            i00 = off+r*n_cols+c; i01 = off+r*n_cols+cn
            i10 = off+(r+1)*n_cols+c; i11 = off+(r+1)*n_cols+cn
            fs.append((i00, i01, i11)); fs.append((i00, i11, i10))
    if not wrap:
        for r in range(nr-1):
            i0 = r*n_cols; i1 = (r+1)*n_cols
            fs.append((i0, off+i0, off+i1)); fs.append((i0, off+i1, i1))
        for r in range(nr-1):
            i0 = r*n_cols+(n_cols-1); i1 = (r+1)*n_cols+(n_cols-1)
            fs.append((i0, i1, off+i1)); fs.append((i0, off+i1, off+i0))
    if rim_start:
        for c in range(n_cols-1 if not wrap else n_cols):
            cn = (c+1) % n_cols
            fs.append((off+cn, off+c, c)); fs.append((off+cn, c, cn))
    if rim_end:
        base = (nr-1)*n_cols
        for c in range(n_cols-1 if not wrap else n_cols):
            cn = (c+1) % n_cols
            fs.append((base+c, off+base+c, off+base+cn)); fs.append((base+c, off+base+cn, base+cn))
    # Orientation: with this face pattern and shell_point's angular sweep,
    # the winding is outward only when the rows run downward (-Y); callers
    # whose rows advance upward (cuffs, waistcoat, collar) come out inside-out,
    # so flip those. (Verified by signed-volume + raycast audits.)
    y_first = rows[0](row_spans[0][0])[0]
    y_last = rows[-1](row_spans[-1][0])[0]
    if y_last > y_first:
        fs = [f[::-1] for f in fs]
    add_mesh(mat, name, pts, fs)

def tube_frames(centers, preferred=(1, 0, 0)):
    centers = [tuple(p) for p in centers]
    frames = []
    t0 = norm(vsub(centers[1], centers[0]))
    pref = norm(preferred)
    if abs(dot(pref, t0)) > 0.95:
        pref = (0.0, 1.0, 0.0) if abs(t0[1]) < 0.95 else (0.0, 0.0, 1.0)
    b1 = norm(cross(t0, pref))
    b2 = norm(cross(t0, b1))
    frames.append((t0, b1, b2))
    for i in range(1, len(centers)):
        prev_t, prev_b1, prev_b2 = frames[-1]
        t = norm(vsub(centers[i], centers[i-1]))
        axis = cross(prev_t, t)
        sine = math.sqrt(dot(axis, axis))
        if sine > 1e-6:
            axis = vmul(axis, 1.0/sine)
            angle = math.atan2(sine, dot(prev_t, t))
            def rot(v, ax=axis, a=angle):
                ca, sa = math.cos(a), math.sin(a)
                return vadd(vmul(v, ca), vadd(vmul(cross(ax, v), sa), vmul(ax, dot(ax, v)*(1.0-ca))))
            b1 = norm(rot(prev_b1))
            b2 = norm(rot(prev_b2))
        else:
            b1, b2 = prev_b1, prev_b2
        frames.append((t, b1, b2))
    return frames

def thick_tube(mat, name, points, radii, sides, thick, fold=None,
               rim_start=True, rim_end=True, inner_mat=None):
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
            if fold:
                dr = fold(i, s, a)
                dvec = norm(vadd(vmul(b1, rw*ca), vmul(b2, rd*sa)))
                po = vadd(po, vmul(dvec, dr))
            dvec = norm(vsub(po, c))
            pi_ = vsub(po, vmul(dvec, thick))
            ro.append(po); ri.append(pi_)
        rings_o.append(ro); rings_i.append(ri)
    pts = [p for row in rings_o for p in row] + [p for row in rings_i for p in row]
    off = n * sides
    fs = []
    for r in range(n - 1):
        for s in range(sides):
            sn = (s + 1) % sides
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
            fs.append((off+base+sn, off+base+s, base+s)); fs.append((base+sn, off+base+sn, base+s))
    add_mesh(mat, name, pts, fs)

def tube(mat, name, points, radii, sides=16, preferred=(1, 0, 0), depth_scale=1.0):
    sides = _segs(sides, 4)
    centers = [tuple(p) for p in points]
    if len(centers) < 2: return
    if isinstance(radii, (float, int)):
        radii = [radii] * len(centers)
    elif len(radii) != len(centers):
        radii = [radii[min(i, len(radii)-1)] for i in range(len(centers))]
    pts = []
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
        for s in range(sides):
            a = 2*math.pi*s/sides
            pts.append(vadd(c, vadd(vmul(b1, rw*math.cos(a)), vmul(b2, rd*math.sin(a)))))
    fs = []
    for r in range(len(centers)-1):
        for s in range(sides):
            a = r*sides+s; an = r*sides+(s+1) % sides
            b = (r+1)*sides+s; bn = (r+1)*sides+(s+1) % sides
            fs.extend(((a, an, b), (an, bn, b)))
    cap0_idx = len(pts)
    pts.append(centers[0])
    for s in range(sides):
        sn = (s+1) % sides
        fs.append((cap0_idx, sn, s))
    cap1_idx = len(pts)
    pts.append(centers[-1])
    base = (len(centers)-1)*sides
    for s in range(sides):
        sn = (s+1) % sides
        fs.append((cap1_idx, base+s, base+sn))
    add_mesh(mat, name, pts, fs)

def ellipsoid(mat, name, center, scale, rings=18, sides=28, rotation=None):
    rings = _segs(rings, 6); sides = _segs(sides, 6)
    rot = rotation or ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    # a left-handed rotation basis mirrors the surface and would invert the
    # winding; track it so faces can be flipped back below
    mirrored = (rot[0][0]*(rot[1][1]*rot[2][2]-rot[1][2]*rot[2][1])
                - rot[0][1]*(rot[1][0]*rot[2][2]-rot[1][2]*rot[2][0])
                + rot[0][2]*(rot[1][0]*rot[2][1]-rot[1][1]*rot[2][0])) < 0
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
    if mirrored:
        fs = [f[::-1] for f in fs]
    add_mesh(mat, name, pts, fs)

def ring_surface(mat, name, profile, sides=48, front_split=0.0):
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
    n = len(corners_per_station)
    fs = []
    rng = range(n) if closed else range(n-1)
    for i in rng:
        j = (i+1) % n
        b0, b1 = i*4, j*4
        for k in range(4):
            kn = (k+1) % 4
            fs.extend(((b1+kn, b1+k, b0+k), (b0+kn, b1+kn, b0+k)))
    if not closed and n > 0:
        fs.extend(((0, 3, 2), (0, 2, 1)))
        last = (n-1)*4
        fs.extend(((last, last+1, last+2), (last, last+2, last+3)))
    pts = [p for station in corners_per_station for p in station]
    add_mesh(mat, name, pts, fs)

def strap_band(mat, name, points, width, thick, normal_fn, closed=False):
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
            p = 2*math.pi*s/sides
            rr = math.cos(p)*r; hh = math.sin(p)*r
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
            fs.extend(((a, b, an), (an, b, bn)))   # flipped: outward normals
    add_mesh(mat, name, pts, fs)

def stitch_dashes(mat, name, path_pts, count, r=0.0024, length=0.011):
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

def double_stitch_band(mat, name, points, count, normal_fn, offset=0.007, r=0.0020, length=0.010):
    pts = [tuple(p) for p in points]
    n = len(pts)
    pts_left, pts_right = [], []
    for i, p in enumerate(pts):
        tangent = norm(vsub(pts[min(i+1, n-1)], pts[max(0, i-1)]))
        nrm = normal_fn(p, tangent)
        side = norm(cross(nrm, tangent))
        pts_left.append(vadd(vadd(p, vmul(nrm, 0.002)), vmul(side, offset)))
        pts_right.append(vadd(vadd(p, vmul(nrm, 0.002)), vmul(side, -offset)))
    stitch_dashes(mat, f"{name}_L", pts_left, count, r=r, length=length)
    stitch_dashes(mat, f"{name}_R", pts_right, count, r=r, length=length)

def button_disc(mat, name, center, normal, up=(0, 1, 0), radius=0.0085, thick=0.0035, thread_mat="BoneThread"):
    nrm = norm(normal)
    up_v = norm(vsub(up, vmul(nrm, dot(up, nrm)))) if abs(dot(up, nrm)) < 0.95 else norm(cross(nrm, (1, 0, 0)))
    side_v = cross(nrm, up_v)
    rot = ((side_v[0], up_v[0], nrm[0]),
           (side_v[1], up_v[1], nrm[1]),
           (side_v[2], up_v[2], nrm[2]))
    ellipsoid(mat, name, center, (radius, radius, thick), 8, 12, rotation=rot)
    torus_arc(mat, f"{name}_Rim", vadd(center, vmul(nrm, thick*0.3)), radius*0.85, radius*0.16, 6, 12, axis=nrm)
    if thread_mat:
        tc = vadd(center, vmul(nrm, thick*0.9))
        d = radius * 0.40
        tube(thread_mat, f"{name}_th1", [vsub(vsub(tc, vmul(up_v, d)), vmul(side_v, d)),
                                         vadd(vadd(tc, vmul(up_v, d)), vmul(side_v, d))], [.0018, .0018], 4, nrm)
        tube(thread_mat, f"{name}_th2", [vadd(vsub(tc, vmul(up_v, d)), vmul(side_v, d)),
                                         vsub(vadd(tc, vmul(up_v, d)), vmul(side_v, d))], [.0018, .0018], 4, nrm)

def buckle_frame(mat, name, center, normal, up=(0, 1, 0), width=0.026, height=0.034, bar_r=0.0028, has_prong=True):
    nrm = norm(normal)
    up_v = norm(vsub(up, vmul(nrm, dot(up, nrm)))) if abs(dot(up, nrm)) < 0.95 else norm(cross(nrm, (1, 0, 0)))
    side_v = cross(nrm, up_v)
    hw = width * 0.5
    hh = height * 0.5
    c_out = vadd(center, vmul(nrm, bar_r))
    tl = vadd(vadd(c_out, vmul(up_v, hh)), vmul(side_v, -hw))
    tr = vadd(vadd(c_out, vmul(up_v, hh)), vmul(side_v, hw))
    br = vadd(vsub(c_out, vmul(up_v, hh)), vmul(side_v, hw))
    bl = vadd(vsub(c_out, vmul(up_v, hh)), vmul(side_v, -hw))
    tube(mat, f"{name}_BarTop", [tl, tr], [bar_r, bar_r], 6, nrm)
    tube(mat, f"{name}_BarRight", [tr, br], [bar_r, bar_r], 6, nrm)
    tube(mat, f"{name}_BarBot", [br, bl], [bar_r, bar_r], 6, nrm)
    tube(mat, f"{name}_BarLeft", [bl, tl], [bar_r, bar_r], 6, nrm)
    mid_l = lerp(tl, bl, 0.5)
    mid_r = lerp(tr, br, 0.5)
    tube(mat, f"{name}_Spindle", [mid_l, mid_r], [bar_r*0.8, bar_r*0.8], 6, nrm)
    if has_prong:
        prong_base = lerp(mid_l, mid_r, 0.5)
        prong_tip = vadd(vadd(prong_base, vmul(up_v, hh*1.08)), vmul(nrm, bar_r*1.1))
        tube(mat, f"{name}_Prong", [prong_base, prong_tip], [bar_r*0.75, bar_r*0.5], 6, side_v)

def rivet_cap(mat, name, center, normal, radius=0.0050, height=0.0032):
    nrm = norm(normal)
    c = vadd(center, vmul(nrm, height*0.5))
    up = (0, 1, 0) if abs(nrm[1]) < 0.9 else (1, 0, 0)
    side = norm(cross(nrm, up))
    up_v = cross(side, nrm)
    rot = ((side[0], up_v[0], nrm[0]), (side[1], up_v[1], nrm[1]), (side[2], up_v[2], nrm[2]))
    ellipsoid(mat, name, c, (radius, radius, height), 6, 10, rotation=rot)

def welt_seam(mat, name, points, radius=0.0032):
    pts = [tuple(p) for p in points]
    tube(mat, name, pts, [radius]*len(pts), 6, (0, 1, 0))


# =========================================================================
# VESPERSHADE PROTAGONIST: ORIGINAL SCULPTED HEAD, FACE, EARS, EYES & HAIR
# =========================================================================

# 1. Sculpted Head, Face and Neck
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
                
                chin = g2(px, y, 0.0, 1.588, 0.018, 0.014) * 0.018
                chin_tub = (g2(px, y, 0.012, 1.588, 0.010, 0.012) + g2(px, y, -0.012, 1.588, 0.010, 0.012)) * 0.007
                mento = g2(px, y, 0.0, 1.606, 0.024, 0.007) * -0.0055
                
                l_lip = g2(px, y, 0.0, 1.618, 0.018, 0.007) * 0.011
                u_lip_mid = g2(px, y, 0.0, 1.632, 0.008, 0.006) * 0.009
                u_lip_peaks = (g2(px, y, 0.008, 1.633, 0.006, 0.006) + g2(px, y, -0.008, 1.633, 0.006, 0.006)) * 0.0095
                fissure = g2(px, y, 0.0, 1.625, 0.022, 0.0035) * -0.006
                corners = (g2(px, y, 0.022, 1.624, 0.006, 0.006) + g2(px, y, -0.022, 1.624, 0.006, 0.006)) * -0.006
                phil_trough = g2(px, y, 0.0, 1.644, 0.004, 0.007) * -0.0028
                phil_cols = (g2(px, y, 0.0045, 1.644, 0.0025, 0.007) + g2(px, y, -0.0045, 1.644, 0.0025, 0.007)) * 0.0025
                
                tip = g2(px, y, 0.0, 1.660, 0.011, 0.011) * 0.024
                bridge = g2(px, y, 0.0, 1.682, 0.007, 0.016) * 0.018
                hump = g2(px, y, 0.0, 1.674, 0.006, 0.009) * 0.004
                alar = (g2(px, y, 0.013, 1.652, 0.006, 0.008) + g2(px, y, -0.013, 1.652, 0.006, 0.008)) * 0.008
                nasion = g2(px, y, 0.0, 1.702, 0.010, 0.008) * -0.0055
                columella = g2(px, y, 0.0, 1.650, 0.005, 0.006) * 0.007
                
                zygoma = (g2(px, y, 0.052, 1.675, 0.018, 0.018) + g2(px, y, -0.052, 1.675, 0.018, 0.018)) * 0.011
                buccal = (g2(px, y, 0.038, 1.644, 0.016, 0.018) + g2(px, y, -0.038, 1.644, 0.016, 0.018)) * -0.006
                canine_fossa = (g2(px, y, 0.018, 1.656, 0.007, 0.012) + g2(px, y, -0.018, 1.656, 0.007, 0.012)) * -0.004
                
                socket = (g2(px, y, 0.033, 1.692, 0.013, 0.010) + g2(px, y, -0.033, 1.692, 0.013, 0.010)) * -0.012
                glabella = g2(px, y, 0.0, 1.714, 0.011, 0.010) * 0.007
                brow = (g2(px, y, 0.030, 1.716, 0.016, 0.009) + g2(px, y, -0.030, 1.716, 0.016, 0.009)) * 0.009
                boss = (g2(px, y, 0.026, 1.742, 0.018, 0.014) + g2(px, y, -0.026, 1.742, 0.018, 0.014)) * 0.004
                
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

# 3. Eyeballs Inset into Anatomical Orbits
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
add_mesh("Skin", "Head/Eyes", eye_pts, eye_polys)

# 4. Sculpted Arched Eyebrows
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
# BODY UNDER-LAYERS (Skin & minimal anatomy)
# =========================================================================

# Anatomically tapered torso (neckline to chest)
ring_surface("Skin", "Body/Torso", [(1.00, .18, .105, 0), (1.10, .205, .115, 0), (1.25, .25, .13, 0), (1.39, .29, .135, 0), (1.49, .255, .115, 0)], 36)
for side, label in ((-1, "L"), (1, "R")):
    x = side
    tube("Skin", f"Body/Forearm_{label}", [(x*.27, 1.27, .005), (x*.34, 1.10, .018), (x*.365, .97, .035), (x*.37, .88, .04)], [(.075, .075), (.065, .065), (.052, .052), (.047, .05)], 20, (1, 0, 0))


# =========================================================================
# TROUSERS: fitted wool with yoked waistband, knee creases, side seams
# =========================================================================

thick_ring_shell("Trouser", "LowerBody/TrouserYoke",
    [(lambda a, y=y, rx=rx, rz=rz, zc=zc: (y, rx, rz, zc)) for y, rx, rz, zc in
     ((1.005, .256, .152, 0.0), (.955, .247, .147, 0.0), (.905, .242, .144, 0.0))],
    thick=.007, sides=26, a0=0.0, a1=2*math.pi, wrap=True, rim_start=False, rim_end=False)
ellipsoid("Trouser", "LowerBody/Seat", (0, .895, 0), (.225, .130, .138), 12, 20)

def trouser_fold(i, s_idx, a):
    back = 0.5 + 0.5 * math.cos(a - 1.5 * math.pi)
    knee = -0.0055 * math.exp(-((i - 1.95)/0.45)**2) * back
    ankle = 0.0028 * math.sin(5*a) * math.exp(-((i - 3.5)/0.5)**2)
    return knee + ankle

for side, label in ((-1, "L"), (1, "R")):
    x = side
    leg_pts = [(x*.113, .915, -.002), (x*.117, .660, -.004), (x*.116, .485, .012), (x*.111, .365, .008), (x*.113, .285, .013)]
    thick_tube("Trouser", f"LowerBody/Leg_{label}", leg_pts,
        [(.102, .106), (.084, .088), (.066, .070), (.069, .073), (.061, .065)],
        sides=18, thick=.006, fold=trouser_fold, rim_start=True, rim_end=False)
    side_seam_pts = [(x*(.117 + .082), .880, -.002), (x*(.117 + .068), .660, -.004),
                     (x*(.116 + .054), .485, .012), (x*(.111 + .056), .365, .008), (x*(.113 + .052), .290, .013)]
    welt_seam("Trouser", f"LowerBody/SideSeam_{label}", side_seam_pts, radius=0.0032)
    stitch_dashes("BoneThread", f"LowerBody/SideSeamStitch_{label}", side_seam_pts, 8, r=0.0020, length=0.012)


# =========================================================================
# BOOTS: multi-part leather cavalry boots - continuous tall shaft,
# stitched vamp, toe cap with saddle stitching, heel counter,
# welted sole, brass heel plate, crossed instep straps + buckles,
# upper calf strap + buckle, rear pull tab & vertical back spine seam.
# =========================================================================

def boot_normal(side):
    def fn(p, tangent):
        return norm(((p[0] - side*.118)*1.25, 0.0, (p[2] - 0.05)*0.8))
    return fn

for side, label in ((-1, "L"), (1, "R")):
    x = side
    # 1. Welted Sole, Stacked Heel and Aged Brass Heel Plate Rim
    ellipsoid("BootSole", f"Boots/Sole_{label}", (x*.118, .038, .058), (.102, .026, .188), 10, 22)
    ellipsoid("BootSole", f"Boots/Heel_{label}", (x*.118, .045, -.065), (.068, .042, .072), 8, 16)
    torus_arc("AgedBrass", f"Boots/HeelPlate_{label}", (x*.118, .026, -.065), .058, .0032, 6, 12, axis=(0, 1, 0))
    welt_pts = [(x*.118 + .104*math.cos(2*math.pi*k/14), .068, .058 + .190*math.sin(2*math.pi*k/14)) for k in range(14)]
    welt_pts.append(welt_pts[0])
    tube("Leather", f"Boots/Welt_{label}", welt_pts, [.0055]*15, 8, (0, 1, 0))
    stitch_dashes("BoneThread", f"Boots/WeltStitch_{label}", welt_pts[:-1], 12, r=0.0018, length=0.010)

    # 2. Vamp & Stitched Toe Cap
    ellipsoid("Leather", f"Boots/Vamp_{label}", (x*.118, .108, .082), (.090, .068, .138), 12, 22)
    ellipsoid("Leather", f"Boots/ToeCap_{label}", (x*.118, .098, .168), (.086, .058, .072), 10, 18)
    cap_st1 = [(x*.118 + .078, .090, .146), (x*.118 + .058, .114, .192), (x*.118, .128, .210), (x*.118 - .058, .114, .192), (x*.118 - .078, .090, .146)]
    cap_st2 = [(x*.118 + .074, .096, .140), (x*.118 + .054, .120, .186), (x*.118, .134, .204), (x*.118 - .054, .120, .186), (x*.118 - .074, .096, .140)]
    stitch_dashes("BoneThread", f"Boots/ToeCapStitch1_{label}", cap_st1, 8, r=0.0022, length=0.010)
    stitch_dashes("BoneThread", f"Boots/ToeCapStitch2_{label}", cap_st2, 8, r=0.0020, length=0.009)

    # 3. Heel Counter
    thick_ring_shell("Leather", f"Boots/Counter_{label}",
        [(lambda a, y=y, rx=rx, rz=rz, zc=zc: (y, rx, rz, zc)) for y, rx, rz, zc in
         ((.070, .096, .098, -.010), (.140, .094, .096, -.008), (.210, .092, .094, -.006))],
        thick=.006, sides=16, a0=math.pi - 1.15, a1=math.pi + 1.15,
        rim_start=True, rim_end=False, center=(x*.118, 0, 0))
    counter_st = [(x*.118 + .088*math.sin(math.pi - 1.10 + 2.20*k/6), .208, -.006 + .092*math.cos(math.pi - 1.10 + 2.20*k/6)) for k in range(7)]
    stitch_dashes("BoneThread", f"Boots/CounterStitch_{label}", counter_st, 7, r=0.0022, length=0.010)

    # 4. Continuous Boot Shaft from ankle (y=0.125) to knee (y=0.440)
    def shaft_fold(i, s_idx, a, side=side):
        return .0045 * math.sin(4*a + .7) * math.exp(-((i - 1.2)/0.6)**2)
    shaft_pts = [(x*.118, .125, .016), (x*.117, .205, .012), (x*.116, .285, .008), (x*.116, .365, .005), (x*.117, .440, .002)]
    thick_tube("Leather", f"Boots/Shaft_{label}", shaft_pts,
        [(.082, .088), (.086, .092), (.096, .100), (.100, .106), (.106, .114)],
        sides=22, thick=.007, fold=shaft_fold, rim_start=False, rim_end=True)

    # 5. Rear Vertical Shaft Spine Seam + Saddle Stitching
    rear_seam_pts = [(x*.118, .140, -.074), (x*.117, .220, -.078), (x*.116, .300, -.086), (x*.116, .380, -.095), (x*.117, .442, -.106)]
    welt_seam("Leather", f"Boots/RearSeam_{label}", rear_seam_pts, radius=0.0035)
    stitch_dashes("BoneThread", f"Boots/RearSeamStitch_{label}", rear_seam_pts, 8, r=0.0022, length=0.012)

    # 6. Folded Top Cuff & Accent Lining
    thick_tube("ClothAccent", f"Boots/CuffFold_{label}",
        [(x*.117, .435, .004), (x*.118, .462, .002)],
        [(.112, .120), (.109, .118)], sides=20, thick=.005, rim_start=False, rim_end=True)
    thick_ring_shell("ClothAccent", f"Boots/CuffLining_{label}",
        [(lambda a, y=y, rx=rx, rz=rz, zc=zc: (y, rx, rz, zc)) for y, rx, rz, zc in
         ((.450, .101, .111, .002), (.458, .103, .113, .002))],
        thick=.003, sides=16, a0=0.0, a1=2*math.pi, wrap=True,
        rim_start=False, rim_end=True, center=(x*.118, 0, 0))

    # 7. Back Pull Tab + Brass Rivet
    strap_band("Leather", f"Boots/PullTab_{label}",
        [(x*.116, .450, -.102), (x*.116, .476, -.114), (x*.116, .450, -.124)],
        width=.016, thick=.0035, normal_fn=lambda p, t: (0, 0, -1.0))
    rivet_cap("AgedBrass", f"Boots/PullTabRivet_{label}", (x*.116, .452, -.112), (0, 0, -1.0), radius=0.004)

    # 8. Crossed Instep Straps + Buckles
    strap_band("Leather", f"Boots/InstepStrapA_{label}",
        [(x*.152, .155, .030), (x*.120, .128, .120), (x*.086, .150, .208)],
        width=.015, thick=.0032, normal_fn=boot_normal(side))
    strap_band("Leather", f"Boots/InstepStrapB_{label}",
        [(x*.090, .128, .028), (x*.122, .102, .118), (x*.154, .126, .205)],
        width=.015, thick=.0032, normal_fn=boot_normal(side))
    stitch_dashes("BoneThread", f"Boots/InstepStitchA_{label}",
        [(x*.150, .155, .032), (x*.120, .128, .120), (x*.088, .150, .206)], 5, r=0.0018, length=0.009)
    stitch_dashes("BoneThread", f"Boots/InstepStitchB_{label}",
        [(x*.092, .130, .030), (x*.122, .104, .118), (x*.152, .128, .203)], 5, r=0.0018, length=0.009)

    bx, by, bz = x*.158, .158, .026
    buckle_frame("AgedBrass", f"Boots/AnkleBuckle_{label}", (bx, by, bz), (x*1.0, 0.2, 0.2), up=(0, 1, 0), width=.020, height=.026, bar_r=.0026)

    # 9. Upper Calf Strap + Miniature Buckle
    calf_pts = [(x*.117 + .110*math.cos(2*math.pi*k/12), .412, .004 + .116*math.sin(2*math.pi*k/12)) for k in range(12)]
    calf_pts.append(calf_pts[0])
    strap_band("Leather", f"Boots/CalfStrap_{label}", calf_pts, width=.014, thick=.003, normal_fn=boot_normal(side), closed=True)
    cbx, cby, cbz = x*(.117 + .112), .412, .004
    buckle_frame("AgedBrass", f"Boots/CalfBuckle_{label}", (cbx, cby, cbz), (x*1.0, 0, 0), up=(0, 1, 0), width=.018, height=.022, bar_r=.0024)

    # 10. Brass Eyelets / Speed Hooks along the vamp
    for ei in range(3):
        ey = .112 + .022 * ei
        ez = .148 - .024 * ei
        rivet_cap("AgedBrass", f"Boots/EyeletL_{label}_{ei+1}", (x*.118 + x*.038, ey, ez), (x*0.8, 0.3, 0.5), radius=0.0035, height=0.0025)
        rivet_cap("AgedBrass", f"Boots/EyeletR_{label}_{ei+1}", (x*.118 - x*.038, ey, ez), (-x*0.8, 0.3, 0.5), radius=0.0035, height=0.0025)


# =========================================================================
# HANDS: anatomical base + fitted gloves, rigged for deformation.
#
# The hand is authored once in hand_rig.py's canonical local space (axes
# r = radial, d = distal, n = dorsal; wrist joint at the origin) and placed
# per side, so left and right are exact mirrors. The visible surface is the
# fitted leather glove; the anatomical skin hand underneath is built from the
# same profiles with a measured leather offset, so the glove provably follows
# the hand. Every hand/glove piece is registered in RIG_PARTS with a rig
# chain id; Tools/verify_hands.py uses the same module to skin, pose and
# check the hands (stand / walk / attack / dodge).
# =========================================================================

RIG_PARTS = []   # per-material vertex ranges: name/mat/start/end/side/chain

def _record_part(mat, name, side, chain, base):
    end = len(verts[mat])
    if end > base:
        RIG_PARTS.append({"name": name, "mat": mat, "start": base, "end": end,
                          "side": "R" if side > 0 else "L", "chain": chain})

def add_part(mat, name, points, polys, side, chain):
    """add_mesh + rig part record (points already in world space)."""
    base = len(verts[mat])
    add_mesh(mat, name, points, polys)
    _record_part(mat, name, side, chain, base)

def place_local(points, polys, side):
    """Canonical local (r,d,n) -> world. The left hand is an exact mirror
    (world-x flip), so face winding is reversed to keep normals outward."""
    w = [hand_rig.to_world(p, 1) for p in points]
    if side < 0:
        w = [(-px, py, pz) for (px, py, pz) in w]
        polys = [tuple(reversed(f)) for f in polys]
    return w, polys

def local_tube(centers, radii, sides, preferred=(1, 0, 0)):
    """tube() ring logic returning (points, polys) in local space."""
    sides = _segs(sides, 4)
    centers = [tuple(p) for p in centers]
    if isinstance(radii, (float, int)):
        radii = [radii] * len(centers)
    elif len(radii) != len(centers):
        radii = [radii[min(i, len(radii)-1)] for i in range(len(centers))]
    pts = []
    for i, c in enumerate(centers):
        tangent = norm(vsub(centers[min(i+1, len(centers)-1)], centers[max(0, i-1)]))
        hint = preferred
        b1 = vsub(hint, vmul(tangent, dot(hint, tangent)))
        if dot(b1, b1) < 1e-6:
            hint = (0, 0, 1) if abs(tangent[2]) < 0.8 else (0, 1, 0)
            b1 = vsub(hint, vmul(tangent, dot(hint, tangent)))
        b1 = norm(b1); b2 = norm(cross(tangent, b1))
        rad = radii[i]
        rw, rd = (rad, rad) if isinstance(rad, (float, int)) else rad
        for s in range(sides):
            a = 2*math.pi*s/sides
            pts.append(vadd(c, vadd(vmul(b1, rw*math.cos(a)), vmul(b2, rd*math.sin(a)))))
    fs = []
    for r in range(len(centers)-1):
        for s in range(sides):
            a = r*sides+s; an = r*sides+(s+1) % sides
            b = (r+1)*sides+s; bn = (r+1)*sides+(s+1) % sides
            fs.extend(((a, an, b), (an, bn, b)))
    cap0 = len(pts); pts.append(centers[0])
    for s in range(sides):
        fs.append((cap0, (s+1) % sides, s))
    cap1 = len(pts); pts.append(centers[-1])
    base = (len(centers)-1)*sides
    for s in range(sides):
        fs.append((cap1, base+s, base+(s+1) % sides))
    return pts, fs

def _chain_interp(chain, s, back_dir):
    """Point at arc length s along the chain (s<0 extends along back_dir)."""
    if s <= 0.0:
        return vadd(chain[0], vmul(back_dir, s))
    acc = 0.0
    for i in range(len(chain)-1):
        seg = vsub(chain[i+1], chain[i]); L = math.sqrt(dot(seg, seg))
        if acc + L >= s or i == len(chain)-2:
            t = clamp((s-acc)/L, 0.0, 1.0) if L > 1e-12 else 0.0
            return lerp(chain[i], chain[i+1], t)
        acc += L
    return chain[-1]

# Palm station rows (d, width scale, thickness scale) from the wrist cap to
# the webbing dome; scales are relative to the wrist half width/thickness.
PALM_ROWS = [
    (-0.0215, 0.62, 0.66), (-0.0120, 0.92, 0.94), (-0.0020, 1.00, 1.00),
    ( 0.0100, 0.99, 0.99), ( 0.0260, 1.06, 0.97), ( 0.0440, 1.18, 0.95),
    ( 0.0620, 1.30, 0.93), ( 0.0790, 1.40, 0.91), ( 0.0925, 1.44, 0.90),
    ( 0.1005, 1.30, 0.86), ( 0.1055, 0.80, 0.62), ( 0.1095, 0.28, 0.24),
]
PALM_POLE_P = (0.0000, -0.0270, 0.0012)   # wrist cap pole (hidden in the gauntlet)
PALM_POLE_D = (0.0015, 0.1125, 0.0020)    # webbing dome pole (between fingers)

def _palm_ring_raw(d, phi, row):
    """Skin-layer palm cross-section (r, n) at station d, angle phi
    (phi = 0 radial apex, pi/2 dorsal, pi ulnar, 3*pi/2 palmar)."""
    w = hand_rig.PALM_HALF_R * row[1]
    t = hand_rig.PALM_HALF_N * row[2]
    ca, sa = math.cos(phi), math.sin(phi)
    ulnar = 0.80 + 0.20*smoothstep(0.02, 0.09, d)   # trapezoid plan shape
    r = w * ca * (ulnar if ca < 0 else 1.0)
    n = t * sa
    dorsal = max(0.0, sa)
    palmar = max(0.0, -sa)
    if dorsal > 0.0:
        # metacarpal arch, knuckle row bumps, valleys between the knuckles
        n += 0.0008 * dorsal**1.5 * smoothstep(0.02, 0.07, d)
        bump = 0.0
        for di, dig in enumerate(hand_rig.DIGITS):
            bump += (0.0015, 0.0018, 0.0016, 0.0012)[di] * gauss(r, dig["mcp"][0], 0.011)
        n += bump * dorsal**1.6 * gauss(d, 0.094, 0.012)
        valley = (gauss(r, 0.0210, 0.0065) + gauss(r, 0.0005, 0.0065)
                  + gauss(r, -0.0190, 0.0065))
        n -= 0.0011 * valley * dorsal**1.6 * smoothstep(0.055, 0.08, d) \
             * (1.0 - smoothstep(0.098, 0.108, d))
    if palmar > 0.0:
        n -= 0.0012 * palmar**1.6 * smoothstep(0.03, 0.06, d)   # palmar cup
        n -= 0.0006 * palmar**2.0 * gauss(d, 0.006, 0.006)      # wrist crease
    # thenar (thumb base) and hypothenar eminences
    th = 0.0028 * gauss(d, 0.032, 0.024) * max(0.0, math.cos(phi + math.pi/4))**2.5
    r += 0.7071 * th; n -= 0.7071 * th
    hy = 0.0016 * gauss(d, 0.055, 0.030) * max(0.0, math.cos(phi + 3*math.pi/4))**2.5
    r -= 0.7071 * hy; n -= 0.7071 * hy
    return r, n

GLOVE_PALM_OFF = 0.0029     # leather thickness between hand and glove palm
GLOVE_DIGIT_OFF = 0.0026    # leather thickness of a finger stall

def _palm_ring(d, phi, row, glove):
    r, n = _palm_ring_raw(d, phi, row)
    if glove:
        # parallel offset of the cross-section curve -> true fitted shell
        dphi = (2*math.pi/_segs(18, 10)) * 0.6
        r1, n1 = _palm_ring_raw(d, phi + dphi, row)
        r0, n0 = _palm_ring_raw(d, phi - dphi, row)
        tr, tn = r1 - r0, n1 - n0
        ln = math.hypot(tr, tn)
        if ln > 1e-9:
            off = GLOVE_PALM_OFF
            if math.sin(phi) > 0.3 and 0.078 <= d <= 0.101:
                off += 0.0006                     # leather ease over knuckles
            r += (tn/ln) * off; n += (-tr/ln) * off
    return r, n

def build_palm_local(glove):
    """Palm solid: wrist cap pole + PALM_ROWS rings + webbing dome pole.
    Ring points are ordered (r, d, n) to match hand_rig's local axes."""
    sides = _segs(18, 10)
    rows = []
    for row in PALM_ROWS:
        d = row[0]
        rows.append([(lambda rn, d=d: (rn[0], d, rn[1]))(
                        _palm_ring(d, 2*math.pi*s/sides, row, glove))
                     for s in range(sides)])
    off = GLOVE_PALM_OFF if glove else 0.0
    pole_p = (PALM_POLE_P[0], PALM_POLE_P[1]-off, PALM_POLE_P[2])
    pole_d = (PALM_POLE_D[0], PALM_POLE_D[1]+0.8*off, PALM_POLE_D[2])
    pts = [pole_p] + [p for row in rows for p in row] + [pole_d]
    fs = []
    for s in range(sides):                       # proximal cap fan
        fs.append((0, 1+(s+1) % sides, 1+s))
    for ri in range(len(rows)-1):
        for s in range(sides):
            a = 1+ri*sides+s; an = 1+ri*sides+(s+1) % sides
            b = 1+(ri+1)*sides+s; bn = 1+(ri+1)*sides+(s+1) % sides
            fs.extend(((a, an, b), (an, bn, b)))
    base = 1+(len(rows)-1)*sides                 # distal cap fan
    for s in range(sides):
        fs.append((len(pts)-1, base+s, base+(s+1) % sides))
    fs = [f[::-1] for f in fs]   # rings advance +d; flip to keep normals out
    return pts, fs

def _tube_solid(centers, stations, base_radius, off, sides):
    """Shared digit solid: rings at stations with joint bulges (dorsal),
    creases (palmar) and a tapered pulp fingertip. Returns (points, polys)
    in the digit's local space."""
    # preferred = -n so the parallel-transport frames give b2 ~ +n (dorsal)
    # and b1 ~ -r: knuckle bulges land dorsally, creases palmarly.
    frames = tube_frames(centers, preferred=(0, 0, -1))
    pts = []
    for i, c in enumerate(centers):
        _, b1, b2 = frames[i]
        ws, ts, bulp, crease, pulp = stations[i][1:]
        rw = base_radius[0]*ws + off
        rn = base_radius[1]*ts + off
        for s in range(sides):
            phi = 2*math.pi*s/sides
            p = vadd(c, vadd(vmul(b1, rw*math.cos(phi)), vmul(b2, rn*math.sin(phi))))
            if bulp:
                p = vadd(p, vmul(b2, bulp * max(0.0, math.sin(phi))**1.5))
            if crease:
                p = vsub(p, vmul(b2, crease * max(0.0, -math.sin(phi))**1.5))
            if pulp:
                p = vsub(p, vmul(b2, pulp * 0.0009 * max(0.0, -math.sin(phi))**2.0))
            pts.append(p)
    fs = []
    for r in range(len(centers)-1):
        for s in range(sides):
            a = r*sides+s; an = r*sides+(s+1) % sides
            b = (r+1)*sides+s; bn = (r+1)*sides+(s+1) % sides
            fs.extend(((a, an, b), (an, bn, b)))
    cap0 = len(pts)
    # Root cap: flat disc for the skin; for the glove stall (off>0) the apex
    # sits 'off' behind the root plane so the skin disc stays strictly inside.
    back = norm(vsub(centers[1], centers[0]))
    pts.append(vsub(centers[0], vmul(back, off)))
    for s in range(sides):
        fs.append((cap0, (s+1) % sides, s))
    return pts, fs, frames

def _tip_cap(pts, fs, chain, frames, sides, pull, extra):
    tipdir = norm(vsub(chain[-1], chain[-2]))
    cap = len(pts)
    pts.append(vsub(vadd(chain[-1], vmul(tipdir, extra)), vmul(frames[-1][2], pull)))
    # pts layout here: rings (n*sides) + root pole, so the last ring starts at
    # len(pts) - sides - 1  (root pole is the final vertex before the cap).
    base = len(pts) - sides - 2
    for s in range(sides):
        fs.append((cap, base+s, base+(s+1) % sides))
    return pts, fs

def build_digit_local(dig, glove):
    """One finger: root flare buried in the palm, three phalanges, MCP/PIP/DIP
    knuckle bulges + palmar creases, tapered fingertip with pulp."""
    sides = _segs(8, 6)
    chain = dig["chain"]
    l1, l2, l3 = dig["segs"]
    ltip = l1 + l2 + l3
    off = GLOVE_DIGIT_OFF if glove else 0.0
    bm, bp, bd = hand_rig.KNUCKLE_BUMP
    cm, cp, cd = hand_rig.CREASE_DIP
    if glove:
        bm += 0.0004; bp += 0.0004; bd += 0.0004
        cm *= 0.7; cp *= 0.7; cd *= 0.7
    stations = [  # (arc length, width x, thickness x, bulge, crease, pulp)
        # Monotonic in arc length: root flare in the palm, knuckle bumps just
        # past each joint (dorsal) with matching palmar creases, then a smooth
        # distal taper with pulp flatten into the tip ring.
        (-0.0200,        1.16, 1.14, 0.0, 0.0, 0.0),
        (-0.0090,        1.09, 1.07, 0.0, 0.0, 0.0),
        (0.0040,         1.00, 1.00, bm,  cm, 0.0),
        (l1-0.0060,      1.02, 1.01, 0.0, 0.0, 0.0),
        (l1+0.0050,      0.97, 0.96, bp,  cp, 0.0),
        (l1+l2-0.0070,   0.945, 0.94, 0.0, 0.0, 0.0),
        (l1+l2+0.0050,   0.91, 0.90, bd,  cd, 0.0),
        (l1+l2+0.5*l3,   0.85, 0.83, 0.0, 0.0, 0.12),
        (ltip-0.0060,    0.79, 0.76, 0.0, 0.0, 0.35),
        (ltip-0.0015,    0.74, 0.70, 0.0, 0.0, 0.55),
    ]
    centers = [_chain_interp(chain, s[0], dig["prox"]) for s in stations]
    pts, fs, frames = _tube_solid(centers, stations, dig["radius"], off, sides)
    return _tip_cap(pts, fs, chain, frames, sides, 0.0008, 0.0035 + off)

def build_thumb_local(glove):
    """Thumb: saddle root blended into the thenar, two phalanges, tip."""
    sides = _segs(8, 6)
    chain = hand_rig.local_anatomy()["thumb"]
    cmc, mcp, ip, tip = chain
    l1 = math.dist(cmc, mcp); l2 = math.dist(mcp, ip); l3 = math.dist(ip, tip)
    off = GLOVE_DIGIT_OFF if glove else 0.0
    bm, bp = 0.0012, 0.0008
    cm_, cp_ = 0.0010, 0.0006
    if glove:
        bm += 0.0004; bp += 0.0004; cm_ *= 0.7; cp_ *= 0.7
    # Root stations (s<0) extend BACK from the CMC into the thenar: the
    # _chain_interp convention is chain[0] + dir*s with s negative, so the
    # direction must point FORWARD along the chain (toward the MCP).
    fwd = norm(vsub(mcp, cmc))
    stations = [  # monotonic: saddle root, MCP/IP knuckles, pulp taper
        (-0.0180,          1.20, 1.18, 0.0, 0.0, 0.0),
        (-0.0080,          1.12, 1.10, 0.0, 0.0, 0.0),
        (l1+0.0040,        1.02, 1.01, bm,  cm_, 0.0),
        (l1+l2-0.0070,     1.00, 0.99, 0.0, 0.0, 0.0),
        (l1+l2+0.0050,     0.97, 0.96, bp,  cp_, 0.0),
        (l1+l2+0.5*l3,     0.90, 0.88, 0.0, 0.0, 0.15),
        (l1+l2+l3-0.0100,  0.84, 0.82, 0.0, 0.0, 0.30),
        (l1+l2+l3-0.0040,  0.79, 0.76, 0.0, 0.0, 0.45),
        (l1+l2+l3-0.0015,  0.74, 0.71, 0.0, 0.0, 0.55),
    ]
    centers = [_chain_interp(chain, s[0], fwd) for s in stations]
    pts, fs, frames = _tube_solid(centers, stations, hand_rig.THUMB["radius"], off, sides)
    return _tip_cap(pts, fs, chain, frames, sides, 0.0008, 0.0032 + off)

def _knuckle_surface_n(dig):
    """Dorsal n height of a gloved knuckle apex (guard/ridge/seam riding)."""
    return (dig["mcp_n"] + dig["radius"][1] + GLOVE_DIGIT_OFF
            + hand_rig.KNUCKLE_BUMP[0] + 0.0004)

for side, label in ((-1, "L"), (1, "R")):
    x = side
    ana = hand_rig.local_anatomy()

    # --- sleeve-side cuffs (ivory shirt cuff + turned-back coat cuff) ---
    thick_ring_shell("BoneThread", f"UpperClothing/ShirtCuff_{label}",
        [(lambda a, y=y, rx=rx, rz=rz: (y, rx, rz, .037)) for y, rx, rz in
         ((.962, .051, .048), (.986, .054, .051))],
        thick=.003, sides=16, a0=0.0, a1=2*math.pi, wrap=True,
        rim_start=False, rim_end=True, center=(x*.390, 0, 0))
    button_disc("BoneThread", f"UpperClothing/ShirtCuffButton_{label}", (x*.446, .974, .037), (x*1.0, 0, 0), radius=.0045, thick=.002, thread_mat=None)

    thick_tube("ClothAccent", f"UpperClothing/CuffFold_{label}",
        [(x*.389, 1.012, .036), (x*.392, .982, .038)],
        [(.061, .065), (.068, .073)], sides=20, thick=.005, rim_start=False, rim_end=True)
    for bi in range(3):
        by = 1.025 - bi * 0.018
        bx = x * (.389 + .068)
        bz = .036
        button_disc("AgedBrass", f"UpperClothing/CuffButton_{label}_{bi+1}", (bx, by, bz), (x*1.0, 0, 0), radius=.0048, thick=.0025, thread_mat=None)

    # --- flared leather gauntlet over the coat cuff (rigid on the wrist) ---
    base = len(verts["Leather"])
    thick_tube("Leather", f"Accessories/Gauntlet_{label}",
        [(x*.387, 1.062, .035), (x*.385, 1.034, .038), (x*.384, 1.008, .040)],
        [(.072, .076), (.0695, .0735), (.0675, .0715)],
        sides=20, thick=.005, rim_start=True, rim_end=True)
    _record_part("Leather", f"Hand/Glove/Gauntlet_{label}", side, "cuff", base)
    base = len(verts["BoneThread"])
    g_rim = [(x*.387 + .0718*math.cos(2*math.pi*k/10), 1.058, .035 + .0758*math.sin(2*math.pi*k/10)) for k in range(10)]
    stitch_dashes("BoneThread", f"Accessories/GauntletStitch_{label}", g_rim, 8, r=0.0020, length=0.010)
    _record_part("BoneThread", f"Hand/Glove/GauntletStitch_{label}", side, "cuff", base)

    # --- anatomical skin hand (base layer under the glove) ---
    pts, polys = build_palm_local(False)
    wpts, wpolys = place_local(pts, polys, side)
    add_part("Skin", f"Hand/Skin/Palm_{label}", wpts, wpolys, side, "palm")
    for di, dig in enumerate(ana["digits"]):
        pts, polys = build_digit_local(dig, False)
        wpts, wpolys = place_local(pts, polys, side)
        add_part("Skin", f"Hand/Skin/{dig['key']}_{label}", wpts, wpolys, side, f"digit{di}")
    pts, polys = build_thumb_local(False)
    wpts, wpolys = place_local(pts, polys, side)
    add_part("Skin", f"Hand/Skin/Thumb_{label}", wpts, wpolys, side, "thumb")

    # --- fitted glove: palm stall, individual finger stalls, thumb stall ---
    pts, polys = build_palm_local(True)
    wpts, wpolys = place_local(pts, polys, side)
    add_part("Leather", f"Hand/Glove/PalmStall_{label}", wpts, wpolys, side, "palm")
    for di, dig in enumerate(ana["digits"]):
        pts, polys = build_digit_local(dig, True)
        wpts, wpolys = place_local(pts, polys, side)
        add_part("Leather", f"Hand/Glove/{dig['key']}Stall_{label}", wpts, wpolys, side, f"digit{di}")
    pts, polys = build_thumb_local(True)
    wpts, wpolys = place_local(pts, polys, side)
    add_part("Leather", f"Hand/Glove/ThumbStall_{label}", wpts, wpolys, side, "thumb")

    # glove wrist bridge: flares up inside the gauntlet, seals the cuff gap
    fr = hand_rig.frame(side)
    Cw, Dw = fr["wrist"], fr["D"]
    base = len(verts["Leather"])
    thick_tube("Leather", f"Accessories/GloveBridge_{label}",
        [vsub(Cw, vmul(Dw, u)) for u in (.006, .018, .032, .048)],
        [(.0345, .0245), (.040, .029), (.047, .035), (.053, .0415)],
        sides=16, thick=.0025, rim_start=True, rim_end=True)
    _record_part("Leather", f"Hand/Glove/Bridge_{label}", side, "bridge", base)

    # dorsal seams along every stall (bulge-aware, so they ride the knuckles)
    for di, dig in enumerate(ana["digits"]):
        chain = dig["chain"]
        l1, l2, l3 = dig["segs"]; ltip = l1+l2+l3
        nfr = tube_frames(chain, preferred=(0, 0, -1))
        bulges = [hand_rig.KNUCKLE_BUMP[0]+0.0004, hand_rig.KNUCKLE_BUMP[1]+0.0004,
                  hand_rig.KNUCKLE_BUMP[2]+0.0004, 0.0]
        nodes_s = [0.0, l1, l1+l2, ltip]
        def seam_pt(s, chain=chain, nfr=nfr, bulges=bulges, nodes_s=nodes_s, dig=dig, ltip=ltip):
            i = max(0, [k for k in range(3) if nodes_s[k] <= s][-1])
            u = clamp((s-nodes_s[i])/max(nodes_s[i+1]-nodes_s[i], 1e-9), 0.0, 1.0)
            c = lerp(chain[i], chain[i+1], u)
            b2 = norm(lerp(nfr[i][2], nfr[i+1][2], u))
            bl = lerp(bulges[i], bulges[i+1], u)
            rn = dig["radius"][1]*(0.95 - 0.18*s/ltip) + GLOVE_DIGIT_OFF
            return vadd(c, vmul(b2, rn + bl + 0.0005))
        pts, polys = local_tube([seam_pt(s) for s in
                                 (l1+.006, l1+l2*.55, l1+l2+.004, ltip-.006)],
                                [.0011, .0011, .0011, .0011], 5)
        wpts, wpolys = place_local(pts, polys, side)
        add_part("Leather", f"Hand/Glove/{dig['key']}Seam_{label}", wpts, wpolys, side, f"digit{di}")
    tchain = ana["thumb"]
    tl = [math.dist(tchain[0], tchain[1]), math.dist(tchain[1], tchain[2]),
          math.dist(tchain[2], tchain[3])]
    tnfr = tube_frames(tchain, preferred=(0, 0, -1))
    tbul = [0.0, hand_rig.KNUCKLE_BUMP[0]+0.0004, hand_rig.KNUCKLE_BUMP[1]+0.0004, 0.0]
    tnodes = [0.0, tl[0], tl[0]+tl[1], tl[0]+tl[1]+tl[2]]
    def tseam_pt(s):
        i = max(0, [k for k in range(3) if tnodes[k] <= s][-1])
        u = clamp((s-tnodes[i])/max(tnodes[i+1]-tnodes[i], 1e-9), 0.0, 1.0)
        c = lerp(tchain[i], tchain[i+1], u)
        b2 = norm(lerp(tnfr[i][2], tnfr[i+1][2], u))
        bl = lerp(tbul[i], tbul[i+1], u)
        rn = hand_rig.THUMB["radius"][1]*0.95 + GLOVE_DIGIT_OFF
        return vadd(c, vmul(b2, rn + bl + 0.0005))
    pts, polys = local_tube([tseam_pt(s) for s in
                             (tl[0]+.006, tl[0]+tl[1]*.6, tl[0]+tl[1]+tl[2]-.007)],
                            [.0011, .0011, .0011], 5)
    wpts, wpolys = place_local(pts, polys, side)
    add_part("Leather", f"Hand/Glove/ThumbSeam_{label}", wpts, wpolys, side, "thumb")

    # webbing gussets: leather Vs filling the valley between adjacent stalls
    for wi in range(3):
        d0, d1 = ana["digits"][wi], ana["digits"][wi+1]
        m0, m1 = d0["chain"][0], d1["chain"][0]
        bpt = ((m0[0]+m1[0])*0.5, (m0[1]+m1[1])*0.5 - 0.004, 0.0025)
        bdir = norm(vadd(vmul(d0["prox"], 0.5), vmul(d1["prox"], 0.5)))
        pts, polys = local_tube(
            [vadd(bpt, vmul(bdir, u)) for u in (0.006, 0.013, 0.020)],
            [(.0040, .0017), (.0036, .0015), (.0032, .0013)], 6,
            preferred=(0, 0, -1))
        wpts, wpolys = place_local(pts, polys, side)
        add_part("Leather", f"Hand/Glove/Web{wi}_{label}", wpts, wpolys, side, f"web{wi}")
    # thumb web (thenar span between the thumb metacarpal and the index base)
    iw = ana["digits"][0]["chain"][0]
    tbpt = ((hand_rig.THUMB["mcp"][0] + iw[0])*0.5,
            (hand_rig.THUMB["mcp"][1] + iw[1])*0.5 - 0.003, 0.0010)
    tbdir = norm((0.62, 0.76, -0.18))
    pts, polys = local_tube(
        [vadd(tbpt, vmul(tbdir, u)) for u in (0.004, 0.011, 0.018)],
        [(.0046, .0020), (.0041, .0018), (.0036, .0015)], 6,
        preferred=(0, 0, -1))
    wpts, wpolys = place_local(pts, polys, side)
    add_part("Leather", f"Hand/Glove/ThumbWeb_{label}", wpts, wpolys, side, "webT")

    # reinforced knuckle guard riding the MCP bumps, one ridge per knuckle
    krow = [(dig["chain"][0][0], dig["chain"][0][1], _knuckle_surface_n(dig))
            for dig in [ana["digits"][3], ana["digits"][2], ana["digits"][1], ana["digits"][0]]]
    guard_local = [(krow[0][0]-0.0075, krow[0][1]-0.0010, krow[0][2]-0.0026)]
    for k in range(4):
        rr, dd, nn = krow[k]
        guard_local.append((rr, dd+0.0015, nn+0.0009))
        if k < 3:
            rr2, dd2, nn2 = krow[k+1]
            guard_local.append(((rr+rr2)*0.5, (dd+dd2)*0.5+0.0012, (nn+nn2)*0.5-0.0012))
    guard_local.append((krow[3][0]+0.0075, krow[3][1]-0.0010, krow[3][2]-0.0026))
    guard_pts = [hand_rig.to_world(p, side) for p in guard_local]
    knuckle_worlds = [hand_rig.to_world(dig["chain"][0], side) for dig in ana["digits"]]
    def guard_normal(p, t, side=side):
        loc = hand_rig.to_local(p, side)
        best = min(ana["digits"], key=lambda d: abs(d["chain"][0][0]-loc[0]))
        m = hand_rig.to_world(best["chain"][0], side)
        return norm(vsub(p, m))
    base = len(verts["Leather"])
    strap_band("Leather", f"Accessories/KnuckleGuard_{label}", guard_pts,
        width=.016, thick=.0028, normal_fn=guard_normal, closed=False)
    _record_part("Leather", f"Hand/Glove/KnuckleGuard_{label}", side, "guard", base)
    for edge in (-0.0072, 0.0072):
        stitch_path = [hand_rig.to_world((p[0], p[1]+edge, p[2]+0.0015), side)
                       for p in guard_local]
        base = len(verts["BoneThread"])
        stitch_dashes("BoneThread", f"Accessories/KnuckleGuardStitch_{label}_{edge:+.4f}",
                      stitch_path, 7, r=0.0016, length=0.007)
        _record_part("BoneThread", f"Hand/Glove/KnuckleGuardStitch_{label}", side, "guard", base)
    for dig in ana["digits"]:
        mp = dig["chain"][0]
        nn = _knuckle_surface_n(dig) + 0.0009 + 0.0014 + 0.0010
        pts, polys = local_tube(
            [(mp[0]-0.0060, mp[1]+0.0015, nn), (mp[0], mp[1]+0.0015, nn+0.0004),
             (mp[0]+0.0060, mp[1]+0.0015, nn)],
            [.0023, .0026, .0023], 5)
        wpts, wpolys = place_local(pts, polys, side)
        add_part("Leather", f"Hand/Glove/KnuckleRidge_{dig['key']}_{label}",
                 wpts, wpolys, side, "guard")

    # wrist cinch strap over the gauntlet: buckle right, brass button left
    base = len(verts["Leather"])
    ring_pts = [(x*.3847 + .0693*math.cos(2*math.pi*k/12), 1.030, .0383 + .0733*math.sin(2*math.pi*k/12)*0.9) for k in range(12)]
    ring_pts.append(ring_pts[0])
    strap_band("Leather", f"Accessories/WristStrap_{label}", ring_pts, width=.014, thick=.003,
        normal_fn=lambda p, t: norm((p[0]-x*.3847, 0, p[2]-.0383)), closed=True)
    _record_part("Leather", f"Hand/Glove/WristStrap_{label}", side, "cuff", base)
    if side > 0:
        base = len(verts["AgedBrass"])
        buckle_frame("AgedBrass", f"Accessories/WristBuckle_{label}", (x*(.3847+.0705), 1.030, .0383),
                     (x*1.0, 0, 0), up=(0, 1, 0), width=.018, height=.022, bar_r=.0022)
        _record_part("AgedBrass", f"Hand/Glove/WristBuckle_{label}", side, "cuff", base)
    else:
        base = len(verts["AgedBrass"])
        button_disc("AgedBrass", f"Accessories/WristButton_{label}", (x*(.3847+.0705), 1.030, .0383),
                    (x*1.0, 0, 0), radius=.0052, thick=.0028, thread_mat=None)
        _record_part("AgedBrass", f"Hand/Glove/WristButton_{label}", side, "cuff", base)


# =========================================================================
# WAISTCOAT & SHIRT & CRAVAT: fitted wine wool vest, vertical seams,
# bone buttons with thread stitches, pocket welts with brass watch fob chain,
# ivory standing shirt collar band, wrapped cravat with aged brass pin brooch.
# =========================================================================

WC_ROWS = [(0.985, .250, .147, -0.12, 0.06), (1.05, .238, .141, -0.13, 0.07),
           (1.13, .230, .138, -0.16, 0.10), (1.21, .238, .141, -0.24, 0.18),
           (1.29, .262, .146, -0.40, 0.34), (1.37, .300, .152, -0.50, 0.44),
           (1.43, .306, .146, -0.54, 0.48), (1.468, .292, .128, -0.56, 0.50)]

def wc_rows():
    return [(lambda a, y=y, rx=rx, rz=rz, a0=a0, a1=a1: (y, rx, rz, 0.0, a0, a1))
            for y, rx, rz, a0, a1 in WC_ROWS]

def wc_fold(a, ri):
    y = WC_ROWS[ri][0]
    return (0.0028*math.sin(7*a + 1.0)*smoothstep(1.05, 1.15, y)*(1.0 - smoothstep(1.30, 1.40, y)), 0.0, 0.0)

thick_ring_shell("ClothAccent", "UpperClothing/Waistcoat", wc_rows(),
    thick=.008, sides=20, a0=-0.70, a1=0.66, rim_start=True, rim_end=True, fold=wc_fold)

wc_y = [r[0] for r in WC_ROWS]; wc_rx = [r[1] for r in WC_ROWS]; wc_rz = [r[2] for r in WC_ROWS]
for i in range(5):
    y = 1.38 - .082*i
    ry = interp_val(y, wc_y, wc_rx); rzv = interp_val(y, wc_y, wc_rz)
    p = shell_point(y, ry, rzv, 0.0, -0.06, 0.005, 0, 0)
    button_disc("BoneThread", f"Accessories/WaistcoatButton_{i+1}", p, (0, 0.15, 1.0), radius=.0075, thick=.0032, thread_mat="AgedBrass")

for wi, wy in ((1, 1.14), (2, 1.23)):
    ry = interp_val(wy, wc_y, wc_rx); rzv = interp_val(wy, wc_y, wc_rz)
    p0 = shell_point(wy, ry, rzv, 0.0, -0.16, 0.005, 0, 0)
    p1 = shell_point(wy, ry, rzv, 0.0, -0.02, 0.005, 0, 0)
    tube("BoneThread", f"Accessories/WaistcoatWeltL_{wi}", [p0, vadd(lerp(p0, p1, .5), (0, .002, 0)), p1], [.0028]*3, 6, (0, 1, 0))
    p0r = shell_point(wy, ry, rzv, 0.0, 0.02, 0.005, 0, 0)
    p1r = shell_point(wy, ry, rzv, 0.0, 0.16, 0.005, 0, 0)
    tube("BoneThread", f"Accessories/WaistcoatWeltR_{wi}", [p0r, vadd(lerp(p0r, p1r, .5), (0, .002, 0)), p1r], [.0028]*3, 6, (0, 1, 0))

chain_pts = []
for k in range(9):
    t = k / 8.0
    cy = 1.22 - 0.05 * math.sin(math.pi * t)
    cx = 0.08 * (1.0 - t) - 0.04 * t
    cz = 0.142 + 0.010 * math.sin(math.pi * t)
    chain_pts.append((cx, cy, cz))
tube("AgedBrass", "Accessories/WatchChain", chain_pts, [.0022]*9, 6, (0, 1, 0))

thick_ring_shell("BoneThread", "UpperClothing/ShirtCollar",
    [(lambda a, y=y, rx=rx, rz=rz: (y, rx, rz, -0.011)) for y, rx, rz in
     ((1.477, .0675, .0715), (1.522, .0705, .0745))],
    thick=.0035, sides=24, a0=0.0, a1=2*math.pi, wrap=True, rim_start=False, rim_end=True)
collar_stitch_pts = [(.071*math.sin(2*math.pi*k/12), 1.520, -.011 + .075*math.cos(2*math.pi*k/12)) for k in range(12)]
stitch_dashes("ClothAccent", "UpperClothing/ShirtCollarStitch", collar_stitch_pts, 10, r=0.0018, length=0.009)

neck_pts = []
for k in range(8):
    a = -0.95 + 1.9*k/7
    neck_pts.append((0.083*math.sin(a), 1.494 - 0.006*(k/7.0), -0.011 + 0.082*math.cos(a)))
strap_band("BoneThread", "Accessories/CravatBand", neck_pts, width=.034, thick=.006,
    normal_fn=lambda p, t: norm((p[0], 0.15, p[2])))
ellipsoid("BoneThread", "Accessories/CravatKnot", (.014, 1.488, .108), (.026, .021, .017), 8, 12)

button_disc("AgedBrass", "Accessories/CravatBrooch", (.014, 1.488, .124), (0.05, 0.1, 1.0), radius=.0075, thick=.0032, thread_mat=None)

def front_normal(p, t):
    return norm((p[0]*0.35, 0, 1.0))

strap_band("BoneThread", "Accessories/CravatTailL",
    [(.026, 1.478, .114), (.042, 1.410, .122), (.050, 1.340, .116), (.054, 1.324, .114)],
    width=.026, thick=.004, normal_fn=front_normal)
stitch_dashes("ClothAccent", "Accessories/CravatTailLStitch",
    [(.026, 1.478, .116), (.042, 1.410, .124), (.050, 1.340, .118)], 4, r=0.0018, length=0.009)

strap_band("BoneThread", "Accessories/CravatTailR",
    [(.004, 1.480, .115), (-.004, 1.435, .123), (-.012, 1.404, .118)],
    width=.024, thick=.004, normal_fn=front_normal)


# =========================================================================
# GREATCOAT BODICE & BACK TAILORING (Crucial for Gameplay Camera!):
# Asymmetric left-over-right closure, raised center-back spine seam welt,
# curved shoulder-blade princess seams, shoulder epaulettes with brass buttons,
# folded-back wine lapels with double saddle stitching, 4 pairs of aged
# brass frog clasps down torso, side pocket welts with button flaps.
# =========================================================================

BODICE_ROWS = [(1.00, .272, .168), (1.03, .254, .157),
               (1.16, .262, .158), (1.28, .290, .162), (1.38, .312, .160),
               (1.455, .302, .148), (1.495, .266, .125)]
COAT_T = 0.011

def coat_inner(y):
    return (interp_val(y, [r[0] for r in BODICE_ROWS], [r[1] for r in BODICE_ROWS]),
            interp_val(y, [r[0] for r in BODICE_ROWS], [r[2] for r in BODICE_ROWS]))

def coat_surf(a, y, out=0.0):
    rx, rz = coat_inner(y)
    return shell_point(y, rx + COAT_T + out, rz + COAT_T + out, 0.0, a, 0.0, 0.0, 0.0)

def edge_left(y):
    return 0.50 * smoothstep(1.20, 1.47, y) + 0.10 * (1 - smoothstep(1.20, 1.47, y))
def edge_right(y):
    return 0.42 * smoothstep(1.18, 1.45, y) + 0.06 * (1 - smoothstep(1.18, 1.45, y))

def bodice_rows_factory(which):
    rows = []
    for y, rx, rz in BODICE_ROWS:
        def fn(a, y=y, rx=rx, rz=rz, which=which):
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
        w = smoothstep(1.40, 1.475, y)
        dr += 0.005 * w * (gauss(am, math.pi/2, .50) + gauss(am, 1.5*math.pi, .50))
        dr += 0.004 * math.sin(9*a + 0.8) * smoothstep(.94, 1.02, y) * (1 - smoothstep(1.08, 1.22, y))
        dr -= 0.004 * gauss(am, math.pi, 0.45) * (1 - smoothstep(1.18, 1.34, y))
        if panel == "L":
            dr += 0.005 * max(0.0, math.cos(am))
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

spine_pts = [coat_surf(math.pi, y, out=0.002) for y in (1.02, 1.10, 1.18, 1.26, 1.35, 1.44, 1.485)]
welt_seam("Cloth", "UpperClothing/SpineSeam", spine_pts, radius=0.004)
stitch_dashes("BoneThread", "UpperClothing/SpineSeamStitch", spine_pts, 8, r=0.0022, length=0.012)

for side, s_ang, label in ((-1, math.pi - 0.42, "L"), (1, math.pi + 0.42, "R")):
    prin_pts = [coat_surf(s_ang + 0.08*(1.48 - y), y, out=0.002) for y in (1.03, 1.12, 1.22, 1.32, 1.42, 1.48)]
    welt_seam("Cloth", f"UpperClothing/PrincessSeam_{label}", prin_pts, radius=0.0035)
    stitch_dashes("BoneThread", f"UpperClothing/PrincessSeamStitch_{label}", prin_pts, 6, r=0.0020, length=0.011)

for side, label in ((-1, "L"), (1, "R")):
    x = side
    ep_pts = [(x*.16, 1.478, -.005), (x*.22, 1.468, .002), (x*.28, 1.455, .008)]
    strap_band("Leather", f"UpperClothing/Epaulette_{label}", ep_pts, width=.024, thick=.004, normal_fn=lambda p, t: (0, 1.0, 0))
    stitch_dashes("BoneThread", f"UpperClothing/EpauletteStitch_{label}", ep_pts, 4, r=0.0020, length=0.009)
    button_disc("AgedBrass", f"UpperClothing/EpauletteButton_{label}", (x*.17, 1.482, -.005), (0, 1.0, 0), radius=.0075, thick=.0032, thread_mat=None)

def thick_panel(mat, name, grid, thick):
    rows, cols = len(grid), len(grid[0])
    pts = [p for row in grid for p in row]
    back = []
    for p in grid:
        brow = []
        for x, y, z in p:
            r = math.hypot(x, z)
            k = (r - thick) / r if r > 1e-9 else 1.0
            brow.append((x*k, y, z*k))
        back.append(brow)
    pts += [p for row in back for p in row]
    fs = []
    for r in range(rows-1):
        for c in range(cols-1):
            i00 = r*cols+c; i01 = r*cols+c+1; i10 = (r+1)*cols+c; i11 = (r+1)*cols+c+1
            o = rows*cols
            fs.append((i00, i10, i11)); fs.append((i00, i11, i01))
            fs.append((o+i00, o+i11, o+i10)); fs.append((o+i00, o+i01, o+i11))
            fs.append((i01, i11, o+i11)); fs.append((i01, o+i11, o+i01))
    for r in range(rows-1):
        i0 = r*cols; i1 = (r+1)*cols; o = rows*cols
        fs.append((i0, o+i0, o+i1)); fs.append((i0, o+i1, i1))
    for c in range(cols-1):
        i0 = c; i1 = c+1; o = rows*cols; b = (rows-1)*cols
        fs.append((i0, i1, o+i1)); fs.append((i0, o+i1, o+i0))
        fs.append((b+c, o+b+c, o+b+c+1)); fs.append((b+c, o+b+c+1, b+c+1))
    add_mesh(mat, name, pts, fs)

for panel, label, spread_top, spread_bot, y0, y1 in (("L", "L", 0.15, 0.30, 1.22, 1.496),
                                                     ("R", "R", 0.13, 0.26, 1.24, 1.464)):
    sgn = 1.0 if panel == "L" else -1.0
    edge_fn = edge_left if panel == "L" else edge_right
    grid = []
    outer_lapel_edge = []
    for k in range(9):
        t = k / 8.0
        y = y0 + (y1 - y0)*t
        row = []
        for j in range(4):
            u = j / 3.0
            spread = spread_bot + (spread_top - spread_bot) * t
            a = sgn * (edge_fn(y) + spread * u)
            p = coat_surf(a, y, out=0.002 + 0.002*u)
            row.append(p)
            if j == 3:
                outer_lapel_edge.append(p)
        grid.append(row)
    thick_panel("ClothAccent", f"UpperClothing/Lapel_{label}", grid, thick=.006)
    stitch_dashes("BoneThread", f"UpperClothing/LapelStitch_{label}", outer_lapel_edge, 8, r=0.0022, length=0.011)
    top_p = outer_lapel_edge[-1]
    rivet_cap("AgedBrass", f"UpperClothing/LapelStud_{label}", top_p, (sgn*0.5, 0.2, 0.8), radius=0.0055, height=0.0035)

def coat_edge_point(y, panel, out=0.0):
    a = edge_left(y) if panel == "L" else edge_right(y)
    p = coat_surf(a, y, out=out)
    return p

for hi, hy in enumerate((1.02, 1.10, 1.18, 1.26)):
    pL = coat_edge_point(hy, "L", out=0.004)
    pR = coat_edge_point(hy, "R", out=0.004)
    strap_band("Leather", f"Accessories/FrogTabL_{hi+1}", [vadd(pL, (.020, 0, -.005)), pL], width=.014, thick=.003, normal_fn=lambda p, t: (0, 0, 1.0))
    strap_band("Leather", f"Accessories/FrogTabR_{hi+1}", [vadd(pR, (-.020, 0, -.005)), pR], width=.014, thick=.003, normal_fn=lambda p, t: (0, 0, 1.0))
    rivet_cap("AgedBrass", f"Accessories/FrogRivetL_{hi+1}", vadd(pL, (.016, 0, -.003)), (0, 0, 1.0), radius=0.0045)
    rivet_cap("AgedBrass", f"Accessories/FrogRivetR_{hi+1}", vadd(pR, (-.016, 0, -.003)), (0, 0, 1.0), radius=0.0045)
    torus_arc("AgedBrass", f"Accessories/FrogLoop_{hi+1}", vadd(pL, (-.005, 0, .002)), .007, .0022, 6, 10, axis=(0, 1, 0))
    tube("AgedBrass", f"Accessories/FrogToggle_{hi+1}", [vadd(pR, (-.012, -.008, .002)), vadd(pR, (-.002, .008, .002))], [.0026, .0026], 6, (0, 0, 1))

for side, s_ang, label in ((-1, math.pi*0.5 + 0.15, "L"), (1, 1.5*math.pi - 0.15, "R")):
    x = side
    p_pts = [coat_surf(s_ang - 0.10, 1.06, out=0.004), coat_surf(s_ang, 1.055, out=0.006), coat_surf(s_ang + 0.10, 1.06, out=0.004)]
    strap_band("ClothAccent", f"UpperClothing/PocketFlap_{label}", p_pts, width=.036, thick=.005, normal_fn=lambda p, t: norm((p[0], 0, p[2])))
    stitch_dashes("BoneThread", f"UpperClothing/PocketFlapStitch_{label}", p_pts, 4, r=0.0020, length=0.010)
    p_mid = coat_surf(s_ang, 1.045, out=0.008)
    button_disc("AgedBrass", f"UpperClothing/PocketButton_{label}", p_mid, norm((p_mid[0], 0, p_mid[2])), radius=.007, thick=.003, thread_mat=None)


# =========================================================================
# COAT SKIRT & REAR VENT (High Gameplay Camera Visibility!):
# Sweeping asymmetric skirt, bound hem piping along bottom edges,
# rear split tail vent with accordion kick pleat, rear waist martingale
# tab with pair of aged brass crested greatcoat tail buttons.
# =========================================================================

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

# Rear Tail Vent & Accordion Kick Pleat
pleat_pts = [coat_surf(math.pi, y, out=-0.004) for y in (0.42, 0.55, 0.70, 0.85, 0.98)]
welt_seam("ClothAccent", "LowerClothing/VentPleat", pleat_pts, radius=0.008)

# Rear Waist Martingale Tab & Aged Brass Greatcoat Buttons
tab_pts = [coat_surf(math.pi - 0.32, 1.018, out=0.012), coat_surf(math.pi, 1.015, out=0.014), coat_surf(math.pi + 0.32, 1.018, out=0.012)]
strap_band("Leather", "Accessories/RearMartingale", tab_pts, width=.038, thick=.006, normal_fn=lambda p, t: norm((p[0], 0, p[2])))
stitch_dashes("BoneThread", "Accessories/RearMartingaleStitch", tab_pts, 6, r=0.0024, length=0.012)
btnL = coat_surf(math.pi - 0.28, 1.018, out=0.018)
btnR = coat_surf(math.pi + 0.28, 1.018, out=0.018)
button_disc("AgedBrass", "Accessories/RearCoatButton_L", btnL, norm((btnL[0], 0, btnL[2])), radius=.010, thick=.004, thread_mat=None)
button_disc("AgedBrass", "Accessories/RearCoatButton_R", btnR, norm((btnR[0], 0, btnR[2])), radius=.010, thick=.004, thread_mat=None)


# =========================================================================
# STANDING GREATCOAT COLLAR: high standing collar wrapping the neck,
# wine outer shell with dark blue facing, bone piping along top rim,
# buckled leather throat tab & aged brass studs.
# =========================================================================

def collar_profile(y0, h_front, h_back, rx, rz, grow, zc=-0.008):
    def fn(a):
        ang = (a + math.pi) % (2*math.pi) - math.pi
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
collar_top = collar_profile(1.486, .030, .078, .0945, .1005, .16)
thick_ring_shell("ClothAccent", "UpperClothing/CoatCollar",
    blended_rows(collar_base, collar_top, (0.0, 0.4, 0.75, 1.0)),
    thick=.006, sides=30, a0=COLLAR_A0, a1=2*math.pi-COLLAR_A0, rim_start=False, rim_end=True)

facing_base = collar_profile(1.486, 0.0, 0.0, .0885, .0945, .16)
facing_top = collar_profile(1.486, .024, .064, .0885, .0945, .16)
thick_ring_shell("Cloth", "UpperClothing/CollarFacing",
    blended_rows(facing_base, facing_top, (0.0, 0.55, 1.0)),
    thick=.005, sides=30, a0=COLLAR_A0, a1=2*math.pi-COLLAR_A0, rim_start=False, rim_end=True)

collar_edge = []
for k in range(15):
    t = k / 14.0
    a = (COLLAR_A0 + (2*math.pi - 2*COLLAR_A0) * t)
    p = collar_top(a)
    collar_edge.append(shell_point(p[0] + 0.002, p[1] + 0.008, p[2] + 0.008, p[3], a, 0, 0, 0))
tube("BoneThread", "Accessories/CollarPiping", collar_edge, [.0034]*15, 6, (0, 1, 0))
stitch_dashes("ClothAccent", "Accessories/CollarStitch", collar_edge, 10, r=0.0020, length=0.010)

tab_pts = []
for k in range(7):
    t = k / 6.0
    a = 0.92 - (0.92 + 0.92)*t
    tab_pts.append(shell_point(1.512 + 0.004*t, .101 - .002*t, .106 + .002*t, -0.008, a, 0, 0, 0))
strap_band("Leather", "Accessories/CollarTab", tab_pts, width=.016, thick=.0032, normal_fn=lambda p, t: norm((p[0], 0.35, p[2])))
stitch_dashes("BoneThread", "Accessories/CollarTabStitch", tab_pts, 4, r=0.0018, length=0.009)
be = tab_pts[-1]
buckle_frame("AgedBrass", "Accessories/CollarBuckle", (be[0], be[1], be[2] + .004), (0, 0.2, 1.0), up=(0, 1, 0), width=.018, height=.022, bar_r=.0022)
stud_p = shell_point(1.508, .102, .107, -0.008, -0.86, 0, 0, 0)
rivet_cap("AgedBrass", "Accessories/CollarStud", stud_p, (-0.6, 0.2, 0.8), radius=.0055)


# =========================================================================
# SHOULDER MANTLE / HALF-CAPE (High Gameplay Camera Visibility!):
# Asymmetric mantle wrapping back and shoulders (deeper on left),
# bound hem with bone piping, hem saddle stitching, cowl neck fold,
# dual aged brass ornate shoulder clasps and connecting chain swag.
# =========================================================================

MANTLE_A0, MANTLE_A1 = 1.95, 2*math.pi - 1.95

def mantle_row_fn(t):
    def fn(a, t=t):
        s = (a - MANTLE_A0) / (MANTLE_A1 - MANTLE_A0)
        back_w = math.sin(clamp(s, 0.0, 1.0) * math.pi)
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
tube("BoneThread", "Accessories/MantleHemPiping", mantle_hem, [.0034]*23, 6, (0, 1, 0))
stitch_dashes("ClothAccent", "Accessories/MantleHemStitch", mantle_hem, 14, r=0.0022, length=0.012)

for si, sa, label in ((1, MANTLE_A0 + 0.06, "R"), (2, 2*math.pi - MANTLE_A0 - 0.06, "L")):
    p = mantle_row_fn(0.04)(sa)
    clasp_c = (p[0], p[1] + 0.004, p[2] + 0.004)
    button_disc("AgedBrass", f"Accessories/MantleClasp_{label}", clasp_c, (0, 0.8, 0.6), radius=.009, thick=.004, thread_mat=None)
    torus_arc("AgedBrass", f"Accessories/MantleClaspRing_{label}", clasp_c, .011, .0024, 6, 10, axis=(0, 1, 0))

chain_pts = []
p_clasp_R = mantle_row_fn(0.04)(MANTLE_A0 + 0.06)
p_clasp_L = mantle_row_fn(0.04)(2*math.pi - MANTLE_A0 - 0.06)
for k in range(11):
    t = k / 10.0
    cp = lerp(p_clasp_R, p_clasp_L, t)
    sag = 0.024 * math.sin(math.pi * t)
    chain_pts.append((cp[0], cp[1] - sag, cp[2] + 0.010 * math.sin(math.pi * t)))
tube("AgedBrass", "Accessories/MantleChainSwag", chain_pts, [.0022]*11, 6, (0, 1, 0))


# =========================================================================
# COAT SLEEVES: gathered heads, elbow creases, tailored arm seams,
# left stitched elbow reinforcement patch, right cuff strap & buckle.
# =========================================================================

def sleeve_fold_factory(side):
    def fold(i, s_idx, a):
        dr = 0.0
        dr += 0.005 * math.sin(3*a + 1.7*side) * max(0.0, 1.0 - i)
        dr -= 0.0065 * math.exp(-((i - 2.05)/0.55)**2) * (0.55 + 0.45*math.cos(2*a + side))
        return dr
    return fold

for side, label in ((-1, "L"), (1, "R")):
    x = side
    sleeve_pts = [(x*.201, 1.462, -.008), (x*.296, 1.360, .008), (x*.352, 1.185, .020),
                  (x*.383, 1.065, .032), (x*.389, 1.012, .036)]
    thick_tube("Cloth", f"UpperClothing/CoatSleeve_{label}", sleeve_pts,
        [(.097, .100), (.080, .084), (.069, .073), (.061, .064), (.058, .061)],
        sides=22, thick=.009, fold=sleeve_fold_factory(side), rim_start=True, rim_end=True)
    outer_seam = [(x*(.201 + .098), 1.462, -.008), (x*(.296 + .082), 1.360, .008),
                  (x*(.352 + .070), 1.185, .020), (x*(.383 + .062), 1.065, .032), (x*(.389 + .059), 1.012, .036)]
    welt_seam("Cloth", f"UpperClothing/SleeveSeam_{label}", outer_seam, radius=0.0034)
    stitch_dashes("BoneThread", f"UpperClothing/SleeveSeamStitch_{label}", outer_seam, 8, r=0.0020, length=0.011)

    if side < 0:
        ellipsoid("ClothAccent", f"UpperClothing/ElbowPatch_{label}", (x*.416, 1.185, .022), (.012, .052, .048), 8, 12)
        patch_rim = [(x*.424, 1.185 + .043*math.cos(2*math.pi*k/10), .022 + .040*math.sin(2*math.pi*k/10)) for k in range(10)]
        stitch_dashes("BoneThread", f"Accessories/ElbowPatchStitch_{label}", patch_rim, 10, r=0.0024, length=0.010)
    else:
        ring_pts = [(x*.388 + .0645*math.cos(2*math.pi*k/10), 1.048, .034 + .058*math.sin(2*math.pi*k/10)) for k in range(10)]
        ring_pts.append(ring_pts[0])
        strap_band("Leather", f"Accessories/CuffStrap_{label}", ring_pts, width=.014, thick=.0032, normal_fn=lambda p, t: norm((p[0]-x*.388, 0, p[2]-.034)), closed=True)
        bxc = x * (.388 + .066)
        buckle_frame("AgedBrass", f"Accessories/CuffBuckle_{label}", (bxc, 1.048, .034), (x*1.0, 0, 0), up=(0, 1, 0), width=.018, height=.022, bar_r=.0024)


# =========================================================================
# BELT & ACCESSORIES (High Gameplay Camera Visibility!):
# Cinched wide leather belt with double border saddle stitching,
# ornate aged brass frame buckle, prong & dual leather keepers,
# punched hanging tip with eyelet, field pouch with lid flap,
# stitching & brass stud, left hip hanger strap, brass D-ring,
# mourning tassel with bone thread coil, and secondary brass clip.
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

double_stitch_band("BoneThread", "Accessories/BeltStitch", belt_pts[:-1], 28,
    normal_fn=lambda p, t: norm((p[0], 0, p[2])), offset=0.030, r=0.0022, length=0.012)

BA = 0.30
buck_c = belt_ring(BA)
buck_out = norm((buck_c[0], 0, buck_c[2]))
buckle_frame("AgedBrass", "Accessories/MainBeltBuckle", vadd(buck_c, vmul(buck_out, .010)), buck_out, up=(0, 1, 0), width=.048, height=.082, bar_r=.0045)

for ki, ka in enumerate((0.56, 0.05)):
    keep_pts = [belt_ring(ka - 0.11 + 0.22*k/7) for k in range(8)]
    keep_pts = [vadd(p, vmul(norm((p[0], 0, p[2])), .002)) for p in keep_pts]
    strap_band("Leather", f"Accessories/BeltKeeper_{ki+1}", keep_pts, width=.086, thick=.012,
        normal_fn=lambda p, t: norm((p[0], 0, p[2])))
    stitch_dashes("BoneThread", f"Accessories/BeltKeeperStitch_{ki+1}", keep_pts, 4, r=0.0020, length=0.009)

tip_pts = [vadd(belt_ring(BA - 0.05), (0, -.015, 0)),
           vadd(belt_ring(BA - 0.09), (0, -.055, 0)),
           vadd(belt_ring(BA - 0.12), (0, -.100, 0))]
tip_pts = [vadd(p, vmul(norm((p[0], 0, p[2])), .005)) for p in tip_pts]
strap_band("Leather", "Accessories/BeltTip", tip_pts, width=.050, thick=.007,
    normal_fn=lambda p, t: norm((p[0], 0, p[2])))
double_stitch_band("BoneThread", "Accessories/BeltTipStitch", tip_pts, 4,
    normal_fn=lambda p, t: norm((p[0], 0, p[2])), offset=0.018, r=0.0020, length=0.009)

for hh in range(3):
    hp = lerp(tip_pts[0], tip_pts[2], 0.35 + 0.3*hh)
    ellipsoid("BootSole", f"Accessories/BeltHole_{hh+1}", vadd(hp, vmul(norm((hp[0], 0, hp[2])), .004)),
              (.0042, .0065, .0042), 6, 8)
eye_c = lerp(tip_pts[0], tip_pts[2], 0.30)
torus_arc("AgedBrass", "Accessories/BeltEyelet", vadd(eye_c, vmul(norm((eye_c[0], 0, eye_c[2])), .006)),
          .007, .0022, 6, 10, axis=(math.cos(BA - 0.07), 0, -math.sin(BA - 0.07)))

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
stitch_dashes("BoneThread", "Accessories/PouchFlapStitch", flap_pts, 6, r=.0024, length=.011)
rivet_cap("AgedBrass", "Accessories/PouchStud", vadd(vadd(flap_pts[2], (0, -.018, 0)), vmul(norm((flap_pts[2][0], 0, flap_pts[2][2])), .008)), pout, radius=.007, height=.004)

for li, la in enumerate((PA - 0.28, PA + 0.28)):
    lp = belt_ring(la)
    rivet_cap("AgedBrass", f"Accessories/PouchRivet_{li+1}", vadd(lp, (0, -.025, 0)), norm((lp[0], 0, lp[2])), radius=.0045)

HA = 2.35
hang_pts = [vadd(belt_ring(HA), (0, .012, 0)),
            vadd(belt_ring(HA + .06), (0, -.062, 0)),
            vadd(belt_ring(HA + .09), (0, -.125, 0))]
hang_pts = [vadd(p, vmul(norm((p[0], 0, p[2])), .004)) for p in hang_pts]
strap_band("Leather", "Accessories/HangerStrap", hang_pts, width=.020, thick=.004,
    normal_fn=lambda p, t: norm((p[0], 0, p[2])))
stitch_dashes("BoneThread", "Accessories/HangerStrapStitch", hang_pts, 4, r=0.0018, length=0.009)

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

torus_arc("AgedBrass", "Accessories/ToolClipRing", vadd(dring_c, (0, -.025, .012)), .010, .0020, 6, 10, axis=(0, 1, 0))


# =========================================================================
# BALDRIC & GOTHIC NAVIGATIONAL COMPASS / ASTROLABE:
# Diagonal leather baldric across chest & back with double saddle stitching,
# front aged brass adjustment frame buckle with prong & keeper,
# rear shoulder-blade strap slider, drop strap with brass mounting loop,
# nested gimballed brass astrolabe rings, pointer needle & dial face.
# =========================================================================

bald_pts_front = [coat_surf(-1.50, 1.452, out=.013),
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

strap_band("Leather", "Accessories/Baldric", bald_pts_front, width=.034, thick=.0045, normal_fn=baldric_normal)
double_stitch_band("BoneThread", "Accessories/BaldricStitch", bald_pts_front, 10,
    normal_fn=baldric_normal, offset=0.012, r=0.0022, length=0.011)

bald_pts_back = [coat_surf(-1.50, 1.452, out=.013),
                 coat_surf(-1.95, 1.370, out=.012),
                 coat_surf(-2.40, 1.280, out=.012),
                 coat_surf(-2.80, 1.180, out=.012),
                 coat_surf(2.80, 1.080, out=.013)]
strap_band("Leather", "Accessories/BaldricBack", bald_pts_back, width=.034, thick=.0045, normal_fn=baldric_normal)
double_stitch_band("BoneThread", "Accessories/BaldricBackStitch", bald_pts_back, 8,
    normal_fn=baldric_normal, offset=0.012, r=0.0022, length=0.011)

b_buck_p = bald_pts_front[2]
b_buck_n = baldric_normal(b_buck_p, None)
buckle_frame("AgedBrass", "Accessories/BaldricBuckle", b_buck_p, b_buck_n, up=(0.6, 0.8, 0), width=.028, height=.038, bar_r=.0032)

b_back_p = bald_pts_back[2]
b_back_n = baldric_normal(b_back_p, None)
buckle_frame("AgedBrass", "Accessories/BaldricBackSlider", b_back_p, b_back_n, up=(0.6, 0.8, 0), width=.026, height=.036, bar_r=.0030, has_prong=False)

drop_top = bald_pts_front[3]
drop_bot = vadd(drop_top, (0, -.032, 0))
drop_bot = vadd(drop_bot, vmul(norm((drop_bot[0], 0, drop_bot[2])), .006))
strap_band("Leather", "Accessories/CompassDrop",
           [drop_top, vadd(lerp(drop_top, drop_bot, .5), vmul(norm((drop_top[0], 0, drop_bot[2])), .004)), drop_bot],
           width=.014, thick=.003, normal_fn=lambda p, t: norm((p[0], 0, p[2])))
stitch_dashes("BoneThread", "Accessories/CompassDropStitch", [drop_top, drop_bot], 3, r=0.0018, length=0.008)

comp_c = vadd(drop_bot, (0, -.038, 0))
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
tube("AgedBrass", "Accessories/CompassNeedle", [needle_a, comp_c, needle_b], [.002, .0028, .002], 6, (0, 1, 0))
button_disc("AgedBrass", "Accessories/CompassStud", vadd(comp_c, vmul(comp_dir, .008)), comp_dir, radius=.006, thick=.0035, thread_mat=None)
torus_arc("AgedBrass", "Accessories/CompassLoop", vadd(drop_bot, (0, .004, 0)), .008, .002, 6, 10, axis=(1, 0, 0))


# =========================================================================
# EXPORT BUFFERS IN STABLE ORDER
# =========================================================================

obj_path = os.path.join(OUT, f"SM_Character_VeilboundWayfarer{SUFFIX}.obj")
mtl_path = os.path.join(OUT, f"SM_Character_VeilboundWayfarer{SUFFIX}.mtl")

with open(obj_path, "w", encoding="utf-8") as f:
    f.write(f"# Veilbound Wayfarer - original Vespershade protagonist (DETAIL={DETAIL:.2f}), 1 unit = 1 metre\n")
    f.write("# Layered wardrobe: closed cloth solids with outer face, lining face, bound edge rims,\n")
    f.write("# tailoring seams, double saddle stitching, crested buttons, frame buckles, straps, clasps and astrolabe.\n")
    f.write("mtllib SM_Character_VeilboundWayfarer.mtl\no SM_Character_VeilboundWayfarer\ng VeilboundWayfarer\n")
    offset = 0
    for mat in MATERIALS:
        for x, y, z in verts[mat]:
            f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
        f.write(f"usemtl {mat}\n")
        for a, b, c in faces[mat]:
            f.write(f"f {a+offset} {b+offset} {c+offset}\n")
        offset += len(verts[mat])

with open(mtl_path, "w", encoding="utf-8") as f:
    f.write("# Original tonal palette; Unity prefab uses authored Standard / PBR materials.\n")
    for mat in MATERIALS:
        rgb, shine = colors[mat]
        f.write(f"newmtl {mat}\nKa 0.03 0.03 0.03\nKd {rgb[0]:.4f} {rgb[1]:.4f} {rgb[2]:.4f}\nKs {shine:.3f} {shine:.3f} {shine:.3f}\nNs 32\n\n")

# --- hand rig sidecar: joints + rigged part ranges (per LOD mesh) ---------
import json
offsets = {}
acc = 0
for mat in MATERIALS:
    offsets[mat] = acc
    acc += len(verts[mat])

rig_path = os.path.join(OUT, f"SM_Character_VeilboundWayfarer{SUFFIX}.handrig.json")
rig = {
    "format": "vespershade.handrig/1",
    "mesh": os.path.basename(obj_path),
    "units": "metres", "up": "Y", "character_faces": "+Z",
    "bind_pose": "identity (mesh authored in bind pose; zero-rotation FK "
                 "reproduces the OBJ exactly)",
    "default_bone": "Root (any vertex outside the parts list binds 100% to Root)",
    "weights": "computed deterministically from vertex positions by "
               "Tools/hand_rig.py:weights_for(side, chain, point)",
    "bones": [
        {"name": name, "parent": parent, "head": [round(c, 6) for c in head],
         **({"axes": {k: [round(c, 6) for c in v] for k, v in axes.items()},
             "axis_convention": "flex=+palmar curl (arm: swing forward), "
                                "abd=+towards thumb side, twist=+segment roll"}
            if axes else {})}
        for (name, parent, head, axes) in hand_rig.joint_list()
    ],
    "parts": [
        {"name": p["name"], "mat": p["mat"],
         "start": offsets[p["mat"]] + p["start"],
         "end": offsets[p["mat"]] + p["end"],
         "side": p["side"], "chain": p["chain"]}
        for p in RIG_PARTS
    ],
}
with open(rig_path, "w", encoding="utf-8") as f:
    json.dump(rig, f, indent=1)

print(f"Wrote {obj_path}: {sum(map(len, verts.values()))} vertices, {sum(map(len, faces.values()))} triangles, {len(MATERIALS)} material regions")
