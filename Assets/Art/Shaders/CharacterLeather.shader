Shader "Vespershade/CharacterLeather"
{
    Properties
    {
        _Color ("Base Color", Color) = (0.165, 0.105, 0.072, 1)
        _ColorVar ("Color Variation", Color) = (0.205, 0.13, 0.085, 1)
        _WearColor ("Wear Highlight", Color) = (0.26, 0.18, 0.12, 1)
        _Metallic ("Metallic", Range(0,0.15)) = 0.03
        _Glossiness ("Smoothness", Range(0,1)) = 0.48
        _GlossVar ("Roughness Variation", Range(0,0.6)) = 0.24
        _GrainScale ("Grain Scale", Float) = 42
        _GrainStrength ("Grain Strength", Range(0,1)) = 0.42
        _ScratchScale ("Scratch Scale", Float) = 165
        _WearAmount ("Wear Amount", Range(0,1)) = 0.20
        _OcclusionStrength ("Occlusion", Range(0,1)) = 0.9
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
        fixed4 _WearColor;
        half _Metallic;
        half _Glossiness;
        half _GlossVar;
        half _GrainScale;
        half _GrainStrength;
        half _ScratchScale;
        half _WearAmount;
        half _OcclusionStrength;

        struct Input
        {
            float3 worldPos;
            float3 worldNormal;
            INTERNAL_DATA
        };

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
            float v=0; float amp=0.5;
            for(int j=0;j<4;j++){ v+=ValueNoise(p)*amp; p=p*2.13+float2(2.7,1.9); amp*=0.5; }
            return v;
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 wp = IN.worldPos;
            float2 uvA = wp.xz * 0.8 + wp.y * 0.18;
            float2 uvB = wp.xy * 0.7 + wp.z * 0.2;

            float nLarge = FBM(uvA*0.45);
            float nMed = FBM(uvB*0.9);
            float nFine = ValueNoise(wp.xz * 35.0);

            // Leather grain - cellular-ish
            float2 grainUV = wp.xz * 0.35 + wp.y*0.1;
            float grain = sin(grainUV.x * _GrainScale * 0.18) * sin(grainUV.y * _GrainScale * 0.18);
            grain = grain*0.5+0.5;
            float grain2 = FBM(grainUV * 1.8) * 0.6 + ValueNoise(grainUV*12.0)*0.4;
            float leatherPore = saturate(grain2*1.2 - 0.15);

            // Scratches - stretched noise
            float2 scratchUV = float2(wp.x*0.2 + wp.y*0.8, wp.z*0.3) * _ScratchScale * 0.02;
            float scratch = ValueNoise(scratchUV*float2(8,1)) * ValueNoise(scratchUV*float2(1,4)*1.3);
            scratch = pow(scratch, 2.5) * 0.6;

            // Albedo variation
            float varMask = saturate(nLarge*0.5 + leatherPore*0.35 + nMed*0.15);
            fixed3 albedo = lerp(_Color.rgb, _ColorVar.rgb, varMask * 0.65);
            // Subtle darker crevice, lighter wear at stretched areas
            float crevice = saturate((1.0-leatherPore)*0.5 + (1.0-nMed)*0.2) * 0.18;
            albedo *= lerp(1.0, 0.88, crevice);
            float wear = saturate(scratch*1.2 + nFine*0.25 + nLarge*0.15) * _WearAmount;
            albedo = lerp(albedo, _WearColor.rgb, wear*0.55);

            float ao = lerp(1.0, 1.0 - crevice*0.6 - leatherPore*0.12, _OcclusionStrength);

            // Smoothness - leather has different roughness from cloth: higher base, but varied
            // More polished where worn, more matte in grain pits
            float roughVar = (nMed*0.5 + leatherPore*0.3 + scratch*0.4) - 0.45;
            half smoothness = saturate(_Glossiness + roughVar*_GlossVar);
            smoothness = saturate(smoothness + wear*0.12 - crevice*0.18);

            // Normal - grain bump + scratch
            float nx = (ValueNoise(grainUV* _GrainScale*0.25)-0.5) * _GrainStrength;
            float ny = (ValueNoise(grainUV* _GrainScale*0.27 + 4.3)-0.5) * _GrainStrength;
            float sx = (ValueNoise(scratchUV*float2(6,0.5))-0.5)*0.18 * saturate(scratch*3);
            float3 n = normalize(float3(nx+sx, ny, 1.0));

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
