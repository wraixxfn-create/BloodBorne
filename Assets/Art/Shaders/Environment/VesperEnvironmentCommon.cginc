// Vespershade - shared environment surface code (Built-in RP, surface shaders)
//
// Provides:
//   * projection space selection (world / object-rotated, metric) for triplanar mapping
//   * triplanar sampling of albedo / normal / roughness / metallic / AO with a
//     whiteout normal blend (correct handedness on all six faces)
//   * macro variation (world-space, low-frequency) to break tiling
//   * per-object hash for subtle tone variation between identical modules
//   * damp base grime, vertical leak streaks and a height-aware dust layer
//
// All maps are authored as ROUGHNESS; conversion to Unity smoothness happens
// once here, so artists never have to invert textures.

#ifndef VESPER_ENVIRONMENT_COMMON_INCLUDED
#define VESPER_ENVIRONMENT_COMMON_INCLUDED

#include "UnityPBSLighting.cginc"

// ---------------------------------------------------------------------------
// Resources. One sampler per "family" keeps us well under the 16-sampler limit.
// ---------------------------------------------------------------------------
UNITY_DECLARE_TEX2D(_MainTex);
UNITY_DECLARE_TEX2D_NOSAMPLER(_BumpMap);
UNITY_DECLARE_TEX2D_NOSAMPLER(_RoughnessMap);
UNITY_DECLARE_TEX2D_NOSAMPLER(_MetallicGlossMap);
UNITY_DECLARE_TEX2D_NOSAMPLER(_OcclusionMap);
UNITY_DECLARE_TEX2D_NOSAMPLER(_EmissionMap);
UNITY_DECLARE_TEX2D(_MacroMap);
UNITY_DECLARE_TEX2D(_DustMap);
UNITY_DECLARE_TEX2D_NOSAMPLER(_DustBumpMap);

half4  _Color;
half   _BumpScale;
half   _RoughnessMin;
half   _RoughnessMax;
half   _Metallic;
half   _OcclusionStrength;

float  _TileSize;          // metres covered by one texture repeat
float  _BlendSharpness;    // triplanar blend exponent
float  _ObjectSpace;       // 0 = world, 1 = object (rotation only, metric)
float4 _MainTex_ST;

// variation
float  _MacroScale;        // metres per macro repeat
half   _MacroAlbedo;       // +/- brightness from macro R
half   _MacroRoughness;    // +/- roughness from macro G
half4  _VariationTint;     // tint pushed into macro G blotches
half   _VariationTintStrength;
half   _ObjectVariation;   // per-object brightness spread

// grime & leaks
half   _GrimeHeight;       // metres above world y=0 affected by damp
half   _GrimeStrength;
half   _StreakStrength;    // vertical leak streak darkening

// dust
half   _DustAmount;
half   _DustSharpness;
half   _DustCavityBias;
float  _DustTileSize;
half4  _DustColor;
float4 _DustCenter;        // xz = centre of the swept (clean) area
float4 _DustRadius;        // x = clean radius, y = fully dusty radius, z = min multiplier at centre

// emission
half4  _EmissionColor;
float  _EmissionTileSize;
half   _EmissionFlow;
half   _EmissionFlowSpeed;
float  _RitualPulse;       // driven at runtime by ArenaLightingController (MaterialPropertyBlock)

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
inline float VesperHash31(float3 p)
{
    p = frac(p * 0.1031);
    p += dot(p, p.zyx + 31.32);
    return frac((p.x + p.y) * p.z);
}

inline float3x3 VesperObjectRotation()
{
    float3x3 m = (float3x3)unity_ObjectToWorld;
    float3 s = float3(length(float3(m[0].x, m[1].x, m[2].x)),
                      length(float3(m[0].y, m[1].y, m[2].y)),
                      length(float3(m[0].z, m[1].z, m[2].z)));
    s = max(s, 1e-5);
    return float3x3(m[0] / s, m[1] / s, m[2] / s); // columns normalised -> pure rotation
}

inline float3 VesperObjectOrigin()
{
    return float3(unity_ObjectToWorld[0].w, unity_ObjectToWorld[1].w, unity_ObjectToWorld[2].w);
}

