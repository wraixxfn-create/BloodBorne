#!/usr/bin/env python3
"""Geometry kernel for the Vespershade protagonist's layered clothing.

Everything here is original procedural code. The kernel exists because the
protagonist's garments need *volume*: every cloth/leather surface is authored as
a shell with an outer face, an inner face and connecting rim bands, so collars,
cuffs, belts, hems and coat edges read as thick material instead of a painted
surface on a flat body.

Conventions used by every garment in character_clothing.py
---------------------------------------------------------
* Unity axes: +X = character's right, +Y = up, +Z = forward (the face looks +Z).
* Ring/limb parameter `u` is in radians: u=0 points along +X (character's right),
  u=pi/2 points +Z (front), u=pi points -X (left), u=3pi/2 points -Z (back).
  Sweeps take explicit reference directions so u means the same thing on both
  arms and both legs (u=0 outward, u=pi/2 forward).
* Parameter `v` always runs 0 -> 1 along the garment length.
* Triangle winding is derived from an interior reference point, so Unity's
  single-sided Standard shader always shows the outside of the garment.
"""
import math

TAU = 2.0 * math.pi

# Tooling switch: audit_clothing.py rebuilds the garments with folds disabled to
# measure how much displacement the fold/tension functions actually contribute.
FOLDS = [True]


