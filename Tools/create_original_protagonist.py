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
import boot_rig

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


# ---------------------------------------------------------------------------
# Footwear kit: contour lofts, stacked slabs, swept bands and surface panels
#
# Every piece below is a closed solid whose winding is fixed automatically from
# its signed volume, so the boot meshes are provably outward-facing (the boot
# parts are also re-audited by Tools/verify_boots.py).
# ---------------------------------------------------------------------------

def _signed_volume(pts, fs):
    """Six times the signed volume of a triangle soup (winding probe)."""
    vol = 0.0
    for a, b, c in fs:
        pa, pb, pc = pts[a], pts[b], pts[c]
        vol += (pa[0]*(pb[1]*pc[2]-pb[2]*pc[1])
                - pa[1]*(pb[0]*pc[2]-pb[2]*pc[0])
                + pa[2]*(pb[0]*pc[1]-pb[1]*pc[0]))
    return vol / 6.0


def _orient(pts, fs):
    """Flip the winding when the enclosed signed volume is negative."""
    return [f[::-1] for f in fs] if _signed_volume(pts, fs) < 0.0 else fs


def _fix_winding(pts, fs):
    """Make every face of a closed shell consistent, then point it outward.

    Boot parts are assembled from separate wall / rim patches (and open shells
    are wrapped around the lacing slit), so a hand-written winding is easy to
    get subtly wrong: one inverted patch renders as a hole. This walks the face
    graph across shared edges - flipping a face whenever it meets a shared edge
    in the same direction as its neighbour - and finishes by orienting the whole
    shell outwards from its signed volume. Deterministic, O(faces).
    """
    fs = [tuple(f) for f in fs]
    edge = {}
    for fi, f in enumerate(fs):
        for k in range(len(f)):
            a, b = f[k], f[(k + 1) % len(f)]
            if a == b:
                continue
            lo, hi = (a, b) if a < b else (b, a)
            edge.setdefault((lo, hi), []).append((fi, 1 if a == lo else -1))
    flip = [False] * len(fs)
    seen = [False] * len(fs)
    for start in range(len(fs)):
        if seen[start]:
            continue
        seen[start] = True
        stack = [start]
        while stack:
            fi = stack.pop()
            f = fs[fi]
            for k in range(len(f)):
                a, b = f[k], f[(k + 1) % len(f)]
                if a == b:
                    continue
                lo, hi = (a, b) if a < b else (b, a)
                si = (1 if a == lo else -1) * (-1 if flip[fi] else 1)
                for fj, sj in edge[(lo, hi)]:
                    if seen[fj]:
                        continue
                    seen[fj] = True
                    if sj * (-si) < 0:
                        flip[fj] = True
                    stack.append(fj)
    out = [f[::-1] if flip[fi] else f for fi, f in enumerate(fs)]
    return _orient(pts, out) if _signed_volume(pts, out) < 0.0 else out


def _connect_rings(pts, rings, closed=False):
    """Quads between consecutive rings of a point stack, as flat index faces.

    `rings` are point lists laid out in `pts` in the same order (every caller
    builds `pts` by flattening the ring stack); a one-point ring becomes a cap
    fan. `closed=True` welds the last ring back onto the first (a torus with a
    single set of seam vertices, not two coincident boundaries). Winding is
    normalised afterwards by _fix_winding from the shell graph and volume.
    """
    fs = []
    offs, acc = [], 0
    for r in rings:
        offs.append(acc)
        acc += len(r)
    pairs = list(range(len(rings) - 1))
    if closed:
        pairs.append(len(rings) - 1)
    for i in pairs:
        A, B = rings[i], rings[(i + 1) % len(rings)]
        oa, ob = offs[i], offs[(i + 1) % len(rings)]
        if len(A) == 1:
            for k in range(len(B)):
                fs.append((oa, ob + (k+1) % len(B), ob + k))
        elif len(B) == 1:
            for k in range(len(A)):
                fs.append((ob, oa + k, oa + (k+1) % len(A)))
        else:
            n = len(A)
            for k in range(n):
                kn = (k+1) % n
                fs.append((oa + k, oa + kn, ob + kn))
                fs.append((oa + k, ob + kn, ob + k))
    return fs


def _ring_centre(ring):
    n = len(ring)
    return (sum(p[0] for p in ring)/n, sum(p[1] for p in ring)/n,
            sum(p[2] for p in ring)/n)


def _shrink_ring(ring, thick, centre=None):
    """Copy of a ring offset `thick` towards its centre (lining wall)."""
    c = centre or _ring_centre(ring)
    out = []
    for p in ring:
        dx, dy, dz = p[0]-c[0], p[1]-c[1], p[2]-c[2]
        l = math.sqrt(dx*dx + dy*dy + dz*dz)
        k = max(0.0, l - thick)/l if l > 1e-9 else 1.0
        out.append((c[0]+dx*k, c[1]+dy*k, c[2]+dz*k))
    return out


def _stamp(mat, name, pts, fs, place=None, flip=False, orient=True, part=None):
    """Auto-orient, place and append a closed solid to a material buffer.

    Local-frame solids are stamped through here: `place`/`flip` mirror the part
    for the left side and `_orient` guarantees the winding is outward, so a
    mirrored part can never end up inside-out. `part=(side, chain)` registers
    the vertex range in RIG_PARTS for the boot rig sidecar.
    """
    if orient:
        # if the mesh is not edge-consistent already (checked offline by
        # Tools/verify_boots.py) this also repairs the offending patch
        fs = _fix_winding(pts, fs)
    if place is not None:
        pts = [place(p) for p in pts]
    if flip:
        fs = [f[::-1] for f in fs]
    if part is not None:
        add_part(mat, name, pts, fs, part[0], part[1])
    else:
        add_mesh(mat, name, pts, fs)


def loft_solid(mat, name, rings, cap_start=True, cap_end=True, place=None, flip=False,
               part=None):
    """Closed solid lofted through a stack of equal-length rings."""
    rings = [list(r) for r in rings]
    if cap_start and len(rings[0]) > 1:
        rings = [[_ring_centre(rings[0])]] + rings
    if cap_end and len(rings[-1]) > 1:
        rings = rings + [[_ring_centre(rings[-1])]]
    pts = [p for ring in rings for p in ring]
    _stamp(mat, name, pts, _connect_rings(pts, rings), place, flip, part=part)


def loft_shell(mat, name, rings, thick, closed=True, rim_start=True, rim_end=True,
               place=None, flip=False, part=None):
    """Hollow leather shell: outer wall, lining wall and border rims.

    Works for closed loops (a tube) and for open arcs (a sheet wrapped into a
    solid: the lacing slit keeps real leather edges).
    """
    n_r = len(rings)
    n_c = len(rings[0])
    inner = [_shrink_ring(r, thick) for r in rings]
    pts = [p for r in rings for p in r] + [p for r in inner for p in r]
    off = n_r * n_c
    span = n_c if closed else n_c - 1
    fs = []
    for i in range(n_r - 1):
        for k in range(span):
            kn = (k + 1) % n_c
            a0, a1 = i*n_c + k, i*n_c + kn
            b0, b1 = (i+1)*n_c + k, (i+1)*n_c + kn
            fs.append((a0, b0, b1)); fs.append((a0, b1, a1))
            fs.append((off+a0, off+a1, off+b1)); fs.append((off+a0, off+b1, off+b0))
        if not closed:
            for k in (0, n_c - 1):
                a = i*n_c + k; b = (i+1)*n_c + k
                fs.append((a, b, off+b)); fs.append((a, off+b, off+a))
    if rim_start:
        for k in range(span):
            kn = (k + 1) % n_c
            fs.append((kn, k, off+k)); fs.append((kn, off+k, off+kn))
    if rim_end:
        base = (n_r-1)*n_c
        for k in range(span):
            kn = (k + 1) % n_c
            fs.append((base+k, base+kn, off+base+kn))
            fs.append((base+k, off+base+kn, off+base+k))
    _stamp(mat, name, pts, fs, place, flip, part=part)


def rect_ring(z, y0, y1, half_w, taper=0.94, n_edge=4):
    """Closed trapezoid section: top edge +-half_w, ground edge +-half_w*taper.

    Used for the sole slab, the stacked heel laminations and thin plates. The
    taper feathers the ground edge (a raw box section reads as plastic) and the
    `n_edge` interior samples keep the long wall from collapsing on thin slabs.
    """
    wb = max(0.0008, half_w * taper)
    n_edge = max(2, int(n_edge))
    out = []
    for k in range(n_edge):                     # outboard wall: top -> ground
        u = k / (n_edge - 1.0)
        out.append((half_w + (wb - half_w) * u, y1 + (y0 - y1) * u))
    for k in range(n_edge):                     # inboard wall: ground -> top
        u = k / (n_edge - 1.0)
        out.append((-wb + (wb - half_w) * u, y0 + (y1 - y0) * u))
    return [(x, y, z) for (x, y) in out]


def sweep_loop(mat, name, path, profile, closed=True, place=None, flip=False,
               centre=None, cap=True, part=None):
    """Sweep a closed 2D profile (outward, along-surface) along a 3D path.

    `profile` is a list of (u, v): u runs along the surface's outward normal,
    v runs along the surface tangent perpendicular to the path - so a welt, a
    strap or a fold band is described by its cross-section alone.
    """
    n = len(path)
    if centre is None:
        # centre for the outward normal: full 3D centroid, so the hint also
        # works for vertical sweeps (buckle edges, cuff beads)
        centre = (sum(p[0] for p in path)/n, sum(p[1] for p in path)/n,
                  sum(p[2] for p in path)/n)
    rings = []
    for i, p in enumerate(path):
        a = path[(i-1) % n] if closed else path[max(0, i-1)]
        b = path[(i+1) % n] if closed else path[min(n-1, i+1)]
        t = norm(vsub(b, a))
        hint = (p[0]-centre[0], p[1]-centre[1], p[2]-centre[2])
        if dot(hint, hint) < 1e-10:
            hint = (1.0, 0.0, 0.0)
        nn = norm(vsub(hint, vmul(t, dot(hint, t))))
        bn = norm(cross(t, nn))
        rings.append([vadd(p, vadd(vmul(nn, u), vmul(bn, v))) for (u, v) in profile])
    if not closed and cap:
        rings = [[_ring_centre(rings[0])]] + rings + [[_ring_centre(rings[-1])]]
    pts = [q for ring in rings for q in ring]
    _stamp(mat, name, pts, _connect_rings(pts, rings, closed=closed), place, flip,
           part=part)


def panel_solid(mat, name, grid, thick, place=None, flip=False, out_sign=1.0,
                part=None):
    """Curved panel with thickness, built from a rows x cols surface grid."""
    rows, cols = len(grid), len(grid[0])
    norms = []
    for r in range(rows):
        row = []
        for c in range(cols):
            r0 = grid[max(0, r-1)][c]; r1 = grid[min(rows-1, r+1)][c]
            c0 = grid[r][max(0, c-1)]; c1 = grid[r][min(cols-1, c+1)]
            n = norm(cross(vsub(r1, r0), vsub(c1, c0)))
            row.append(vmul(n, out_sign) if (n[0] or n[1] or n[2]) else (0.0, 1.0, 0.0))
        norms.append(row)
    outer = [vadd(grid[r][c], vmul(norms[r][c], thick*0.5))
             for r in range(rows) for c in range(cols)]
    inner = [vsub(grid[r][c], vmul(norms[r][c], thick*0.5))
             for r in range(rows) for c in range(cols)]
    pts = outer + inner
    o = rows*cols
    fs = quad_grid(outer, rows, cols, False, flip=False)
    # the inner wall is built from its own point list, so its face indices have
    # to be shifted into the merged (outer + inner) buffer
    fs += [tuple(i + o for i in f) for f in quad_grid(inner, rows, cols, False, flip=True)]
    for r in range(rows-1):                       # side rims (cols 0 and last)
        for c0, c1 in ((0, 0), (cols-1, cols-1)):
            i00 = r*cols + c0; i10 = (r+1)*cols + c0
            fs.append((i00, i10, o+i10)); fs.append((i00, o+i10, o+i00))
    for c in range(cols-1):                       # end rims (rows 0 and last)
        for r0 in (0, rows-1):
            i00 = r0*cols + c; i01 = r0*cols + c + 1
            fs.append((i00, i01, o+i01)); fs.append((i00, o+i01, o+i00))
    _stamp(mat, name, pts, fs, place, flip, part=part)


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

