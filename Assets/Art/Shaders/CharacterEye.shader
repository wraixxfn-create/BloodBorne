Shader "Vespershade/CharacterEye"
{
    Properties
    {
        _IrisColor ("Iris Color", Color) = (0.18, 0.31, 0.42, 1)
        _IrisVar ("Iris Variation", Color) = (0.27, 0.39, 0.47, 1)
        _ScleraColor ("Warm Sclera", Color) = (0.76, 0.73, 0.68, 1)
        _PupilColor ("Pupil", Color) = (0.025, 0.03, 0.04, 1)
        _LimbalColor ("Limbal Ring", Color) = (0.055, 0.085, 0.11, 1)
        _VeinColor ("Faint Vein Tint", Color) = (0.38, 0.19, 0.17, 1)
        _CorneaColor ("Cornea Tint", Color) = (0.84, 0.89, 0.94, 1)
        _Metallic ("Metallic", Range(0,0.1)) = 0.0
        _Glossiness ("Eye Moisture", Range(0,1)) = 0.72
        _IrisScale ("Iris Fiber Count", Float) = 36
        _PupilSize ("Pupil Size", Range(0.1,0.6)) = 0.30
        _IrisDepth ("Iris Recess", Range(0,1)) = 0.30
        _OcclusionStrength ("Occlusion", Range(0,1)) = 0.38
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 300
        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows vertex:vert
        #pragma target 3.0

        fixed4 _IrisColor;
        fixed4 _IrisVar;
        fixed4 _ScleraColor;
        fixed4 _PupilColor;
        fixed4 _LimbalColor;
        fixed4 _VeinColor;
        fixed4 _CorneaColor;
        half _Metallic;
        half _Glossiness;
        half _IrisScale;
        half _PupilSize;
        half _IrisDepth;
        half _OcclusionStrength;

        struct Input
        {
            float3 objPos;
            INTERNAL_DATA
        };

        // The source OBJ has no UVs. Its authored local eye centres are stable
        // under the player transform, and a generated TBN supports the normal output.
        void vert(inout appdata_full v, out Input o)
        {
            UNITY_INITIALIZE_OUTPUT(Input, o);
            o.objPos = v.vertex.xyz;
            float3 n = normalize(v.normal);
            float3 axis = abs(n.y) < 0.92 ? float3(0.0, 1.0, 0.0) : float3(1.0, 0.0, 0.0);
            v.tangent = float4(normalize(cross(axis, n)), 1.0);
        }

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
            f = f * f * (3.0 - 2.0 * f);
            float a = Hash21(i);
            float b = Hash21(i + float2(1, 0));
            float c = Hash21(i + float2(0, 1));
            float d = Hash21(i + float2(1, 1));
            return lerp(lerp(a, b, f.x), lerp(c, d, f.x), f.y);
        }

        void surf(Input IN, inout SurfaceOutputStandard o)
        {
            float3 p = IN.objPos;
            float eyeCenterX = p.x < 0.0 ? -0.033 : 0.033;
            float2 delta = float2(p.x - eyeCenterX, p.y - 1.692);
            float radius = length(delta);
            float angle = atan2(delta.y, delta.x);

            // The existing inset eye spheres are ~10.5 mm radius. Keep the iris
            // and pupil within that surface, leaving a visible warm scleral rim.
            float irisRadius = 0.0052;
            float pupilRadius = irisRadius * _PupilSize;
            float irisMask = 1.0 - smoothstep(irisRadius * 0.94, irisRadius * 1.06, radius);
            float pupilMask = 1.0 - smoothstep(pupilRadius * 0.82, pupilRadius * 1.10, radius);
            float radialT = saturate(radius / irisRadius);

            // Fine, subdued radial fibers with a little asymmetry; no emissive or
            // painted-on white highlight, so the eye reflects the actual scene.
            float fiberWave = sin(angle * _IrisScale + radialT * 17.0 + sin(angle * 7.0) * 0.55);
            float fibers = 0.5 + 0.5 * fiberWave;
            float irisNoise = ValueNoise(float2(cos(angle) * 6.0, sin(angle) * 6.0) + radialT * 3.0);
            fixed3 iris = lerp(_IrisColor.rgb, _IrisVar.rgb,
                               saturate(0.22 + fibers * 0.36 + irisNoise * 0.28));
            float innerShadow = 1.0 - smoothstep(0.08, 0.72, radialT);
            iris *= lerp(0.74, 1.0, innerShadow);
            float limbal = smoothstep(0.76, 0.99, radialT) * irisMask;
            iris = lerp(iris, _LimbalColor.rgb, limbal * 0.72);

            float scleraNoise = ValueNoise(p.xy * 180.0 + p.z * 23.0);
            fixed3 sclera = _ScleraColor.rgb * (0.97 + scleraNoise * 0.045);
            float vesselWave = pow(saturate(0.5 + 0.5 * sin(angle * 5.0 + radialT * 18.0)), 14.0);
            float vein = vesselWave * smoothstep(0.68, 0.98, radialT) * (1.0 - irisMask) * 0.08;
            sclera = lerp(sclera, _VeinColor.rgb, vein);

            fixed3 albedo = lerp(sclera, iris, irisMask);
            albedo = lerp(albedo, _PupilColor.rgb, pupilMask * irisMask);
            albedo = lerp(albedo, albedo * _CorneaColor.rgb, 0.035);

            float aoMask = irisMask * _IrisDepth * 0.22 + pupilMask * 0.08;
            float ao = lerp(1.0, 1.0 - aoMask, _OcclusionStrength);
            half smoothness = lerp(0.48, _Glossiness, 0.42 + irisMask * 0.30);
            smoothness = lerp(smoothness, _Glossiness * 0.92, pupilMask * irisMask * 0.35);
            smoothness += (ValueNoise(p.xy * 320.0) - 0.5) * 0.025;

            // Preserve the sphere's authored curvature; its wet corneal response
            // comes from restrained smoothness under the real arena lights.
            o.Albedo = albedo;
            o.Metallic = _Metallic;
            o.Smoothness = saturate(smoothness);
            o.Normal = float3(0.0, 0.0, 1.0);
            o.Occlusion = ao;
            o.Alpha = 1.0;
        }
        ENDCG
    }
    FallBack "Standard"
}
