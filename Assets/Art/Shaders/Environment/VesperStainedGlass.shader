// Vespershade / Environment / Stained Glass
//
// Physically based leaded glass (Standard GGX, premultiplied transparency so
// specular reflections stay visible on nearly clear panes).
//   * Lead came is metallic & opaque, glass is smooth dielectric
//   * BaseColor alpha is a per-cell palette key -> each variant defines a
//     3-colour palette (primary / secondary / accent) instead of new textures
//   * Fake moonlight transmission emission keeps windows reading as light
//     sources against the void outside, without blooming
//   * Object-space metric projection: pattern stays glued to the pane and is
//     never stretched by non-uniform scale
Shader "Vespershade/Environment/Stained Glass"
{
    Properties
    {
        [Header(Palette)]
        _Color ("Primary Glass", Color) = (0.20, 0.32, 0.70, 1)
        _ColorSecondary ("Secondary Glass", Color) = (0.30, 0.18, 0.55, 1)
        _ColorAccent ("Accent Glass", Color) = (0.85, 0.55, 0.18, 1)
        _SecondaryThreshold ("Secondary Share", Range(0, 1)) = 0.55
        _AccentThreshold ("Accent Share (top of key)", Range(0, 1)) = 0.9

        [Header(Maps)]
        _MainTex ("Base Color (RGB) + Palette Key (A)", 2D) = "white" {}
        [Normal][NoScaleOffset] _BumpMap ("Normal", 2D) = "bump" {}
        _BumpScale ("Normal Strength", Range(0, 2)) = 1
        [NoScaleOffset] _RoughnessMap ("Roughness (R)", 2D) = "white" {}
        [NoScaleOffset] _MetallicGlossMap ("Metallic / Lead Mask (R)", 2D) = "black" {}
        [NoScaleOffset] _OcclusionMap ("Ambient Occlusion (R)", 2D) = "white" {}
        _TileSize ("Pattern Size (m)", Float) = 1.2
        _BlendSharpness ("Projection Blend Sharpness", Range(1, 16)) = 8

        [Header(Optics)]
        _GlassOpacity ("Glass Opacity", Range(0, 1)) = 0.42
        _Transmission ("Moonlight Transmission (emission)", Range(0, 2)) = 0.35
        _GrimeDarkening ("Grime Darkening", Range(0, 1)) = 0.35
        [NoScaleOffset] _MacroMap ("Macro Variation", 2D) = "gray" {}
        _MacroScale ("Macro Scale (m)", Float) = 5
    }

    SubShader
    {
        Tags { "Queue" = "Transparent" "RenderType" = "Transparent" "IgnoreProjector" = "True" }
        LOD 300

        CGPROGRAM
        #pragma surface surf Standard alpha:premul
        #pragma target 3.5

        #include "VesperEnvironmentCommon.cginc"

        half4 _ColorSecondary;
        half4 _ColorAccent;
        half  _SecondaryThreshold;
        half  _AccentThreshold;
        half  _GlassOpacity;
        half  _Transmission;
        half  _GrimeDarkening;

        struct Input
        {
            float3 worldPos;
            float3 worldNormal;
            INTERNAL_DATA
        };

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 nGeoW = normalize(WorldNormalVector(IN, float3(0, 0, 1)));
            float3 posW = IN.worldPos;
            float seed = VesperHash31(floor(VesperObjectOrigin() * 5.3) + 0.11);
            VesperTri tri = VesperMakeTri(posW, nGeoW, _TileSize, _BlendSharpness, 1.0, seed);

            half4 base = VESPER_TRI_SAMPLE(_MainTex, _MainTex, tri);
            half rough = VESPER_TRI_SAMPLE(_RoughnessMap, _MainTex, tri).r;
            half lead  = VESPER_TRI_SAMPLE(_MetallicGlossMap, _MainTex, tri).r;
            half ao    = VESPER_TRI_SAMPLE(_OcclusionMap, _MainTex, tri).r;
            float3 nW  = VesperTriNormal(tri, _BumpScale);

            // palette from key (alpha)
            half key = base.a;
            half3 tint = lerp(_Color.rgb, _ColorSecondary.rgb, step(_SecondaryThreshold, key));
            tint = lerp(tint, _ColorAccent.rgb, step(_AccentThreshold, key));

            half leadMask = saturate(lead * 1.25);
            half macro = VesperMacro(posW, nGeoW).r;
            half grime = saturate(1.0 - base.g) * _GrimeDarkening * (0.6 + 0.8 * macro);

            half3 glassAlbedo = tint * base.rgb * (1.0 - grime);
            o.Albedo     = lerp(glassAlbedo, base.rgb, leadMask);
            o.Normal     = VESPER_WORLD_TO_TANGENT(IN, nW);
            o.Metallic   = lead;
            o.Smoothness = 1.0 - rough;
            o.Occlusion  = ao;
            // transmitted moonlight: tinted, dimmed by grime, blocked by lead
            o.Emission   = tint * base.rgb * _Transmission * (1.0 - leadMask) * (1.0 - grime) * (0.75 + 0.5 * macro);
            o.Alpha      = lerp(_GlassOpacity * (1.0 + grime), 1.0, leadMask);
        }
        ENDCG
    }

    FallBack "Transparent/Diffuse"
}