# 5. Volumetric Layered Gothic Hairstyle - "the Vigil Sweep" (original design)
# ---------------------------------------------------------------------------
# Design intent: dark blue-black, mid-length hair swept back and across from
# an offset part, collected low at the back of the crown into a bound tail,
# with a layered nape draping over the greatcoat collar and face-framing
# temple strands. Built as ~20 individually swept solid locks over a padded
# scalp cap - never a single blob, never primitive geometry.
#
# Sections (each an independent swept solid, recorded in the .hairrig.json):
#   CrownCap        scalp shell, padded volume, scalloped hairline (widow's
#                   peak, temple peaks, ear notches, nape drop), part groove
#   CrownSweep_*    tapered locks radiating from the part line
#   Fringe_*        asymmetric forehead sweep + short part strands
#   Temple_*        cheek-framing strands in front of the ears + tucked pair
#   NapeLayer_*     staggered locks draping over the coat collar
#   Gather          root bulge where the mass is collected
#   TailRope_*      twisted rope strands of the bound tail (staggered tips)
#   HairlineWisp_*  short rim wisps (base LOD only)
#   (BoneThread)    HairTie* cord bound around the Gather
#
# Stability: the hair is rigid geometry parented to the player mesh (no
# cloth/jiggle simulation to destabilise), every loose element keeps
# clearance from the collar/mantle sweep envelope, and the hair shader's
# flow pattern is evaluated in object space so nothing swims in motion.

HAIR_SECTIONS = []     # (name, role, start, end) ranges in the Hair buffer
HAIR_TIE_SECTIONS = [] # (name, start, end) ranges in the BoneThread buffer

HAIR_PAD = 0.0075            # base scalp->cap offset (believable hair volume)
HAIR_CROWN_TOP = 1.833       # padded crown apex

# Part line (lon, y) walking front hairline -> over the crown -> back.
HAIR_PART_2D = [(0.30, 1.742), (0.26, 1.772), (0.18, 1.800), (0.06, 1.820),
                (-0.06, 1.812), (-0.16, 1.786), (-0.20, 1.758)]

# Scalloped hairline: (lon, y) control pairs, mirrored on |lon|.
#   centre dip = widow's peak, rise at the temples, a raised notch over the
#   sculpted ears (they sit in open air), then a nape drop around the back.
HAIRLINE_CTRL = [(0.00, 1.7285), (0.42, 1.7430), (0.78, 1.7255), (1.10, 1.7110),
                 (1.30, 1.6985), (1.48, 1.7090), (1.62, 1.7125), (1.80, 1.7095),
                 (1.98, 1.6990), (2.14, 1.6480), (2.42, 1.5940), (math.pi, 1.5660)]

# Head splines (same values as generate_unified_head above) so the hair hugs
# the sculpted skull exactly.
_hair_spline_y        = [1.440, 1.490, 1.530, 1.555, 1.580, 1.605, 1.635, 1.665, 1.695, 1.718, 1.745, 1.772, 1.792, 1.808, 1.815]
_hair_spline_rx       = [0.076, 0.068, 0.064, 0.065, 0.060, 0.068, 0.078, 0.086, 0.084, 0.082, 0.080, 0.074, 0.062, 0.038, 0.006]
_hair_spline_rz_back  = [0.072, 0.066, 0.066, 0.072, 0.082, 0.092, 0.102, 0.108, 0.112, 0.112, 0.108, 0.098, 0.082, 0.052, 0.010]
_hair_spline_rz_front = [0.076, 0.068, 0.064, 0.068, 0.074, 0.078, 0.082, 0.086, 0.084, 0.082, 0.078, 0.068, 0.056, 0.035, 0.006]
_hair_spline_cz       = [0.000, 0.002, 0.004, 0.005, 0.004, 0.000,-0.006,-0.010,-0.014,-0.016,-0.018,-0.018,-0.018,-0.018,-0.018]


def _hash1(n):
    """Deterministic 0..1 hash (no random module - regeneration is stable)."""
    x = math.sin(n * 127.1 + 311.7) * 43758.5453
    return x - math.floor(x)


def _cosy_interp(x, ctrl):
    """Smooth (cosine-eased) interpolation over (x, value) control pairs."""
    a = abs(x)
    if a <= ctrl[0][0]:
        return ctrl[0][1]
    if a >= ctrl[-1][0]:
        return ctrl[-1][1]
    for k in range(len(ctrl) - 1):
        x0, v0 = ctrl[k]
        x1, v1 = ctrl[k + 1]
        if x0 <= a <= x1:
            t = (a - x0) / (x1 - x0)
            te = 0.5 - 0.5 * math.cos(math.pi * t)
            return v0 + (v1 - v0) * te
    return ctrl[-1][1]


def hairline_y(lon):
    """Hairline height at longitude lon (0 = front, pi = back)."""
    y = _cosy_interp(lon, HAIRLINE_CTRL)
    # scallop ripple so the rim never reads as a machined edge (fades behind)
    y += 0.0031 * math.sin(abs(lon) * 9.0 + 0.7) * max(0.0, 1.0 - abs(lon) / 2.3)
    return y


def scalp_point(y, lon, lift=0.0):
    """Point on the hair-padded scalp surface at height y, longitude lon."""
    rx = interp_val(y, _hair_spline_y, _hair_spline_rx) + HAIR_PAD + lift
    rz_b = interp_val(y, _hair_spline_y, _hair_spline_rz_back) + HAIR_PAD + lift + 0.002
    rz_f = interp_val(y, _hair_spline_y, _hair_spline_rz_front) + HAIR_PAD + lift
    cz = interp_val(y, _hair_spline_y, _hair_spline_cz)
    blend_t = 0.5 * (math.cos(lon) + 1.0)
    rz = rz_b * (1.0 - blend_t) + rz_f * blend_t
    return (rx * math.sin(lon), y, cz + rz * math.cos(lon))


def _cap_pad(y, lon):
    """Sculpted volume padding of the cap over the bare scalp offset."""
    pad = 0.0045 * gauss(y, 1.800, 0.050)                              # crown dome
    pad += 0.0042 * gauss(y, 1.788, 0.042) * gauss(lon, -0.52, 0.55)   # deep sweep ridge
    pad += 0.0026 * gauss(y, 1.618, 0.055) * gauss(lon, math.pi, 0.9)  # occiput fullness
    return pad


_HAIR_PART_3D = None
def _seg_dist(p, a, b):
    ab = vsub(b, a)
    tt = dot(vsub(p, a), ab) / max(dot(ab, ab), 1e-12)
    tt = clamp(tt, 0.0, 1.0)
    return math.sqrt(dot(vsub(p, vadd(a, vmul(ab, tt))), vsub(p, vadd(a, vmul(ab, tt)))))


def _part_groove(y, lon):
    """Downward displacement along the part line (a visible crown parting)."""
    global _HAIR_PART_3D
    if _HAIR_PART_3D is None:
        _HAIR_PART_3D = [scalp_point(yy, ll, 0.0) for (ll, yy) in HAIR_PART_2D]
    p = scalp_point(y, lon, 0.0)
    d = min(_seg_dist(p, _HAIR_PART_3D[k], _HAIR_PART_3D[k + 1])
            for k in range(len(_HAIR_PART_3D) - 1))
    if d >= 0.010:
        return 0.0
    return -0.0034 * (1.0 - smoothstep(0.002, 0.010, d))


def _catmull_sample(ctrl, count):
    """Resample an open Catmull-Rom spline through ctrl points to `count` stations."""
    pts = [tuple(map(float, c)) for c in ctrl]
    if len(pts) < 2:
        return pts
    ext = [pts[0]] + pts + [pts[-1]]
    segs = len(pts) - 1
    out = []
    for k in range(count):
        s = k / (count - 1) * segs
        i = min(int(s), segs - 1)
        t = s - i
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        t2, t3 = t * t, t * t * t
        out.append(tuple(
            0.5 * ((2 * p1[j]) + (-p0[j] + p2[j]) * t
                   + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                   + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)
            for j in range(3)))
    return out


def _lock_width_profile(t, root=0.62, mid=1.0, tip=0.16):
    """Root swelling out of the cap -> full body -> long taper -> blunt tip."""
    grow = root + (mid - root) * smoothstep(0.0, 0.14, t)
    taper = 1.0 - (1.0 - tip) * smoothstep(0.58, 0.99, t)
    pinch = 1.0 - 0.70 * smoothstep(0.99, 1.0, t)
    return grow * taper * max(pinch, 0.30)


def _hair_lock(mat, sections, name, role, ctrl, width, sides=8, stations=16,
               flat=0.62, twist=0.35, grooves=2, groove_depth=0.10,
               jitter=0.0016, seed=0.0, preferred=(0.0, 1.0, 0.0)):
    """Sweep one solid hair lock: a smoothed centreline carries an elliptical,
    flattened cross-section with longitudinal grooves, twist, organic jitter,
    a swollen root sunk into the cap and a pinched fan tip. Records the
    vertex range in `sections`."""
    sides = _segs(sides, 6)
    stations = _segs(stations, 8)
    centers = _catmull_sample(ctrl, stations)
    n = len(centers)
    # low-frequency deterministic jitter so no two locks share one plane
    j1, j2, j3 = _hash1(seed + 1.7), _hash1(seed + 5.3), _hash1(seed + 9.1)
    ph1, ph2 = _hash1(seed + 2.9) * 6.283, _hash1(seed + 4.1) * 6.283
    for i in range(n):
        t = i / (n - 1)
        centers[i] = vadd(centers[i], (
            jitter * math.sin(t * 5.3 + ph1) * math.cos(t * 2.1 + j1 * 6.283),
            jitter * math.sin(t * 4.1 + ph2) * 0.6,
            jitter * math.cos(t * 6.2 + ph1 * 0.7) * math.sin(t * 1.7 + j2 * 6.283)))
    frames = tube_frames(centers, preferred)
    start = len(verts[mat])
    pts = []
    for i in range(n):
        t = i / (n - 1)
        tangent, b1, b2 = frames[i]
        rot = twist * (t - 0.5)
        cr, sr = math.cos(rot), math.sin(rot)
        rb1 = vadd(vmul(b1, cr), vmul(b2, sr))
        rb2 = vadd(vmul(b1, -sr), vmul(b2, cr))
        w = width * _lock_width_profile(t) * (1.0 + 0.05 * math.sin(t * 9.0 + j3 * 6.283))
        d = w * flat
        ring = []
        for s in range(sides):
            a = 2.0 * math.pi * s / sides
            gf = 1.0 - groove_depth * (0.5 + 0.5 * math.cos(a * grooves + j1 * 6.283))
            off = vadd(vmul(rb1, 0.5 * w * gf * math.cos(a)),
                       vmul(rb2, 0.5 * d * gf * math.sin(a)))
            ring.append(vadd(centers[i], off))
        pts.extend(ring)
    fs = []
    for r in range(n - 1):
        for s in range(sides):
            a = r * sides + s
            an = r * sides + (s + 1) % sides
            b = (r + 1) * sides + s
            bn = (r + 1) * sides + (s + 1) % sides
            fs.extend(((a, an, b), (an, bn, b)))
    # root fan (sunk inside the cap, hidden) and pinched tip fan
    root_c = len(pts)
    pts.append(vadd(centers[0], vmul(norm(vsub(centers[1], centers[0])), -0.002)))
    for s in range(sides):
        fs.append((root_c, (s + 1) % sides, s))
    tip_c = len(pts)
    pts.append(vadd(centers[-1], vmul(norm(vsub(centers[-1], centers[-2])), 0.0025)))
    base = (n - 1) * sides
    for s in range(sides):
        fs.append((tip_c, base + s, base + (s + 1) % sides))
    add_mesh(mat, name, pts, fs)
    sections.append((name, role, start, len(verts[mat])))
    return start, len(verts[mat])


