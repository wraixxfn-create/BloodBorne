Shader "Vespershade/CharacterCloth"
{
    Properties
    {
        _Color ("Base Color", Color) = (0.125, 0.15, 0.195, 1)
        _ColorVar ("Color Variation", Color) = (0.155, 0.18, 0.23, 1)
        _WearColor ("Wear Highlight", Color) = (0.16, 0.18, 0.235, 1)
        _Metallic ("Metallic", Range(0, 0.15)) = 0.015
        _Glossiness ("Smoothness", Range(0,1)) = 0.24
        _GlossVar ("Roughness Variation", Range(0,0.5)) = 0.13
        _WeaveScale ("Weave Scale", Float) = 88
        _WeaveStrength ("Weave Normal Strength", Range(0,1)) = 0.22
        _FabricSheen ("Fabric Sheen", Range(0,1)) = 0.15
        _SheenColor ("Sheen Tint", Color) = (0.36, 0.40, 0.48, 1)
        _DetailScale ("Detail Noise Scale", Float) = 1.35
        _WearAmount ("Wear Amount", Range(0,1)) = 0.12
        _OcclusionStrength ("Occlusion Strength", Range(0,1)) = 0.72
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        CGPROGRAM
        #pragma surface surf StandardFabric fullforwardshadows vertex:vert
        #pragma target 3.0

        #include "UnityLightingCommon.cginc"

        #include "UnityCG.cginc"

        fixed4 _Color;
        fixed4 _ColorVar;
        fixed4 _WearColor;
        fixed4 _SheenColor;
        half _Metallic;
        half _Glossiness;
        half _GlossVar;
        half _WeaveScale;
        half _WeaveStrength;
        half _FabricSheen;
        half _DetailScale;
        half _WearAmount;
        half _OcclusionStrength;

        struct Input
        {
            float3 objPos;
            float3 worldNormal;
            INTERNAL_DATA
        };
        // The mesh has no UVs or imported tangents. Build a stable local TBN so
        // procedural micro-normal detail is well-defined and stays attached.
        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            o.objPos = v.vertex.xyz;
            float3 n = normalize(v.normal);
            float3 axis = abs(n.y) < 0.92 ? float3(0.0, 1.0, 0.0) : float3(1.0, 0.0, 0.0);
            v.tangent = float4(normalize(cross(axis, n)), 1.0);
        }


        // --- Procedural noise ---
        float Hash21(float2 p)
        {
            p = frac(p * float2(123.34, 456.21));
            p += dot(p, p + 45.32);
            return frac(p.x * p.y);
        }
        float ValueNoise(float2 p)
        {
            float2 i = floor(p);
            float2 f = frac(p);
            f = f*f*(3.0-2.0*f);
            float a = Hash21(i);
            float b = Hash21(i+float2(1,0));
            float c = Hash21(i+float2(0,1));
            float d = Hash21(i+float2(1,1));
            return lerp(lerp(a,b,f.x), lerp(c,d,f.x), f.y);
        }
        float FBM(float2 p)
        {
            float v = 0.0;
            float amp = 0.5;
            float2 q = p;
            for(int j=0;j<4;j++)
            {
                v += ValueNoise(q) * amp;
                q = q*2.17 + float2(3.7, 1.2);
                amp *= 0.5;
            }
            return v;
        }
        float FBM3(float3 p)
        {
            // cheap 3D via 2D projections
            return (FBM(p.xy) + FBM(p.yz) + FBM(p.xz*0.8)) * 0.333;
        }

        // Fabric lighting with sheen
        half4 LightingStandardFabric(SurfaceOutputStandard s, half3 lightDir, half3 viewDir, half atten)
        {
            // Use Unity's standard BRDF then add sheen
            half4 c = LightingStandard(s, lightDir, viewDir, atten);
            // Fabric sheen - grazing retroreflection, tinted
            half NdotV = saturate(dot(s.Normal, viewDir));
            half NdotL = saturate(dot(s.Normal, lightDir));
            half grazing = pow(saturate(1.0 - NdotV), 4.0);
            half lit = pow(NdotL, 0.8);
            // A restrained, light-coloured grazing sheen; it cannot glow in darkness.
            c.rgb += _LightColor0.rgb * _SheenColor.rgb * grazing * lit * _FabricSheen * atten * 0.30;
            return c;
        }
        void LightingStandardFabric_GI(SurfaceOutputStandard s, UnityGIInput data, inout UnityGI gi)
        {
            LightingStandard_GI(s, data, gi);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 wp = IN.objPos;
            // Object-space projections keep the weave anchored while the player moves.
            float2 uvA = wp.xz * _DetailScale + wp.y * 0.22;
            float2 uvB = wp.xy * _DetailScale * 0.9 + wp.z * 0.18;

            float n1 = FBM(uvA * 0.65);
            float n2 = FBM(uvB * 1.1);
            float nLarge = FBM(wp.xz * 0.35) * 0.6 + FBM(wp.xy * 0.28) * 0.4;
            float nFine = ValueNoise(wp.xz * 18.0) * 0.5 + ValueNoise(wp.xy * 22.0) * 0.5;

            // Weave pattern - two interlaced sines
            float2 weaveUV = wp.xz * 0.55 + wp.y * 0.12;
            float weaveS = _WeaveScale * 0.12;
            float warp = sin(weaveUV.x * weaveS) * 0.5 + 0.5;
            float weft = sin(weaveUV.y * weaveS * 1.15 + warp*0.3) * 0.5 + 0.5;
            float weave = warp * weft;
            float weaveAlt = sin(weaveUV.x * weaveS * 0.5) * sin(weaveUV.y * weaveS * 0.5);

            // Albedo variation - subtle, not dirty
            float varMask = saturate(nLarge*0.7 + n1*0.3 + weaveAlt*0.12);
            fixed3 albedo = lerp(_Color.rgb, _ColorVar.rgb, varMask * 0.55);

            // Wear - lighter at exposed edges / high points, subtle
            float heightWear = saturate((wp.y - 0.25) * 0.6 + n2*0.25); // higher up slightly more worn
            float edgeWear = saturate(pow(abs(weave-0.5)*2.0, 2.0) * 0.5 + nFine*0.25);
            float wear = saturate(heightWear*0.35 + edgeWear*0.45 + nLarge*0.15) * _WearAmount;
            albedo = lerp(albedo, _WearColor.rgb, wear * 0.6);

            // Very subtle AO from weave crevices
            float ao = lerp(1.0, 1.0 - saturate((1.0-weave)*0.45 + nFine*0.15)*0.35, _OcclusionStrength);

            // Smoothness variation - critical to avoid uniform roughness
            float roughVar = (n1*0.5 + n2*0.3 + weaveAlt*0.2) - 0.5;
            half smoothness = saturate(_Glossiness + roughVar * _GlossVar + sin(wp.y*32.0)*0.02);

            // Normal - fabric weave bump + fine fiber noise
            float nx = (sin(weaveUV.x * _WeaveScale * 0.22) * cos(weaveUV.y * _WeaveScale * 0.18)) * _WeaveStrength;
            float ny = (sin(weaveUV.y * _WeaveScale * 0.24) * cos(weaveUV.x * _WeaveScale * 0.20)) * _WeaveStrength;
            // fine fiber jitter
            float nfX = (ValueNoise(wp.xz * 75.0)-0.5)*0.12;
            float nfY = (ValueNoise(wp.zy * 68.0)-0.5)*0.12;
            float3 fabricNormal = normalize(float3(nx + nfX, ny + nfY, 1.0));

            o.Albedo = albedo;
            o.Metallic = _Metallic;
            o.Smoothness = smoothness;
            o.Normal = fabricNormal;
            o.Occlusion = ao;
            o.Alpha = 1;
        }
        ENDCG
    }
    FallBack "Standard"
}
