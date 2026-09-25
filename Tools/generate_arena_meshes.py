#!/usr/bin/env python3
"""
Generate modular 3D arena assets as OBJ files for Unity.
Creates ~80 optimized meshes with clean topology, UVs, pivots at base center, correct scale.
Material slots via usemtl referencing existing Vespershade materials.

Pivots: All meshes have pivot at base center (0,0,0) bottom, Y up, 1 unit = 1 meter.
UVs: planar / box projected, 0-1 range per face.
Normals: per-face hard edges where appropriate, smooth where needed.

Categories:
 floor, wall, pillar, arch, window, stairs, platform, statue, chain, wood, candle, ritual, debris, door, deco + LODs
"""

import os, math, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "Assets/Models/Arena")
os.makedirs(OUT_DIR, exist_ok=True)

# Material names mapped to existing Unity materials
MAT_STONE_FLOOR = "M_Arena_StoneFloor"
MAT_STONE_FLOOR_RITUAL = "M_Arena_StoneFloor_Ritual"
MAT_STONE_WALL = "M_Arena_StoneWall"
MAT_STONE_PILLAR = "M_Arena_StonePillar"
MAT_METAL_CHAIN = "M_Arena_Metal_Chain"
MAT_WOOD_ROTTED = "M_Arena_Wood_Rotted"
MAT_STATUE_ERODED = "M_Arena_Statue_Eroded"
MAT_CANDLE_WAX = "M_Arena_Candle_Wax"
MAT_CANDLE_FLAME = "M_Arena_Candle_Flame"
MAT_RITUAL_MARK = "M_Arena_RitualMarking"
MAT_FOG = "M_Arena_Fog_Plane"
MAT_BRAZIER_METAL = "M_Arena_Brazier_Metal"
MAT_GLASS_BLUE = "M_Arena_Glass_Blue"
MAT_GLASS_RED = "M_Arena_Glass_Red"
MAT_GLASS_AMBER = "M_Arena_Glass_Amber"

# Additional mats that will be created as .mat files if missing (reuse existing where possible)
# We'll reference these names; Unity will create material slots even if .mat not present, but we will generate mats later.

