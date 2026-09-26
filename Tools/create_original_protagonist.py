#!/usr/bin/env python3
"""Build the original Vespershade protagonist as a smooth, multi-material OBJ.

All forms are original procedural meshes in metres. Running this script writes
only Assets/Models/Characters/SM_Character_VeilboundWayfarer.obj and its MTL.
"""
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "Assets/Models/Characters")
os.makedirs(OUT, exist_ok=True)

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

def ellipsoid(mat, name, center, scale, rings=18, sides=28, rotation=None):
    # Smooth UV surface with shared ring vertices; poles are merged to avoid pinched fans.
    rot = rotation or ((1,0,0),(0,1,0),(0,0,1))
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
    fs=[]
    for s in range(sides): fs.append((0, 1+(s+1)%sides, 1+s))
    for r in range(rings-2):
        a=1+r*sides; b=a+sides
        for s in range(sides):
            n=(s+1)%sides
            fs.extend(((a+n,b+s,a+s),(b+n,b+s,a+n)))
    last=1+(rings-2)*sides
    for s in range(sides): fs.append((last+(s+1)%sides,bottom,last+s))
    add_mesh(mat,name,pts,fs)

def tube(mat, name, points, radii, sides=16, preferred=(1,0,0), depth_scale=1.0):
    """Smooth swept tapered form; radius entries are (width, depth) or scalars."""
    centers=[tuple(p) for p in points]
    if len(radii) != len(centers): raise ValueError("one radius per tube point")
    rings=[]
    for i,c in enumerate(centers):
        tangent=norm(vsub(centers[min(i+1,len(centers)-1)], centers[max(0,i-1)]))
        hint=preferred
        b1=vsub(hint,vmul(tangent,dot(hint,tangent)))
        if dot(b1,b1)<1e-6:
            hint=(0,0,1) if abs(tangent[2])<0.8 else (0,1,0)
            b1=vsub(hint,vmul(tangent,dot(hint,tangent)))
        b1=norm(b1); b2=norm(cross(tangent,b1))
        rad=radii[i]
        rw,rd=(rad,rad*depth_scale) if isinstance(rad,(float,int)) else rad
        for s in range(sides):
            a=2*math.pi*s/sides
            p=vadd(c,vadd(vmul(b1,rw*math.cos(a)),vmul(b2,rd*math.sin(a))))
            rings.append(p)
    fs=[]
    for r in range(len(centers)-1):
        for s in range(sides):
            a=r*sides+s; an=r*sides+(s+1)%sides
            b=(r+1)*sides+s; bn=(r+1)*sides+(s+1)%sides
            fs.extend(((a,an,b),(an,bn,b)))
    # capped ends
    for end, reverse in ((0,True),(len(centers)-1,False)):
        center_idx=len(rings); rings.append(centers[end]); base=end*sides
        for s in range(sides):
            tri=(center_idx,base+(s+1)%sides,base+s) if reverse else (center_idx,base+s,base+(s+1)%sides)
            fs.append(tri)
    add_mesh(mat,name,rings,fs)

def ring_surface(mat,name,profile,sides=48,front_split=0.0):
    """Closed elliptical garment/neck ring; profile=(y,rx,rz,zcenter)."""
    pts=[]
    for y,rx,rz,zc in profile:
        for s in range(sides):
            a=2*math.pi*s/sides
            x=rx*math.cos(a); z=zc+rz*math.sin(a)
            if front_split and z>0 and abs(x)<front_split: x=math.copysign(front_split,x if x else 1)
            pts.append((x,y,z))
    fs=[]
    for r in range(len(profile)-1):
        for s in range(sides):
            a=r*sides+s; an=r*sides+(s+1)%sides
            b=(r+1)*sides+s; bn=(r+1)*sides+(s+1)%sides
            fs.extend(((b,an,a),(b,bn,an)))
    add_mesh(mat,name,pts,fs)

def panel(mat,name,grid, double_sided=True):
    rows=len(grid); cols=len(grid[0]); pts=[p for row in grid for p in row]; fs=[]
    for r in range(rows-1):
        for c in range(cols-1):
            a=r*cols+c; b=a+cols
            fs.append((a,a+1,b)); fs.append((a+1,b+1,b))
            if double_sided:
                fs.append((b,a+1,a)); fs.append((b,b+1,a+1))
    add_mesh(mat,name,pts,fs)

def strap_path(mat,name,points,width,offset=(0,0,0),segments=20):
    # A raised rounded seam / leather cord follows the path.
    tube(mat,name,points,[width*(0.55+0.45*math.sin(math.pi*i/(len(points)-1))) for i in range(len(points))],12,preferred=(0,1,0),depth_scale=0.55)