def generate_gothic_hair():
    """Adds every hair section directly to the Hair material buffer, recording
    buffer-absolute vertex ranges in HAIR_SECTIONS as it goes."""
    def add_mesh_hair(points, faces, name, role):
        start = len(verts["Hair"])
        add_mesh("Hair", name, points, faces)
        HAIR_SECTIONS.append((name, role, start, len(verts["Hair"])))

    # ---------------- Crown cap: padded scalp shell with modelled hairline
    cap_sides = _segs(46, 14)
    cap_rows = _segs(24, 12)
    cap_pts = []
    cap_fs = []
    pole = (0.0, HAIR_CROWN_TOP, -0.018)
    cap_pts.append(pole)
    y_top, y_bot = 1.827, 1.552
    for r in range(cap_rows):
        y_row = y_top - (y_top - y_bot) * r / (cap_rows - 1.0)
        for s in range(cap_sides):
            lon = -math.pi + 2.0 * math.pi * s / cap_sides
            hl = hairline_y(lon)
            yy = max(y_row, hl)
            lift = _cap_pad(yy, lon) + _part_groove(yy, lon)
            # flow ripples: subtle horizontal wave ridges down the sides/back
            # so the cap itself carries hair direction instead of reading as
            # a smooth shell (fades out on the crown dome)
            lift += (0.0013 * math.sin(6 * lon + (yy - 1.55) * 36.0 + 0.6)
                     + 0.0007 * math.sin(11 * lon + 2.2)) \
                * gauss(lon, math.pi, 1.5) \
                * (1.0 - smoothstep(1.70, 1.78, yy)) \
                * smoothstep(1.556, 1.576, yy)
            # rim tuck: the last few millimetres press against the skin so no
            # light leaks under the hairline edge
            rim = yy - hl
            if rim < 0.006:
                lift = lerp(-0.0012, lift, smoothstep(0.0, 0.006, rim))
            cap_pts.append(scalp_point(yy, lon, lift))
    # winding matches the legacy cap (rows run downward, faces point outward)
    for s in range(cap_sides):
        cap_fs.append((0, 1 + s, 1 + (s + 1) % cap_sides))
    for r in range(cap_rows - 1):
        for s in range(cap_sides):
            p0 = 1 + r * cap_sides + s
            p1 = 1 + r * cap_sides + (s + 1) % cap_sides
            p2 = 1 + (r + 1) * cap_sides + s
            p3 = 1 + (r + 1) * cap_sides + (s + 1) % cap_sides
            cap_fs.extend(((p0, p2, p1), (p1, p2, p3)))
    add_mesh_hair(cap_pts, cap_fs, "Hair/CrownCap", "cap")

    def SP(lon, y, lift=0.0035):
        # ride above the cap's sculpted padding so locks never sink into it
        return scalp_point(y, lon, lift + _cap_pad(y, lon))

    seed = 10.0

    # ---------------- Crown sweeps radiating from the part line
    # right of the part: shorter locks sweeping back over the right temple
    crown_R = [
        ("CrownSweep_R1", [(0.42, 1.740), (0.58, 1.748), (0.76, 1.724), (0.94, 1.698), (1.06, 1.680)], 0.0130),
        ("CrownSweep_R2", [(0.50, 1.760), (0.68, 1.754), (0.90, 1.726), (1.10, 1.698), (1.24, 1.674)], 0.0125),
        ("CrownSweep_R3", [(0.56, 1.780), (0.76, 1.766), (1.00, 1.736), (1.22, 1.710), (1.38, 1.698)], 0.0130),
        ("CrownSweep_R4", [(0.60, 1.800), (0.82, 1.786), (1.08, 1.752), (1.32, 1.722), (1.48, 1.704)], 0.0125),
        ("CrownSweep_R5", [(0.62, 1.818), (0.86, 1.806), (1.14, 1.772), (1.42, 1.736), (1.60, 1.712)], 0.0120),
    ]
    # left of the part: the deep diagonal sweep across the crown
    crown_L = [
        ("CrownSweep_L1", [(0.16, 1.752), (-0.06, 1.752), (-0.34, 1.736), (-0.62, 1.712), (-0.86, 1.684)], 0.0145),
        ("CrownSweep_L2", [(0.08, 1.774), (-0.16, 1.766), (-0.46, 1.740), (-0.76, 1.704), (-1.02, 1.664)], 0.0140),
        ("CrownSweep_L3", [(0.00, 1.796), (-0.24, 1.786), (-0.54, 1.754), (-0.86, 1.712), (-1.14, 1.664)], 0.0135),
        ("CrownSweep_L4", [(-0.08, 1.812), (-0.34, 1.800), (-0.66, 1.764), (-0.98, 1.720), (-1.26, 1.668)], 0.0130),
        ("CrownSweep_L5", [(-0.16, 1.824), (-0.42, 1.812), (-0.74, 1.776), (-1.06, 1.732), (-1.34, 1.676)], 0.0125),
    ]
        # over the crown and down the back, converging into the gather
        # (mid controls ride ~1.826-1.831 so they clear the padded dome)
    crown_B = [
        ("CrownSweep_B1", [(0.22, 1.776), (0.06, 1.824), (-0.30, 1.826), (-0.95, 1.788), (-1.90, 1.726), (-2.66, 1.664), (-3.02, 1.622)], 0.0135),
        ("CrownSweep_B2", [(0.34, 1.790), (0.14, 1.828), (-0.22, 1.828), (-0.88, 1.796), (-1.84, 1.740), (-2.60, 1.680), (-2.96, 1.638)], 0.0130),
        ("CrownSweep_B3", [(0.46, 1.800), (0.22, 1.830), (-0.12, 1.828), (-0.78, 1.802), (-1.70, 1.754), (-2.44, 1.696), (-2.84, 1.652)], 0.0130),
        ("CrownSweep_B4", [(0.58, 1.806), (0.32, 1.830), (0.00, 1.826), (-0.68, 1.806), (-1.52, 1.764), (-2.26, 1.710), (-2.70, 1.664)], 0.0125),
        ("CrownSweep_B5", [(0.70, 1.808), (0.44, 1.826), (0.12, 1.820), (-0.56, 1.806), (-1.36, 1.770), (-2.10, 1.722), (-2.56, 1.676)], 0.0120),
        ("CrownSweep_B6", [(0.14, 1.826), (-0.10, 1.824), (-0.46, 1.812), (-1.10, 1.788), (-1.98, 1.746), (-2.72, 1.690), (-3.06, 1.644)], 0.0120),
        # center-back fillers hugging the cap so no smooth dome shows above the gather
        ("CrownSweep_B7", [(2.74, 1.814), (2.90, 1.778), (3.05, 1.736), (3.16, 1.688)], 0.0125),
        ("CrownSweep_B8", [(3.54, 1.814), (3.38, 1.778), (3.23, 1.736), (3.12, 1.688)], 0.0125),
    ]
    for li, (name, ctrl2d, w) in enumerate(crown_R + crown_L + crown_B):
        # alternate ride height so neighbouring bands never merge into a shell
        lift = 0.0026 + 0.0032 * ((li % 2) == 0) + 0.0020 * ((li % 3) == 0)
        ctrl = [SP(lon, y, lift + 0.0012 * (1.0 - abs(lon) / 1.9)) for (lon, y) in ctrl2d]
        _hair_lock("Hair", HAIR_SECTIONS, name, "crown", ctrl, w,
                   sides=8, stations=15, flat=0.46, twist=0.5, seed=seed, jitter=0.0012)
        seed += 1.0

    # ---------------- Crown whorl: two spiral locks wrapping the apex
    # hair grows from a whorl just off the crown apex; these two S-spirals
    # wrap the pole so the dome top carries the same swept-solid reading as
    # the rest of the cut (and the apex fan never shows as a bald dome).
    apex_pt = (0.0, HAIR_CROWN_TOP - 0.004, -0.018)
    for wi, (phase, dirn) in enumerate(((0.35, 1.0), (0.35 + math.pi, 1.0))):
        ctrl = []
        for k in range(9):
            t = k / 8.0
            ang = phase + dirn * (0.9 + 2.1 * t)
            rr = 0.0135 + 0.0300 * t
            yy = (HAIR_CROWN_TOP - 0.0015 - 0.015 * t)
            czf = -0.018 - 0.006 * t
            ctrl.append((apex_pt[0] + rr * math.sin(ang),
                         yy,
                         czf + rr * 0.9 * math.cos(ang)))
        _hair_lock("Hair", HAIR_SECTIONS, f"CrownWhorl_{wi + 1}", "crown", ctrl, 0.0118,
                   sides=8, stations=16, flat=0.48, twist=0.6, seed=seed, jitter=0.0008)
        seed += 1.0

    # ---------------- Dome fans: locks flowing back over the bare dome top
    # the part line and the B-sweeps bound a smooth region over the crown
    # dome flanks; these fans comb back across it on both sides.
    dome_fans = [
        ("DomeFan_R0", [(0.26, 1.824), (0.58, 1.828), (0.94, 1.820), (1.34, 1.798), (1.74, 1.766), (2.14, 1.726)], 0.0110),
        ("DomeFan_R1", [(0.38, 1.816), (0.70, 1.820), (1.05, 1.810), (1.45, 1.786), (1.85, 1.754), (2.25, 1.714)], 0.0100),
        ("DomeFan_R2", [(0.50, 1.806), (0.82, 1.808), (1.18, 1.798), (1.58, 1.776), (1.98, 1.744), (2.35, 1.704)], 0.0095),
        ("DomeFan_R3", [(0.62, 1.794), (0.94, 1.796), (1.30, 1.786), (1.68, 1.764), (2.06, 1.732), (2.42, 1.692)], 0.0095),
        ("DomeFan_L0", [(0.02, 1.830), (-0.32, 1.824), (-0.70, 1.812), (-1.10, 1.790), (-1.58, 1.758), (-2.03, 1.716)], 0.0110),
        ("DomeFan_L1", [(-0.10, 1.820), (-0.44, 1.814), (-0.82, 1.802), (-1.22, 1.780), (-1.68, 1.748), (-2.11, 1.706)], 0.0100),
        ("DomeFan_L2", [(-0.22, 1.808), (-0.58, 1.802), (-0.96, 1.792), (-1.34, 1.770), (-1.78, 1.738), (-2.19, 1.696)], 0.0095),
    ]
    for di, (name, ctrl2d, w) in enumerate(dome_fans):
        # alternating proud ridge heights -> visible valleys between bands
        ctrl = [SP(lon, y, 0.0050 + 0.0034 * ((di % 2) == 0) + 0.0018 * ((di % 3) == 0))
                for (lon, y) in ctrl2d]
        _hair_lock("Hair", HAIR_SECTIONS, name, "crown", ctrl, w,
                   sides=8, stations=14, flat=0.42, twist=0.45, seed=seed, jitter=0.0010)
        seed += 1.0

    # ---------------- Side vault sweeps above the ears
    side_vault = [
        ("SideSweep_R1", [(0.92, 1.776), (1.22, 1.762), (1.52, 1.738), (1.78, 1.714)], 0.0125),
        ("SideSweep_R2", [(1.02, 1.752), (1.32, 1.742), (1.62, 1.722), (1.86, 1.702)], 0.0115),
        ("SideSweep_L1", [(-0.90, 1.774), (-1.20, 1.758), (-1.50, 1.732), (-1.76, 1.708)], 0.0125),
        ("SideSweep_L2", [(-1.00, 1.750), (-1.30, 1.738), (-1.60, 1.716), (-1.84, 1.696)], 0.0115),
    ]
    for name, ctrl2d, w in side_vault:
        ctrl = [SP(lon, y, 0.0032) for (lon, y) in ctrl2d]
        _hair_lock("Hair", HAIR_SECTIONS, name, "side", ctrl, w,
                   sides=8, stations=13, flat=0.50, twist=0.4, seed=seed, jitter=0.0010)
        seed += 1.0

    # short rim fills closing the strip between vault sweeps and the ear notch
    ear_fill = [
        ("EarFill_R", [(1.50, 1.718), (1.66, 1.710), (1.82, 1.706), (1.96, 1.705)], 0.0110),
        ("EarFill_L", [(-1.48, 1.716), (-1.64, 1.706), (-1.80, 1.702), (-1.94, 1.701)], 0.0115),
    ]
    for name, ctrl2d, w in ear_fill:
        ctrl = [SP(lon, y, 0.0026) for (lon, y) in ctrl2d]
        _hair_lock("Hair", HAIR_SECTIONS, name, "side", ctrl, w,
                   sides=7, stations=11, flat=0.58, twist=0.3, seed=seed, jitter=0.0008)
        seed += 1.0

    # ---------------- Fringe: asymmetric sweep + short part strands
    fringe = [
        ("Fringe_Sweep", [(0.30, 1.738), (0.10, 1.730), (-0.15, 1.727), (-0.42, 1.719), (-0.68, 1.711)], 0.0145, 0.55),
        ("Fringe_Sweep_R", [(0.56, 1.742), (0.50, 1.726), (0.44, 1.712), (0.38, 1.702)], 0.0095, 0.52),
        ("Fringe_Sweep_L", [(-0.10, 1.733), (-0.28, 1.724), (-0.48, 1.715), (-0.62, 1.708)], 0.0105, 0.52),
        ("Fringe_PartShort", [(0.44, 1.742), (0.39, 1.724), (0.35, 1.708)], 0.0095, 0.55),
        ("Fringe_WidowsPeak", [(0.06, 1.736), (0.01, 1.7225), (-0.03, 1.7165)], 0.0085, 0.55),
    ]
    for name, ctrl2d, w, fl in fringe:
        ctrl = [SP(lon, y, 0.0042) for (lon, y) in ctrl2d]
        _hair_lock("Hair", HAIR_SECTIONS, name, "fringe", ctrl, w,
                   sides=7, stations=12, flat=fl, twist=0.25, seed=seed, jitter=0.0007)
        seed += 1.0

    # ---------------- Temple frames (in front of the ears) + behind-ear tucks
    # the ear notch keeps the cap rim high over the ears, so frames run in
    # front of them and tuck locks fold behind towards the nape.
    temple = [
        ("Temple_Frame_R", [(0.95, 1.720), (1.08, 1.680), (1.20, 1.644), (1.30, 1.616)], 0.0120),
        ("Temple_Frame_L", [(-0.95, 1.718), (-1.09, 1.672), (-1.21, 1.634), (-1.32, 1.604)], 0.0125),
        ("Temple_Tuck_R", [(1.95, 1.704), (2.15, 1.668), (2.35, 1.634), (2.52, 1.606)], 0.0125),
        ("Temple_Tuck_L", [(-1.93, 1.700), (-2.13, 1.662), (-2.33, 1.626), (-2.50, 1.596)], 0.0130),
    ]
    for name, ctrl2d, w in temple:
        ctrl = [SP(lon, y, 0.0050) for (lon, y) in ctrl2d]
        _hair_lock("Hair", HAIR_SECTIONS, name, "temple", ctrl, w,
                   sides=7, stations=12, flat=0.58, twist=0.3, seed=seed)
        seed += 1.0

    # ---------------- Nape layers draping over the greatcoat collar
    # roots on the cap rim; explicit 3D control points hug the collar's
    # outward-sloping back face (z -0.127 @ y1.564 -> bodice -0.136 @ y1.495),
    # then fan out and rest ON the mantle drape (z ~ -0.173 @ y1.46) so the
    # hair visibly layers over the coat instead of floating in the gap.
    nape_root = [(-2.98, 1.598), (-2.86, 1.602), (-2.66, 1.604), (-2.52, 1.606),
                 (2.52, 1.606), (2.66, 1.602), (2.88, 1.600), (2.98, 1.598)]
    nape_paths = [
        [(-0.013, 1.556, -0.1305), (-0.020, 1.514, -0.1280), (-0.030, 1.462, -0.178), (-0.037, 1.416, -0.186)],
        [(-0.010, 1.560, -0.1315), (-0.017, 1.516, -0.1290), (-0.026, 1.466, -0.180), (-0.032, 1.424, -0.188)],
        [(-0.002, 1.562, -0.1325), (-0.005, 1.520, -0.1305), (-0.008, 1.472, -0.182), (-0.010, 1.432, -0.190)],
        [(-0.016, 1.552, -0.1300), (-0.026, 1.508, -0.1270), (-0.038, 1.452, -0.176), (-0.046, 1.408, -0.184)],
        [(0.017, 1.552, -0.1300), (0.027, 1.508, -0.1270), (0.039, 1.452, -0.176), (0.047, 1.408, -0.184)],
        [(0.004, 1.560, -0.1315), (0.009, 1.518, -0.1290), (0.015, 1.468, -0.180), (0.019, 1.428, -0.188)],
        [(0.014, 1.556, -0.1305), (0.024, 1.512, -0.1270), (0.037, 1.462, -0.178), (0.045, 1.418, -0.186)],
        [(0.014, 1.552, -0.1300), (0.021, 1.514, -0.1280), (0.031, 1.462, -0.178), (0.038, 1.416, -0.186)],
    ]
    nape_widths = [0.0165, 0.0170, 0.0160, 0.0160, 0.0160, 0.0155, 0.0165, 0.0160]
    for k in range(8):
        rl, ry = nape_root[k]
        ctrl = [SP(rl, ry, 0.002), SP(rl * 0.96, ry - 0.020, 0.004)]
        ctrl += [tuple(p) for p in nape_paths[k]]
        _hair_lock("Hair", HAIR_SECTIONS, f"NapeLayer_{k + 1}", "nape", ctrl, nape_widths[k],
                   sides=7, stations=14, flat=0.58, twist=0.45, seed=seed,
                   jitter=0.0010, preferred=(0.0, 0.0, -1.0))
        seed += 1.0

    # ---------------- Gather bulge where the mass is collected
    # a small rippled dome bulging off the cap at the back-crown; its rim
    # sits on the cap surface so it always reads as attached.
    dome_base = scalp_point(1.630, math.pi, 0.0)
    dome_n = norm((dome_base[0] * 0.4, 0.16, dome_base[2]))      # cap surface normal
    dome_side = norm(cross((0.0, 1.0, 0.0), dome_n))
    dome_up = norm(cross(dome_n, dome_side))
    rim_c = vadd(dome_base, vmul(dome_n, 0.001))
    apex = vadd(rim_c, vmul(dome_n, 0.0135))
    Rp, D = 0.0225, 0.0135
    gat_rows, gat_sides = _segs(8, 5), _segs(20, 8)
    gat_pts = [apex]
    for r in range(1, gat_rows):
        lat = (math.pi * 0.46) * r / (gat_rows - 1.0)
        rr = Rp * math.sin(lat) ** 0.75
        dn = D * math.sin(lat)
        for s in range(gat_sides):
            a = 2.0 * math.pi * s / gat_sides
            wob = 1.0 + 0.09 * math.sin(3.0 * a + 1.2) + 0.05 * math.sin(5.0 * a + 0.4)
            gat_pts.append(vadd(apex,
                                vadd(vmul(dome_n, -dn),
                                     vadd(vmul(dome_side, rr * wob * math.cos(a)),
                                          vmul(dome_up, rr * wob * math.sin(a) * 0.92)))))
    gat_fs = []
    for s in range(gat_sides):
        gat_fs.append((0, 1 + s, 1 + (s + 1) % gat_sides))
    for r in range(gat_rows - 2):
        for s in range(gat_sides):
            p0 = 1 + r * gat_sides + s
            p1 = 1 + r * gat_sides + (s + 1) % gat_sides
            p2 = 1 + (r + 1) * gat_sides + s
            p3 = 1 + (r + 1) * gat_sides + (s + 1) % gat_sides
            gat_fs.extend(((p0, p2, p1), (p1, p2, p3)))
    add_mesh_hair(gat_pts, gat_fs, "Hair/Gather", "gather")

    # ---------------- Bound tail: four twisted rope strands around an axis
    # strands orbit a curved, tapering axis that leans back and comes to rest
    # ON the mantle drape, so the bound tail layers over the coat (visible
    # from the back) instead of hiding in the collar-mantle gap.
    axis = [(0.002, 1.612, -0.148), (0.000, 1.572, -0.163), (-0.008, 1.524, -0.176),
            (-0.014, 1.470, -0.184), (-0.018, 1.424, -0.190)]
    axis_pts = _catmull_sample(axis, 16)
    ax_frames = tube_frames(axis_pts, (0.0, 1.0, 0.0))
    rope_plan = [(0.0, 1.00), (1.57, 0.93), (3.14, 0.84), (4.71, 0.68)]
    for k, (phase, span) in enumerate(rope_plan):
        turns = 2.1 + 0.35 * _hash1(seed + k)
        ctrl = []
        steps = 13
        for j in range(steps):
            t = j / (steps - 1.0)
            ti = min(int(t * (len(axis_pts) - 1)), len(axis_pts) - 2)
            ft = t * (len(axis_pts) - 1) - ti
            ap = lerp(axis_pts[ti], axis_pts[ti + 1], ft)
            _, b1, b2 = ax_frames[ti]
            orbit = lerp(0.0090, 0.0030, t)
            ang = phase + turns * 6.283 * t
            ctrl.append(vadd(ap, vadd(vmul(b1, orbit * math.cos(ang)),
                                      vmul(b2, orbit * math.sin(ang)))))
        cut = max(7, int(round(steps * span)))
        ctrl = ctrl[:cut]
        ctrl[-1] = vadd(ctrl[-1], vmul(norm(vsub(ctrl[-1], ctrl[-2])), 0.004))
        _hair_lock("Hair", HAIR_SECTIONS, f"TailRope_{k + 1}", "tail", ctrl, 0.0092,
                   sides=7, stations=13, flat=0.78, twist=2.4 + 0.4 * k,
                   grooves=3, groove_depth=0.16, seed=seed + k)
    seed += 4.0

    # ---------------- Hairline wisps (base LOD only)
    if DETAIL >= 0.8:
        wisp_lons = [0.55, 0.24, -0.05, -0.34, -0.62, 1.05, -1.02, 1.30]
        for k, lon in enumerate(wisp_lons):
            hl = hairline_y(lon)
            sgn = 1.0 if lon >= 0 else -1.0
            ctrl = [SP(lon, hl + 0.003, 0.0008),
                    SP(lon + sgn * 0.035, hl - 0.005, 0.0004),
                    SP(lon + sgn * 0.065, hl - 0.012, 0.0)]
            _hair_lock("Hair", HAIR_SECTIONS, f"HairlineWisp_{k + 1}", "wisp", ctrl,
                       0.0032 + 0.0010 * _hash1(k * 3.3), sides=5, stations=7,
                       flat=0.5, twist=0.2, jitter=0.0003, seed=seed + k)


