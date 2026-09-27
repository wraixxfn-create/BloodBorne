Shader "Vespershade/CharacterGlove"
{
    Properties
    {
        _Color ("Base Color", Color) = (0.145, 0.095, 0.065, 1)
        _ColorVar ("Variation", Color) = (0.18, 0.115, 0.078, 1)
        _WearColor ("Wear Highlight", Color) = (0.22, 0.15, 0.10, 1)
        _Metallic ("Metallic", Range(0,0.12)) = 0.02
        _Glossiness ("Smoothness", Range(0,1)) = 0.34
        _GlossVar ("Roughness Variation", Range(0,0.5)) = 0.20
        _GrainScale ("Grain Scale", Float) = 58
        _FuzzAmount ("Fuzz / Suede", Range(0,1)) = 0.32
        _FuzzColor ("Fuzz Color", Color) = (0.24, 0.18, 0.13, 1)
        _WearAmount ("Wear Amount", Range(0,1)) = 0.16
        _OcclusionStrength ("Occlusion", Range(0,1)) = 0.88
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        CGPROGRAM
        #pragma surface surf StandardGlove fullforwardshadows
        #pragma target 3.0

        fixed4 _Color;
        fixed4 _ColorVar;
        fixed4 _WearColor;
        fixed4 _FuzzColor;
        half _Metallic;
        half _Glossiness;
        half _GlossVar;
        half _GrainScale;
        half _FuzzAmount;
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
        float FBM(float2 p){ float v=0; float amp=0.5; for(int j=0;j<4;j++){ v+=ValueNoise(p)*amp; p=p*2.17+float2(2.7,1.9); amp*=0.5; } return v; }

        half4 LightingStandardGlove(SurfaceOutputStandard s, half3 lightDir, half3 viewDir, half atten)
        {
            half4 c = LightingStandard(s, lightDir, viewDir, atten);
            half NdotV = saturate(dot(s.Normal, viewDir));
            half fuzz = pow(1.0 - NdotV, 2.8) * _FuzzAmount * 0.45;
            c.rgb += _FuzzColor.rgb * fuzz * atten;
            return c;
        }
        void LightingStandardGlove_GI(SurfaceOutputStandard s, UnityGIInput data, inout UnityGI gi)
        {
            LightingStandard_GI(s, data, gi);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 wp = IN.worldPos;
            float2 uvA = wp.xz*0.7 + wp.y*0.2;
            float2 uvB = wp.xy*0.6;

            float nLarge = FBM(uvA*0.6);
            float nMed = FBM(uvB*1.2);
            float nFine = ValueNoise(wp.xz*42.0);

            float2 grainUV = wp.xz*0.38 + wp.y*0.12;
            float grain = FBM(grainUV*1.1)*0.6 + ValueNoise(grainUV*9.0)*0.4;

            float varMask = saturate(nLarge*0.5 + grain*0.3 + nMed*0.2);
            fixed3 albedo = lerp(_Color.rgb, _ColorVar.rgb, varMask*0.6);

            float wear = saturate(nFine*0.35 + nLarge*0.15 + grain*0.15) * _WearAmount;
            albedo = lerp(albedo, _WearColor.rgb, wear*0.5);

            float crevice = saturate((1.0-grain)*0.35) * 0.18;
            float ao = lerp(1.0, 1.0 - crevice*0.5, _OcclusionStrength);

            // Smoothness - gloves softer than belt leather, distinct from cloth and boots
            float roughVar = (nMed*0.4 + grain*0.3 + nFine*0.3) - 0.45;
            half smoothness = saturate(_Glossiness + roughVar*_GlossVar);
            smoothness = saturate(smoothness - crevice*0.12 + wear*0.08);

            float nx = (ValueNoise(grainUV*_GrainScale*0.26)-0.5)*0.32;
            float ny = (ValueNoise(grainUV*_GrainScale*0.29+3.4)-0.5)*0.32;
            float3 n = normalize(float3(nx, ny, 1.0));

            o.Albedo = albedo * ao;
            o.Metallic = _Metallic;
            o.Smoothness = smoothness;
            o.Normal = n;
            o.Occlusion = ao;
            o.Alpha = 1;
        }
        ENDCG
    }
    FallBack "Standard"
}