# Human base silhouette: long-limbed, narrow waist, relaxed neutral A-stance.
# Trousers remain articulated at knees and ankles with sculpted taper.
for side, label in ((-1,"L"),(1,"R")):
    x=side
    tube("Trouser",f"LowerBody/Leg_{label}",[(x*.105,.83,0),(x*.112,.68,-.005),(x*.115,.48,.018),(x*.12,.28,.012)],[(.102,.112),(.090,.098),(.073,.078),(.068,.073)],22,(1,0,0))
    # Hidden shirt/sleeve underlayer gives a complete body when seen between layers.
    tube("Skin",f"Body/Forearm_{label}",[(x*.27,1.27,.005),(x*.34,1.10,.018),(x*.365,.97,.035),(x*.37,.88,.04)],[(.075,.075),(.065,.065),(.052,.052),(.047,.05)],20,(1,0,0))
    # Long, tailored outer sleeves follow the slightly relaxed arms.
    tube("Cloth",f"UpperClothing/Sleeve_{label}",[(x*.19,1.47,-.005),(x*.29,1.37,.005),(x*.36,1.21,.018),(x*.38,1.04,.03),(x*.38,.96,.035)],[(.105,.105),(.098,.10),(.081,.084),(.069,.072),(.071,.073)],24,(1,0,0))
    # Narrow rolled cuff and leather glove.
    tube("Leather",f"Accessories/Cuff_{label}",[(x*.38,1.01,.032),(x*.38,.965,.035)],[(.074,.077),(.071,.073)],24,(1,0,0))
    tube("Leather",f"Accessories/Glove_{label}",[(x*.38,.97,.037),(x*.385,.91,.055),(x*.39,.855,.065)],[(.067,.070),(.060,.058),(.051,.047)],20,(1,0,0))
    # Five distinct, softly tapered fingers; curled slightly inward, no mitten silhouette.
    for j in range(4):
        fx=x*.39+(j-1.5)*.024
        length=(.076,.092,.091,.073)[j]
        z=.067+(.012 if j in (1,2) else 0)
        tube("Leather",f"Accessories/Glove_{label}_Finger{j+1}",[(fx,.875,z),(fx+x*.003,.835,z+.005),(fx+x*.006,.875-length,z+.014)],[(.014,.014),(.012,.012),(.008,.009)],12,(1,0,0))
    # Thumb sweeps diagonally inward in a natural resting fist.
    tube("Leather",f"Accessories/Glove_{label}_Thumb",[(x*.345,.91,.055),(x*.325,.875,.077),(x*.319,.84,.087)],[(.021,.022),(.017,.018),(.011,.012)],14,(1,0,0))
    # Tall fitted boot shaft over the trouser cuff.
    tube("Leather",f"Boots/BootShaft_{label}",[(x*.12,.33,.005),(x*.12,.24,.012),(x*.12,.105,.025),(x*.12,.065,.035)],[(.085,.092),(.088,.095),(.095,.11),(.10,.115)],24,(1,0,0))
    # Toe cap and raised sole have distinct silhouettes.
    ellipsoid("Leather",f"Boots/Toe_{label}",(x*.12,.105,.092),(.096,.078,.172),18,32)
    ellipsoid("BootSole",f"Boots/Sole_{label}",(x*.12,.045,.055),(.103,.035,.19),12,32)
    tube("AgedBrass",f"Boots/AnkleHookRow_{label}",[(x*.12,.26,-.03),(x*.12,.23,-.03)],[(.091,.095),(.092,.097)],24,(1,0,0))
    # Three tiny brass lace hooks, set into the boot's outward facing quarter.
    for k in range(3):
        ellipsoid("AgedBrass",f"Boots/Hook_{label}_{k}",(x*(.12+.083),.20-k*.035,.015),(.009,.009,.012),8,12)

# Pelvis and trousers beneath the coat.
ring_surface("Trouser","LowerBody/TailoredWaist",[(.72,.20,.125,0),(.80,.205,.13,0),(.94,.235,.14,0),(1.04,.245,.145,0)],40)
ellipsoid("Trouser","LowerBody/Pelvis",(0,.91,0),(.235,.15,.142),18,32)
# Anatomically tapered shirt/torso, neck and visible face/hands.
ring_surface("Skin","Body/Torso",[(1.00,.18,.105,0),(1.10,.205,.115,0),(1.25,.25,.13,0),(1.39,.29,.135,0),(1.49,.255,.115,0)],36)
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