def generate_hair_tie():
    """Bone twine cord bound around the gather: wraps, knot, hanging ends."""
    dome_base = scalp_point(1.630, math.pi, 0.0)
    nrm = norm((dome_base[0] * 0.4, 0.16, dome_base[2]))
    side = norm(cross((0.0, 1.0, 0.0), nrm))
    upv = norm(cross(side, nrm))
    cx = vadd(dome_base, vmul(nrm, 0.0075))   # mid-dome, just behind the cap
    R = 0.0210
    # 2.25 wraps of cord around the gathered mass
    for w in range(2):
        pts = []
        for k in range(19):
            a = 2.0 * math.pi * (k / 18.0) + w * 0.5
            pts.append(vadd(vadd(cx, vmul(side, R * math.cos(a))),
                            vmul(upv, R * 0.82 * math.sin(a) - 0.006 + 0.009 * w)))
        start = len(verts["BoneThread"])
        tube("BoneThread", f"Accessories/HairTieWrap_{w + 1}", pts, [0.0026] * 19, 6, (0.0, 1.0, 0.0))
        HAIR_TIE_SECTIONS.append((f"Accessories/HairTieWrap_{w + 1}", start, len(verts["BoneThread"])))
    # small knot: two interlocked loops
    for k in range(2):
        c = vadd(cx, vmul(side, -0.006 + 0.012 * k))
        pts = []
        for i in range(13):
            a = 2.0 * math.pi * i / 12.0
            pts.append(vadd(vadd(c, vmul(side, 0.0055 * math.cos(a))),
                            vmul(upv, 0.0042 * math.sin(a))))
        start = len(verts["BoneThread"])
        tube("BoneThread", f"Accessories/HairTieKnot_{k + 1}", pts, [0.0028] * 13, 6, (0.0, 1.0, 0.0))
        HAIR_TIE_SECTIONS.append((f"Accessories/HairTieKnot_{k + 1}", start, len(verts["BoneThread"])))
    # two short curled cord ends hanging from the knot
    for k, sgn in enumerate((-1.0, 1.0)):
        p0 = vadd(cx, vmul(side, -0.006 + 0.012 * k))
        pts = [p0,
               vadd(p0, (sgn * 0.008, -0.014, -0.004)),
               vadd(p0, (sgn * 0.013, -0.027, -0.002)),
               vadd(p0, (sgn * 0.010, -0.037, 0.003))]
        start = len(verts["BoneThread"])
        tube("BoneThread", f"Accessories/HairTieEnd_{k + 1}", pts,
             [0.0026, 0.0023, 0.0019, 0.0014], 6, (0.0, 1.0, 0.0))
        HAIR_TIE_SECTIONS.append((f"Accessories/HairTieEnd_{k + 1}", start, len(verts["BoneThread"])))


