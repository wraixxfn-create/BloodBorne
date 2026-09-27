Shader "Vespershade/CharacterEye"
{
    Properties
    {
        _IrisColor ("Iris Color", Color) = (0.22, 0.36, 0.48, 1)
        _IrisVar ("Iris Variation", Color) = (0.28, 0.44, 0.55, 1)
        _ScleraColor ("Sclera", Color) = (0.92, 0.905, 0.87, 1)
        _PupilColor ("Pupil", Color) = (0.04, 0.045, 0.06, 1)
        _CorneaColor ("Cornea Tint", Color) = (0.85, 0.90, 0.98, 1)
        _Metallic ("Metallic", Range(0,0.1)) = 0.0
        _Glossiness ("Smoothness", Range(0,1)) = 0.92
        _IrisScale ("Iris Detail Scale", Float) = 18
        _PupilSize ("Pupil Size", Range(0.1,0.6)) = 0.32
        _IrisDepth ("Iris Depth", Range(0,1)) = 0.35
        _OcclusionStrength ("Occlusion", Range(0,1)) = 0.6
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows
        #pragma target 3.0

        fixed4 _IrisColor;
        fixed4 _IrisVar;
        fixed4 _ScleraColor;
        fixed4 _PupilColor;
        fixed4 _CorneaColor;
        half _Metallic;
        half _Glossiness;
        half _IrisScale;
        half _PupilSize;
        half _IrisDepth;
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
            // Approximate eye center at head ~1.70m, use local offset from world
            // For procedural iris, use polar coordinates around eye forward (approx +Z)
            // Use worldNormal to orient: front of eye is where normal Z is high
            float3 wn = normalize(IN.worldNormal);
            // Use spherical mapping: project onto plane perpendicular to forward
            float2 irisUV = float2(wp.x, wp.y) * 12.0;
            // Actually use worldPos relative to approximate eye socket positions
            // Two eyes: left/right at x ~ +/-0.03, y ~1.70, z ~0.06
            float eyeCenterX = sign(wp.x) * 0.032;
            float2 delta = float2(wp.x - eyeCenterX, wp.y - 1.705);
            float r = length(delta);
            float angle = atan2(delta.y, delta.x);

            // Sclera vs iris: iris radius ~0.011, sclera larger
            float irisRadius = 0.0115;
            float pupilRadius = irisRadius * _PupilSize;

            float irisMask = 1.0 - smoothstep(irisRadius*0.92, irisRadius, r);
            float pupilMask = 1.0 - smoothstep(pupilRadius*0.85, pupilRadius, r);

            // Iris detail - radial fibers + subtle color variation
            float radial = frac(angle * 6.0 / 6.28318 + r*22.0);
            float fiber = sin(angle * _IrisScale + r*85.0) * 0.5 + 0.5;
            float fiber2 = ValueNoise(float2(angle*3.0, r*55.0));
            float irisNoise = FBM(float2(angle*2.0, r*18.0));

            fixed3 irisCol = lerp(_IrisColor.rgb, _IrisVar.rgb, saturate(fiber*0.5 + irisNoise*0.5));
            // Darken iris towards pupil and limb
            float limbDark = pow(saturate(r/irisRadius), 2.2)*0.35;
            irisCol *= lerp(1.0, 0.65, limbDark);
            // Slight radial dark streaks
            irisCol *= lerp(1.0, 0.85, pow(fiber, 4.0)*0.5);

            fixed3 sclera = _ScleraColor.rgb * (0.92 + ValueNoise(wp.xz*45.0)*0.08);
            // Subtle vein tint near edges
            float vein = ValueNoise(wp.xy*28.0) * 0.04 * (1.0-irisMask);

            fixed3 albedo = lerp(sclera, irisCol, irisMask);
            albedo = lerp(albedo, _PupilColor.rgb, pupilMask*irisMask);

            // Cornea highlight - not albedo but smoothness and subtle tint
            float cornea = saturate(irisMask*0.6 + (1.0-irisMask)*0.15);
            albedo = lerp(albedo, _CorneaColor.rgb*albedo, cornea*0.08);

            // AO - iris depth
            float ao = lerp(1.0, 1.0 - irisMask* _IrisDepth *0.35 - pupilMask*0.15, _OcclusionStrength);

            // Smoothness - cornea very smooth, sclera less, iris medium
            half smoothness = lerp(0.35, _Glossiness, cornea);
            smoothness = lerp(smoothness, _Glossiness*0.92, irisMask*0.7);
            smoothness = lerp(smoothness, 0.15, pupilMask*0.8);
            // Add tiny variation to avoid uniform roughness
            smoothness += (ValueNoise(wp.xz*65.0)-0.5)*0.04;
            smoothness = saturate(smoothness);

            // Normal - slight iris concave + cornea convex
            float irisConcave = irisMask * (1.0-pupilMask) * -0.18;
            float3 n = normalize(float3(delta.x* irisConcave * 18.0, delta.y* irisConcave * 18.0, 1.0));

            o.Albedo = albedo * ao + vein*0.02;
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
