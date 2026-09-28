Shader "Vespershade/CharacterSkin"
{
    Properties
    {
        _Color ("Base Skin", Color) = (0.52, 0.37, 0.30, 1)
        _ColorVar ("Variation (Warm)", Color) = (0.58, 0.43, 0.36, 1)
        _RednessColor ("Redness (Cheeks/Nose)", Color) = (0.64, 0.34, 0.30, 1)
        _SSSColor ("Subsurface Color", Color) = (0.68, 0.36, 0.32, 1)
        _Metallic ("Metallic", Range(0,0.05)) = 0.0
        _Glossiness ("Smoothness", Range(0,1)) = 0.27
        _GlossVar ("Roughness Variation", Range(0,0.5)) = 0.11
        _PoreScale ("Pore Scale", Float) = 165
        _PoreStrength ("Pore Strength", Range(0,0.5)) = 0.12
        _SSSAmount ("SSS Amount", Range(0,1)) = 0.24
        _RednessAmount ("Redness Amount", Range(0,1)) = 0.18
        _OcclusionStrength ("Occlusion", Range(0,1)) = 0.68
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        CGPROGRAM
        #pragma surface surf StandardSkin fullforwardshadows vertex:vert
        #pragma target 3.0

        #include "UnityLightingCommon.cginc"

        fixed4 _Color;
        fixed4 _ColorVar;
        fixed4 _RednessColor;
        fixed4 _SSSColor;
        half _Metallic;
        half _Glossiness;
        half _GlossVar;
        half _PoreScale;
        half _PoreStrength;
        half _SSSAmount;
        half _RednessAmount;
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


        float Hash21(float2 p){ p=frac(p*float2(123.34,456.21)); p+=dot(p,p+45.32); return frac(p.x*p.y); }
        float ValueNoise(float2 p){
            float2 i=floor(p); float2 f=frac(p); f=f*f*(3-2*f);
            float a=Hash21(i); float b=Hash21(i+float2(1,0)); float c=Hash21(i+float2(0,1)); float d=Hash21(i+float2(1,1));
            return lerp(lerp(a,b,f.x), lerp(c,d,f.x), f.y);
        }
        float FBM(float2 p){ float v=0; float amp=0.5; for(int j=0;j<4;j++){ v+=ValueNoise(p)*amp; p=p*2.17+float2(2.7,1.9); amp*=0.5; } return v; }

        // Skin lighting with wrap + SSS approximation to avoid plastic look
        half4 LightingStandardSkin(SurfaceOutputStandard s, half3 lightDir, half3 viewDir, half atten)
        {
            half4 c = LightingStandard(s, lightDir, viewDir, atten);
            // Restrained back-scatter follows the actual light colour and energy.
            // Standard specular remains broad and low through the skin material.
            half NdotL = dot(s.Normal, lightDir);
            half transmission = pow(saturate(0.5 - 0.5 * NdotL), 2.4);
            half3 scatterTint = lerp(s.Albedo, _SSSColor.rgb, 0.30);
            c.rgb += _LightColor0.rgb * scatterTint * transmission * _SSSAmount * atten * 0.12;
            return c;
        }
        void LightingStandardSkin_GI(SurfaceOutputStandard s, UnityGIInput data, inout UnityGI gi)
        {
            LightingStandard_GI(s, data, gi);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 wp = IN.objPos;
            float2 uvA = wp.xz*0.7 + wp.y*0.2;
            float2 uvB = wp.xy*0.6;

            float nLarge = FBM(uvA*0.6); // overall tone variation
            float nMed = FBM(uvB*1.4);
            float nPore = ValueNoise(wp.xz * _PoreScale * 0.08) * ValueNoise(wp.zy * _PoreScale * 0.09);

            // Pore detail
            float pore = saturate(nPore*1.4 - 0.2);

            // Redness - cheeks, nose, ears - use height and noise
            float redMask = saturate(FBM(wp.xz*1.8)*0.5 + sin(wp.y*6.0)*0.15 + nMed*0.3) * _RednessAmount;
            // Less redness on forehead, more on lower face
            redMask *= saturate(1.0 - (wp.y - 1.62)*2.5 + nLarge*0.3);

            fixed3 albedo = lerp(_Color.rgb, _ColorVar.rgb, saturate(nLarge*0.6 + nMed*0.2)*0.55);
            albedo = lerp(albedo, _RednessColor.rgb, redMask*0.5);
            // Subtle darker occlusion in pores
            float aoPore = lerp(1.0, 1.0 - pore*0.18, _OcclusionStrength);

            // Smoothness - skin should NOT look like plastic: keep low, varied
            // Oilier T-zone slightly more glossy, pores more matte
            float roughVar = (nMed*0.4 + nLarge*0.3 + pore*0.3) - 0.45;
            half smoothness = saturate(_Glossiness + roughVar*_GlossVar);
            smoothness = saturate(smoothness - pore*0.12 + redMask*0.05);

            // Normal - pore bump
            float nx = (ValueNoise(wp.xz * _PoreScale * 0.22)-0.5) * _PoreStrength;
            float ny = (ValueNoise(wp.zy * _PoreScale * 0.23 + 2.1)-0.5) * _PoreStrength;
            float3 n = normalize(float3(nx, ny, 1.0));

            o.Albedo = albedo;
            o.Metallic = _Metallic;
            o.Smoothness = smoothness;
            o.Normal = n;
            o.Occlusion = aoPore;
            o.Alpha = 1;
        }
        ENDCG
    }
    FallBack "Standard"
}