# Distinctive fitted high-collared long coat: narrow waist, broad shoulder line, split tails.
ring_surface("Cloth","UpperClothing/LongCoat_Bodice",[(.94,.237,.153,0),(1.01,.235,.152,0),(1.12,.221,.143,0),(1.26,.265,.147,0),(1.39,.305,.145,0),(1.49,.285,.125,0)],48)
# Shaped shoulder mantle, softly raised across the back and outward over each shoulder.
ring_surface("ClothAccent","UpperClothing/ShoulderMantle",[(1.39,.30,.151,0),(1.43,.325,.154,0),(1.48,.31,.137,0)],48)
# Wine-black high collar sits under the jaw; taller at the back than front.
ring_surface("ClothAccent","UpperClothing/StandingCollar",[(1.475,.148,.12,0),(1.515,.142,.115,0),(1.565,.128,.108,-.006)],40)
ring_surface("Cloth","UpperClothing/CollarFacing",[(1.49,.151,.123,0),(1.515,.146,.119,0),(1.545,.137,.113,-.005)],40)
# Narrow ivory piping accents the collar edge and asymmetric lapels.
tube("BoneThread","Accessories/CollarPiping",[(0,1.56,-.105),(.075,1.55,-.082),(.125,1.53,-.01),(.11,1.515,.075),(0,1.51,.125),(-.10,1.515,.08),(-.125,1.53,0),(-.07,1.55,-.085),(0,1.56,-.105)],[.004]*9,10,(1,0,0))
# Long, split rear coat tails, gently swept backward and edged with muted wine lining.
for side,label in ((-1,"L"),(1,"R")):
    cols=9; rows=9; grid=[]; lining=[]
    for r in range(rows):
        t=r/(rows-1); y=1.00-.45*t
        row=[]; lrow=[]
        for c in range(cols):
            u=c/(cols-1)*2-1
            x=side*(.015+.15*u*(.76+.28*t)) + side*.14*t
            z=-.105-.055*math.sin(math.pi*t)+.045*abs(u)+.012*math.cos(u*math.pi)
            z+=.025*math.sin(t*math.pi+u*1.7)
            row.append((x,y,z))
            lrow.append((x,y,z-.009))
        grid.append(row); lining.append(lrow)
    panel("Cloth",f"LowerClothing/CoatTail_{label}",grid)
    # narrow visible inner facing along the lower split panel
    panel("ClothAccent",f"LowerClothing/CoatTailLining_{label}",[row[:2]+row[-2:] for row in []] if False else [
        [grid[r][c] for c in range(cols)] for r in range(rows-1, max(-1,rows-4), -1)
    ])
    # Raised tailored edge seams run along outer edges and hem.
    tube("BoneThread",f"Accessories/TailEdge_{label}",[grid[r][0] for r in range(rows)],[.0035]*rows,10,(0,0,1))
    tube("BoneThread",f"Accessories/TailEdge2_{label}",[grid[r][-1] for r in range(rows)],[.0035]*rows,10,(0,0,1))
# A structured front bib peeks between the coat fronts.
# Chest bib as sculpted shield-shaped layered panel on the front (+Z).
for mat, name, zoff, width in (("ClothAccent","UpperClothing/InnerWaistcoat",.154,.095),("BoneThread","UpperClothing/WaistcoatPiping",.162,.004)):
    grid=[]
    for r in range(9):
        t=r/8; y=1.47-.39*t; w=width*(.73+.27*math.sin(math.pi*t))
        if mat=="BoneThread": w=.004
        grid.append([(-w+(2*w*c/8),y,.145+zoff*.05+0.006*math.sin(math.pi*c/8)) for c in range(9)])
    if mat=="BoneThread":
        tube(mat,name,[grid[r][4] for r in range(9)],[.003]*9,10,(1,0,0))
    else: panel(mat,name,grid)
# Asymmetric overlapping lapels on the chest.
for side,label in ((-1,"L"),(1,"R")):
    lapel=[]
    for r in range(8):
        t=r/7; y=1.50-.34*t; row=[]
        for c in range(5):
            u=c/4
            x=side*(.145*(1-t)+.018*t) + side*(u-.5)*.075
            z=.141+.036*math.sin(math.pi*u)*(.7+.3*t)
            row.append((x,y,z))
        lapel.append(row)
    panel("ClothAccent",f"UpperClothing/Lapel_{label}",lapel)
    tube("BoneThread",f"Accessories/LapelStitch_{label}",[lapel[r][2] for r in range(8)],[.003]*8,10,(1,0,0))
# Sleeve elbow darts, cuff embroidery and shoulders.
for side,label in ((-1,"L"),(1,"R")):
    tube("Leather",f"UpperClothing/ShoulderInset_{label}",[(side*.215,1.455,-.07),(side*.28,1.40,-.075),(side*.335,1.32,-.05)],[(.028,.016),(.025,.014),(.010,.010)],14,(1,0,0))
    tube("AgedBrass",f"Accessories/CuffInlay_{label}",[(side*.382,1.005,-.01),(side*.38,.995,.07),(side*.38,.98,.11)],[(.004,.003)]*3,10,(1,0,0))