generate_gothic_hair()
generate_hair_tie()


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

# Leg profile: (world x offset from the leg axis, y, z centre, rx, rz).
# The three lowest stations are the boot_rig trouser tuck: the wool leg is
# compressed inside the shaft (the shaft's inner wall clears it by >= 2 mm
# everywhere below the cuff opening, checked by Tools/verify_boots.py) and
# flares back out above the opening so the cloth drapes over the boot cuff.
LEG_PROFILE = [(0.113, 0.915, -0.002, 0.102, 0.106),
               (0.117, 0.660, -0.004, 0.084, 0.088)]
# boot_rig.TROUSER_TUCK starts at the knee flare (y = 0.485), so the stations
# stay strictly monotonic - a duplicated station folds the tube onto itself
LEG_PROFILE += [(0.118, y, zc, rx, rz) for (y, rx, rz, zc) in boot_rig.TROUSER_TUCK]


def trouser_fold_tuck(i, s_idx, a):
    """Knee / ankle creases, faded out where the leg is inside the boot."""
    y = LEG_PROFILE[max(0, min(len(LEG_PROFILE) - 1, int(round(i))))][1]
    return trouser_fold(i, s_idx, a) * smoothstep(0.470, 0.560, y)


for side, label in ((-1, "L"), (1, "R")):
    x = side
    leg_pts = [(x*dx, y, zc) for (dx, y, zc, rx, rz) in LEG_PROFILE]
    thick_tube("Trouser", f"LowerBody/Leg_{label}", leg_pts,
        [(rx, rz) for (dx, y, zc, rx, rz) in LEG_PROFILE],
        sides=18, thick=.006, fold=trouser_fold_tuck, rim_start=True, rim_end=False)
    side_seam_pts = [(x*(dx + 0.97*rx), y + 0.012*(1 if i == 0 else 0), zc)
                     for i, (dx, y, zc, rx, rz) in enumerate(LEG_PROFILE)]
    welt_seam("Trouser", f"LowerBody/SideSeam_{label}", side_seam_pts, radius=0.0032)
    stitch_dashes("BoneThread", f"LowerBody/SideSeamStitch_{label}", side_seam_pts, 8, r=0.0020, length=0.012)


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

def mantle_surf(t, a, out=0.0):
    """World point on the mantle shell at row t, angle a.

    mantle_row_fn returns a *row* (y, rx, rz, zc, a0, a1); the surface point has
    to be built with shell_point - passing the row straight into a mesh call
    silently places the part at (y, rx, rz) as if it were (x, y, z).
    """
    row = mantle_row_fn(t)(a)
    p = shell_point(row[0], row[1], row[2], row[3], a, 0, 0, 0)
    return vadd(p, vmul(norm((p[0], 0.0, p[2])), out)) if out else p


mantle_hem = []
for k in range(23):
    a = MANTLE_A0 + (MANTLE_A1 - MANTLE_A0)*k/22
    p = mantle_row_fn(1.0)(a)
    dr, dy, _ = mantle_fold(a, 3)
    mantle_hem.append(shell_point(p[0] + dy, p[1] + dr + .002, p[2] + dr + .002, 0.0, a, 0, 0, 0))
tube("BoneThread", "Accessories/MantleHemPiping", mantle_hem, [.0034]*23, 6, (0, 1, 0))
stitch_dashes("ClothAccent", "Accessories/MantleHemStitch", mantle_hem, 14, r=0.0022, length=0.012)

for si, sa, label in ((1, MANTLE_A0 + 0.06, "R"), (2, 2*math.pi - MANTLE_A0 - 0.06, "L")):
    p = mantle_surf(0.04, sa)
    clasp_c = vadd(p, vmul(norm((p[0], 0.0, p[2])), 0.006))
    button_disc("AgedBrass", f"Accessories/MantleClasp_{label}", clasp_c, (clasp_c[0], 0.8, clasp_c[2]), radius=.009, thick=.004, thread_mat=None)
    torus_arc("AgedBrass", f"Accessories/MantleClaspRing_{label}", clasp_c, .011, .0024, 6, 10, axis=(0, 1, 0))

chain_pts = []
p_clasp_R = mantle_surf(0.04, MANTLE_A0 + 0.06)
p_clasp_L = mantle_surf(0.04, 2*math.pi - MANTLE_A0 - 0.06)
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
# BOOTS: welted leather cavalry boots on anatomically fitted feet.
#
# The boot is authored ONCE in Tools/boot_rig.py's local frame (x = outboard,
# y = 0 exactly at the floor, +z forward, foot centre line at x = 0) and
# mirrored per side by _stamp(place=..., flip=...), which re-fixes the winding
# from each solid's own signed volume - so left and right are exact mirrors and
# can never come out inside-out.
#
# Construction follows how the real thing is made, in this order:
#   1. full-length sole slab: ground contact faces exactly at y = 0 from the
#      ball to the toe-break, the shank lifted off the floor between the heel
#      breast and the ball, a toe spring over the last 25 mm, feathered ground
#      edges and a measured outboard wear flat,
#   2. three stacked heel laminations with shadow grooves between them,
#   3. brass heel edge plate and nail heads,
#   4. welt bead and welt stitching around the sole / upper junction,
#   5. vamp lofted through the boot_rig foot sections, stitched toe cap,
#      heel counter band and throat seam,
#   6. shaft: closed ankle tube, laced upper with a real lacing slit, raised
#      facings, tongue, brass eyelets and speed hooks, crossed leather laces,
#   7. folded wine cuff with lining and a riveted rear pull tab,
#   8. crossed instep strap + buckle over the vamp, calf strap + buckle.
#
# Every part is registered in RIG_PARTS with a rig chain id ("foot" -> ankle /
# ball / toe, "shaft" -> ankle / knee); the vertex ranges are exported to
# SM_Character_VeilboundWayfarer*.bootrig.json and Tools/verify_boots.py
# refits the built mesh, poses idle / walk / run / dodge and checks the floor
# contact contract defined in Tools/boot_rig.py.
# =========================================================================

Z_SOLE0, Z_SOLE1 = -0.0865, 0.1960      # sole slab extent (both caps included)
SOLE_BACK_CAP, SOLE_FRONT_CAP = 0.0105, 0.0100
HEEL_INSET = 0.0016                     # heel block sits inside the sole edge
HEEL_LAYERS, HEEL_GAP = 3, 0.0007
COUNTER_ZCUT = -0.004                   # counter wraps everything behind this
TOE_CAP_OFF = 0.0016                    # toe cap panel offset over the vamp
BOOT_TRIM = 0.0018                      # trim offset of stitching over leather


def _sole_bot(z):
    """Sole bottom line: 0 on both contact faces, lifted through the shank."""
    tab = boot_rig.SOLE_BOTTOM
    if z < tab[0][0]:
        return tab[0][1]
    if z > tab[-1][0]:
        (z0, y0), (z1, y1) = tab[-2], tab[-1]
        return y1 + (y1 - y0) / (z1 - z0) * (z - z1)
    return boot_rig.sole_bottom(z)


def _sole_half(z, inset=0.0, worn=True, floor=0.0045):
    """Half width of the sole / heel footprint, caps rounded elliptically."""
    w = boot_rig.sole_half_width(z, worn) - inset
    if z < boot_rig.FOOT_BACK:
        u = (boot_rig.FOOT_BACK - z) / SOLE_BACK_CAP
    elif z > boot_rig.FOOT_TIP:
        u = (z - boot_rig.FOOT_TIP) / SOLE_FRONT_CAP
    else:
        u = 0.0
    if u > 0.0:
        w *= math.sqrt(max(0.0, 1.0 - min(1.0, u) ** 2))
    return max(floor, w)


def _sole_top(z):
    """Top of the sole slab (the leather line), kept at a usable thickness."""
    zc = min(max(z, boot_rig.FOOT_BACK), boot_rig.FOOT_TIP)
    return max(_sole_bot(z) + 0.0030, boot_rig.leather_bottom(zc))


def _sole_loop(z0, z1, n, inset=0.0, worn=True):
    """Closed (x, z) plan loop of the sole footprint, +x side first."""
    zs = [z0 + (z1 - z0) * k / (n - 1.0) for k in range(n)]
    return ([( _sole_half(z, inset, worn), z) for z in zs] +
            [(-_sole_half(z, inset, worn), z) for z in reversed(zs)])


