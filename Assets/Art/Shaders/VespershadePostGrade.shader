// Foundation fullscreen grade for the built-in render pipeline.
// One pass: saturation/contrast/tint grading, vignette and animated film grain.
// Driven by Vespershade.Rendering.PostProcessController.
Shader "Hidden/Vespershade/PostGrade"
{
    Properties
    {
        _MainTex ("Source", 2D) = "white" {}
        _VignetteColor ("Vignette Color", Color) = (0.01, 0.01, 0.02, 1)
        _VignetteIntensity ("Vignette Intensity", Range(0, 1)) = 0.45
        _VignetteRadius ("Vignette Radius", Range(0, 1)) = 0.58
        _VignetteSoftness ("Vignette Softness", Range(0.01, 1)) = 0.42
        _Saturation ("Saturation", Range(0, 2)) = 0.9
        _Contrast ("Contrast", Range(0.5, 1.5)) = 1.06
        _Tint ("Tint", Color) = (0.96, 0.97, 1.0, 1)
        _GrainIntensity ("Grain Intensity", Range(0, 0.3)) = 0.05
        _GrainSpeed ("Grain Speed", Float) = 24
    }

    SubShader
    {
        Cull Off
        ZWrite Off
        ZTest Always

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #include "UnityCG.cginc"

            sampler2D _MainTex;
            half4 _VignetteColor;
            half4 _Tint;
            half _VignetteIntensity;
            half _VignetteRadius;
            half _VignetteSoftness;
            half _Saturation;
            half _Contrast;
            half _GrainIntensity;
            float _GrainSpeed;
            float _GrainTime;

            struct appdata
            {
                float4 vertex : POSITION;
                float2 uv : TEXCOORD0;
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                return o;
            }

            // Cheap 2D -> 1D hash for film grain.
            half Hash21(float2 p)
            {
                p = frac(p * float2(234.34, 435.345));
                p += dot(p, p + 34.23);
                return frac(p.x * p.y);
            }

            half4 frag(v2f i) : SV_Target
            {
                half4 color = tex2D(_MainTex, i.uv);

                // Grading: saturation around luma, contrast around mid grey, then tint.
                half luma = dot(color.rgb, half3(0.299, 0.587, 0.114));
                color.rgb = lerp(half3(luma, luma, luma), color.rgb, _Saturation);
                color.rgb = (color.rgb - half3(0.5, 0.5, 0.5)) * _Contrast + half3(0.5, 0.5, 0.5);
                color.rgb *= _Tint.rgb;

                // Vignette: distance from center normalized so corners reach 1.
                float2 centered = i.uv - float2(0.5, 0.5);
                float dist01 = length(centered) * 1.41421356;
                half vignetteAmount = smoothstep(_VignetteRadius, _VignetteRadius + _VignetteSoftness, dist01);
                color.rgb = lerp(color.rgb, _VignetteColor.rgb, vignetteAmount * _VignetteIntensity);

                // Animated film grain, stepped in time so it shimmers like film.
                float2 grainUv = i.uv * _ScreenParams.xy * 0.5 + floor(_GrainTime * _GrainSpeed).xx;
                half grain = Hash21(grainUv);
                color.rgb += (grain - 0.5h) * _GrainIntensity;

                return color;
            }
            ENDCG
        }
    }

    FallBack Off
}
