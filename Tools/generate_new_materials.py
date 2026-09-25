#!/usr/bin/env python3
"""
Generate additional arena materials for banner, moss, door wood, door iron
"""

import os, uuid
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "vespershade://unity-project")
def guid_for(rel):
    return uuid.uuid5(NAMESPACE, rel.replace(os.sep, "/")).hex

MATERIALS = {
    "Assets/Materials/Arena/M_Arena_Banner_Cloth.mat": {
        "color": (0.62, 0.18, 0.16, 1),
        "metallic": 0.0,
        "gloss": 0.12,
        "emission": (0,0,0,1),
    },
    "Assets/Materials/Arena/M_Arena_Moss.mat": {
        "color": (0.15, 0.25, 0.12, 1),
        "metallic": 0.0,
        "gloss": 0.05,
        "emission": (0,0,0,1),
    },
    "Assets/Materials/Arena/M_Arena_Door_Wood.mat": {
        "color": (0.18, 0.12, 0.08, 1),
        "metallic": 0.0,
        "gloss": 0.08,
        "emission": (0,0,0,1),
    },
    "Assets/Materials/Arena/M_Arena_Door_Iron.mat": {
        "color": (0.08, 0.08, 0.09, 1),
        "metallic": 0.8,
        "gloss": 0.25,
        "emission": (0,0,0,1),
    },
    "Assets/Materials/Arena/M_Arena_StoneTrim.mat": {
        "color": (0.19, 0.185, 0.20, 1),
        "metallic": 0.02,
        "gloss": 0.07,
        "emission": (0,0,0,1),
    },
}

template = """%YAML 1.1
%TAG !u! tag:unity3d.com,2011:
--- !u!21 &2100000
Material:
  serializedVersion: 8
  m_ObjectHideFlags: 0
  m_CorrespondingSourceObject: {{fileID: 0}}
  m_PrefabInstance: {{fileID: 0}}
  m_PrefabAsset: {{fileID: 0}}
  m_Name: {name}
  m_Shader: {{fileID: 46, guid: 0000000000000000f000000000000000, type: 0}}
  m_Parent: {{fileID: 0}}
  m_ModifiedProperties:
  m_ValidKeywords: []
  m_InvalidKeywords: []
  m_LightmapFlags: 4
  m_EnableInstancingVariants: 0
  m_DoubleSidedGI: 0
  m_CustomRenderQueue: -1
  stringTagMap: {{}}
  disabledShaderPasses: []
  m_LockedProperties:
  m_SavedProperties:
    serializedVersion: 3
    m_TexEnvs: []
    m_Ints: []
    m_Floats:
    - _BumpScale: 1
    - _Cutoff: 0.5
    - _DetailNormalMapScale: 1
    - _DstBlend: 0
    - _GlossMapScale: 1
    - _Glossiness: {gloss}
    - _GlossyReflections: 1
    - _Metallic: {metallic}
    - _Mode: 0
    - _OcclusionStrength: 1
    - _Parallax: 0.02
    - _SmoothnessTextureChannel: 0
    - _SpecularHighlights: 1
    - _SrcBlend: 1
    - _UVSec: 0
    - _ZWrite: 1
    m_Colors:
    - _Color: {{r: {r}, g: {g}, b: {b}, a: {a}}}
    - _EmissionColor: {{r: {er}, g: {eg}, b: {eb}, a: {ea}}}
  m_BuildTextureStacks: []
"""

for rel, props in MATERIALS.items():
    full_path = os.path.join(ROOT, rel)
    name = os.path.splitext(os.path.basename(rel))[0]
    r,g,b,a = props["color"]
    er,eg,eb,ea = props["emission"]
    content = template.format(
        name=name,
        gloss=props["gloss"],
        metallic=props["metallic"],
        r=r,g=g,b=b,a=a,
        er=er,eg=eg,eb=eb,ea=ea
    )
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Wrote {rel}")

print("Done generating new materials")