// ---------------------------------------------------------------------------
// Triplanar
// ---------------------------------------------------------------------------
struct VesperTri
{
    float2 uvX, uvY, uvZ;
    float3 w;
    float3 nP;     // geometric normal in projection space
    float3 sgn;
    float3x3 rot;  // projection -> world rotation
};

inline VesperTri VesperMakeTri(float3 posW, float3 nW, float tileSize, float sharpness, float objectSpace, float seedOffset)
{
    VesperTri t;
    float3 p = posW;
    t.nP = nW;
    t.rot = float3x3(1, 0, 0, 0, 1, 0, 0, 0, 1);
    if (objectSpace > 0.5)
    {
        float3x3 R = VesperObjectRotation();
        float3x3 Rt = transpose(R);          // world -> projection
        p = mul(Rt, posW - VesperObjectOrigin()) + seedOffset * 13.7;
        t.nP = mul(Rt, nW);
        t.rot = R;
    }
    p /= max(tileSize, 1e-3);

    float3 w = pow(abs(t.nP), sharpness);
    t.w = w / max(dot(w, 1.0), 1e-5);
    t.sgn = step(0.0, t.nP) * 2.0 - 1.0;

    t.uvX = p.zy; t.uvX.x *= t.sgn.x;
    t.uvY = p.xz; t.uvY.x *= t.sgn.y;
    t.uvZ = p.xy; t.uvZ.x *= -t.sgn.z;
    return t;
}

#define VESPER_TRI_SAMPLE(tex, samplerTex, t) \
    (UNITY_SAMPLE_TEX2D_SAMPLER(tex, samplerTex, (t).uvX) * (t).w.x + \
     UNITY_SAMPLE_TEX2D_SAMPLER(tex, samplerTex, (t).uvY) * (t).w.y + \
     UNITY_SAMPLE_TEX2D_SAMPLER(tex, samplerTex, (t).uvZ) * (t).w.z)

inline float3 VesperTriNormal(VesperTri t, half scale)
{
    half3 tx = UnpackNormalWithScale(UNITY_SAMPLE_TEX2D_SAMPLER(_BumpMap, _MainTex, t.uvX), scale);
    half3 ty = UnpackNormalWithScale(UNITY_SAMPLE_TEX2D_SAMPLER(_BumpMap, _MainTex, t.uvY), scale);
    half3 tz = UnpackNormalWithScale(UNITY_SAMPLE_TEX2D_SAMPLER(_BumpMap, _MainTex, t.uvZ), scale);
    tx.x *= t.sgn.x;
    ty.x *= t.sgn.y;
    tz.x *= -t.sgn.z;
    // whiteout blend onto the projection-space geometric normal
    tx = half3(tx.xy + t.nP.zy, abs(tx.z) * t.nP.x);
    ty = half3(ty.xy + t.nP.xz, abs(ty.z) * t.nP.y);
    tz = half3(tz.xy + t.nP.xy, abs(tz.z) * t.nP.z);
    float3 nP = normalize(tx.zyx * t.w.x + ty.xzy * t.w.y + tz.xyz * t.w.z);
    return normalize(mul(t.rot, nP));
}

// ---------------------------------------------------------------------------
// Layered surface
// ---------------------------------------------------------------------------
struct VesperSurface
{
    half3 albedo;
    float3 normalW;
    half roughness;
    half metallic;
    half occlusion;
    half aoRaw;
    half3 emission;
    half alpha;
};

inline half4 VesperMacro(float3 posW, float3 nW)
{
    float s = 1.0 / max(_MacroScale, 0.01);
    half4 h = UNITY_SAMPLE_TEX2D(_MacroMap, posW.xz * s);
    half4 v = UNITY_SAMPLE_TEX2D(_MacroMap, float2(posW.x + posW.z, posW.y) * s);
    return lerp(v, h, saturate(abs(nW.y) * 1.5 - 0.25));
}

