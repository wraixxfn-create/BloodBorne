Shader "Vespershade/CharacterHair"
{
    Properties
    {
        _Color ("Base Color", Color) = (0.13, 0.145, 0.175, 1)
        _ColorVar ("Variation", Color) = (0.17, 0.18, 0.21, 1)
        _HighlightColor ("Highlight Tint", Color) = (0.32, 0.30, 0.27, 1)
        _Metallic ("Metallic", Range(0,0.1)) = 0.02
        _Glossiness ("Smoothness", Range(0,1)) = 0.34
        _GlossVar ("Roughness Variation", Range(0,0.5)) = 0.22
        _StrandScale ("Strand Scale", Float) = 115
        _AnisoAmount ("Anisotropy", Range(0,1)) = 0.55
        _OcclusionStrength ("Occlusion", Range(0,1)) = 0.85
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        CGPROGRAM
        #pragma surface surf StandardHair fullforwardshadows
        #pragma target 3.0

        fixed4 _Color;
        fixed4 _ColorVar;
        fixed4 _HighlightColor;
        half _Metallic;
        half _Glossiness;
        half _GlossVar;
        half _StrandScale;
        half _AnisoAmount;
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

        half4 LightingStandardHair(SurfaceOutputStandard s, half3 lightDir, half3 viewDir, half atten)
        {
            half4 c = LightingStandard(s, lightDir, viewDir, atten);
            // Kajiya-Kay-ish secondary highlight along strand direction
            // Approximate strand tangent as slightly offset from normal
            half3 halfVec = normalize(lightDir + viewDir);
            half NdotH = saturate(dot(s.Normal, halfVec));
            // Primary highlight already in Standard, add subtle secondary shifted
            half secondary = pow(saturate(1.0 - abs(dot(s.Normal, halfVec))*1.2), 12.0) * _AnisoAmount * 0.35;
            c.rgb += _HighlightColor.rgb * secondary * atten;
            return c;
        }
        void LightingStandardHair_GI(SurfaceOutputStandard s, UnityGIInput data, inout UnityGI gi)
        {
            LightingStandard_GI(s, data, gi);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 wp = IN.worldPos;
            float2 uvA = wp.xz*0.6 + wp.y*0.15;
            float2 uvB = wp.xy*0.8;

            float nLarge = FBM(uvA*0.5);
            float nMed = FBM(uvB*1.1);
            float strand = sin(uvA.x * _StrandScale * 0.18 + nLarge*2.0) * sin(uvA.y * _StrandScale * 0.12);
            strand = strand*0.5+0.5;
            float strandFine = ValueNoise(wp.xz * _StrandScale * 0.35) * 0.6 + ValueNoise(wp.zy * _StrandScale * 0.32)*0.4;

            float varMask = saturate(nLarge*0.5 + strand*0.3 + nMed*0.2);
            fixed3 albedo = lerp(_Color.rgb, _ColorVar.rgb, varMask*0.6);

            // Slightly lighter where highlight would catch
            float highlightMask = pow(strand, 3.0) * 0.18 * _AnisoAmount;
            albedo = lerp(albedo, _HighlightColor.rgb, highlightMask*0.25);

            float ao = lerp(1.0, 1.0 - (1.0-strand)*0.25 - strandFine*0.1, _OcclusionStrength);

            float roughVar = (nMed*0.4 + strandFine*0.4 + nLarge*0.2) - 0.45;
            half smoothness = saturate(_Glossiness + roughVar*_GlossVar);

            // Normal - strand direction
            float nx = (sin(uvA.x * _StrandScale * 0.28)*0.5) * 0.32;
            float ny = (cos(uvA.y * _StrandScale * 0.22)*0.5) * 0.32;
            float nfX = (ValueNoise(wp.xz * 95.0)-0.5)*0.15;
            float3 n = normalize(float3(nx+nfX, ny, 1.0));

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
