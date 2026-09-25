// Vespershade / Environment / Lit
//
// Physically based (Unity Standard GGX / metallic workflow) surface shader for
// every opaque surface of the Hollow Sanctum: stone, cracked stone, wood,
// metals, candle wax, dust and ritual surfaces. One shader + material variants
// instead of one-off materials.
//
// Features
//   * Triplanar world or object-space projection (metric, no UV stretching on
//     scaled primitives/modules), or classic UV0 mapping (_UV_MAPPING)
//   * Separate BaseColor / Normal / Roughness / Metallic / AO maps
//   * Macro variation + per-object tone offset (anti-repetition)
//   * Damp base grime, vertical leak streaks, height-aware dust layer
//   * Emission mask with slow flow + runtime ritual pulse (_RitualPulse)
//   * Optional wrap/back-light translucency for wax (_TRANSLUCENCY)
Shader "Vespershade/Environment/Lit"
{
    Properties
    {
        [Header(Surface Maps)]
        _Color ("Base Color Tint", Color) = (1,1,1,1)
        _MainTex ("Base Color (sRGB)", 2D) = "white" {}
        [Normal][NoScaleOffset] _BumpMap ("Normal", 2D) = "bump" {}
        _BumpScale ("Normal Strength", Range(0, 2)) = 1
        [NoScaleOffset] _RoughnessMap ("Roughness (R)", 2D) = "white" {}
        _RoughnessMin ("Roughness Remap Min", Range(0, 1)) = 0
        _RoughnessMax ("Roughness Remap Max", Range(0, 1)) = 1
        [NoScaleOffset] _MetallicGlossMap ("Metallic (R)", 2D) = "white" {}
        _Metallic ("Metallic Multiplier", Range(0, 1)) = 0
        [NoScaleOffset] _OcclusionMap ("Ambient Occlusion (R)", 2D) = "white" {}
        _OcclusionStrength ("AO Strength", Range(0, 1)) = 1

        [Header(Projection)]
        [Toggle(_UV_MAPPING)] _UVMapping ("Use Mesh UV0 (off = Triplanar)", Float) = 0
        _TileSize ("Triplanar Tile Size (m)", Float) = 2
        _BlendSharpness ("Triplanar Blend Sharpness", Range(1, 16)) = 6
        [Toggle] _ObjectSpace ("Object Space Projection (props)", Float) = 0

        [Header(Surface Variation)]
        [NoScaleOffset] _MacroMap ("Macro Variation (R blotch, G mottle, B streak)", 2D) = "gray" {}
        _MacroScale ("Macro Scale (m)", Float) = 9
        _MacroAlbedo ("Macro Albedo Variation", Range(0, 0.5)) = 0.12
        _MacroRoughness ("Macro Roughness Variation", Range(0, 0.3)) = 0.05
        _VariationTint ("Variation Tint", Color) = (1,1,1,1)
        _VariationTintStrength ("Variation Tint Strength", Range(0, 1)) = 0
        _ObjectVariation ("Per-Object Tone Variation", Range(0, 0.3)) = 0.06

        [Header(Grime)]
        _GrimeHeight ("Damp Base Height (m)", Float) = 1.5
        _GrimeStrength ("Damp Base Strength", Range(0, 1)) = 0
        _StreakStrength ("Leak Streak Strength", Range(0, 1)) = 0

        [Header(Dust Layer)]
        _DustAmount ("Dust Amount", Range(0, 1.5)) = 0
        _DustSharpness ("Dust Up-Facing Sharpness", Range(0.5, 8)) = 3
        _DustCavityBias ("Dust Cavity Bias", Range(0, 2)) = 0.6
        [NoScaleOffset] _DustMap ("Dust Base Color (A = density)", 2D) = "gray" {}
        [Normal][NoScaleOffset] _DustBumpMap ("Dust Normal", 2D) = "bump" {}
        _DustTileSize ("Dust Tile Size (m)", Float) = 1.2
        _DustColor ("Dust Tint", Color) = (1,1,1,1)
        _DustCenter ("Swept Area Centre (xz)", Vector) = (0,0,0,0)
        _DustRadius ("Swept Radii (x clean, y dusty, z centre mult)", Vector) = (0,0,1,0)

        [Header(Emission)]
        _EmissionMap ("Emission Mask (R)", 2D) = "black" {}
        [Toggle(_EMISSION_UV)] _EmissionUV ("Emission Mask Uses UV0", Float) = 0
        [HDR] _EmissionColor ("Emission Color", Color) = (0,0,0,1)
        _EmissionFlow ("Emission Flow Strength", Range(0, 1)) = 0
        _EmissionFlowSpeed ("Emission Flow Speed", Float) = 0.4
        _RitualPulse ("Ritual Pulse (runtime)", Float) = 0

        [Header(Translucency)]
        [Toggle(_TRANSLUCENCY)] _UseTranslucency ("Wax Translucency", Float) = 0
        _Translucency ("Translucency", Range(0, 2)) = 0
        _TranslucencyColor ("Scatter Color", Color) = (1, 0.55, 0.25, 1)
        _TranslucencyWrap ("Wrap", Range(0, 1)) = 0.5
    }

    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" }
        LOD 300

        CGPROGRAM
        #pragma surface surf Vesper fullforwardshadows addshadow
        #pragma target 3.5
        #pragma shader_feature_local _UV_MAPPING
        #pragma shader_feature_local _EMISSION_UV
        #pragma shader_feature_local _TRANSLUCENCY

        #include "VesperEnvironmentCommon.cginc"

        float4 _EmissionMap_ST;
        half   _Translucency;
        half4  _TranslucencyColor;
        half   _TranslucencyWrap;

        struct Input
        {
            float2 uv_MainTex;
            float2 uv_EmissionMap;
            float3 worldPos;
            float3 worldNormal;
            INTERNAL_DATA
        };

        // ------------------------------------------------------------------
        // Lighting: Unity Standard (GGX, energy conserving) + optional
        // wrapped/back-lit scattering for wax. Deferred falls back to Standard.
        // ------------------------------------------------------------------
        inline half4 LightingVesper(SurfaceOutputStandard s, float3 viewDir, UnityGI gi)
        {
            half4 c = LightingStandard(s, viewDir, gi);
        #if defined(_TRANSLUCENCY)
            half3 L = gi.light.dir;
            half ndl = dot(s.Normal, L);
            half wrapped = saturate((ndl + _TranslucencyWrap) / (1.0 + _TranslucencyWrap)) - saturate(ndl);
            half back = pow(saturate(dot(viewDir, -L)), 4.0) * 0.6;
            c.rgb += s.Albedo * _TranslucencyColor.rgb * gi.light.color * (max(wrapped, 0.0) + back) * _Translucency;
        #endif
            return c;
        }

        inline half4 LightingVesper_Deferred(SurfaceOutputStandard s, float3 viewDir, UnityGI gi,
                                             out half4 outGBuffer0, out half4 outGBuffer1, out half4 outGBuffer2)
        {
            return LightingStandard_Deferred(s, viewDir, gi, outGBuffer0, outGBuffer1, outGBuffer2);
        }

        inline void LightingVesper_GI(SurfaceOutputStandard s, UnityGIInput data, inout UnityGI gi)
        {
            LightingStandard_GI(s, data, gi);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 nGeoW = normalize(WorldNormalVector(IN, float3(0, 0, 1)));
            float3 posW = IN.worldPos;

            VesperSurface s;
            half4 albedo;
            half rough, metal, ao;

        #if defined(_UV_MAPPING)
            float2 uv = IN.uv_MainTex;
            albedo = UNITY_SAMPLE_TEX2D(_MainTex, uv);
            half3 tn = UnpackNormalWithScale(UNITY_SAMPLE_TEX2D_SAMPLER(_BumpMap, _MainTex, uv), _BumpScale);
            rough = UNITY_SAMPLE_TEX2D_SAMPLER(_RoughnessMap, _MainTex, uv).r;
            metal = UNITY_SAMPLE_TEX2D_SAMPLER(_MetallicGlossMap, _MainTex, uv).r;
            ao    = UNITY_SAMPLE_TEX2D_SAMPLER(_OcclusionMap, _MainTex, uv).r;
            s.normalW = normalize(WorldNormalVector(IN, tn));
        #else
            float seed = VesperHash31(floor(VesperObjectOrigin() * 5.3) + 0.11);
            VesperTri tri = VesperMakeTri(posW, nGeoW, _TileSize, _BlendSharpness, _ObjectSpace, seed);
            albedo = VESPER_TRI_SAMPLE(_MainTex, _MainTex, tri);
            rough  = VESPER_TRI_SAMPLE(_RoughnessMap, _MainTex, tri).r;
            metal  = VESPER_TRI_SAMPLE(_MetallicGlossMap, _MainTex, tri).r;
            ao     = VESPER_TRI_SAMPLE(_OcclusionMap, _MainTex, tri).r;
            s.normalW = VesperTriNormal(tri, _BumpScale);
        #endif

            s.albedo    = albedo.rgb * _Color.rgb;
            s.roughness = lerp(_RoughnessMin, _RoughnessMax, rough);
            s.metallic  = metal * _Metallic;
            s.aoRaw     = ao;
            s.occlusion = lerp(1.0, ao, _OcclusionStrength);
            s.alpha     = 1.0;

            // emission mask
        #if defined(_EMISSION_UV)
            half emask = UNITY_SAMPLE_TEX2D_SAMPLER(_EmissionMap, _MainTex, IN.uv_EmissionMap).r;
        #elif defined(_UV_MAPPING)
            half emask = UNITY_SAMPLE_TEX2D_SAMPLER(_EmissionMap, _MainTex, IN.uv_MainTex).r;
        #else
            half emask = VESPER_TRI_SAMPLE(_EmissionMap, _MainTex, tri).r;
        #endif
            s.emission = _EmissionColor.rgb * emask * VesperFlow(posW) * (1.0 + _RitualPulse);

            VesperApplyLayers(s, posW, nGeoW);

            o.Albedo     = s.albedo;
            o.Normal     = VESPER_WORLD_TO_TANGENT(IN, s.normalW);
            o.Metallic   = s.metallic;
            o.Smoothness = 1.0 - s.roughness;
            o.Occlusion  = s.occlusion;
            o.Emission   = s.emission;
            o.Alpha      = 1.0;
        }
        ENDCG
    }

    FallBack "Standard"
}
