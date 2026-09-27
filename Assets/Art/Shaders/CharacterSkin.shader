Shader "Vespershade/CharacterSkin"
{
    Properties
    {
        _Color ("Base Skin", Color) = (0.52, 0.37, 0.30, 1)
        _ColorVar ("Variation (Warm)", Color) = (0.58, 0.43, 0.36, 1)
        _RednessColor ("Redness (Cheeks/Nose)", Color) = (0.64, 0.34, 0.30, 1)
        _SSSColor ("Subsurface Color", Color) = (0.68, 0.36, 0.32, 1)
        _Metallic ("Metallic", Range(0,0.05)) = 0.0
        _Glossiness ("Smoothness", Range(0,1)) = 0.33
        _GlossVar ("Roughness Variation", Range(0,0.5)) = 0.16
        _PoreScale ("Pore Scale", Float) = 165
        _PoreStrength ("Pore Strength", Range(0,0.5)) = 0.18
        _SSSAmount ("SSS Amount", Range(0,1)) = 0.34
        _RednessAmount ("Redness Amount", Range(0,1)) = 0.28
        _OcclusionStrength ("Occlusion", Range(0,1)) = 0.75
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        CGPROGRAM
        #pragma surface surf StandardSkin fullforwardshadows
        #pragma target 3.0

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

        // Skin lighting with wrap + SSS approximation to avoid plastic look
        half4 LightingStandardSkin(SurfaceOutputStandard s, half3 lightDir, half3 viewDir, half atten)
        {
            half4 c = LightingStandard(s, lightDir, viewDir, atten);
            // Wrap diffuse for soft skin
            half NdotL = dot(s.Normal, lightDir);
            half wrap = saturate((NdotL*0.5 + 0.5));
            half sss = pow(wrap, 2.2) * _SSSAmount * 0.45;
            c.rgb += _SSSColor.rgb * sss * atten * s.Albedo * 0.6;
            // Reduce harsh specular by slightly blurring with wrap
            return c;
        }
        void LightingStandardSkin_GI(SurfaceOutputStandard s, UnityGIInput data, inout UnityGI gi)
        {
            LightingStandard_GI(s, data, gi);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 wp = IN.worldPos;
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

            o.Albedo = albedo * aoPore;
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
