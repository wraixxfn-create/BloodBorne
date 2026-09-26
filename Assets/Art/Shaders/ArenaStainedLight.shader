// Colored pools beneath broken glass. Real (shadowless) colored spots in the
// rig provide light on geometry; this additive decal only supplies the faint
// fractured pattern on the ground, with no cookie texture or extra light pass.
Shader "Vespershade/ArenaStainedLight"
{
    Properties { _Color ("Glass color (alpha = strength)", Color) = (0.25, 0.43, 0.8, 0.12) }
    SubShader
    {
        Tags { "Queue"="Transparent+2" "RenderType"="Transparent" "IgnoreProjector"="True" }
        Blend SrcAlpha One
        ZWrite Off
        ZTest LEqual
        Cull Off
        Lighting Off
        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma multi_compile_fog
            #include "UnityCG.cginc"

            fixed4 _Color;
            struct appdata { float4 vertex : POSITION; float2 uv : TEXCOORD0; };
            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 uv : TEXCOORD0;
                UNITY_FOG_COORDS(1)
            };
            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                UNITY_TRANSFER_FOG(o, o.pos);
                return o;
            }
            fixed4 frag(v2f i) : SV_Target
            {
                float2 p = i.uv * 2.0 - 1.0;
                float falloff = 1.0 - smoothstep(0.48, 0.98,
                    length(p * float2(1.02, 0.9)));
                // Two fine dark traces read as broken leaded glass, not an AoE.
                float leadA = smoothstep(0.012, 0.055, abs(p.x + 0.27 * p.y - 0.1));
                float leadB = smoothstep(0.014, 0.065, abs(p.y - 0.35 * p.x + 0.18));
                float patch = 0.78 + 0.22 * sin(i.uv.x * 16.0 + i.uv.y * 11.0);
                fixed4 color = fixed4(_Color.rgb,
                    _Color.a * falloff * (0.4 + 0.6 * leadA * leadB) * patch);
                UNITY_APPLY_FOG(i.fogCoord, color);
                return color;
            }
            ENDCG
        }
    }
    FallBack Off
}