// Applies anti-tiling variation, grime, leaks and dust in world space.
inline void VesperApplyLayers(inout VesperSurface s, float3 posW, float3 nGeoW)
{
    half4 macro = VesperMacro(posW, nGeoW);
    float objRand = VesperHash31(floor(VesperObjectOrigin() * 3.17) + 0.37);

    // --- macro / per-object variation --------------------------------------
    half tone = 1.0 + (macro.r - 0.5) * 2.0 * _MacroAlbedo;
    tone *= 1.0 + (objRand - 0.5) * 2.0 * _ObjectVariation;
    s.albedo *= tone;
    s.albedo = lerp(s.albedo, s.albedo * _VariationTint.rgb, saturate(macro.g * 1.6 - 0.5) * _VariationTintStrength);
    s.roughness += (macro.g - 0.5) * 2.0 * _MacroRoughness;

    // --- damp base grime + leak streaks (vertical surfaces only) -----------
    half vertical = 1.0 - saturate(abs(nGeoW.y) * 1.4);
    half damp = saturate(1.0 - posW.y / max(_GrimeHeight, 0.01));
    damp = damp * damp * _GrimeStrength * (0.6 + 0.8 * macro.r);
    s.albedo *= 1.0 - damp * 0.45;
    s.roughness -= damp * 0.18;   // damp stone reads slightly glossier
    half streak = saturate(macro.b * 1.8 - 0.8) * vertical * _StreakStrength;
    s.albedo *= 1.0 - streak * 0.35;

    // --- dust: up-facing, cavity-seeking, thinned in the swept centre ------
    if (_DustAmount > 0.001)
    {
        float2 duv = posW.xz / max(_DustTileSize, 0.01);
        half4 dustTex = UNITY_SAMPLE_TEX2D(_DustMap, duv);
        half3 dustN = UnpackNormal(UNITY_SAMPLE_TEX2D_SAMPLER(_DustBumpMap, _DustMap, duv));

        half up = pow(saturate(s.normalW.y), _DustSharpness);
        float dist = length(posW.xz - _DustCenter.xz);
        half radial = lerp(_DustRadius.z, 1.0, smoothstep(_DustRadius.x, _DustRadius.y, dist));
        half coverage = up * _DustAmount * radial * lerp(0.55, 1.45, macro.r);
        half fill = coverage + (1.0 - s.aoRaw) * _DustCavityBias * up * saturate(_DustAmount * 3.0);
        half mask = smoothstep(0.30, 0.70, fill + (dustTex.a - 0.5) * 0.6 * saturate(coverage * 3.0));

        s.albedo = lerp(s.albedo, dustTex.rgb * _DustColor.rgb, mask);
        s.roughness = lerp(s.roughness, 0.96, mask);
        s.metallic = lerp(s.metallic, 0.0, mask);
        s.occlusion = lerp(s.occlusion, 1.0 - (1.0 - s.occlusion) * 0.5, mask);
        float3 dustNW = normalize(nGeoW + float3(dustN.x, 0, dustN.y) * 0.6);
        s.normalW = normalize(lerp(s.normalW, dustNW, mask * 0.85));
        s.emission *= 1.0 - mask * 0.85;
    }

    s.roughness = saturate(s.roughness);
}

inline half VesperFlow(float3 posW)
{
    float2 uv = posW.xz * 0.21 + posW.y * 0.11;
    float t = _Time.y * _EmissionFlowSpeed;
    half a = UNITY_SAMPLE_TEX2D(_MacroMap, uv + float2(t * 0.031, t * 0.017)).g;
    half b = UNITY_SAMPLE_TEX2D(_MacroMap, uv * 1.7 - float2(t * 0.013, t * 0.029)).r;
    return lerp(1.0 - _EmissionFlow, 1.0 + _EmissionFlow, a * b * 2.0);
}

// Tangent-space conversion helpers for surface shaders (Ben Golus' approach).
#define VESPER_WORLD_TO_TANGENT(IN, nW) \
    normalize(mul(float3x3(WorldNormalVector(IN, float3(1, 0, 0)), \
                           WorldNormalVector(IN, float3(0, 1, 0)), \
                           WorldNormalVector(IN, float3(0, 0, 1))), nW))

#endif // VESPER_ENVIRONMENT_COMMON_INCLUDED