# ---------------------------------------------------------------- vector math
def vadd(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def vsub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def vmul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def vdot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def vcross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def vlen(a):
    return math.sqrt(vdot(a, a))


def vnorm(a):
    length = vlen(a)
    return vmul(a, 1.0 / length) if length > 1e-12 else (0.0, 1.0, 0.0)


def vlerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def section_axes(ref_a, ref_b, tangent):
    """Two perpendicular axes for a swept section.

    Falls back through a list of references when one is (nearly) parallel to the
    sweep direction, which would otherwise collapse the section to a ribbon.
    """
    candidates = [ref_a, ref_b, (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)]
    axis_a = None
    for candidate in candidates:
        projected = project_onto_plane(candidate, tangent)
        if vlen(projected) > 0.15:
            axis_a = vnorm(projected)
            break
    if axis_a is None:
        axis_a = vnorm(cross(tangent, (0.0, 1.0, 0.0)))
        if vlen(axis_a) < 0.5:
            axis_a = vnorm(cross(tangent, (1.0, 0.0, 0.0)))
    axis_b = None
    for candidate in (ref_b, (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)):
        projected = project_onto_plane(candidate, tangent)
        if vlen(projected) > 0.15 and abs(vdot(vnorm(projected), axis_a)) < 0.98:
            axis_b = vnorm(projected)
            break
    if axis_b is None:
        axis_b = vnorm(cross(tangent, axis_a))
    return axis_a, axis_b


def project_onto_plane(vec, normal):
    return vsub(vec, vmul(normal, vdot(vec, normal)))


def bbox_centre(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return ((min(xs) + max(xs)) * 0.5, (min(ys) + max(ys)) * 0.5, (min(zs) + max(zs)) * 0.5)


# ---------------------------------------------------------- scalar utilities
def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else (hi if x > hi else x)


def lerp(a, b, t):
    return a + (b - a) * t


def smoothstep(edge0, edge1, x):
    if abs(edge1 - edge0) < 1e-12:
        return 0.0 if x < edge0 else 1.0
    t = clamp((x - edge0) / (edge1 - edge0))
    return t * t * (3.0 - 2.0 * t)


def gauss(x, mu, sigma):
    if sigma <= 1e-9:
        return 0.0
    d = (x - mu) / sigma
    return math.exp(-0.5 * d * d)


def table(x, xs, ys):
    """Piecewise-linear lookup, clamped at both ends."""
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            t = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] * (1.0 - t) + ys[i + 1] * t
    return ys[-1]


def table3(x, xs, ys_a, ys_b, ys_c):
    return (table(x, xs, ys_a), table(x, xs, ys_b), table(x, xs, ys_c))


def angle_fold(fn, a0=0.0, span=TAU):
    """Wrap an absolute-angle fold fn(u, v) into build_shell's (t_u, t_v) space."""
    def wrapped(t_u, t_v):
        return fn(a0 + span * t_u, t_v)
    return wrapped


def angle_delta(a, b):
    """Signed shortest angular difference a-b, wrapped to [-pi, pi]."""
    d = (a - b + math.pi) % TAU - math.pi
    return d


# ------------------------------------------------------------------ fold maths
def fold_accordion(v, centre, sigma, count, amp, phase=0.0):
    """Compression ridges across a joint (elbow, knee, ankle, waist)."""
    envelope = gauss(v, centre, sigma)
    if envelope < 1e-4:
        return 0.0
    return amp * envelope * math.cos(TAU * count * (v - centre) + phase)


def fold_slant(u, v, u_centre, v_centre, u_spread, v_spread, amp, tilt=0.0):
    """One long diagonal pull-crease (shoulder blades, gathered skirts)."""
    uu = u + tilt * (v - v_centre)
    du = angle_delta(uu, u_centre) / max(u_spread, 1e-6)
    dv = (v - v_centre) / max(v_spread, 1e-6)
    return amp * math.exp(-0.5 * (du * du + dv * dv))


def fold_gather(v, centre, sigma, count, amp):
    """Rings of gathered cloth (cuffs, boot tops, trouser ankles)."""
    envelope = gauss(v, centre, sigma)
    if envelope < 1e-4:
        return 0.0
    return amp * envelope * (0.5 + 0.5 * math.cos(TAU * count * (v - centre)))


def fold_space(u, v, ribs, amp, from_v, to_v, depth=1.4):
    """Vertical pleats/spokes that deepen toward a hem or open edge."""
    if v < from_v or v > to_v:
        return 0.0
    t = (v - from_v) / max(1e-6, to_v - from_v)
    return amp * (t ** depth) * math.cos(ribs * u)


def hem_wave(v, freq, amp, phase=0.0):
    return amp * math.sin(TAU * freq * v + phase)


def wobble(t, freq, amp, phase=0.0):
    return amp * math.sin(TAU * freq * t + phase)


# --------------------------------------------------------------------- mesh
class Mesh:
    """Per-material vertex/face buffers, matching how the OBJ is exported."""

    def __init__(self, materials):
        self.materials = list(materials)
        self.verts = {m: [] for m in self.materials}
        self.faces = {m: [] for m in self.materials}
        self.parts = []          # (name, material, first_vertex, vertex_count)

    def emit(self, material, name, points, faces):
        if not points or not faces:
            return
        base = len(self.verts[material])
        self.verts[material].extend(points)
        self.faces[material].extend(tuple(base + i for i in face) for face in faces)
        self.parts.append((name, material, base, len(points)))

    def merge_into(self, verts, faces, groups, active_group):
        """Append into the protagonist script's per-material buffers."""
        for material in self.materials:
            offset = len(verts[material])
            verts[material].extend(self.verts[material])
            faces[material].extend(tuple(offset + i for i in face) for face in self.faces[material])
        groups = groups  # kept for signature compatibility

    def stats(self):
        return (sum(len(v) for v in self.verts.values()),
                sum(len(f) for f in self.faces.values()))

    def part_stats(self):
        return [(name, material, count) for name, material, base, count in self.parts]


def quad(a, b, c, d):
    return ((a, b, c), (a, c, d))


def orient_face(points, face, ref, flat=None):
    """Return `face` wound so its normal points along `ref`."""
    pts = flat if flat is not None else points
    p0, p1, p2 = pts[face[0]], pts[face[1]], pts[face[2]]
    if vdot(vcross(vsub(p1, p0), vsub(p2, p0)), ref) < 0.0:
        return tuple(reversed(face))
    return tuple(face)


# ------------------------------------------------------------ surface shells
def build_shell(mesh, name, grid, thickness, material_out, material_in=None,
                material_rim=None, inside=None, close_u=False,
                v_lo_rim=True, v_hi_rim=True, u_lo_rim=True, u_hi_rim=True,
                inner="edges", inner_band=(3, 3), fold=None, outer_offset=0.0):
    """Turn a parametric grid into a garment shell with real thickness.

    grid       : grid[v][u] -> (x, y, z); v rows run 0..1 along the garment.
    thickness  : float or callable(u_radians, v01) -> metres (shell depth).
    material_in: material for the lining/inner face (defaults to material_out).
    inner      : 'none'  outer surface + rims only (interior never visible)
                 'edges' outer + lining band along the rimmed borders (default)
                 'full'  outer + continuous lining
    inner_band : (rows near the v borders, columns near the u borders)
    fold       : callable(u, v) -> metres displaced along the surface normal
    inside     : callable(point) -> interior reference point (defaults to the
                 grid bounding-box centre, which is inside any wrapping shell)
    """
    rows = len(grid)
    cols = len(grid[0])
    flat_grid = [p for row in grid for p in row]
    if inside is None:
        centre = bbox_centre(flat_grid)
        inside = lambda p: centre

    def thick(i, j):
        if callable(thickness):
            return thickness(j / cols, i / max(1, rows - 1))
        return thickness

    def folding(i, j):
        if fold is None or not FOLDS[0]:
            return 0.0
        return fold(j / cols, i / max(1, rows - 1))

    # Normals from central differences, oriented away from the interior point.
    normals = [[None] * cols for _ in range(rows)]
    for i in range(rows):
        for j in range(cols):
            i0 = max(0, i - 1)
            i1 = min(rows - 1, i + 1)
            if close_u:
                j0, j1 = (j - 1) % cols, (j + 1) % cols
            else:
                j0, j1 = max(0, j - 1), min(cols - 1, j + 1)
            du = vsub(grid[i][j1], grid[i][j0])
            dv = vsub(grid[i1][j], grid[i0][j])
            normal = vcross(du, dv)
            normal = vnorm(normal) if vlen(normal) > 1e-12 else (0.0, 1.0, 0.0)
            if vdot(normal, vsub(grid[i][j], inside(grid[i][j]))) < 0.0:
                normal = vmul(normal, -1.0)
            normals[i][j] = normal

    def face_point(i, j, sign, depth):
        base = grid[i][j]
        moved = vadd(base, vmul(normals[i][j], folding(i, j)))
        return vadd(moved, vmul(normals[i][j], sign * depth))

    outer = [[face_point(i, j, 1.0, outer_offset) for j in range(cols)] for i in range(rows)]
    lining = [[face_point(i, j, -1.0, thick(i, j)) for j in range(cols)] for i in range(rows)]

    u_span = cols if close_u else cols - 1

    def surface_faces(layer, ref_sign, keep):
        flat = [p for row in layer for p in row]
        faces = []
        for i in range(rows - 1):
            for j in range(u_span):
                if keep is not None and (i, j) not in keep:
                    continue
                jn = (j + 1) % cols
                a = i * cols + j
                b = i * cols + jn
                c = (i + 1) * cols + jn
                d = (i + 1) * cols + j
                mid = vmul(vadd(vadd(layer[i][j], layer[i][jn]),
                                vadd(layer[i + 1][jn], layer[i + 1][j])), 0.25)
                ref = vmul(vsub(mid, inside(mid)), ref_sign)
                for face in quad(a, b, c, d):
                    faces.append(orient_face(None, face, ref, flat=flat))
        return flat, faces

    flat_outer, faces = surface_faces(outer, 1.0, None)
    mesh.emit(material_out, name, flat_outer, faces)

    if inner != "none":
        band_rows, band_cols = inner_band
        keep = set()
        for i in range(rows - 1):
            for j in range(u_span):
                if inner == "full":
                    keep.add((i, j))
                    continue
                if v_lo_rim and i < band_rows:
                    keep.add((i, j))
                if v_hi_rim and i >= rows - 1 - band_rows:
                    keep.add((i, j))
                if not close_u:
                    if u_lo_rim and j < band_cols:
                        keep.add((i, j))
                    if u_hi_rim and j >= u_span - band_cols:
                        keep.add((i, j))
        flat_in, faces_in = surface_faces(lining, -1.0, keep)
        mesh.emit(material_in or material_out, name + "_Lining", flat_in, faces_in)

    rim_material = material_rim or material_out
    lining_flat = [p for row in lining for p in row]
    outer_flat = flat_outer
    # Rim strips are simple bands between matching outer/lining samples; build
    # them explicitly per border for clarity and correct winding.
    def rim_band(border):
        faces = []
        pts = outer_flat + lining_flat
        stride = len(outer_flat)
        if border in ("v_lo", "v_hi"):
            i = 0 if border == "v_lo" else rows - 1
            other = 1 if border == "v_lo" else rows - 2
            for j in range(cols - 1):
                a = i * cols + j
                b = i * cols + j + 1
                c = stride + i * cols + j + 1
                d = stride + i * cols + j
                ref = vnorm(vsub(grid[i][j], grid[other][j]))
                for k in range(1):
                    for face in quad(a, b, c, d):
                        faces.append(orient_face(None, face, ref, flat=pts))
        else:
            j = 0 if border == "u_lo" else cols - 1
            other = 1 if border == "u_lo" else cols - 2
            for i in range(rows - 1):
                a = i * cols + j
                b = (i + 1) * cols + j
                c = stride + (i + 1) * cols + j
                d = stride + i * cols + j
                ref = vnorm(vsub(grid[i][j], grid[i][other]))
                for face in quad(a, b, c, d):
                    faces.append(orient_face(None, face, ref, flat=pts))
        return pts, faces

    for border, wanted in (("v_lo", v_lo_rim), ("v_hi", v_hi_rim),
                           ("u_lo", u_lo_rim and not close_u),
                           ("u_hi", u_hi_rim and not close_u)):
        if not wanted:
            continue
        pts, faces = rim_band(border)
        mesh.emit(rim_material, name + "_Rim_" + border, pts, faces)


def sweep_shell(mesh, name, stations, sides, material_out, thickness,
                material_in=None, material_rim=None, fold=None,
                ref_a=(1.0, 0.0, 0.0), ref_b=(0.0, 0.0, 1.0),
                v_lo_rim=True, v_hi_rim=True, inner="edges", inner_band=(3, 3),
                outer_offset=0.0, inside=None, cap_lo=False, cap_hi=False,
                cap_material=None):
    """Sweep a closed tube shell along `stations` = [(centre, radius_a, radius_b)].

    u=0 lies along `ref_a`, u=pi/2 along `ref_b`, so folds can be placed by
    direction (e.g. the front of an elbow at u=pi/2) on either limb.
    """
    rows = len(stations)
    centres = [station[0] for station in stations]
    grid = []
    axes = []
    for index, (centre, ra, rb) in enumerate(stations):
        if index == 0:
            tangent = vsub(stations[1][0], stations[0][0])
        elif index == rows - 1:
            tangent = vsub(stations[-1][0], stations[-2][0])
        else:
            tangent = vsub(stations[index + 1][0], stations[index - 1][0])
        tangent = vnorm(tangent)
        axis_a, axis_b = section_axes(ref_a, ref_b, tangent)
        axes.append((axis_a, axis_b))
        row = []
        for s in range(sides):
            angle = TAU * s / sides
            row.append(vadd(centre, vadd(vmul(axis_a, ra * math.cos(angle)),
                                          vmul(axis_b, rb * math.sin(angle)))))
        grid.append(row)

    if inside is None:
        def inside(point):
            best = min(centres, key=lambda c: (c[0] - point[0]) ** 2 + (c[1] - point[1]) ** 2 +
                                              (c[2] - point[2]) ** 2)
            return best

    build_shell(mesh, name, grid, thickness, material_out, material_in, material_rim,
                inside=inside, close_u=True, v_lo_rim=v_lo_rim, v_hi_rim=v_hi_rim,
                u_lo_rim=False, u_hi_rim=False, inner=inner, inner_band=inner_band,
                fold=fold, outer_offset=outer_offset)

    if cap_lo:
        _cap(mesh, cap_material or material_in or material_out, name + "_CapLo",
             stations[0][0], grid[0], centres[1], min(rows - 1, 1))
    if cap_hi:
        _cap(mesh, cap_material or material_in or material_out, name + "_CapHi",
             stations[-1][0], grid[-1], centres[-2], rows - 2)


def _cap(mesh, material, name, centre, ring, neighbour, neighbour_index):
    pts = list(ring) + [centre]
    n = len(ring)
    faces = [(i, (i + 1) % n, n) for i in range(n)]
    ref = vnorm(vsub(centre, neighbour))
    faces = [orient_face(None, f, ref, flat=pts) for f in faces]
    mesh.emit(material, name, pts, faces)


# ------------------------------------------------------------------- straps
def strap(mesh, name, path, normals, material, width, thickness, chamfer=0.3,
          close=False, twist=None, taper=None, section_scale=1.0):
    """Chamfered rectangular leather band swept along `path` (real thickness).

    path[i]    : centreline point
    normals[i] : direction away from the body at that station
    width      : float or callable(t01)
    thickness  : float or callable(t01) (how far the strap stands off the body)
    """
    corners = 8
    section = []
    for k in range(corners):
        angle = TAU * k / corners
        c, s = math.cos(angle), math.sin(angle)
        limit = 1.0 / max(abs(c), abs(s), 1e-6)
        shape = min(1.0, limit) ** (1.0 - chamfer)
        section.append((c * 0.5 * shape * section_scale, s * 0.5 * shape * section_scale))

    stations = len(path)
    rings = []
    for i, point in enumerate(path):
        if close:
            prev = path[(i - 1) % stations]
            nxt = path[(i + 1) % stations]
        else:
            prev = path[max(0, i - 1)]
            nxt = path[min(stations - 1, i + 1)]
        tangent = vnorm(vsub(nxt, prev))
        outward = vnorm(project_onto_plane(normals[i], tangent))
        if twist is not None:
            angle = twist(i / max(1, stations - 1))
            side = vnorm(project_onto_plane(vcross(tangent, outward), tangent))
            side = vnorm(vadd(vmul(side, math.cos(angle)), vmul(outward, math.sin(angle))))
        else:
            side = vnorm(vcross(tangent, outward))
        t = i / max(1, stations - 1)
        half_w = (width(t) if callable(width) else width) * 0.5
        if taper is not None:
            half_w *= taper(t)
        th = thickness(t) if callable(thickness) else thickness
        ring = [vadd(point, vadd(vmul(side, cx * 2.0 * half_w), vmul(outward, cy * 2.0 * th)))
                for (cx, cy) in section]
        rings.append(ring)

    flat = [p for ring in rings for p in ring]
    faces = []
    last = stations if close else stations - 1
    for i in range(last):
        inext = (i + 1) % stations
        for k in range(corners):
            knext = (k + 1) % corners
            a = i * corners + k
            b = i * corners + knext
            c = inext * corners + knext
            d = inext * corners + k
            mid = vmul(vadd(vadd(rings[i][k], rings[i][knext]),
                            vadd(rings[inext][knext], rings[inext][k])), 0.25)
            ref = vsub(mid, path[i])
            for face in quad(a, b, c, d):
                faces.append(orient_face(None, face, ref, flat=flat))
    if not close:
        for end in (0, stations - 1):
            base = end * corners
            centre_index = len(flat)
            flat.append(path[end])
            neighbour = path[1] if end == 0 else path[stations - 2]
            ref = vnorm(vsub(path[end], neighbour))
            fan = [(base + k, base + (k + 1) % corners, centre_index) for k in range(corners)]
            for face in fan:
                faces.append(orient_face(None, face, ref, flat=flat))
    mesh.emit(material, name, flat, faces)


def tube(mesh, name, path, material, radius, sides=10, close=False, caps=True,
         ref_a=(1.0, 0.0, 0.0), ref_b=(0.0, 0.0, 1.0), squash=None):
    """Round cord/pipe: laces, piping, thread, small ring ornaments."""
    rows = len(path)

    def rad(t):
        return radius(t) if callable(radius) else radius

    rings = []
    for i, centre in enumerate(path):
        if close:
            prev = path[(i - 1) % rows]
            nxt = path[(i + 1) % rows]
        else:
            prev = path[max(0, i - 1)]
            nxt = path[min(rows - 1, i + 1)]
        tangent = vnorm(vsub(nxt, prev))
        axis_a, axis_b = section_axes(ref_a, ref_b, tangent)
        r = rad(i / max(1, rows - 1))
        ring = []
        for s in range(sides):
            angle = TAU * s / sides
            ra, rb = (r, r) if squash is None else squash(r, angle)
            ring.append(vadd(centre, vadd(vmul(axis_a, ra * math.cos(angle)),
                                          vmul(axis_b, rb * math.sin(angle)))))
        rings.append(ring)

    flat = [p for ring in rings for p in ring]
    faces = []
    last = rows if close else rows - 1
    for i in range(last):
        inext = (i + 1) % rows
        for s in range(sides):
            snext = (s + 1) % sides
            a = i * sides + s
            b = i * sides + snext
            c = inext * sides + snext
            d = inext * sides + s
            mid = vmul(vadd(vadd(rings[i][s], rings[i][snext]),
                            vadd(rings[inext][snext], rings[inext][s])), 0.25)
            ref = vsub(mid, path[i])
            for face in quad(a, b, c, d):
                faces.append(orient_face(None, face, ref, flat=flat))
    if not close and caps:
        for end in (0, rows - 1):
            base = end * sides
            centre_index = len(flat)
            flat.append(path[end])
            neighbour = path[1] if end == 0 else path[rows - 2]
            ref = vnorm(vsub(path[end], neighbour))
            fan = [(base + s, base + (s + 1) % sides, centre_index) for s in range(sides)]
            for face in fan:
                faces.append(orient_face(None, face, ref, flat=flat))
    mesh.emit(material, name, flat, faces)


def ellipsoid(mesh, name, material, centre, scale, rings=14, sides=20, rotation=None,
              squash=None, inner_radius=1.0):
    """Closed blob: studs, buckle tongues, pouches, clasps, rivets."""
    axis_y = rotation[0] if rotation else (0.0, 1.0, 0.0)
    axis_x = rotation[1] if rotation else (1.0, 0.0, 0.0)
    axis_z = rotation[2] if rotation else (0.0, 0.0, 1.0)
    sx, sy, sz = scale

    def place(p):
        return vadd(centre, vadd(vmul(axis_x, p[0]),
                                 vadd(vmul(axis_y, p[1]), vmul(axis_z, p[2]))))

    pts = [place((0.0, sy, 0.0))]
    for r in range(1, rings):
        lat = math.pi * r / rings
        for s in range(sides):
            lon = TAU * s / sides
            px = sx * math.sin(lat) * math.cos(lon) * inner_radius
            py = sy * math.cos(lat)
            pz = sz * math.sin(lat) * math.sin(lon) * inner_radius
            if squash:
                px, py, pz = squash(px, py, pz)
            pts.append(place((px, py, pz)))
    bottom = len(pts)
    pts.append(place((0.0, -sy, 0.0)))
    faces = []
    for s in range(sides):
        faces.append((0, 1 + (s + 1) % sides, 1 + s))
    for r in range(rings - 2):
        a = 1 + r * sides
        b = a + sides
        for s in range(sides):
            n = (s + 1) % sides
            faces.extend(((a + n, b + s, a + s), (b + n, b + s, a + n)))
    last = 1 + (rings - 2) * sides
    for s in range(sides):
        faces.append((last + (s + 1) % sides, bottom, last + s))
    mesh.emit(material, name, pts, faces)


def ring_torus(mesh, name, material, centre, radius, tube_radius, sides=16, ring_sides=8,
               axis=(0.0, 1.0, 0.0), ref=(1.0, 0.0, 0.0)):
    """Small metal ring (harness sighting-ring, belt keeper, collar ring)."""
    path = []
    for s in range(sides):
        angle = TAU * s / sides
        a = vnorm(project_onto_plane(ref, axis))
        b = vnorm(vcross(axis, a))
        path.append(vadd(centre, vadd(vmul(a, radius * math.cos(angle)),
                                      vmul(b, radius * math.sin(angle)))))
    tube(mesh, name, path, material, tube_radius, ring_sides, close=True, ref_a=axis)


def smooth_path(points, samples):
    """Catmull-Rom resample so shoulders, straps and hems read as fabric."""
    pts = [points[0]] + list(points) + [points[-1]]
    out = []
    for i in range(samples):
        t = i / (samples - 1) * (len(points) - 1)
        seg = min(int(t), len(points) - 2)
        out.append(catmull(pts[seg], pts[seg + 1], pts[seg + 2], pts[seg + 3], t - seg))
    return out


def catmull(p0, p1, p2, p3, t):
    t2 = t * t
    t3 = t2 * t
    return tuple(
        0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t +
               (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2 +
               (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
        for k in range(3)
    )


def ring_point(u, y, rx, rz, cz=0.0):
    """Point on a horizontal ellipse: u=0 -> +X (right), u=pi/2 -> +Z (front)."""
    return (rx * math.cos(u), y, cz + rz * math.sin(u))


def axis_inside(cx=0.0, cz=0.0):
    """Interior reference for anything wrapped around a vertical body axis."""
    return lambda point: (cx, point[1], cz)


def limb_inside(centres):
    """Interior reference that snaps to the nearest sweep station centre."""
    def inside(point):
        return min(centres, key=lambda c: (c[0] - point[0]) ** 2 + (c[1] - point[1]) ** 2 +
                                          (c[2] - point[2]) ** 2)
    return inside


# ------------------------------------------------------------------- solids
def solid_loft(mesh, name, rings, material, inside=None, cap_lo=True, cap_hi=True,
               cap_material=None, cap_depth=(0.0, 0.0)):
    """Closed solid from a stack of equal-length rings (boot soles, pouches...).

    Unlike build_shell this is a *solid*: side walls plus fan caps, no interior.
    """
    rows = len(rings)
    cols = len(rings[0])
    flat = [p for ring in rings for p in ring]
    if inside is None:
        centre = bbox_centre(flat)
        inside = lambda p: centre

    faces = []
    for i in range(rows - 1):
        for j in range(cols):
            jn = (j + 1) % cols
            a = i * cols + j
            b = i * cols + jn
            c = (i + 1) * cols + jn
            d = (i + 1) * cols + j
            mid = vmul(vadd(vadd(rings[i][j], rings[i][jn]),
                            vadd(rings[i + 1][jn], rings[i + 1][j])), 0.25)
            ref = vsub(mid, inside(mid))
            for face in quad(a, b, c, d):
                faces.append(orient_face(None, face, ref, flat=flat))
    if cap_lo or cap_hi:
        for end, enabled, depth in ((0, cap_lo, cap_depth[0]), (rows - 1, cap_hi, cap_depth[1])):
            if not enabled:
                continue
            ring = rings[end]
            centre = tuple(sum(p[i] for p in ring) / cols for i in range(3))
            if depth:
                neighbour = rings[end + 1] if end == 0 else rings[end - 2]
                centre = vadd(centre, vmul(vnorm(vsub(centre, neighbour)), depth))
            centre_index = len(flat)
            flat.append(centre)
            base = end * cols
            ref = vnorm(vsub(centre, inside(centre)))
            fan = [(base + j, base + (j + 1) % cols, centre_index) for j in range(cols)]
            for face in fan:
                faces.append(orient_face(None, face, ref, flat=flat))
    mesh.emit(cap_material or material, name, flat, faces)


def extrude_outline(mesh, name, outline, base_y, top_y, material, centre_xy=None):
    """Slab with a shaped footprint (sole, heel, plates, buckle frames)."""
    ring_lo = [(x, base_y, z) for (x, z) in outline]
    ring_hi = [(x, top_y, z) for (x, z) in outline]
    return solid_loft(mesh, name, [ring_lo, ring_hi], material,
                      inside=lambda p: (centre_xy[0], (base_y + top_y) * 0.5, centre_xy[1])
                      if centre_xy else (0.0, (base_y + top_y) * 0.5, 0.0),
                      cap_lo=True, cap_hi=True)


def rounded_rect_outline(centre, half_w, half_d, corner, samples_per_corner=5):
    """Footprint/plate outline with rounded corners, CCW in the XZ plane."""
    cx, cz = centre
    points = []
    corners = ((half_w - corner, half_d - corner, 0.0),
               (-(half_w - corner), half_d - corner, math.pi * 0.5),
               (-(half_w - corner), -(half_d - corner), math.pi),
               (half_w - corner, -(half_d - corner), math.pi * 1.5))
    for (px, pz, start) in corners:
        for s in range(samples_per_corner):
            angle = start + math.pi * 0.5 * s / (samples_per_corner - 1)
            points.append((cx + px + corner * math.cos(angle), cz + pz + corner * math.sin(angle)))
    return points
