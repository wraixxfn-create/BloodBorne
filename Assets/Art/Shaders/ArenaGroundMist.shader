// Periphery-only ground haze on the MeshKit's 10x10m mist meshes.
// Fade toward the edges so no hard-edged transparent slabs cross the fight.
Shader "Vespershade/ArenaGroundMist"
{
    Properties { _Color ("Mist (alpha = opacity)", Color) = (0.16, 0.19, 0.23, 0.07) }
    SubShader
    {
        Tags { "Queue"="Transparent+1" "RenderType"="Transparent" "IgnoreProjector"="True" }
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
            struct appdata { float4 vertex : POSITION; };
            struct v2f
            {
                float4 pos : SV_POSITION;
                float2 localXZ : TEXCOORD0;
                float2 worldXZ : TEXCOORD1;
                float3 world : TEXCOORD2;
                UNITY_FOG_COORDS(3)
            };
            v2f vert(appdata v)
            {
                v2f o;
                o.pos = UnityObjectToClipPos(v.vertex);
                o.localXZ = v.vertex.xz;
                o.world = mul(unity_ObjectToWorld, v.vertex).xyz;
                o.worldXZ = o.world.xz;
                UNITY_TRANSFER_FOG(o, o.pos);
                return o;
            }
            fixed4 frag(v2f i) : SV_Target
            {
                float radius = length(i.localXZ * 0.2); // mesh has a 5m half-width
                float edge = 1.0 - smoothstep(0.48, 1.0, radius);
                float variation = 0.89 + 0.11 * sin(i.worldXZ.x * 0.7 +
                    i.worldXZ.y * 0.41 + _Time.y * 0.18);
                float nearFade = smoothstep(1.2, 3.0,
                    distance(_WorldSpaceCameraPos.xyz, i.world));
                fixed4 color = fixed4(_Color.rgb, _Color.a * edge * variation * nearFade);
                UNITY_APPLY_FOG(i.fogCoord, color);
                return color;
            }
            ENDCG
        }
    }
    FallBack Off
}
