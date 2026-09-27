Shader "Vespershade/CharacterBoot"
{
    Properties
    {
        _Color ("Base Color", Color) = (0.095, 0.065, 0.05, 1)
        _ColorVar ("Variation", Color) = (0.125, 0.085, 0.065, 1)
        _ScuffColor ("Scuff Highlight", Color) = (0.18, 0.15, 0.11, 1)
        _SoleColor ("Sole Base", Color) = (0.055, 0.045, 0.04, 1)
        _Metallic ("Metallic", Range(0,0.12)) = 0.02
        _Glossiness ("Smoothness", Range(0,1)) = 0.22
        _GlossVar ("Roughness Variation", Range(0,0.5)) = 0.16
        _GrainScale ("Grain Scale", Float) = 32
        _ScuffAmount ("Scuff Amount", Range(0,1)) = 0.26
        _OcclusionStrength ("Occlusion", Range(0,1)) = 0.92
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows
        #pragma target 3.0

        fixed4 _Color;
        fixed4 _ColorVar;
        fixed4 _ScuffColor;
        fixed4 _SoleColor;
        half _Metallic;
        half _Glossiness;
        half _GlossVar;
        half _GrainScale;
        half _ScuffAmount;
        half _OcclusionStrength;

        struct Input
        {
            float3 worldPos;
            float3 worldNormal;
            INTERNAL_DATA
        };

        float Hash21(float2 p){ p=frac(p*float2(123.34,456.21)); p+=dot(p,p+45.32); return frac(p.x*p.y); }
        float ValueNoise(float2 p){
            float2 i=floor(p); float2 f=frac(p); f=f*f*(3-2*f);
            float a=Hash21(i); float b=Hash21(i+float2(1,0)); float c=Hash21(i+float2(0,1)); float d=Hash21(i+float2(1,1));
            return lerp(lerp(a,b,f.x), lerp(c,d,f.x), f.y);
        }
        float FBM(float2 p){ float v=0; float amp=0.5; for(int j=0;j<4;j++){ v+=ValueNoise(p)*amp; p=p*2.17+float2(2.7,1.9); amp*=0.5; } return v; }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 wp = IN.worldPos;
            float2 uvA = wp.xz*0.9 + wp.y*0.2;
            float2 uvB = wp.xy*0.7;

            float nLarge = FBM(uvA*0.55);
            float nMed = FBM(uvB*1.0);
            float nFine = ValueNoise(wp.xz*38.0);

            float2 grainUV = wp.xz*0.4 + wp.y*0.15;
            float grain = FBM(grainUV*1.2)*0.6 + ValueNoise(grainUV*8.0)*0.4;

            // Scuff - more at toe and heel
            float toeFactor = saturate((wp.z - 0.02)*2.5 + nLarge*0.2); // forward = +Z? character faces +Z, toe forward
            float heightFactor = saturate(1.0 - (wp.y*6.0) + nMed*0.2);
            float scuff = saturate(toeFactor*0.5 + heightFactor*0.35 + nFine*0.2 + grain*0.15) * _ScuffAmount;

            // Determine if this is sole (very low y) - use sole color
            float isSole = saturate((0.08 - wp.y)*12.0); // sole at y~0-0.08
            fixed3 base = lerp(_Color.rgb, _SoleColor.rgb, isSole*0.85);
            fixed3 var = lerp(_ColorVar.rgb, _SoleColor.rgb*1.25, isSole*0.5);
            float varMask = saturate(nLarge*0.5 + grain*0.35 + nMed*0.15);
            fixed3 albedo = lerp(base, var, varMask*0.6);
            albedo = lerp(albedo, _ScuffColor.rgb, scuff*0.55);
            // Subtle darker crevice
            float crevice = saturate((1.0-grain)*0.4 + (1.0-nMed)*0.2) * 0.22;
            albedo *= lerp(1.0, 0.86, crevice * (1.0-isSole*0.5));

            float ao = lerp(1.0, 1.0 - crevice*0.55 - scuff*0.05, _OcclusionStrength);

            // Smoothness - boots rougher than leather gloves, sole even rougher
            float roughVar = (nMed*0.4 + grain*0.3 + nFine*0.3) - 0.5;
            half smoothness = saturate(_Glossiness + roughVar*_GlossVar - isSole*0.08 + scuff*0.08);

            float nx = (ValueNoise(grainUV*_GrainScale*0.28)-0.5)*0.38;
            float ny = (ValueNoise(grainUV*_GrainScale*0.31+2.7)-0.5)*0.38;
            float3 n = normalize(float3(nx, ny, 1.0));

            o.Albedo = albedo * ao;
            o.Metallic = _Metallic * (1.0 - isSole*0.5);
            o.Smoothness = smoothness;
            o.Normal = n;
            o.Occlusion = ao;
            o.Alpha = 1;
        }
        ENDCG
    }
    FallBack "Standard"
}
