Shader "Vespershade/CharacterMetal"
{
    Properties
    {
        _Color ("Base Color (Brass)", Color) = (0.48, 0.33, 0.135, 1)
        _PatinaColor ("Patina Tint", Color) = (0.30, 0.36, 0.30, 1)
        _WearColor ("Polished Highlight", Color) = (0.62, 0.46, 0.20, 1)
        _Metallic ("Metallic", Range(0.5,1)) = 0.78
        _Glossiness ("Smoothness", Range(0,1)) = 0.62
        _GlossVar ("Smoothness Variation", Range(0,0.5)) = 0.16
        _ScratchScale ("Scratch Scale", Float) = 240
        _PatinaAmount ("Patina Amount", Range(0,1)) = 0.22
        _WearAmount ("Wear Amount", Range(0,1)) = 0.18
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
        fixed4 _PatinaColor;
        fixed4 _WearColor;
        half _Metallic;
        half _Glossiness;
        half _GlossVar;
        half _ScratchScale;
        half _PatinaAmount;
        half _WearAmount;
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
        float FBM(float2 p){ float v=0; float amp=0.5; for(int j=0;j<4;j++){ v+=ValueNoise(p)*amp; p=p*2.17+float2(3.7,1.2); amp*=0.5; } return v; }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 wp = IN.worldPos;
            float2 uvA = wp.xz*0.6 + wp.y*0.2;
            float2 uvB = wp.xy*0.5 + wp.z*0.3;

            float nLarge = FBM(uvA*0.5);
            float nMed = FBM(uvB*1.2);
            float nFine = ValueNoise(wp.xz*48.0);

            // Micro scratches - anisotropic stretched noise
            float2 sUV = float2(dot(wp, float3(0.7,0.3,0.2)), dot(wp, float3(0.2,0.1,0.9))) * _ScratchScale*0.015;
            float scratch1 = ValueNoise(sUV*float2(12,1.2));
            float scratch2 = ValueNoise(sUV*float2(1.5,9.0)+2.4);
            float scratch = pow(saturate(scratch1*scratch2*1.8), 2.2) * 0.7;

            // Patina in recesses, not uniform
            float cavity = saturate((1.0-nMed)*0.6 + (1.0-nLarge)*0.25 + nFine*0.1);
            float patinaMask = cavity * _PatinaAmount * (0.7 + nLarge*0.5);

            fixed3 albedo = _Color.rgb;
            albedo = lerp(albedo, _PatinaColor.rgb, patinaMask*0.55);
            // Polished wear on exposed edges
            float wear = saturate(scratch*1.1 + nLarge*0.15) * _WearAmount;
            albedo = lerp(albedo, _WearColor.rgb, wear*0.6);

            float ao = lerp(1.0, 1.0 - cavity*0.45, _OcclusionStrength);

            // Smoothness: metal should react correctly to light, varied micro-roughness
            float roughVar = (nMed*0.4 + scratch*0.5 + nFine*0.2) - 0.4;
            half smoothness = saturate(_Glossiness + roughVar*_GlossVar);
            smoothness = lerp(smoothness, saturate(smoothness+0.12), wear);
            smoothness = lerp(smoothness, saturate(smoothness-0.15), patinaMask);

            // Normal: micro scratch bump
            float nx = (ValueNoise(sUV*float2(8,0.6))-0.5)*0.35 * scratch;
            float ny = (ValueNoise(sUV*float2(0.6,8)+3.1)-0.5)*0.35 * scratch;
            float nDetail = (ValueNoise(wp.xz*120.0)-0.5)*0.08;
            float3 n = normalize(float3(nx + nDetail, ny + nDetail, 1.0));

            o.Albedo = albedo * ao;
            o.Metallic = saturate(_Metallic - patinaMask*0.35); // patina reduces metallic slightly
            o.Smoothness = smoothness;
            o.Normal = n;
            o.Occlusion = ao;
            o.Alpha = 1;
        }
        ENDCG
    }
    FallBack "Standard"
}
