// Soft, deliberately inexpensive light shafts for the Built-in pipeline.
// A translucent mesh, NOT true volumetric raymarching or another light.
Shader "Vespershade/ArenaLightVeil"
{
    Properties { _Color ("Scattered light (alpha = density)", Color) = (0.4, 0.55, 0.8, 0.045) }
    SubShader
    {
        Tags { "Queue"="Transparent+5" "RenderType"="Transparent" "IgnoreProjector"="True" }
        Blend SrcAlpha OneMinusSrcAlpha
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
                float3 world : TEXCOORD1;
                UNITY_FOG_COORDS(2)
            };

            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.uv = v.uv;
                o.world = mul(unity_ObjectToWorld, v.vertex).xyz;
                UNITY_TRANSFER_FOG(o, o.pos);
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float across = 1.0 - abs(i.uv.x * 2.0 - 1.0);
                float feather = smoothstep(0.0, 0.52, across);
                float ends = smoothstep(0.0, 0.2, i.uv.y) *
                             (1.0 - smoothstep(0.72, 1.0, i.uv.y));
                // A camera passing through a shaft never sees an opaque sheet.
                float nearFade = smoothstep(1.5, 3.5,
                    distance(_WorldSpaceCameraPos.xyz, i.world));
                fixed4 color = fixed4(_Color.rgb, _Color.a * feather * ends * nearFade);
                UNITY_APPLY_FOG(i.fogCoord, color);
                return color;
            }
            ENDCG
        }
    }
    FallBack Off
}