def _offset_loop(loop, dist):
    """Offset a closed (x, z) loop outward along its own plane normal."""
    n = len(loop)
    cx = sum(p[0] for p in loop) / n
    cz = sum(p[1] for p in loop) / n
    out = []
    for i, p in enumerate(loop):
        t = norm(((loop[(i + 1) % n][0] - loop[(i - 1) % n][0]), 0.0,
                  (loop[(i + 1) % n][1] - loop[(i - 1) % n][1])))
        nrm = (t[2], 0.0, -t[0])
        if nrm[0] * (p[0] - cx) + nrm[2] * (p[1] - cz) < 0.0:
            nrm = vmul(nrm, -1.0)
        out.append((p[0] + nrm[0] * dist, p[1] + nrm[2] * dist))
    return out


def _loop_point(loop, t):
    """Point at normalised position t in [0, 1) on a closed polyline."""
    n = len(loop)
    f = (t % 1.0) * n
    i = int(f) % n
    return lerp(loop[i], loop[(i + 1) % n], f - int(f))


def _contour_arc(loop, z_cut, count):
    """`count` points of a closed contour spanning z <= z_cut, around the back.

    The contour is ordered front centre -> outboard -> back -> inboard, so the
    run of vertices with z <= z_cut is a single arc through the heel. Samples
    are placed by normalised position, so every ring of a lofted band has the
    same point count (required by loft_shell).
    """
    n = len(loop)
    flags = [p[2] <= z_cut for p in loop]
    if not any(flags):
        return None
    if all(flags):
        return [_loop_point(loop, k / float(count)) for k in range(count)]
    i_a = flags.index(True) / float(n)
    i_b = (n - 1 - flags[::-1].index(True)) / float(n)
    span = i_b - i_a
    return [_loop_point(loop, i_a + span * k / (count - 1.0)) for k in range(count)]


def _slice_loop(loop, keep):
    """Longest contiguous run (wrapping) of a closed loop satisfying `keep`."""
    n = len(loop)
    flags = [keep(p) for p in loop]
    if not any(flags):
        return []
    if all(flags):
        return list(loop)
    i0 = flags.index(True)
    rot = [loop[(i0 + k) % n] for k in range(n)]
    fl = [keep(p) for p in rot]
    runs, cur = [], [rot[0]]
    for k in range(1, n):
        if fl[k]:
            cur.append(rot[k])
        else:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    if len(runs) > 1 and fl[-1]:
        runs[0] = runs[-1] + runs[0]
        runs.pop()
    return max(runs, key=len)


def _bead_profile(ru, rv, n=8):
    """Round-ish bead cross-section (welt, rim wire) in (outward, vertical)."""
    return [(ru * math.cos(2.0 * math.pi * k / n),
             rv * math.sin(2.0 * math.pi * k / n)) for k in range(n)]


def _merge(parts):
    """Concatenate several (points, faces) solids into one buffer."""
    pts, fs = [], []
    for p, f in parts:
        off = len(pts)
        pts.extend(p)
        fs.extend(tuple(i + off for i in face) for face in f)
    return pts, fs


def _tube_local(centers, radii, sides, preferred=(0, 0, 1)):
    """(points, faces) of a capped tube through local centres."""
    centers = [tuple(c) for c in centers]
    if isinstance(radii, (int, float)):
        radii = [float(radii)] * len(centers)
    sides = _segs(sides, 4)
    rings = []
    for i, c in enumerate(centers):
        t = norm(vsub(centers[min(i + 1, len(centers) - 1)], centers[max(0, i - 1)]))
        hint = preferred
        if abs(dot(hint, t)) > 0.9:
            hint = (1.0, 0.0, 0.0)
        b1 = norm(vsub(hint, vmul(t, dot(hint, t))))
        b2 = norm(cross(t, b1))
        rings.append([vadd(c, vadd(vmul(b1, radii[i] * math.cos(2.0 * math.pi * k / sides)),
                                  vmul(b2, radii[i] * math.sin(2.0 * math.pi * k / sides))))
                      for k in range(sides)])
    rings = [[_ring_centre(rings[0])]] + rings + [[_ring_centre(rings[-1])]]
    pts = [p for r in rings for p in r]
    return pts, _connect_rings(pts, rings)


def _dash_local(path, count, r, length):
    """Merged saddle-stitch dashes along a local path -> (points, faces)."""
    count = max(2, int(round(count * DETAIL)))
    path = [tuple(p) for p in path]
    segs = []
    for k in range(count):
        f = (k + 0.5) / count * (len(path) - 1)
        i = min(int(f), len(path) - 2)
        c = lerp(path[i], path[i + 1], f - i)
        half = vmul(norm(vsub(path[i + 1], path[i])), length * 0.5)
        segs.append(_tube_local((vsub(c, half), vadd(c, half)), (r, r), 6))
    return _merge(segs)


def _rivet_local(center, normal, radius, height):
    """Domed stud (eyelet, nail head, rivet) in local space."""
    nrm = norm(normal)
    up = (0.0, 1.0, 0.0) if abs(nrm[1]) < 0.9 else (1.0, 0.0, 0.0)
    b1 = norm(cross(nrm, up))
    b2 = cross(nrm, b1)
    rings = []
    for u, h in ((1.0, 0.0), (0.86, 0.42), (0.52, 0.78)):
        rings.append([vadd(vadd(center, vmul(nrm, height * h)),
                           vadd(vmul(b1, radius * u * math.cos(2.0 * math.pi * k / 8)),
                                vmul(b2, radius * u * math.sin(2.0 * math.pi * k / 8))))
                      for k in range(8)])
    rings = [[vadd(center, vmul(nrm, -0.0006))]] + rings + [[vadd(center, vmul(nrm, height))]]
    pts = [p for r in rings for p in r]
    return pts, _connect_rings(pts, rings)


def _torus_local(center, R, r, axis, segs=10, sides=6):
    """Torus ring (lace loop, speed hook, strap keeper) in local space."""
    ax = norm(axis)
    ref = vsub((0.0, 1.0, 0.0), vmul(ax, dot((0.0, 1.0, 0.0), ax)))
    b1 = norm(ref) if dot(ref, ref) > 1e-8 else (1.0, 0.0, 0.0)
    b2 = norm(cross(ax, b1))
    n_seg, n_side = _segs(segs, 5), _segs(sides, 4)
    rings = []
    for s in range(n_seg):
        a = 2.0 * math.pi * s / n_seg
        c = vadd(center, vadd(vmul(b1, R * math.cos(a)), vmul(b2, R * math.sin(a))))
        rad = norm(vadd(vmul(b1, math.cos(a)), vmul(b2, math.sin(a))))
        rings.append([vadd(c, vadd(vmul(rad, r * math.cos(2.0 * math.pi * k / n_side)),
                                   vmul(ax, r * math.sin(2.0 * math.pi * k / n_side))))
                      for k in range(n_side)])
    pts = [p for ring in rings for p in ring]
    return pts, _connect_rings(pts, rings, closed=True)


def _loop_tube_local(path, r, plane_normal, sides=6):
    """Closed tube swept through a closed path lying in a plane."""
    n = len(path)
    hint = norm(plane_normal)
    rings = []
    for i, p in enumerate(path):
        t = norm(vsub(path[(i + 1) % n], path[(i - 1) % n]))
        b1 = vsub(hint, vmul(t, dot(hint, t)))
        b1 = norm(b1) if dot(b1, b1) > 1e-10 else (1.0, 0.0, 0.0)
        b2 = norm(cross(t, b1))
        rings.append([vadd(p, vadd(vmul(b1, r * math.cos(2.0 * math.pi * k / sides)),
                                   vmul(b2, r * math.sin(2.0 * math.pi * k / sides))))
                      for k in range(sides)])
    pts = [p for ring in rings for p in ring]
    return pts, _connect_rings(pts, rings, closed=True)


def _bow_loop_local(center, radius, elong, r, normal, up, squash):
    """One tied-bow loop: a flattened oval tube plus its inboard twist."""
    up_v = norm(vsub(up, vmul(normal, dot(up, normal))))
    side_v = norm(cross(normal, up_v))
    path = []
    for k in range(14):
        a = 2.0 * math.pi * k / 14
        q = vadd(center, vadd(vmul(side_v, radius * math.cos(a)),
                              vmul(up_v, radius * elong * math.sin(a))))
        q = vadd(q, vmul(normal, -squash * (1.0 + math.cos(a)) * 0.5))
        path.append(q)
    return _loop_tube_local(path, r, normal, 6)


def _band_local(path, normals, width, thick, closed=False, cap=True):
    """Rectangular-section band (strap, tab, cuff bead) through local points."""
    stations = []
    n = len(path)
    for i, p in enumerate(path):
        t = norm(vsub(path[(i + 1) % n] if closed else path[min(n - 1, i + 1)],
                     path[(i - 1) % n] if closed else path[max(0, i - 1)]))
        nn = norm(normals[i])
        side = norm(cross(nn, t))
        stations.append([vadd(p, vadd(vmul(nn, thick * 0.5), vmul(side, width * 0.5))),
                         vadd(p, vadd(vmul(nn, thick * 0.5), vmul(side, -width * 0.5))),
                         vadd(p, vadd(vmul(nn, -thick * 0.5), vmul(side, -width * 0.5))),
                         vadd(p, vadd(vmul(nn, -thick * 0.5), vmul(side, width * 0.5)))])
    if not closed and cap:
        stations = [[_ring_centre(stations[0])]] + stations + [[_ring_centre(stations[-1])]]
    pts = [q for st in stations for q in st]
    return pts, _connect_rings(pts, stations, closed=closed)


def _buckle_local(center, normal, up, width, height, bar_r, prong=True):
    """Small brass frame buckle (rectangular ring + spindle + prong)."""
    nrm = norm(normal)
    up_v = norm(vsub(up, vmul(nrm, dot(up, nrm))))
    side_v = norm(cross(nrm, up_v))
    hw, hh = width * 0.5, height * 0.5
    c_out = vadd(center, vmul(nrm, bar_r * 0.9))
    tl = vadd(vadd(c_out, vmul(up_v, hh)), vmul(side_v, -hw))
    tr = vadd(vadd(c_out, vmul(up_v, hh)), vmul(side_v, hw))
    br = vsub(vadd(c_out, vmul(side_v, hw)), vmul(up_v, hh))
    bl = vsub(vadd(c_out, vmul(side_v, -hw)), vmul(up_v, hh))
    parts = [_tube_local((a, b), (bar_r, bar_r), 6)
             for a, b in ((tl, tr), (tr, br), (br, bl), (bl, tl))]
    mid_l, mid_r = lerp(tl, bl, 0.5), lerp(tr, br, 0.5)
    parts.append(_tube_local((mid_l, mid_r), (bar_r * 0.8, bar_r * 0.8), 6))
    if prong:
        base = lerp(mid_l, mid_r, 0.5)
        tip = vadd(vadd(base, vmul(up_v, hh * 1.05)), vmul(nrm, bar_r * 1.1))
        parts.append(_tube_local((base, tip), (bar_r * 0.7, bar_r * 0.45), 6))
    return _merge(parts)


def _panel_out_sign(grid, centre):
    """+1 / -1 so panel_solid's outer face points away from `centre`."""
    r0, c0 = len(grid) // 2, len(grid[0]) // 2
    dr = vsub(grid[min(r0 + 1, len(grid) - 1)][c0], grid[max(r0 - 1, 0)][c0])
    dc = vsub(grid[r0][min(c0 + 1, len(grid[0]) - 1)], grid[r0][max(c0 - 1, 0)])
    return 1.0 if dot(cross(dr, dc), vsub(grid[r0][c0], centre)) >= 0.0 else -1.0


