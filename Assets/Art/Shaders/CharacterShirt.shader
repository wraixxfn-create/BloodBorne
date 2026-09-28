Shader "Vespershade/CharacterShirt"
{
    Properties
    {
        _Color ("Base Color", Color) = (0.60, 0.52, 0.39, 1)
        _ColorVar ("Variation", Color) = (0.66, 0.57, 0.43, 1)
        _ThreadColor ("Thread Tint", Color) = (0.52, 0.45, 0.33, 1)
        _Metallic ("Metallic", Range(0,0.12)) = 0.02
        _Glossiness ("Smoothness", Range(0,1)) = 0.27
        _GlossVar ("Roughness Variation", Range(0,0.5)) = 0.10
        _WeaveScale ("Weave Scale", Float) = 105
        _WeaveStrength ("Weave Strength", Range(0,1)) = 0.18
        _WearAmount ("Wear Amount", Range(0,1)) = 0.10
        _OcclusionStrength ("Occlusion", Range(0,1)) = 0.72
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows vertex:vert
        #pragma target 3.0

        fixed4 _Color;
        fixed4 _ColorVar;
        fixed4 _ThreadColor;
        half _Metallic;
        half _Glossiness;
        half _GlossVar;
        half _WeaveScale;
        half _WeaveStrength;
        half _WearAmount;
        half _OcclusionStrength;

        struct Input { float3 objPos; INTERNAL_DATA };

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

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 wp = IN.objPos;
            float2 uvA = wp.xz*0.75 + wp.y*0.18;
            float2 uvB = wp.xy*0.6;

            float nLarge = FBM(uvA*0.6);
            float nMed = FBM(uvB*1.2);
            float nFine = ValueNoise(wp.xz*40.0);

            float2 weaveUV = wp.xz*0.6 + wp.y*0.14;
            float weave = sin(weaveUV.x*_WeaveScale*0.18)*sin(weaveUV.y*_WeaveScale*0.18);
            weave = weave*0.5+0.5;

            float varMask = saturate(nLarge*0.5 + weave*0.25 + nMed*0.25);
            fixed3 albedo = lerp(_Color.rgb, _ColorVar.rgb, varMask*0.55);
            // Subtle thread darker in crevices
            float thread = saturate((1.0-weave)*0.35) * 0.18;
            albedo = lerp(albedo, _ThreadColor.rgb, thread);

            float wear = saturate(nFine*0.3 + nLarge*0.15)*_WearAmount;
            albedo = lerp(albedo, _ColorVar.rgb*1.1, wear*0.35);

            float ao = lerp(1.0, 1.0 - thread*0.5, _OcclusionStrength);

            float roughVar = (nMed*0.4 + nFine*0.3 + weave*0.2) - 0.45;
            half smoothness = saturate(_Glossiness + roughVar*_GlossVar);

            float nx = (ValueNoise(weaveUV*_WeaveScale*0.22)-0.5)*_WeaveStrength;
            float ny = (ValueNoise(weaveUV*_WeaveScale*0.24+3.1)-0.5)*_WeaveStrength;
            float3 n = normalize(float3(nx, ny, 1.0));

            o.Albedo = albedo;
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