# Sculpted belt, buckle, loops and small travel pouches.
ring_surface("Leather","Accessories/WideWaistBelt",[(.995,.242,.161,0),(1.035,.246,.165,0),(1.075,.238,.157,0)],48)
# Front buckle, a rounded frame with a central tongue.
for x in (-.043,.043): tube("AgedBrass","Accessories/BuckleSide",[(x,1.018,.166),(x,1.055,.166)], [.007,.007],10,(1,0,0))
for y in (1.018,1.055): tube("AgedBrass","Accessories/BuckleBar",[(-.043,y,.166),(.043,y,.166)],[.007,.007],10,(1,0,0))
tube("AgedBrass","Accessories/BuckleTongue",[(0,1.036,.17),(.025,1.036,.171)],[.004,.004],10,(1,0,0))
for side,label in ((-1,"L"),(1,"R")):
    for i in range(2):
        ellipsoid("AgedBrass",f"Accessories/BeltStud_{label}{i}",(side*(.105+i*.045),1.035,.164),(.008,.008,.006),8,12)
    ellipsoid("Leather",f"Accessories/FieldPouch_{label}",(side*.205,1.035,.038),(.042,.052,.032),14,20)
    tube("AgedBrass",f"Accessories/PouchFlap_{label}",[(side*.24,1.055,.045),(side*.205,1.07,.065),(side*.17,1.055,.045)],[.004]*3,10,(1,0,0))

# Fine chest harness: crossed leather straps and a small original crescent-like astrolabe clasp.
tube("Leather","Accessories/DiagonalHarness",[(-.21,1.43,.105),(-.12,1.35,.151),(-.04,1.27,.163),(.07,1.18,.15),(.19,1.10,.117)],[(.022,.009)]*5,12,(1,0,0))
tube("Leather","Accessories/ShoulderHarness",[(.19,1.43,.10),(.11,1.35,.15),(.015,1.26,.164),(-.10,1.16,.15),(-.20,1.10,.11)],[(.018,.009)]*5,12,(1,0,0))
# Disc/clasp and suspended tiny ring: original celestial navigation ornament, not a weapon.
ellipsoid("AgedBrass","Accessories/AstrolabeClasp",(0,1.30,.178),(.047,.052,.014),16,28)
ellipsoid("ClothAccent","Accessories/ClaspInset",(0,1.30,.194),(.031,.037,.006),14,24)
tube("AgedBrass","Accessories/ClaspArc",[(-.025,1.285,.204),(-.014,1.321,.203),(0,1.338,.203),(.018,1.324,.203),(.026,1.294,.203)],[.003]*5,10,(1,0,0))
ellipsoid("AgedBrass","Accessories/ClaspStar",(0,1.30,.206),(.006,.009,.004),10,14)
# Five understated coat buttons descend from sternum; catches moonlit highlights.
for i in range(5):
    y=1.43-i*.064
    ellipsoid("AgedBrass",f"Accessories/CoatButton_{i+1}",(.015,y,.165-.012*i),(.012,.012,.007),10,16)
    ellipsoid("BoneThread",f"Accessories/ButtonCore_{i+1}",(.015,y,.171-.012*i),(.004,.004,.002),8,12)
# One asymmetrical shoulder fastener and two small hanging thread tassels.
ellipsoid("AgedBrass","Accessories/ShoulderClasp",(-.255,1.435,.076),(.028,.034,.012),14,20)
tube("BoneThread","Accessories/ShoulderPin",[(-.255,1.47,.084),(-.255,1.40,.084)],[.003,.003],10,(1,0,0))
for s in (-1,1):
    tube("ClothAccent",f"Accessories/ThreadTassel_{s}",[(s*.18,1.06,-.15),(s*.19,.99,-.17),(s*.205,.91,-.16)],[(.013,.01),(.009,.008),(.002,.003)],12,(1,0,0))

# Export material buffers in stable order. Normals are generated by Unity from smooth vertex rings.
obj_path=os.path.join(OUT,"SM_Character_VeilboundWayfarer.obj")
mtl_path=os.path.join(OUT,"SM_Character_VeilboundWayfarer.mtl")
with open(obj_path,"w",encoding="utf-8") as f:
    f.write("# Veilbound Wayfarer - original Vespershade protagonist, 1 unit = 1 metre\n")
    f.write("# Smooth assembled sculptural parts; material submeshes separate clothing layers and accessories.\n")
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