def _foot_normal(z, s):
    """Outward normal of the boot upper's surface at (station z, section s)."""
    e = 0.004
    p = boot_rig.foot_section_point(z, s)
    dz = vsub(boot_rig.foot_section_point(z + e, s), boot_rig.foot_section_point(z - e, s))
    ds = vsub(boot_rig.foot_section_point(z, min(1.0, s + 0.06)),
              boot_rig.foot_section_point(z, max(-1.0, s - 0.06)))
    nn = cross(ds, dz)
    axis = (0.0, boot_rig.leather_bottom(z) + 0.015, z)
    return norm(nn if dot(nn, vsub(p, axis)) >= 0.0 else vmul(nn, -1.0))


def _shaft_axis(y):
    """Point on the shaft's local centre line at height y."""
    return (0.0, y, boot_rig.shaft_row(y)[3])


def _shaft_arc(y, t0, t1, n, off):
    """`n` sample points of the shaft surface between polar angles t0..t1."""
    return [boot_rig.shaft_point(y, t0 + (t1 - t0) * k / (n - 1.0), off) for k in range(n)]


def build_boot(side):
    """Build one boot (side = +1 right / -1 left); `side` mirrors the local frame."""
    label = "R" if side > 0 else "L"

    def place(p):
        return (side * (boot_rig.FOOT_X + p[0]), p[1], boot_rig.FOOT_Z + p[2])

    flip = side < 0

    def nm(name):
        return f"Boots/{name}_{label}"

    def stamp(mat, name, pts, fs, chain):
        _stamp(mat, nm(name), pts, fs, place=place, flip=flip, orient=True,
               part=(side, chain))

    n_edge = _segs(4, 2)
    n_col = _segs(24, 10)

    # ---- 1. full-length sole slab ---------------------------------------
    n_z = _segs(28, 12)
    rings = []
    for k in range(n_z):
        z = Z_SOLE0 + (Z_SOLE1 - Z_SOLE0) * k / (n_z - 1.0)
        rings.append(rect_ring(z, _sole_bot(z), _sole_top(z), _sole_half(z),
                               taper=0.95, n_edge=n_edge))
    loft_solid("BootSole", nm("Sole"), rings, place=place, flip=flip,
               part=(side, "foot"))

    # ---- 2. stacked heel laminations ------------------------------------
    n_hz = _segs(11, 6)
    h_layer = (boot_rig.HEEL_BLOCK_TOP - (HEEL_LAYERS - 1) * HEEL_GAP) / HEEL_LAYERS
    for layer in range(HEEL_LAYERS):
        y0 = layer * (h_layer + HEEL_GAP)
        rings = []
        for k in range(n_hz):
            z = Z_SOLE0 + (boot_rig.HEEL_BREAST - Z_SOLE0) * k / (n_hz - 1.0)
            half = _sole_half(z, HEEL_INSET, worn=False, floor=0.0040)
            rings.append(rect_ring(z, y0, y0 + h_layer, half, taper=0.96, n_edge=n_edge))
        loft_solid("BootSole", nm(f"Heel{layer + 1}"), rings, place=place, flip=flip,
                   part=(side, "foot"))

    # ---- 3. brass heel edge plate + nail heads --------------------------
    heel_loop = _sole_loop(Z_SOLE0, boot_rig.HEEL_BREAST, _segs(24, 12),
                           HEEL_INSET, worn=False)
    plate = _slice_loop(heel_loop, lambda p: p[1] <= -0.0435)
    sweep_loop("AgedBrass", nm("HeelPlate"), [(x, 0.0023, z) for (x, z) in plate],
               _bead_profile(0.0018, 0.0018, 6), closed=False, place=place,
               flip=flip, part=(side, "foot"))
    i_back = min(range(len(plate)), key=lambda i: plate[i][1])
    nails = []
    for k in (-6, 0, 6):
        x, z = plate[(i_back + k) % len(plate)]
        nrm = norm((x, 0.0, z - sum(p[1] for p in plate) / len(plate)))
        nails.append(_rivet_local((x, 0.0058, z + 0.0004), nrm, 0.0026, 0.0017))
    stamp("AgedBrass", "HeelNails", *_merge(nails), "foot")

    # ---- 4. welt bead + welt stitching ----------------------------------
    arc = _slice_loop(_offset_loop(_sole_loop(boot_rig.FOOT_BACK, Z_SOLE1,
                                              _segs(36, 15)), 0.0014),
                      lambda p: p[1] >= boot_rig.HEEL_BREAST)
    sweep_loop("Leather", nm("Welt"),
               [(x, _sole_top(z) - 0.0012, z) for (x, z) in arc],
               _bead_profile(0.0028, 0.0036), closed=False, place=place, flip=flip,
               part=(side, "foot"))
    stamp("BoneThread", "WeltStitch",
          *_dash_local([(x, _sole_top(z) + 0.0026, z) for (x, z) in arc],
                       30, 0.0016, 0.0075), "foot")

    # ---- 5. vamp, toe cap, heel counter, throat seam --------------------
    n_ring, n_flat = _segs(22, 8), _segs(5, 3)
    vamp_z = _segs(24, 10)
    rings = [boot_rig.foot_ring(boot_rig.FOOT_BACK
                                + (boot_rig.FOOT_TIP - boot_rig.FOOT_BACK) * k / (vamp_z - 1.0),
                                n_ring, n_flat) for k in range(vamp_z)]
    loft_solid("Leather", nm("Vamp"), rings, place=place, flip=flip,
               part=(side, "foot"))

    rows, cols = _segs(9, 5), _segs(15, 7)
    grid = []
    for r in range(rows):
        z = boot_rig.TOE_CAP_SEAM + (boot_rig.FOOT_TIP - boot_rig.TOE_CAP_SEAM) * \
            (r / (rows - 1.0)) ** 0.92
        grid.append([boot_rig.foot_section_point(z, -1.0 + 2.0 * c / (cols - 1.0),
                                                 TOE_CAP_OFF) for c in range(cols)])
    panel_solid("Leather", nm("ToeCap"), grid, 0.0024, place=place, flip=flip,
                out_sign=_panel_out_sign(grid, (0.0, 0.024, boot_rig.TOE_CAP_SEAM)),
                part=(side, "foot"))
    for row_i, (dz, cnt) in enumerate(((0.0018, 13), (0.0086, 12))):
        pts = [boot_rig.foot_section_point(boot_rig.TOE_CAP_SEAM - dz,
                                           -0.97 + 1.94 * c / 12.0, 0.0028)
               for c in range(13)]
        stamp("BoneThread", f"ToeCapStitch{row_i + 1}",
              *_dash_local(pts, cnt, 0.0017, 0.0080), "foot")

    counter_ys = (0.0400, 0.0580, 0.0760, 0.0940)
    counter_n = _segs(16, 8)
    rings = [_contour_arc(boot_rig.foot_contour(y, _segs(48, 20), 0.0016),
                          COUNTER_ZCUT, counter_n) for y in counter_ys]
    rings = [r for r in rings if r]
    loft_shell("Leather", nm("Counter"), rings, 0.0030, closed=False, place=place,
               flip=flip, part=(side, "foot"))
    stamp("BoneThread", "CounterStitch",
          *_dash_local(_slice_loop(boot_rig.foot_contour(0.0880, _segs(36, 14), 0.0028),
                                   lambda p: p[2] <= COUNTER_ZCUT + 0.004),
                       16, 0.0016, 0.0070), "foot")
    throat = boot_rig.foot_contour(0.1065, _segs(36, 14), 0.0018)
    stamp("BoneThread", "ThroatSeam", *_dash_local(throat + [throat[0]], 18, 0.0016, 0.0070),
          "foot")

    # ---- 6. shaft: ankle tube, laced upper, facings, tongue, hardware ----
    rings = [boot_rig.shaft_ring(y, n=n_col, gap=0.0)[0]
             for y in (0.0950, 0.1000, 0.1060, 0.1120, 0.1180)]
    loft_shell("Leather", nm("ShaftAnkle"), rings, boot_rig.SHAFT_THICK,
               closed=True, place=place, flip=flip, part=(side, "shaft"))

    ys_up = (0.1180, 0.1300, 0.1500, 0.1800, 0.2200, 0.2600, 0.3000, 0.3400,
             0.3800, 0.4200, 0.4550)
    rings = [boot_rig.shaft_ring(y, n=n_col)[0] for y in ys_up]
    loft_shell("Leather", nm("Shaft"), rings, boot_rig.SHAFT_THICK, closed=False,
               place=place, flip=flip, part=(side, "shaft"))

    ys_f = (0.1220, 0.1600, 0.2000, 0.2400, 0.2800, 0.3200, 0.3600, 0.4000, 0.4400, 0.4550)
    for sgn, tag in ((1.0, "Out"), (-1.0, "In")):
        grid = []
        for y in ys_f:
            half_w = max(0.020, boot_rig.shaft_row(y)[1])
            dgap = boot_rig.EYELET_FACING_W / half_w
            gap = boot_rig.shaft_row(y)[4]
            grid.append([boot_rig.shaft_point(y, sgn * (gap + dgap * k / 5.0), 0.0020)
                         for k in range(6)])
        panel_solid("Leather", nm(f"Facing{tag}"), grid, 0.0026, place=place, flip=flip,
                    out_sign=_panel_out_sign(grid, _shaft_axis(grid[len(grid) // 2][0][1])),
                    part=(side, "shaft"))

    tongue_ys = (0.1220, 0.1700, 0.2200, 0.2700, 0.3180)
    grid = [[boot_rig.shaft_point(y, -0.34 + 0.68 * k / 5.0, -0.0016) for k in range(6)]
            for y in tongue_ys]
    panel_solid("Leather", nm("Tongue"), grid, 0.0028, place=place, flip=flip,
                out_sign=_panel_out_sign(grid, _shaft_axis(0.22)), part=(side, "shaft"))

    for i, y in enumerate(boot_rig.EYELET_Y):
        parts = []
        for sgn in (1.0, -1.0):
            t = sgn * (boot_rig.shaft_row(y)[4] + 0.0055)
            parts.append(_rivet_local(boot_rig.shaft_point(y, t, 0.0032),
                                      boot_rig.shaft_outer_normal(y, t), 0.0034, 0.0022))
        stamp("AgedBrass", f"EyeletRow{i + 1}", *_merge(parts), "shaft")
    for i, y in enumerate(boot_rig.HOOK_Y):
        parts = []
        for sgn in (1.0, -1.0):
            t = sgn * (boot_rig.shaft_row(y)[4] + 0.0055)
            p = boot_rig.shaft_point(y, t, 0.0030)
            nrm = boot_rig.shaft_outer_normal(y, t)
            parts.append(_rivet_local(p, nrm, 0.0030, 0.0020))
            parts.append(_torus_local(vadd(p, vmul(nrm, 0.0026)), 0.0044, 0.0013, nrm, 9, 6))
        stamp("AgedBrass", f"HookRow{i + 1}", *_merge(parts), "shaft")

    lace_rows = tuple(boot_rig.EYELET_Y) + tuple(boot_rig.HOOK_Y)
    segs = []
    for g in range(len(lace_rows) - 1):
        y0, y1 = lace_rows[g], lace_rows[g + 1]
        for sgn in (1.0, -1.0):
            pts = []
            for k in range(5):
                u = k / 4.0
                y = y0 + (y1 - y0) * u
                t = sgn * (boot_rig.shaft_row(y)[4] + 0.0060) * (1.0 - 2.0 * u)
                pts.append(boot_rig.shaft_point(y, t,
                                                0.0032 + 0.0022 * math.sin(math.pi * u)))
            segs.append(_tube_local(pts, 0.0019, 5))
    stamp("BoneThread", "Laces", *_merge(segs), "shaft")

    yb = boot_rig.LACE_BOW_Y
    bow = boot_rig.shaft_point(yb, 0.0, 0.0050)
    bow_n = boot_rig.shaft_outer_normal(yb, 0.0)
    up_v = norm(vsub((0.0, 1.0, 0.0), vmul(bow_n, dot((0.0, 1.0, 0.0), bow_n))))
    side_v = norm(cross(bow_n, up_v))
    # tied bow: a knot, two loops lying flat against the shaft and two loose
    # lace ends hanging down the tongue
    bow_parts = [_rivet_local(bow, bow_n, 0.0055, 0.0048)]
    for sgn in (1.0, -1.0):
        bow_parts.append(_bow_loop_local(
            vadd(vadd(bow, vmul(side_v, sgn * 0.0126)), vmul(up_v, 0.0042)),
            0.0112, 0.74, 0.0019, bow_n, up_v, 0.0032))
        a = vadd(vadd(bow, vmul(side_v, sgn * 0.0052)), vmul(up_v, -0.0022))
        b = vadd(vadd(vadd(bow, vmul(side_v, sgn * 0.0110)), vmul(up_v, -0.0120)),
                 vmul(bow_n, 0.0022))
        c = vadd(vadd(vadd(bow, vmul(side_v, sgn * 0.0086)), vmul(up_v, -0.0225)),
                 vmul(bow_n, -0.0004))
        d = vadd(vadd(vadd(bow, vmul(side_v, sgn * 0.0118)), vmul(up_v, -0.0305)),
                 vmul(bow_n, 0.0014))
        bow_parts.append(_tube_local((a, b, c, d), (0.0019, 0.0017, 0.0014, 0.0010), 5))
    stamp("ClothAccent", "LaceBow", *_merge(bow_parts), "shaft")

    # ---- 7. folded wine cuff, lining, pull tab --------------------------
    rings = []
    for y, off in ((0.4545, 0.0022), (0.4620, 0.0060), (0.4470, 0.0074), (0.4335, 0.0050)):
        gap = boot_rig.shaft_row(y)[4]
        rings.append([boot_rig.shaft_point(y, gap + (2.0 * math.pi - 2.0 * gap) * k / (n_col - 1.0), off)
                      for k in range(n_col)])
    loft_shell("ClothAccent", nm("CuffFold"), rings, 0.0026, closed=False, place=place,
               flip=flip, part=(side, "shaft"))
    rings = []
    for y, off in ((0.4180, -0.0056), (0.4400, -0.0052), (0.4550, -0.0048)):
        gap = boot_rig.shaft_row(y)[4]
        rings.append([boot_rig.shaft_point(y, gap + (2.0 * math.pi - 2.0 * gap) * k / (n_col - 1.0), off)
                      for k in range(n_col)])
    loft_shell("ClothAccent", nm("CuffLining"), rings, 0.0014, closed=False, place=place,
               flip=flip, part=(side, "shaft"))

    tab_a = boot_rig.shaft_point(0.4430, math.pi, 0.0020)
    tab_b = vadd(boot_rig.shaft_point(0.4650, math.pi, 0.0022), (0.0, 0.0, -0.0060))
    tab_c = vadd(boot_rig.shaft_point(0.4520, math.pi, 0.0018), (0.0, 0.0, -0.0100))
    stamp("Leather", "PullTab",
          *_band_local([tab_a, tab_b, tab_c],
                       [norm((0.0, 0.30, -1.0)), norm((0.0, 0.75, -1.0)),
                        norm((0.0, -0.35, -1.0))], 0.015, 0.0032), "shaft")
    stamp("AgedBrass", "PullTabRivet",
          *_rivet_local(vadd(tab_a, (0.0, -0.0028, -0.0006)), norm((0.0, 0.15, -1.0)),
                        0.0032, 0.0022), "shaft")

    # ---- 8. instep strap, keepers, buckles, calf strap -------------------
    z_s, n_s = boot_rig.INSTEP_STRAP_Y, 13
    s_list = [-1.0 + 2.0 * k / (n_s - 1.0) for k in range(n_s)]
    path = [boot_rig.foot_section_point(z_s, s, 0.0026) for s in s_list]
    normals = [_foot_normal(z_s, s) for s in s_list]
    stamp("Leather", "InstepStrap", *_band_local(path, normals, 0.016, 0.0030), "foot")
    stamp("BoneThread", "InstepStrapStitch",
          *_dash_local([vadd(p, vmul(nn, 0.0018)) for p, nn in zip(path, normals)],
                       14, 0.0014, 0.0065), "foot")

    s_b = 0.52                       # buckle rides the outboard crest of the instep
    p_b = boot_rig.foot_section_point(z_s, s_b, 0.0026)
    n_b = _foot_normal(z_s, s_b)
    up_b = norm(vsub(boot_rig.foot_section_point(z_s, s_b + 0.12, 0.0026),
                     boot_rig.foot_section_point(z_s, s_b - 0.12, 0.0026)))
    stamp("AgedBrass", "InstepBuckle", *_buckle_local(p_b, n_b, up_b, 0.0125, 0.0190, 0.0022),
          "foot")
    p_k = boot_rig.foot_section_point(z_s, -0.52, 0.0032)
    stamp("AgedBrass", "InstepKeeper",
          *_torus_local(p_k, 0.0058, 0.0014, _foot_normal(z_s, -0.52), 9, 6), "foot")

    y_c = boot_rig.CUFF_STRAP_Y
    ts = [2.0 * math.pi * k / n_col for k in range(n_col)]
    path = [boot_rig.shaft_point(y_c, t, 0.0026) for t in ts]
    normals = [boot_rig.shaft_outer_normal(y_c, t) for t in ts]
    stamp("Leather", "CuffStrap", *_band_local(path, normals, 0.015, 0.0030, closed=True),
          "shaft")
    p_cb = boot_rig.shaft_point(y_c, math.pi * 0.5, 0.0060)
    stamp("AgedBrass", "CuffBuckle",
          *_buckle_local(p_cb, boot_rig.shaft_outer_normal(y_c, math.pi * 0.5),
                         (0.0, 1.0, 0.0), 0.0150, 0.0195, 0.0022), "shaft")


for side in (1, -1):
    build_boot(side)


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
        for p in RIG_PARTS if p["name"].startswith("Hand/")
    ],
}
with open(rig_path, "w", encoding="utf-8") as f:
    json.dump(rig, f, indent=1)

# --- boot rig sidecar: leg/boot joints + boot part ranges -----------------
boot_path = os.path.join(OUT, f"SM_Character_VeilboundWayfarer{SUFFIX}.bootrig.json")
boot_rig_data = {
    "format": "vespershade.bootrig/1",
    "mesh": os.path.basename(obj_path),
    "units": "metres", "up": "Y", "character_faces": "+Z",
    "bind_pose": "identity (mesh authored in bind pose; zero-rotation FK "
                 "reproduces the OBJ exactly)",
    "floor": {"contact_plane_y": 0.0,
              "contact_patch_min_mm": 40.0,
              "contact_patch_tol_mm": 1.5,
              "note": "sole ground faces and the heel laminations are authored "
                      "exactly at y = 0; the shank is lifted between the heel "
                      "breast and the ball and the toe springs up over the last "
                      "25 mm, so a planted boot always has a flat contact patch "
                      "and never clips the floor"},
    "default_bone": "Root (any vertex outside the parts list binds 100% to Root)",
    "weights": "computed deterministically from vertex positions by "
               "Tools/boot_rig.py:weights_for(side, chain, point)",
    "bones": [
        {"name": name, "parent": parent, "head": [round(c, 6) for c in head],
         **(dict(axes={k: [round(c, 6) for c in v] for k, v in axes.items()},
                 axis_convention="flex + = dorsiflexion / forward swing, "
                                 "abd + = outboard, twist + = toes out")
            if axes else {})}
        for (name, parent, head, axes) in boot_rig.joint_list()
    ],
    "parts": [
        {"name": p["name"], "mat": p["mat"],
         "start": offsets[p["mat"]] + p["start"],
         "end": offsets[p["mat"]] + p["end"],
         "side": p["side"], "chain": p["chain"]}
        for p in RIG_PARTS if p["name"].startswith("Boots/")
    ],
}
with open(boot_path, "w", encoding="utf-8") as f:
    json.dump(boot_rig_data, f, indent=1)

# --- hair sidecar: "Vigil Sweep" section ranges + design contract ----------
# Vertex ranges are global OBJ indices, 0-based, end-exclusive. The verify and
# preview tooling (Tools/verify_hair.py, Tools/render_hair_previews.py) reads
# this file the same way verify_boots.py reads the bootrig sidecar.
def _hair_triangles(range_pairs, mat):
    total = 0
    for _, _, start, end in range_pairs:
        total += sum(1 for a, b, c in faces[mat] if start <= a - 1 < end)
    return total

hair_tri_count = _hair_triangles(HAIR_SECTIONS, "Hair")
hair_section_records = []
for (name, role, start, end) in HAIR_SECTIONS:
    hair_section_records.append({
        "name": name, "role": role,
        "mat": "Hair", "start": offsets["Hair"] + start,
        "end": offsets["Hair"] + end,
    })
for (name, start, end) in HAIR_TIE_SECTIONS:
    hair_section_records.append({
        "name": name, "role": "tie",
        "mat": "BoneThread", "start": offsets["BoneThread"] + start, "end": offsets["BoneThread"] + end,
    })

hair_path = os.path.join(OUT, f"SM_Character_VeilboundWayfarer{SUFFIX}.hairrig.json")
hair_rig = {
    "format": "vespershade.hair/1",
    "mesh": os.path.basename(obj_path),
    "units": "metres", "up": "Y", "character_faces": "+Z",
    "style": "Vigil Sweep (original): offset part, deep diagonal sweep, "
             "gathered bound tail with bone twine tie, layered nape, "
             "face-framing temple strands",
    "attachment": "rigid (same transform as the player mesh; no cloth/jiggle "
                  "simulation - stable under locomotion by construction)",
    "ranges_note": "start/end are global OBJ vertex indices, 0-based, "
                   "end-exclusive; every face of a section uses only its range",
    "design": {
        "part_line_lon_y": [[lon, y] for (lon, y) in HAIR_PART_2D],
        "hairline_ctrl_lon_y": [[c[0], c[1]] for c in HAIRLINE_CTRL],
        "scalp_pad_m": HAIR_PAD,
        "crown_apex_y": HAIR_CROWN_TOP,
        "skull_apex_y": 1.815,
        "gather_center": [round(c, 6) for c in scalp_point(1.630, math.pi, 0.0)],
        "clearance": {
            "collar_top_back_y": 1.564,
            "tail_axis_min_clearance_m": 0.010,
            "face_zone_rule": "no hair vertex with z > 0.082, y < 1.702, |x| < 0.055",
        },
    },
    "sections": hair_section_records,
    "budget": {
        "hair_triangles": hair_tri_count,
        "hair_vertices": sum(end - start for (_, _, start, end) in HAIR_SECTIONS),
        "detail_level": round(DETAIL, 3),
    },
}
with open(hair_path, "w", encoding="utf-8") as f:
    json.dump(hair_rig, f, indent=1)

role_counts = {}
for (_, role, _, _) in HAIR_SECTIONS:
    role_counts[role] = role_counts.get(role, 0) + 1
print(f"Wrote {obj_path}: {sum(map(len, verts.values()))} vertices, {sum(map(len, faces.values()))} triangles, {len(MATERIALS)} material regions")
print(f"  hair: {hair_tri_count} tris in {len(HAIR_SECTIONS)} sections "
      f"({', '.join(f'{k}={v}' for k, v in sorted(role_counts.items()))}) + "
      f"{len(HAIR_TIE_SECTIONS)} tie sections on BoneThread")
