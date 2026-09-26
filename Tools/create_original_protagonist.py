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
tube("Skin","Body/Neck",[(0,1.43,0),(0,1.53,.012),(0,1.60,.018)],[(.080,.079),(.071,.073),(.068,.071)],24,(1,0,0))
# Face has tapered jaw/chin proportions, subtle ears, brows, nose and inset eyes.
ellipsoid("Skin","Head/Face",(0,1.675,.018),(.116,.151,.103),24,36)
ellipsoid("Skin","Head/Jaw",(0,1.615,.035),(.096,.087,.088),18,32)
for side,label in ((-1,"L"),(1,"R")):
    ellipsoid("Skin",f"Head/Ear_{label}",(side*.113,1.674,.005),(.024,.043,.027),14,20)
    ellipsoid("Hair",f"Head/EyeSocket_{label}",(side*.045,1.683,.108),(.022,.013,.008),12,20)
    ellipsoid("BoneThread",f"Head/Eye_{label}",(side*.045,1.683,.114),(.010,.006,.004),10,16)
    tube("Skin",f"Head/Brow_{label}",[(side*.075,1.707,.102),(side*.045,1.716,.113),(side*.018,1.707,.111)],[(.009,.008),(.010,.008),(.006,.006)],12,(1,0,0))
# Fine angular nose bridge and tip in two softly blended forms.
tube("Skin","Head/Nose",[(0,1.70,.105),(0,1.672,.136),(0,1.653,.132)],[(.012,.011),(.010,.010),(.014,.012)],14,(1,0,0))
# Mouth line, subtle and subdued.
tube("Leather","Head/Mouth",[(-.027,1.625,.111),(0,1.622,.12),(.027,1.625,.111)],[.003,.004,.003],10,(1,0,0))

# Face-framing swept dark hair: short nape, one long asymmetric temple lock, carved locks.
ellipsoid("Hair","Hair/Crown",(0,1.785,-.002),(.127,.073,.112),20,32)
for i in range(7):
    x=-.095+i*.031
    z=-.012-0.013*math.sin(i*.55)
    tube("Hair",f"Hair/SweptLock_{i+1}",[(x,1.812,z),(x*.86,1.788,z+.047),(x*.67,1.746,z+.091),(x*.58,1.707,z+.078)],[(.034,.031),(.031,.027),(.022,.021),(.007,.010)],16,(1,0,0))
# Left temple fall and rear nape locks make the profile distinct.
tube("Hair","Hair/TempleFall",[(-.092,1.79,.032),(-.119,1.74,.075),(-.122,1.675,.078),(-.105,1.625,.045)],[(.034,.027),(.028,.022),(.021,.018),(.006,.008)],16,(1,0,0))
for s in (-1,1):
    tube("Hair",f"Hair/Nape_{s}",[(s*.075,1.755,-.065),(s*.082,1.70,-.092),(s*.07,1.63,-.083)],[(.030,.031),(.024,.025),(.006,.009)],14,(1,0,0))

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