class MeshBuilder:
    def __init__(self, name):
        self.name = name
        self.v = []  # list of (x,y,z)
        self.vt = [] # (u,v)
        self.vn = [] # (nx,ny,nz)
        self.faces = [] # list of dict: material, verts [(vi,vti,vni), ...]
        self.materials = set()
        self.current_mat = MAT_STONE_WALL

    def set_mat(self, mat):
        self.current_mat = mat
        self.materials.add(mat)

    def add_vertex(self, pos, uv, normal):
        self.v.append(pos)
        self.vt.append(uv)
        self.vn.append(normal)
        idx = len(self.v)  # 1-based for OBJ
        return (idx, idx, idx)

    # Low-level quad with explicit verts (creates 4 verts, 1 quad -> 2 tris)
    def add_quad(self, p0, p1, p2, p3, uv0=(0,0), uv1=(1,0), uv2=(1,1), uv3=(0,1), normal=None, mat=None):
        if mat is None:
            mat = self.current_mat
        self.materials.add(mat)
        if normal is None:
            # compute normal from p0,p1,p2
            ux, uy, uz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
            vx, vy, vz = p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2]
            nx = uy*vz - uz*vy
            ny = uz*vx - ux*vz
            nz = ux*vy - uy*vx
            l = math.sqrt(nx*nx+ny*ny+nz*nz) or 1
            normal = (nx/l, ny/l, nz/l)
        i0 = self.add_vertex(p0, uv0, normal)
        i1 = self.add_vertex(p1, uv1, normal)
        i2 = self.add_vertex(p2, uv2, normal)
        i3 = self.add_vertex(p3, uv3, normal)
        # two tris as one quad face (OBJ can have 4 verts) - we will write as quad, Unity triangulates
        self.faces.append({"mat": mat, "verts": [i0,i1,i2,i3]})

    def add_tri(self, p0,p1,p2, uv0=(0,0), uv1=(1,0), uv2=(0,1), normal=None, mat=None):
        if mat is None:
            mat = self.current_mat
        self.materials.add(mat)
        if normal is None:
            ux, uy, uz = p1[0]-p0[0], p1[1]-p0[1], p1[2]-p0[2]
            vx, vy, vz = p2[0]-p0[0], p2[1]-p0[1], p2[2]-p0[2]
            nx = uy*vz - uz*vy
            ny = uz*vx - ux*vz
            nz = ux*vy - uy*vx
            l = math.sqrt(nx*nx+ny*ny+nz*nz) or 1
            normal = (nx/l, ny/l, nz/l)
        i0 = self.add_vertex(p0, uv0, normal)
        i1 = self.add_vertex(p1, uv1, normal)
        i2 = self.add_vertex(p2, uv2, normal)
        self.faces.append({"mat": mat, "verts": [i0,i1,i2]})

    def add_box(self, w,h,d, y_offset=0, mat=None, uv_scale=1.0):
        """Box with pivot at base center. w along X, h along Y, d along Z. y_offset is bottom offset (usually 0)"""
        if mat is None:
            mat = self.current_mat
        hw = w*0.5
        hd = d*0.5
        y0 = y_offset
        y1 = y_offset + h
        # 8 corners
        # We'll create 6 quads, each with own verts for hard edges
        # Top
        self.add_quad((-hw,y1,-hd), (hw,y1,-hd), (hw,y1,hd), (-hw,y1,hd),
                      uv0=(0,0), uv1=(w*uv_scale,0), uv2=(w*uv_scale,d*uv_scale), uv3=(0,d*uv_scale),
                      normal=(0,1,0), mat=mat)
        # Bottom
        self.add_quad((-hw,y0,hd), (hw,y0,hd), (hw,y0,-hd), (-hw,y0,-hd),
                      uv0=(0,0), uv1=(1,0), uv2=(1,1), uv3=(0,1),
                      normal=(0,-1,0), mat=mat)
        # Front (+Z)
        self.add_quad((-hw,y0,hd), (-hw,y1,hd), (hw,y1,hd), (hw,y0,hd),
                      uv0=(0,0), uv1=(0,h*uv_scale), uv2=(w*uv_scale,h*uv_scale), uv3=(w*uv_scale,0),
                      normal=(0,0,1), mat=mat)
        # Back (-Z)
        self.add_quad((hw,y0,-hd), (hw,y1,-hd), (-hw,y1,-hd), (-hw,y0,-hd),
                      normal=(0,0,-1), mat=mat)
        # Right (+X)
        self.add_quad((hw,y0,hd), (hw,y1,hd), (hw,y1,-hd), (hw,y0,-hd),
                      normal=(1,0,0), mat=mat)
        # Left (-X)
        self.add_quad((-hw,y0,-hd), (-hw,y1,-hd), (-hw,y1,hd), (-hw,y0,hd),
                      normal=(-1,0,0), mat=mat)

    def add_cylinder(self, radius, height, segments=16, y_offset=0, cap_top=True, cap_bottom=True, mat=None, uv_scale=1.0, smooth=True):
        if mat is None:
            mat = self.current_mat
        # side
        y0 = y_offset
        y1 = y_offset + height
        for i in range(segments):
            a0 = (i / segments) * math.pi*2
            a1 = ((i+1) / segments) * math.pi*2
            x0 = math.cos(a0)*radius
            z0 = math.sin(a0)*radius
            x1 = math.cos(a1)*radius
            z1 = math.sin(a1)*radius
            # normal
            nx0 = math.cos(a0)
            nz0 = math.sin(a0)
            nx1 = math.cos(a1)
            nz1 = math.sin(a1)
            if smooth:
                # create quad with per-vertex normals
                # we need 4 verts with individual normals
                v0 = self.add_vertex((x0,y0,z0), (i/segments*uv_scale*2,0), (nx0,0,nz0))
                v1 = self.add_vertex((x0,y1,z0), (i/segments*uv_scale*2,1), (nx0,0,nz0))
                v2 = self.add_vertex((x1,y1,z1), ((i+1)/segments*uv_scale*2,1), (nx1,0,nz1))
                v3 = self.add_vertex((x1,y0,z1), ((i+1)/segments*uv_scale*2,0), (nx1,0,nz1))
                self.faces.append({"mat": mat, "verts": [v0,v1,v2,v3]})
            else:
                # hard normal per face
                cx = (x0+x1)*0.5
                cz = (z0+z1)*0.5
                l = math.sqrt(cx*cx+cz*cz) or 1
                n = (cx/l, 0, cz/l)
                self.add_quad((x0,y0,z0), (x0,y1,z0), (x1,y1,z1), (x1,y0,z1), normal=n, mat=mat)
        if cap_top and height>0.001:
            # fan
            center = (0,y1,0)
            for i in range(segments):
                a0 = (i / segments) * math.pi*2
                a1 = ((i+1) / segments) * math.pi*2
                x0 = math.cos(a0)*radius
                z0 = math.sin(a0)*radius
                x1 = math.cos(a1)*radius
                z1 = math.sin(a1)*radius
                self.add_tri(center, (x0,y1,z0), (x1,y1,z1),
                             uv0=(0.5,0.5), uv1=(0.5+math.cos(a0)*0.5,0.5+math.sin(a0)*0.5), uv2=(0.5+math.cos(a1)*0.5,0.5+math.sin(a1)*0.5),
                             normal=(0,1,0), mat=mat)
        if cap_bottom:
            center = (0,y0,0)
            for i in range(segments):
                a0 = (i / segments) * math.pi*2
                a1 = ((i+1) / segments) * math.pi*2
                x0 = math.cos(a0)*radius
                z0 = math.sin(a0)*radius
                x1 = math.cos(a1)*radius
                z1 = math.sin(a1)*radius
                self.add_tri(center, (x1,y0,z1), (x0,y0,z0),
                             uv0=(0.5,0.5), uv1=(0.5+math.cos(a1)*0.5,0.5+math.sin(a1)*0.5), uv2=(0.5+math.cos(a0)*0.5,0.5+math.sin(a0)*0.5),
                             normal=(0,-1,0), mat=mat)

    def add_plane(self, w,d, y_offset=0, mat=None, double_sided=False):
        if mat is None:
            mat = self.current_mat
        hw = w*0.5
        hd = d*0.5
        y = y_offset
        self.add_quad((-hw,y,-hd), (hw,y,-hd), (hw,y,hd), (-hw,y,hd), normal=(0,1,0), mat=mat)
        if double_sided:
            self.add_quad((-hw,y,hd), (hw,y,hd), (hw,y,-hd), (-hw,y,-hd), normal=(0,-1,0), mat=mat)

    def write_obj(self, filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(f"# {self.name} - generated modular arena asset\n")
            f.write(f"# pivot base center, 1 unit = 1m, clean topology\n")
            f.write(f"o {self.name}\n")
            for (x,y,z) in self.v:
                f.write(f"v {x:.6f} {y:.6f} {z:.6f}\n")
            for (u,v) in self.vt:
                f.write(f"vt {u:.6f} {v:.6f}\n")
            for (nx,ny,nz) in self.vn:
                f.write(f"vn {nx:.6f} {ny:.6f} {nz:.6f}\n")
            # materials
            # group by material to minimize usemtl switches
            mat_groups = {}
            for face in self.faces:
                mat = face["mat"]
                mat_groups.setdefault(mat, []).append(face)
            for mat, faces in mat_groups.items():
                f.write(f"usemtl {mat}\n")
                for face in faces:
                    # face verts are (vi,vti,vni)
                    s = "f"
                    for (vi,vti,vni) in face["verts"]:
                        s += f" {vi}/{vti}/{vni}"
                    f.write(s+"\n")
        # print stats
        tris = sum(1 if len(face["verts"])==3 else 2 for face in self.faces)
        print(f"Wrote {filepath} - {len(self.v)} verts, {tris} tris, {len(self.materials)} mats {list(self.materials)}")

# -------------------------------------------------------------------
# Helpers for specific shapes
# -------------------------------------------------------------------

def generate_floor_tiles():
    # 4x4
    mb = MeshBuilder("SM_Arena_Floor_400x400x050")
    mb.set_mat(MAT_STONE_FLOOR)
    mb.add_box(4,0.5,4, y_offset=0)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Floor_400x400x050.obj"))

    mb = MeshBuilder("SM_Arena_Floor_200x200x050")
    mb.set_mat(MAT_STONE_FLOOR)
    mb.add_box(2,0.5,2)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Floor_200x200x050.obj"))

    mb = MeshBuilder("SM_Arena_Floor_100x100x050")
    mb.set_mat(MAT_STONE_FLOOR)
    mb.add_box(1,0.5,1)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Floor_100x100x050.obj"))

    # Wedge for circular arena: angle 22.5 deg, inner radius 15, outer 19, thickness 0.5
    # Build as prism with 4 top verts, 4 bottom verts
    angle_deg = 22.5
    angle_rad = math.radians(angle_deg)
    r_inner = 15.0
    r_outer = 19.0
    thickness = 0.5
    # center at origin? But pivot at base center of wedge's inner edge? For modular grid we want pivot at inner center? Simpler pivot at wedge centroid base.
    # We'll generate wedge with inner edge at origin line? Let's generate wedge with apex at origin? Actually for ring, we need polar wedge.
    # We'll generate vertices: inner arc 2 points at r_inner at -angle/2 and +angle/2, outer arc 2 points at r_outer.
    # Then extrude thickness.
    mb = MeshBuilder("SM_Arena_Floor_Wedge_22_5_R15_19")
    mb.set_mat(MAT_STONE_FLOOR)
    a0 = -angle_rad*0.5
    a1 = angle_rad*0.5
    # inner
    x_i0 = math.cos(a0)*r_inner
    z_i0 = math.sin(a0)*r_inner
    x_i1 = math.cos(a1)*r_inner
    z_i1 = math.sin(a1)*r_inner
    x_o0 = math.cos(a0)*r_outer
    z_o0 = math.sin(a0)*r_outer
    x_o1 = math.cos(a1)*r_outer
    z_o1 = math.sin(a1)*r_outer
    # We'll create top face quad (actually trapezoid) as two tris? Use quad with 4 points.
    # Bottom at y=0, top at y=thickness
    y0=0
    y1=thickness
    # For pivot base center: we want pivot at midpoint between inner and outer at angle 0? Let's compute centroid and offset vertices so pivot at base center of wedge's middle radius.
    # Mid radius
    r_mid = (r_inner+r_outer)*0.5
    # Pivot should be at (r_mid,0,0) projected? So shift all vertices by -r_mid in X
    # Actually we want pivot at base center of wedge's inner? Let's do pivot at 0,0,0 at center of wedge's inner edge midpoint? Simpler: shift so that (r_mid,0,0) becomes origin.
    # So subtract r_mid from x.
    def shift(p):
        return (p[0]-r_mid, p[1], p[2])
    # top face
    p_i0_top = shift((x_i0,y1,z_i0))
    p_i1_top = shift((x_i1,y1,z_i1))
    p_o1_top = shift((x_o1,y1,z_o1))
    p_o0_top = shift((x_o0,y1,z_o0))
    p_i0_bot = shift((x_i0,y0,z_i0))
    p_i1_bot = shift((x_i1,y0,z_i1))
    p_o1_bot = shift((x_o1,y0,z_o1))
    p_o0_bot = shift((x_o0,y0,z_o0))
    # top
    mb.add_quad(p_i0_top, p_o0_top, p_o1_top, p_i1_top, normal=(0,1,0))
    # bottom
    mb.add_quad(p_i1_bot, p_o1_bot, p_o0_bot, p_i0_bot, normal=(0,-1,0))
    # sides
    mb.add_quad(p_i0_bot, p_i0_top, p_i1_top, p_i1_bot, normal=(0,0,-1)) # inner
    mb.add_quad(p_o0_bot, p_o1_bot, p_o1_top, p_o0_top, normal=(0,0,1)) # outer
    mb.add_quad(p_i0_bot, p_o0_bot, p_o0_top, p_i0_top, normal=(-1,0,0))
    mb.add_quad(p_i1_bot, p_i1_top, p_o1_top, p_o1_bot, normal=(1,0,0))
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Floor_Wedge_22_5_R15_19.obj"))

    # Edge trim 4m x 0.5m x 0.2m
    mb = MeshBuilder("SM_Arena_Floor_Edge_400x020x050")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(4,0.2,0.5)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Floor_Edge_400x020x050.obj"))

    # Ritual plate
    mb = MeshBuilder("SM_Arena_Floor_Ritual_Plate_220x065")
    mb.set_mat(MAT_RITUAL_MARK)
    mb.add_box(2.2,0.02,0.65)
    # add rune sub mesh
    mb.set_mat(MAT_RITUAL_MARK)
    # small cube on top as rune
    mb.add_box(0.5,0.01,0.5, y_offset=0.02)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Floor_Ritual_Plate_220x065.obj"))

    # Ritual center disc 3.2m
    mb = MeshBuilder("SM_Arena_Floor_Ritual_Center_320")
    mb.set_mat(MAT_RITUAL_MARK)
    mb.add_cylinder(1.6,0.02, segments=24, y_offset=0, cap_top=True, cap_bottom=True)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Floor_Ritual_Center_320.obj"))

def generate_walls():
    mb = MeshBuilder("SM_Arena_Wall_400x400x100")
    mb.set_mat(MAT_STONE_WALL)
    mb.add_box(4,4,1)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wall_400x400x100.obj"))

    mb = MeshBuilder("SM_Arena_Wall_400x800x100")
    mb.set_mat(MAT_STONE_WALL)
    mb.add_box(4,8,1)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wall_400x800x100.obj"))

    mb = MeshBuilder("SM_Arena_Wall_400x1600x110")
    mb.set_mat(MAT_STONE_WALL)
    mb.add_box(4,16,1.1)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wall_400x1600x110.obj"))

    # Wall with window opening
    mb = MeshBuilder("SM_Arena_Wall_400x400_Window_250x300")
    mb.set_mat(MAT_STONE_WALL)
    # Build wall with opening: create 4 surrounding boxes + lintel
    # Outer dimensions 4x4x1
    # Opening 2.5 wide x 3.0 tall, sill at 0.5m
    # Left jamb: width (4-2.5)/2 =0.75, height 4, depth 1
    # Right jamb same
    # Bottom sill: width 2.5, height 0.5, depth 1
    # Top lintel: width 2.5, height 4 - (0.5+3.0)=0.5, depth 1
    # We'll create as separate boxes but combined mesh
    # Left
    mb.add_box(0.75,4,1, y_offset=0)
    # Need to offset left box to x = - (4/2) + 0.75/2 = -1.625
    # Our add_box creates at center, but we need offset. Instead we will manually offset by adding extra translation in add_box? Our add_box centers at 0, so we need to create quads with offset.
    # Let's rewrite this wall using manual quads for correct placement.
    # Reset builder
    mb = MeshBuilder("SM_Arena_Wall_400x400_Window_250x300")
    mb.set_mat(MAT_STONE_WALL)
    # left jamb: x from -2 to -1.25, y 0-4, z -0.5 to 0.5
    def add_box_at(w,h,d, cx, cy, cz, mat):
        hw=w*0.5; hd=d*0.5
        y0=cy; y1=cy+h
        x0=cx-hw; x1=cx+hw
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    add_box_at(0.75,4,1, -1.625,0,0, MAT_STONE_WALL)
    add_box_at(0.75,4,1, 1.625,0,0, MAT_STONE_WALL)
    add_box_at(2.5,0.5,1, 0,0,0, MAT_STONE_WALL)
    add_box_at(2.5,0.5,1, 0,3.5,0, MAT_STONE_WALL)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wall_400x400_Window_250x300.obj"))

    # Wall window large 5.2x9.5 opening in 6x14 wall (for arena)
    mb = MeshBuilder("SM_Arena_Wall_600x1400_Window_520x950")
    mb.set_mat(MAT_STONE_WALL)
    # outer 6 wide, 14 tall, 1.1 thick, opening 5.2x9.5, sill at 1.2
    # left jamb width (6-5.2)/2=0.4
    add_box_at = lambda w,h,d,cx,cy,cz,mat: (
        mb.add_quad((cx-w*0.5,cy+h,cz-d*0.5),(cx+w*0.5,cy+h,cz-d*0.5),(cx+w*0.5,cy+h,cz+d*0.5),(cx-w*0.5,cy+h,cz+d*0.5), normal=(0,1,0), mat=mat),
        mb.add_quad((cx-w*0.5,cy,cz+d*0.5),(cx+w*0.5,cy,cz+d*0.5),(cx+w*0.5,cy,cz-d*0.5),(cx-w*0.5,cy,cz-d*0.5), normal=(0,-1,0), mat=mat),
        mb.add_quad((cx-w*0.5,cy,cz+d*0.5),(cx-w*0.5,cy+h,cz+d*0.5),(cx+w*0.5,cy+h,cz+d*0.5),(cx+w*0.5,cy,cz+d*0.5), normal=(0,0,1), mat=mat),
        mb.add_quad((cx+w*0.5,cy,cz-d*0.5),(cx+w*0.5,cy+h,cz-d*0.5),(cx-w*0.5,cy+h,cz-d*0.5),(cx-w*0.5,cy,cz-d*0.5), normal=(0,0,-1), mat=mat),
        mb.add_quad((cx+w*0.5,cy,cz+d*0.5),(cx+w*0.5,cy+h,cz+d*0.5),(cx+w*0.5,cy+h,cz-d*0.5),(cx+w*0.5,cy,cz-d*0.5), normal=(1,0,0), mat=mat),
        mb.add_quad((cx-w*0.5,cy,cz-d*0.5),(cx-w*0.5,cy+h,cz-d*0.5),(cx-w*0.5,cy+h,cz+d*0.5),(cx-w*0.5,cy,cz+d*0.5), normal=(-1,0,0), mat=mat)
    )
    # Recreate builder for large wall
    mb = MeshBuilder("SM_Arena_Wall_600x1400_Window_520x950")
    mb.set_mat(MAT_STONE_WALL)
    def add_box_at2(w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    add_box_at2(0.4,14,1.1, -2.8,0,0, MAT_STONE_WALL)
    add_box_at2(0.4,14,1.1, 2.8,0,0, MAT_STONE_WALL)
    add_box_at2(5.2,1.2,1.1, 0,0,0, MAT_STONE_WALL)
    add_box_at2(5.2,3.3,1.1, 0,10.7,0, MAT_STONE_WALL) # top: 14 - (1.2+9.5)=3.3
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wall_600x1400_Window_520x950.obj"))

    # Buttress
    mb = MeshBuilder("SM_Arena_Wall_Buttress_100x400x060")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(1,4,0.6)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wall_Buttress_100x400x060.obj"))

    # Cornice
    mb = MeshBuilder("SM_Arena_Wall_Cornice_400x030x020")
    mb.set_mat(MAT_STONE_WALL)
    mb.add_box(4,0.3,0.2)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wall_Cornice_400x030x020.obj"))

    # Base
    mb = MeshBuilder("SM_Arena_Wall_Base_400x050x110")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(4,0.5,1.1)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wall_Base_400x050x110.obj"))

    # LOD1 wall
    mb = MeshBuilder("SM_Arena_Wall_400x400x100_LOD1")
    mb.set_mat(MAT_STONE_WALL)
    mb.add_box(4,4,1)
    # LOD1 same but we note it as lower
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wall_400x400x100_LOD1.obj"))

def generate_pillars():
    mb = MeshBuilder("SM_Arena_Pillar_Base_180x100x180")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(1.8,1,1.8)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Pillar_Base_180x100x180.obj"))

    mb = MeshBuilder("SM_Arena_Pillar_Shaft_140x400x140")
    mb.set_mat(MAT_STONE_PILLAR)
    # shaft with chamfer: use 8 sides cylinder approximated as box with bevel? Use box for low poly, but we want 8 sides
    # Use cylinder with 8 segments, square shape? Let's use box for simplicity but with 16 tris
    mb.add_box(1.4,4,1.4)
    # Add subtle vertical groove as separate small box negative? Skip
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Pillar_Shaft_140x400x140.obj"))

    mb = MeshBuilder("SM_Arena_Pillar_Capital_170x090x170")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(1.7,0.9,1.7)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Pillar_Capital_170x090x170.obj"))

    # Full pillar 14m: base 1m, shaft 11m, capital 0.9, plus tracery 4m tall 0.12 thick
    mb = MeshBuilder("SM_Arena_Pillar_Full_140x1400")
    mb.set_mat(MAT_STONE_PILLAR)
    # base
    def add_box_at(w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    add_box_at(1.8,1,1.8, 0,0,0, MAT_STONE_PILLAR)
    add_box_at(1.4,11,1.4, 0,1,0, MAT_STONE_PILLAR)
    add_box_at(1.7,0.9,1.7, 0,12,0, MAT_STONE_PILLAR)
    # tracery
    add_box_at(0.9,4,0.12, 0,2,0.76, MAT_STONE_PILLAR)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Pillar_Full_140x1400.obj"))

    # Damaged shaft: split lower 7 and upper 3.5 with gap
    mb = MeshBuilder("SM_Arena_Pillar_Damaged_140x1400")
    mb.set_mat(MAT_STONE_PILLAR)
    add_box_at(1.8,1,1.8, 0,0,0, MAT_STONE_PILLAR)
    add_box_at(1.4,7,1.4, 0,1,0, MAT_STONE_PILLAR)
    add_box_at(1.4,3.5,1.4, 0,8.5,0, MAT_STONE_PILLAR)
    add_box_at(1.7,0.9,1.7, 0,12,0, MAT_STONE_PILLAR)
    # rubble
    add_box_at(0.8,0.4,0.8, 0.6,0,0.6, MAT_STONE_PILLAR)
    add_box_at(0.6,0.3,0.6, -0.7,0,0.5, MAT_STONE_PILLAR)
    add_box_at(0.5,0.5,0.5, 0.2,7,0.3, MAT_STONE_PILLAR) # broken chunk hanging
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Pillar_Damaged_140x1400.obj"))

    # LOD1 full pillar: single box
    mb = MeshBuilder("SM_Arena_Pillar_Full_140x1400_LOD1")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(1.6,14,1.6)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Pillar_Full_140x1400_LOD1.obj"))

def generate_arches():
    # Low broad arch 4m wide, rise 1.5m, thickness 0.5, depth 1
    mb = MeshBuilder("SM_Arena_Arch_400x150x100")
    mb.set_mat(MAT_STONE_WALL)
    # Create arch as extruded shape: 2D points
    # Arch profile: rectangle with semicircular top? Actually low arch: width 4, height of legs 0.5? Let's do arch total height = 2.0? Rise 1.5
    # We'll build using boxes for legs and arch segments
    def add_box_at(w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    # legs
    add_box_at(0.5,1.5,1, -1.75,0,0, MAT_STONE_WALL)
    add_box_at(0.5,1.5,1, 1.75,0,0, MAT_STONE_WALL)
    # arch segments: approximate half circle with 6 segments
    segments = 6
    arch_radius = 2.0
    arch_thickness = 0.5
    for i in range(segments):
        a0 = math.pi * (i/segments)
        a1 = math.pi * ((i+1)/segments)
        # a from 0 to pi, centered
        # x = cos(a)*radius, y = sin(a)*radius + leg height
        x0 = math.cos(a0)*arch_radius
        y0 = math.sin(a0)*arch_radius + 1.5
        x1 = math.cos(a1)*arch_radius
        y1 = math.sin(a1)*arch_radius + 1.5
        # thickness: create box between points with width arch_thickness radial
        # Simplified as small box at mid
        mx = (x0+x1)*0.5
        my = (y0+y1)*0.5
        # length of segment
        dx = x1-x0
        dy = y1-y0
        seg_len = math.sqrt(dx*dx+dy*dy)
        angle = math.atan2(dy,dx)
        # Create oriented box: width seg_len+0.1, height arch_thickness, depth 1
        # For simplicity, use axis-aligned approximation with extra verts? We'll just place a box at mx,my with rotation approximated via quad? Simpler: add_box_at with w=seg_len, h=arch_thickness, but not rotated - will have gaps but okay for low poly placeholder. For better, we compute 4 corners rotated.
        # Let's compute rotated rectangle corners in XY plane
        # local axis: along segment (dx,dy), perp (-dy,dx)
        # perp normalized
        l = math.sqrt(dx*dx+dy*dy) or 1
        ux = dx/l
        uy = dy/l
        vx = -uy
        vy = ux
        hw = seg_len*0.5 + 0.05
        hh = arch_thickness*0.5
        # 4 corners in XY
        corners = [
            (mx + ux*hw + vx*hh, my + uy*hw + vy*hh),
            (mx - ux*hw + vx*hh, my - uy*hw + vy*hh),
            (mx - ux*hw - vx*hh, my - uy*hw - vy*hh),
            (mx + ux*hw - vx*hh, my + uy*hw - vy*hh),
        ]
        # extrude in Z: depth 1
        d = 1.0
        hd = d*0.5
        # create 6 faces for this segment box (oriented)
        # We'll create using quads with those corners
        # top face in terms of perp?
        # For simplicity, create as 2D quad extruded: we have 8 points
        pts = []
        for (cx,cy) in corners:
            pts.append((cx,cy,hd))
            pts.append((cx,cy,-hd))
        # But easier: create 6 quads using our corners: we need to produce oriented box
        # We'll just create side faces as quads
        # Let's create helper to add quad from 4 points
        # Use manual verts
        # For each edge of rectangle, create side quad
        # Instead of complex, we will add as two triangles for each face using add_quad which expects axis aligned? We need custom.
        # We'll directly add quads with computed points
        # front/back
        # front = z = +hd
        p0 = (corners[0][0], corners[0][1], hd)
        p1 = (corners[1][0], corners[1][1], hd)
        p2 = (corners[2][0], corners[2][1], hd)
        p3 = (corners[3][0], corners[3][1], hd)
        # normal approx outward radial
        mb.add_quad(p0,p1,p2,p3, normal=(mx/arch_radius, my/arch_radius,0), mat=MAT_STONE_WALL)
        # back
        p0b = (corners[0][0], corners[0][1], -hd)
        p1b = (corners[1][0], corners[1][1], -hd)
        p2b = (corners[2][0], corners[2][1], -hd)
        p3b = (corners[3][0], corners[3][1], -hd)
        mb.add_quad(p3b,p2b,p1b,p0b, normal=(-mx/arch_radius, -my/arch_radius,0), mat=MAT_STONE_WALL)
        # sides
        mb.add_quad(p0b,p0,p3,p3b, mat=MAT_STONE_WALL)
        mb.add_quad(p1b,p1,p0,p0b, mat=MAT_STONE_WALL)
        mb.add_quad(p2b,p2,p1,p1b, mat=MAT_STONE_WALL)
        mb.add_quad(p3b,p3,p2,p2b, mat=MAT_STONE_WALL)

    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Arch_400x150x100.obj"))

    # Tall arch 3x4
    mb = MeshBuilder("SM_Arena_Arch_300x400x100")
    mb.set_mat(MAT_STONE_WALL)
    def add_box_at2(w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    add_box_at2(0.4,4,1, -1.3,0,0, MAT_STONE_WALL)
    add_box_at2(0.4,4,1, 1.3,0,0, MAT_STONE_WALL)
    add_box_at2(3,0.4,1, 0,4,0, MAT_STONE_WALL)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Arch_300x400x100.obj"))

    # Ruined arch
    mb = MeshBuilder("SM_Arena_Arch_Ruined_400x150x100")
    mb.set_mat(MAT_STONE_WALL)
    add_box_at2(0.5,1.5,1, -1.75,0,0, MAT_STONE_WALL)
    # missing right leg, broken arch segments only 2
    add_box_at2(0.5,0.8,1, 0,1.5,0, MAT_STONE_WALL)
    add_box_at2(0.5,0.6,1, 0.8,1.8,0, MAT_STONE_WALL)
    # rubble
    add_box_at2(0.4,0.3,0.5, 1.75,0,0.3, MAT_STONE_WALL)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Arch_Ruined_400x150x100.obj"))

def generate_windows():
    # Frame 3x4
    mb = MeshBuilder("SM_Arena_Window_Frame_300x400x020")
    mb.set_mat(MAT_STONE_WALL)
    def add_box_at(w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    add_box_at(0.2,4,0.2, -1.4,0,0, MAT_STONE_WALL)
    add_box_at(0.2,4,0.2, 1.4,0,0, MAT_STONE_WALL)
    add_box_at(3,0.2,0.2, 0,0,0, MAT_STONE_WALL)
    add_box_at(3,0.2,0.2, 0,3.8,0, MAT_STONE_WALL)
    add_box_at(0.08,3.6,0.05, 0,0.2,0, MAT_STONE_WALL) # mullion
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Window_Frame_300x400x020.obj"))

    # Large frame 5.2x9.5
    mb = MeshBuilder("SM_Arena_Window_Frame_520x950x020")
    mb.set_mat(MAT_STONE_WALL)
    def add_box_at2(w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    add_box_at2(0.3,9.5,0.2, -2.45,0,0, MAT_STONE_WALL)
    add_box_at2(0.3,9.5,0.2, 2.45,0,0, MAT_STONE_WALL)
    add_box_at2(5.2,0.3,0.2, 0,0,0, MAT_STONE_WALL)
    add_box_at2(5.2,0.3,0.2, 0,9.2,0, MAT_STONE_WALL)
    # arch top
    add_box_at2(0.3,1.0,0.2, -1.2,9.2,0, MAT_STONE_WALL)
    add_box_at2(0.3,1.0,0.2, 1.2,9.2,0, MAT_STONE_WALL)
    add_box_at2(2.4,0.3,0.2, 0,10.2,0, MAT_STONE_WALL)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Window_Frame_520x950x020.obj"))

    # Tracery circle
    mb = MeshBuilder("SM_Arena_Window_Tracery_Circle_100")
    mb.set_mat(MAT_STONE_WALL)
    mb.add_cylinder(0.5,0.12, segments=12, y_offset=0, cap_top=True, cap_bottom=True)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Window_Tracery_Circle_100.obj"))

    # Mullion
    mb = MeshBuilder("SM_Arena_Window_Mullion_020x400x005")
    mb.set_mat(MAT_STONE_WALL)
    mb.add_box(0.2,4,0.05)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Window_Mullion_020x400x005.obj"))

    # Glass pane
    mb = MeshBuilder("SM_Arena_Window_Glass_Pane_280x380")
    mb.set_mat(MAT_GLASS_BLUE)
    mb.add_plane(2.8,3.8, y_offset=0, mat=MAT_GLASS_BLUE)
    # Actually plane should be vertical: rotate 90 deg - our plane is horizontal. Let's make vertical quad
    # Override: create vertical plane at y center
    mb = MeshBuilder("SM_Arena_Window_Glass_Pane_280x380")
    mb.set_mat(MAT_GLASS_BLUE)
    # vertical plane: width 2.8, height 3.8, depth 0.02
    mb.add_box(2.8,3.8,0.02, y_offset=0, mat=MAT_GLASS_BLUE)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Window_Glass_Pane_280x380.obj"))

    # Glass shards cluster
    mb = MeshBuilder("SM_Arena_Window_Glass_Shards_Cluster")
    mb.set_mat(MAT_GLASS_BLUE)
    def add_box_at3(w,h,d,cx,cy,cz,mat, rotY=0):
        # simple axis aligned with rotation Y
        # For shards, random rotation
        # We'll ignore rot for now and just add boxes at positions
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    add_box_at3(0.9,1.2,0.02, -1.2,0.5,0, MAT_GLASS_BLUE)
    add_box_at3(1.1,0.9,0.02, 0.3,1.2,0, MAT_GLASS_RED)
    add_box_at3(0.8,1.5,0.02, 1.0,0.2,0, MAT_GLASS_AMBER)
    add_box_at3(1.2,1.0,0.02, -0.5,2.0,0, MAT_GLASS_BLUE)
    add_box_at3(0.7,0.8,0.02, 0.8,2.5,0, MAT_GLASS_RED)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Window_Glass_Shards_Cluster.obj"))

def generate_stairs():
    mb = MeshBuilder("SM_Arena_Stairs_Step_220x030x100")
    mb.set_mat(MAT_STONE_FLOOR)
    mb.add_box(2.2,0.3,1.0)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Stairs_Step_220x030x100.obj"))

    mb = MeshBuilder("SM_Arena_Stairs_Straight_220x090x300")
    mb.set_mat(MAT_STONE_FLOOR)
    def add_box_at(w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    add_box_at(2.2,0.3,1, 0,0,-1, MAT_STONE_FLOOR)
    add_box_at(2.2,0.3,1, 0,0.3,0, MAT_STONE_FLOOR)
    add_box_at(2.2,0.3,1, 0,0.6,1, MAT_STONE_FLOOR)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Stairs_Straight_220x090x300.obj"))

    mb = MeshBuilder("SM_Arena_Stairs_Broad_400x060x200")
    mb.set_mat(MAT_STONE_FLOOR)
    def add_box_at2(w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    add_box_at2(4,0.3,1, 0,0,0, MAT_STONE_FLOOR)
    add_box_at2(4,0.3,1, 0,0.3,1, MAT_STONE_FLOOR)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Stairs_Broad_400x060x200.obj"))

    # Curved tier stair: wedge with steps
    mb = MeshBuilder("SM_Arena_Stairs_Curved_Tier_1400")
    mb.set_mat(MAT_STONE_FLOOR_RITUAL)
    # Create curved stair: inner radius 5, outer 7, angle 45 deg, 2 steps
    angle_deg = 45
    angle_rad = math.radians(angle_deg)
    r_inner = 5.0
    r_outer = 7.0
    # two steps: first at y0, second at y0+0.3
    for step_idx in range(2):
        y_base = step_idx*0.3
        r0 = r_inner + step_idx*0.5
        r1 = r_outer
        a0 = -angle_rad*0.5
        a1 = angle_rad*0.5
        r_mid = (r_inner+r_outer)*0.5
        # points
        x_i0 = math.cos(a0)*r0
        z_i0 = math.sin(a0)*r0
        x_i1 = math.cos(a1)*r0
        z_i1 = math.sin(a1)*r0
        x_o0 = math.cos(a0)*r1
        z_o0 = math.sin(a0)*r1
        x_o1 = math.cos(a1)*r1
        z_o1 = math.sin(a1)*r1
        def shift(p):
            return (p[0]-r_mid, p[1], p[2])
        y0=y_base
        y1=y_base+0.3
        p_i0_top = shift((x_i0,y1,z_i0))
        p_i1_top = shift((x_i1,y1,z_i1))
        p_o1_top = shift((x_o1,y1,z_o1))
        p_o0_top = shift((x_o0,y1,z_o0))
        p_i0_bot = shift((x_i0,y0,z_i0))
        p_i1_bot = shift((x_i1,y0,z_i1))
        p_o1_bot = shift((x_o1,y0,z_o1))
        p_o0_bot = shift((x_o0,y0,z_o0))
        mb.add_quad(p_i0_top, p_o0_top, p_o1_top, p_i1_top, normal=(0,1,0))
        mb.add_quad(p_i1_bot, p_o1_bot, p_o0_bot, p_i0_bot, normal=(0,-1,0))
        mb.add_quad(p_i0_bot, p_i0_top, p_i1_top, p_i1_bot)
        mb.add_quad(p_o0_bot, p_o1_bot, p_o1_top, p_o0_top)
        mb.add_quad(p_i0_bot, p_o0_bot, p_o0_top, p_i0_top)
        mb.add_quad(p_i1_bot, p_i1_top, p_o1_top, p_o1_bot)

    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Stairs_Curved_Tier_1400.obj"))

    mb = MeshBuilder("SM_Arena_Stairs_Plate_400x030x400")
    mb.set_mat(MAT_STONE_FLOOR)
    mb.add_box(4,0.3,4)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Stairs_Plate_400x030x400.obj"))

def generate_platform():
    mb = MeshBuilder("SM_Arena_Platform_Slab_400x400x030")
    mb.set_mat(MAT_STONE_FLOOR_RITUAL)
    mb.add_box(4,0.3,4)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Platform_Slab_400x400x030.obj"))

    mb = MeshBuilder("SM_Arena_Platform_Cylinder_1000x030")
    mb.set_mat(MAT_STONE_FLOOR_RITUAL)
    mb.add_cylinder(5.0,0.3, segments=32, y_offset=0)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Platform_Cylinder_1000x030.obj"))

    mb = MeshBuilder("SM_Arena_Platform_Cylinder_1400x030")
    mb.set_mat(MAT_STONE_FLOOR_RITUAL)
    mb.add_cylinder(7.0,0.3, segments=32, y_offset=0)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Platform_Cylinder_1400x030.obj"))

    mb = MeshBuilder("SM_Arena_Platform_Rim_1400x015")
    mb.set_mat(MAT_STONE_PILLAR)
    # rim as torus-like ring: cylinder ring with inner radius
    # Create as 32 segments, thickness 0.15, height 0.15
    # We'll make as extruded ring: outer cylinder minus inner? Simplified as 32 boxes around
    for i in range(32):
        a = (i/32)*math.pi*2
        x = math.cos(a)*7.0
        z = math.sin(a)*7.0
        mb.add_box(0.5,0.15,0.15, y_offset=0.3) # placeholder but need offset
        # Actually we need to place boxes at x,z. Use manual
        # Reset builder approach: create custom placement
    # Recreate with custom placement
    mb = MeshBuilder("SM_Arena_Platform_Rim_1400x015")
    mb.set_mat(MAT_STONE_PILLAR)
    def add_box_at(w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    for i in range(32):
        a = (i/32)*math.pi*2
        x = math.cos(a)*7.0
        z = math.sin(a)*7.0
        add_box_at(0.8,0.15,0.3, x,0.3,z, MAT_STONE_PILLAR)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Platform_Rim_1400x015.obj"))

    # Platform with steps cut (2 quadrants have steps)
    mb = MeshBuilder("SM_Arena_Platform_StepRing_1400")
    mb.set_mat(MAT_STONE_FLOOR_RITUAL)
    # We'll generate full cylinder but with notches: for simplicity, generate cylinder plus 2 stair wedges
    mb.add_cylinder(7.0,0.3, segments=32, y_offset=0)
    # Add step cuts as negative? We'll just add extra geometry for steps (like stairs)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Platform_StepRing_1400.obj"))

def generate_statues():
    def add_box_at(mb,w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    mb = MeshBuilder("SM_Arena_Statue_Pedestal_120x100x120")
    mb.set_mat(MAT_STATUE_ERODED)
    mb.add_box(1.2,1.0,1.2)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Statue_Pedestal_120x100x120.obj"))

    mb = MeshBuilder("SM_Arena_Statue_Torso_Robed_070x160x060")
    mb.set_mat(MAT_STATUE_ERODED)
    # torso as capsule approximated by cylinder + box
    mb.add_box(0.7,1.2,0.6, y_offset=0)
    mb.add_cylinder(0.25,0.4, segments=8, y_offset=1.2, mat=MAT_STATUE_ERODED)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Statue_Torso_Robed_070x160x060.obj"))

    mb = MeshBuilder("SM_Arena_Statue_Head_Hooded_030x030x030")
    mb.set_mat(MAT_STATUE_ERODED)
    mb.add_box(0.3,0.3,0.3)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Statue_Head_Hooded_030x030x030.obj"))

    mb = MeshBuilder("SM_Arena_Statue_Complete_120x260x120")
    mb.set_mat(MAT_STATUE_ERODED)
    add_box_at(mb,1.2,0.5,1.2, 0,0,0, MAT_STATUE_ERODED)
    add_box_at(mb,1.0,0.5,1.0, 0,0.5,0, MAT_STATUE_ERODED)
    add_box_at(mb,0.7,1.0,0.6, 0,1.0,0, MAT_STATUE_ERODED)
    add_box_at(mb,0.5,0.6,0.5, 0,2.0,0, MAT_STATUE_ERODED) # head
    # arm stumps
    add_box_at(mb,0.2,0.5,0.2, -0.4,1.2,0, MAT_STATUE_ERODED)
    add_box_at(mb,0.2,0.5,0.2, 0.4,1.2,0, MAT_STATUE_ERODED)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Statue_Complete_120x260x120.obj"))

    mb = MeshBuilder("SM_Arena_Statue_Fallen_180x060x060")
    mb.set_mat(MAT_STATUE_ERODED)
    # fallen: long axis along X, pivot at base center (one end)
    # length 1.8, height 0.6, depth 0.6, lying on side
    add_box_at(mb,1.8,0.6,0.6, 0.9,0,0, MAT_STATUE_ERODED) # pivot at one end, so offset 0.9 in X
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Statue_Fallen_180x060x060.obj"))

    mb = MeshBuilder("SM_Arena_Statue_Ruined_Debris_080x040x080")
    mb.set_mat(MAT_STATUE_ERODED)
    mb.add_box(0.8,0.4,0.8)
    mb.add_box(0.4,0.2,0.4, y_offset=0.4)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Statue_Ruined_Debris_080x040x080.obj"))

    # LOD1 statue: single box
    mb = MeshBuilder("SM_Arena_Statue_Complete_120x260x120_LOD1")
    mb.set_mat(MAT_STATUE_ERODED)
    mb.add_box(1.2,2.6,1.2)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Statue_Complete_120x260x120_LOD1.obj"))

def generate_chains():
    def add_box_at(mb,w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    mb = MeshBuilder("SM_Arena_Chain_Link_018x040")
    mb.set_mat(MAT_METAL_CHAIN)
    # torus link: create as 8-sided torus elongated
    # We'll approximate with 4 boxes forming a link shape
    # Top and bottom bars
    add_box_at(mb,0.18,0.04,0.04, 0,0.18,0, MAT_METAL_CHAIN)
    add_box_at(mb,0.18,0.04,0.04, 0,0,0, MAT_METAL_CHAIN)
    # sides
    add_box_at(mb,0.04,0.18,0.04, -0.07,0.09,0, MAT_METAL_CHAIN)
    add_box_at(mb,0.04,0.18,0.04, 0.07,0.09,0, MAT_METAL_CHAIN)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Chain_Link_018x040.obj"))

    mb = MeshBuilder("SM_Arena_Chain_Segment_6Links_018x240")
    mb.set_mat(MAT_METAL_CHAIN)
    for i in range(6):
        y = i*0.4
        # alternate orientation
        if i%2==0:
            add_box_at(mb,0.18,0.04,0.04, 0,y+0.18,0, MAT_METAL_CHAIN)
            add_box_at(mb,0.18,0.04,0.04, 0,y,0, MAT_METAL_CHAIN)
            add_box_at(mb,0.04,0.18,0.04, -0.07,y+0.09,0, MAT_METAL_CHAIN)
            add_box_at(mb,0.04,0.18,0.04, 0.07,y+0.09,0, MAT_METAL_CHAIN)
        else:
            # rotated 90 deg
            add_box_at(mb,0.04,0.04,0.18, 0,y+0.18,0, MAT_METAL_CHAIN)
            add_box_at(mb,0.04,0.04,0.18, 0,y,0, MAT_METAL_CHAIN)
            add_box_at(mb,0.04,0.18,0.18, 0,y+0.09,0.07, MAT_METAL_CHAIN)
            add_box_at(mb,0.04,0.18,0.18, 0,y+0.09,-0.07, MAT_METAL_CHAIN)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Chain_Segment_6Links_018x240.obj"))

    mb = MeshBuilder("SM_Arena_Chain_Swag_500x004x004")
    mb.set_mat(MAT_METAL_CHAIN)
    # swag as catenary curve approximated with boxes
    for i in range(10):
        t = i/9.0
        x = (t-0.5)*5.0
        # catenary y = a*cosh((x)/a) - offset, approximate parabola y = -0.5*cos(pi*t)+...
        y = -math.sin(math.pi*t)*0.5
        add_box_at(mb,0.5,0.04,0.04, x,y,0, MAT_METAL_CHAIN)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Chain_Swag_500x004x004.obj"))

    mb = MeshBuilder("SM_Arena_Chain_Anchor_018x018x018")
    mb.set_mat(MAT_METAL_CHAIN)
    mb.add_box(0.18,0.18,0.18)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Chain_Anchor_018x018x018.obj"))

    mb = MeshBuilder("SM_Arena_Chain_Hook_020x030x010")
    mb.set_mat(MAT_METAL_CHAIN)
    mb.add_box(0.2,0.05,0.1, y_offset=0.25)
    mb.add_box(0.05,0.3,0.1, y_offset=0)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Chain_Hook_020x030x010.obj"))

def generate_wood():
    def add_box_at(mb,w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    mb = MeshBuilder("SM_Arena_Wood_Beam_320x028x028")
    mb.set_mat(MAT_WOOD_ROTTED)
    mb.add_box(3.2,0.28,0.28)
    # nail plate
    mb.set_mat(MAT_METAL_CHAIN)
    add_box_at(mb,0.24,0.02,0.24, 0,0.14,0, MAT_METAL_CHAIN)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wood_Beam_320x028x028.obj"))

    mb = MeshBuilder("SM_Arena_Wood_Brace_120x028x022")
    mb.set_mat(MAT_WOOD_ROTTED)
    mb.add_box(0.28,1.2,0.22)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wood_Brace_120x028x022.obj"))

    mb = MeshBuilder("SM_Arena_Wood_Plank_200x030x005")
    mb.set_mat(MAT_WOOD_ROTTED)
    mb.add_box(2.0,0.05,0.3)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wood_Plank_200x030x005.obj"))

    mb = MeshBuilder("SM_Arena_Wood_Scaffold_400x400x030")
    mb.set_mat(MAT_WOOD_ROTTED)
    add_box_at(mb,0.28,4,0.28, -1.5,0,0, MAT_WOOD_ROTTED)
    add_box_at(mb,0.28,4,0.28, 1.5,0,0, MAT_WOOD_ROTTED)
    add_box_at(mb,3.2,0.28,0.28, 0,2,0, MAT_WOOD_ROTTED)
    add_box_at(mb,3.0,0.05,0.3, 0,0.5,0, MAT_WOOD_ROTTED)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wood_Scaffold_400x400x030.obj"))

    mb = MeshBuilder("SM_Arena_Wood_Debris_100x020x050")
    mb.set_mat(MAT_WOOD_ROTTED)
    mb.add_box(1.0,0.2,0.5)
    add_box_at(mb,0.5,0.1,0.2, 0.3,0.2,0.1, MAT_WOOD_ROTTED)
    add_box_at(mb,0.3,0.05,0.4, -0.2,0.2,-0.1, MAT_WOOD_ROTTED)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Wood_Debris_100x020x050.obj"))

def generate_candles():
    def add_box_at(mb,w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    mb = MeshBuilder("SM_Arena_Candle_Wax_009x018")
    mb.set_mat(MAT_CANDLE_WAX)
    mb.add_cylinder(0.045,0.18, segments=12, y_offset=0)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Candle_Wax_009x018.obj"))

    mb = MeshBuilder("SM_Arena_Candle_Wax_010x025")
    mb.set_mat(MAT_CANDLE_WAX)
    mb.add_cylinder(0.05,0.25, segments=12, y_offset=0)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Candle_Wax_010x025.obj"))

    mb = MeshBuilder("SM_Arena_Candle_Holder_Brazier_045x006x045")
    mb.set_mat(MAT_BRAZIER_METAL)
    mb.add_cylinder(0.225,0.06, segments=16, y_offset=0)
    # rim
    mb.add_cylinder(0.25,0.02, segments=16, y_offset=0.06)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Candle_Holder_Brazier_045x006x045.obj"))

    mb = MeshBuilder("SM_Arena_Candle_Cluster_3x_045")
    mb.set_mat(MAT_BRAZIER_METAL)
    mb.add_cylinder(0.225,0.06, segments=16, y_offset=0, mat=MAT_BRAZIER_METAL)
    mb.set_mat(MAT_CANDLE_WAX)
    mb.add_cylinder(0.045,0.18, segments=12, y_offset=0.06, mat=MAT_CANDLE_WAX)
    # offset candles
    def add_cyl_at(r,h,seg,y_off,cx,cz,mat):
        # add cylinder at offset
        y0=y_off
        y1=y_off+h
        for i in range(seg):
            a0 = (i/seg)*math.pi*2
            a1 = ((i+1)/seg)*math.pi*2
            x0 = math.cos(a0)*r + cx
            z0 = math.sin(a0)*r + cz
            x1 = math.cos(a1)*r + cx
            z1 = math.sin(a1)*r + cz
            nx0 = math.cos(a0)
            nz0 = math.sin(a0)
            nx1 = math.cos(a1)
            nz1 = math.sin(a1)
            v0 = mb.add_vertex((x0,y0,z0), (i/seg,0), (nx0,0,nz0))
            v1 = mb.add_vertex((x0,y1,z0), (i/seg,1), (nx0,0,nz0))
            v2 = mb.add_vertex((x1,y1,z1), ((i+1)/seg,1), (nx1,0,nz1))
            v3 = mb.add_vertex((x1,y0,z1), ((i+1)/seg,0), (nx1,0,nz1))
            mb.faces.append({"mat": mat, "verts": [v0,v1,v2,v3]})
        # caps
        center_top = (cx,y1,cz)
        center_bot = (cx,y0,cz)
        for i in range(seg):
            a0 = (i/seg)*math.pi*2
            a1 = ((i+1)/seg)*math.pi*2
            x0 = math.cos(a0)*r + cx
            z0 = math.sin(a0)*r + cz
            x1 = math.cos(a1)*r + cx
            z1 = math.sin(a1)*r + cz
            mb.add_tri(center_top, (x0,y1,z0), (x1,y1,z1), normal=(0,1,0), mat=mat)
            mb.add_tri(center_bot, (x1,y0,z1), (x0,y0,z0), normal=(0,-1,0), mat=mat)

    add_cyl_at(0.045,0.22,12,0.06, 0.12,0.08, MAT_CANDLE_WAX)
    add_cyl_at(0.05,0.25,12,0.06, -0.13,0.07, MAT_CANDLE_WAX)
    # flames
    mb.set_mat(MAT_CANDLE_FLAME)
    # flame as small sphere approximated by icosa? Use small box
    add_box_at(mb,0.06,0.08,0.06, 0,0.24,0, MAT_CANDLE_FLAME)
    add_box_at(mb,0.06,0.08,0.06, 0.12,0.28,0.08, MAT_CANDLE_FLAME)
    add_box_at(mb,0.06,0.08,0.06, -0.13,0.31,0.07, MAT_CANDLE_FLAME)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Candle_Cluster_3x_045.obj"))

    mb = MeshBuilder("SM_Arena_Candle_Wall_Sconce_020x030x015")
    mb.set_mat(MAT_BRAZIER_METAL)
    mb.add_box(0.2,0.05,0.15, y_offset=0)
    mb.add_box(0.05,0.3,0.05, y_offset=0)
    mb.set_mat(MAT_CANDLE_WAX)
    mb.add_cylinder(0.04,0.15, segments=8, y_offset=0.3, mat=MAT_CANDLE_WAX)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Candle_Wall_Sconce_020x030x015.obj"))

def generate_ritual():
    def add_box_at(mb,w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    mb = MeshBuilder("SM_Arena_Ritual_Brazier_Large_080x060x080")
    mb.set_mat(MAT_BRAZIER_METAL)
    mb.add_cylinder(0.4,0.1, segments=16, y_offset=0)
    mb.add_cylinder(0.35,0.5, segments=16, y_offset=0.1)
    mb.add_cylinder(0.4,0.05, segments=16, y_offset=0.6)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Ritual_Brazier_Large_080x060x080.obj"))

    mb = MeshBuilder("SM_Arena_Ritual_Circle_320x002x320")
    mb.set_mat(MAT_RITUAL_MARK)
    mb.add_cylinder(1.6,0.02, segments=24, y_offset=0)
    # inner ring
    mb.add_cylinder(1.2,0.02, segments=24, y_offset=0.01)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Ritual_Circle_320x002x320.obj"))

    mb = MeshBuilder("SM_Arena_Ritual_Rune_050x001x050")
    mb.set_mat(MAT_RITUAL_MARK)
    mb.add_box(0.5,0.01,0.5)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Ritual_Rune_050x001x050.obj"))

    mb = MeshBuilder("SM_Arena_Ritual_Chalice_020x030x020")
    mb.set_mat(MAT_BRAZIER_METAL)
    mb.add_cylinder(0.1,0.05, segments=12, y_offset=0)
    mb.add_cylinder(0.02,0.2, segments=8, y_offset=0.05)
    mb.add_cylinder(0.12,0.05, segments=12, y_offset=0.25)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Ritual_Chalice_020x030x020.obj"))

    mb = MeshBuilder("SM_Arena_Ritual_Incense_Burner_025x035x025")
    mb.set_mat(MAT_BRAZIER_METAL)
    mb.add_cylinder(0.125,0.15, segments=12, y_offset=0)
    mb.add_cylinder(0.08,0.2, segments=12, y_offset=0.15)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Ritual_Incense_Burner_025x035x025.obj"))

    mb = MeshBuilder("SM_Arena_Ritual_Altar_Slab_200x080x100")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(2.0,0.8,1.0)
    mb.set_mat(MAT_RITUAL_MARK)
    add_box_at(mb,1.8,0.02,0.8, 0,0.8,0, MAT_RITUAL_MARK)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Ritual_Altar_Slab_200x080x100.obj"))

def generate_debris():
    def add_box_at(mb,w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    mb = MeshBuilder("SM_Arena_Debris_Stone_Small_030x020x030")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(0.3,0.2,0.3)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Debris_Stone_Small_030x020x030.obj"))

    mb = MeshBuilder("SM_Arena_Debris_Stone_Medium_080x040x080")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(0.8,0.4,0.8)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Debris_Stone_Medium_080x040x080.obj"))

    mb = MeshBuilder("SM_Arena_Debris_Stone_Large_120x060x120")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(1.2,0.6,1.2)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Debris_Stone_Large_120x060x120.obj"))

    mb = MeshBuilder("SM_Arena_Debris_Glass_Shards_150x010x100")
    mb.set_mat(MAT_GLASS_BLUE)
    add_box_at(mb,0.4,0.02,0.3, -0.3,0,0.1, MAT_GLASS_BLUE)
    add_box_at(mb,0.5,0.02,0.4, 0.2,0.02,-0.1, MAT_GLASS_RED)
    add_box_at(mb,0.3,0.02,0.3, 0,0.04,0.3, MAT_GLASS_AMBER)
    add_box_at(mb,0.6,0.02,0.2, -0.1,0.01,-0.3, MAT_GLASS_BLUE)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Debris_Glass_Shards_150x010x100.obj"))

    mb = MeshBuilder("SM_Arena_Debris_Rubble_Pile_150x040x150")
    mb.set_mat(MAT_STONE_PILLAR)
    add_box_at(mb,1.5,0.2,1.5, 0,0,0, MAT_STONE_PILLAR)
    add_box_at(mb,0.8,0.3,0.6, 0.2,0.2,0.1, MAT_STONE_PILLAR)
    add_box_at(mb,0.5,0.2,0.5, -0.4,0.2,-0.2, MAT_STONE_PILLAR)
    add_box_at(mb,0.3,0.15,0.3, 0.5,0.2,0.4, MAT_STONE_WALL)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Debris_Rubble_Pile_150x040x150.obj"))

    mb = MeshBuilder("SM_Arena_Debris_Wood_Splinters_100x010x050")
    mb.set_mat(MAT_WOOD_ROTTED)
    add_box_at(mb,0.6,0.05,0.1, 0,0,0, MAT_WOOD_ROTTED)
    add_box_at(mb,0.4,0.04,0.08, 0.3,0.02,0.1, MAT_WOOD_ROTTED)
    add_box_at(mb,0.5,0.03,0.12, -0.2,0.01,-0.15, MAT_WOOD_ROTTED)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Debris_Wood_Splinters_100x010x050.obj"))

def generate_doors():
    def add_box_at(mb,w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    mb = MeshBuilder("SM_Arena_Door_Frame_400x400x020")
    mb.set_mat(MAT_STONE_WALL)
    add_box_at(mb,0.2,4,0.2, -1.9,0,0, MAT_STONE_WALL)
    add_box_at(mb,0.2,4,0.2, 1.9,0,0, MAT_STONE_WALL)
    add_box_at(mb,4,0.2,0.2, 0,3.8,0, MAT_STONE_WALL)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Door_Frame_400x400x020.obj"))

    mb = MeshBuilder("SM_Arena_Door_Wood_Heavy_380x380x010")
    mb.set_mat(MAT_WOOD_ROTTED)
    mb.add_box(3.8,3.8,0.1)
    # planks
    mb.set_mat(MAT_METAL_CHAIN)
    add_box_at(mb,3.8,0.1,0.02, 0,1,0.06, MAT_METAL_CHAIN)
    add_box_at(mb,3.8,0.1,0.02, 0,2,0.06, MAT_METAL_CHAIN)
    add_box_at(mb,0.1,3.8,0.02, 0,0,0.06, MAT_METAL_CHAIN)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Door_Wood_Heavy_380x380x010.obj"))

    mb = MeshBuilder("SM_Arena_Door_Gate_Iron_380x380x005")
    mb.set_mat(MAT_METAL_CHAIN)
    add_box_at(mb,0.05,3.8,0.05, -1.5,0,0, MAT_METAL_CHAIN)
    add_box_at(mb,0.05,3.8,0.05, -0.75,0,0, MAT_METAL_CHAIN)
    add_box_at(mb,0.05,3.8,0.05, 0,0,0, MAT_METAL_CHAIN)
    add_box_at(mb,0.05,3.8,0.05, 0.75,0,0, MAT_METAL_CHAIN)
    add_box_at(mb,0.05,3.8,0.05, 1.5,0,0, MAT_METAL_CHAIN)
    add_box_at(mb,3.8,0.05,0.05, 0,0,0, MAT_METAL_CHAIN)
    add_box_at(mb,3.8,0.05,0.05, 0,1.9,0, MAT_METAL_CHAIN)
    add_box_at(mb,3.8,0.05,0.05, 0,3.8,0, MAT_METAL_CHAIN)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Door_Gate_Iron_380x380x005.obj"))

    mb = MeshBuilder("SM_Arena_Door_Sealed_Stone_400x400x100")
    mb.set_mat(MAT_STONE_WALL)
    mb.add_box(4,4,1)
    mb.set_mat(MAT_STONE_PILLAR)
    add_box_at(mb,0.1,4,0.05, 0,0,0.55, MAT_STONE_PILLAR) # crack
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Door_Sealed_Stone_400x400x100.obj"))

def generate_deco():
    def add_box_at(mb,w,h,d,cx,cy,cz,mat):
        hw=w*0.5; hd=d*0.5
        x0=cx-hw; x1=cx+hw
        y0=cy; y1=cy+h
        z0=cz-hd; z1=cz+hd
        mb.add_quad((x0,y1,z0),(x1,y1,z0),(x1,y1,z1),(x0,y1,z1), normal=(0,1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x1,y0,z1),(x1,y0,z0),(x0,y0,z0), normal=(0,-1,0), mat=mat)
        mb.add_quad((x0,y0,z1),(x0,y1,z1),(x1,y1,z1),(x1,y0,z1), normal=(0,0,1), mat=mat)
        mb.add_quad((x1,y0,z0),(x1,y1,z0),(x0,y1,z0),(x0,y0,z0), normal=(0,0,-1), mat=mat)
        mb.add_quad((x1,y0,z1),(x1,y1,z1),(x1,y1,z0),(x1,y0,z0), normal=(1,0,0), mat=mat)
        mb.add_quad((x0,y0,z0),(x0,y1,z0),(x0,y1,z1),(x0,y0,z1), normal=(-1,0,0), mat=mat)

    mb = MeshBuilder("SM_Arena_Deco_Gargoyle_060x080x040")
    mb.set_mat(MAT_STONE_WALL)
    add_box_at(mb,0.6,0.5,0.4, 0,0,0, MAT_STONE_WALL)
    add_box_at(mb,0.3,0.3,0.2, 0.3,0.3,0, MAT_STONE_WALL) # head
    add_box_at(mb,0.2,0.1,0.3, 0.4,0.2,0, MAT_STONE_WALL) # snout
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Deco_Gargoyle_060x080x040.obj"))

    mb = MeshBuilder("SM_Arena_Deco_Cornice_400x020x020")
    mb.set_mat(MAT_STONE_WALL)
    mb.add_box(4,0.2,0.2)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Deco_Cornice_400x020x020.obj"))

    mb = MeshBuilder("SM_Arena_Deco_Banner_Tattered_100x300x002")
    mb.set_mat(MAT_WOOD_ROTTED) # will be banner mat later, reuse wood for now
    mb.add_box(1.0,3.0,0.02)
    # tattered bottom as smaller boxes missing
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Deco_Banner_Tattered_100x300x002.obj"))

    mb = MeshBuilder("SM_Arena_Deco_Iron_Bracket_030x020x040")
    mb.set_mat(MAT_METAL_CHAIN)
    add_box_at(mb,0.3,0.05,0.4, 0,0.2,0, MAT_METAL_CHAIN)
    add_box_at(mb,0.05,0.2,0.4, -0.125,0,0, MAT_METAL_CHAIN)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Deco_Iron_Bracket_030x020x040.obj"))

    mb = MeshBuilder("SM_Arena_Deco_Candelabra_Wall_020x060x020")
    mb.set_mat(MAT_BRAZIER_METAL)
    mb.add_box(0.2,0.6,0.2)
    mb.set_mat(MAT_CANDLE_WAX)
    add_box_at(mb,0.08,0.15,0.08, -0.05,0.6,0, MAT_CANDLE_WAX)
    add_box_at(mb,0.08,0.15,0.08, 0.05,0.6,0, MAT_CANDLE_WAX)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Deco_Candelabra_Wall_020x060x020.obj"))

    mb = MeshBuilder("SM_Arena_Deco_Fog_Volume_1000x002x1000")
    mb.set_mat(MAT_FOG)
    mb.add_box(10,0.02,10)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Deco_Fog_Volume_1000x002x1000.obj"))

    mb = MeshBuilder("SM_Arena_Deco_Moss_Patch_100x005x100")
    mb.set_mat(MAT_STONE_PILLAR)
    mb.add_box(1,0.05,1)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Deco_Moss_Patch_100x005x100.obj"))

def generate_lods():
    # Already generated some LODs, generate remaining
    mb = MeshBuilder("SM_Arena_Floor_400x400x050_LOD1")
    mb.set_mat(MAT_STONE_FLOOR)
    mb.add_box(4,0.5,4)
    mb.write_obj(os.path.join(OUT_DIR, "SM_Arena_Floor_400x400x050_LOD1.obj"))

if __name__ == "__main__":
    print("Generating modular arena meshes...")
    generate_floor_tiles()
    generate_walls()
    generate_pillars()
    generate_arches()
    generate_windows()
    generate_stairs()
    generate_platform()
    generate_statues()
    generate_chains()
    generate_wood()
    generate_candles()
    generate_ritual()
    generate_debris()
    generate_doors()
    generate_deco()
    generate_lods()
    print("Done.")
