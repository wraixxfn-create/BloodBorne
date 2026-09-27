// Vespershade character hair material.
//
// Written for the "Vigil Sweep" hairstyle: a swept-solid lock build whose
// macro shape is geometry, while this shader supplies the strand-level
// material response (flow-aligned banding, anisotropic highlight, root
// occlusion). All flow/pattern work is evaluated in OBJECT space via a
// custom vertex function, so the pattern is glued to the mesh and cannot
// swim, crawl or slide when the character moves, animates or the camera
// orbits - the failure mode of world/triplanar procedural hair shading.
//
// Lighting: Kajiya-Kay style two-lobe anisotropic specular over the
// strand tangent field (primary shifted + tight, secondary wider and
// tinted), on top of a wrapped diffuse for the soft look hair gives.
Shader "Vespershade/CharacterHair"
{
    Properties
    {
        _Color ( "Base Color", Color ) = ( 0.13, 0.145, 0.175, 1 )
        _ColorVar ( "Variation", Color ) = ( 0.17, 0.18, 0.21, 1 )
        _HighlightColor ( "Highlight Tint", Color ) = ( 0.32, 0.30, 0.27, 1 )
        _Metallic ( "Metallic", Range( 0, 0.1 ) ) = 0.02
        _Glossiness ( "Smoothness", Range( 0, 1 ) ) = 0.38
        _GlossVar ( "Roughness Variation", Range( 0, 0.5 ) ) = 0.22
        _StrandScale ( "Strand Scale", Float ) = 140
        _AnisoAmount ( "Anisotropy", Range( 0, 1 ) ) = 0.65
        _OcclusionStrength ( "Occlusion", Range( 0, 1 ) ) = 0.85
        _RootDarkening ( "Root Darkening", Range( 0, 1 ) ) = 0.45
        _FlowStrength ( "Flow Strength", Range( 0, 1 ) ) = 0.8
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" }
        LOD 300

        CGPROGRAM
        // custom lighting: Kajiya-Kay two-lobe anisotropic on SurfaceOutputHair
        #pragma surface surf Hair fullforwardshadows
        #pragma target 3.0

        #include "UnityLightingCommon.cginc"   // _LightColor0

        fixed4 _Color;
        fixed4 _ColorVar;
        fixed4 _HighlightColor;
        half _Metallic;
        half _Glossiness;
        half _GlossVar;
        half _StrandScale;
        half _AnisoAmount;
        half _OcclusionStrength;
        half _RootDarkening;
        half _FlowStrength;

        // Extended surface output carrying the per-pixel strand tangent so
        // the lighting function can do the anisotropic (tangent-based) spec.
        struct SurfaceOutputHair
        {
            fixed3 Albedo;
            fixed3 Normal;
            fixed3 Emission;
            half3  StrandTangent;   // world-space hair flow direction
            half   Metallic;
            half   Smoothness;
            half   Occlusion;
            half   Alpha;
        };

        struct Input
        {
            float3 objPos;          // object-space position (stable bind-pose frame)
            float3 worldNormal;
            INTERNAL_DATA
        };

        void vert ( inout appdata_full v, out Input o )
        {
            UNITY_INITIALIZE_OUTPUT( Input, o );
            o.objPos = v.vertex.xyz;
        }

        // ------------------------------------------------------------------ noise
        float Hash21 ( float2 p ) { p = frac( p * float2( 123.34, 456.21 ) ); p += dot( p, p + 45.32 ); return frac( p.x * p.y ); }
        float ValueNoise ( float2 p )
        {
            float2 i = floor( p ); float2 f = frac( p ); f = f * f * ( 3 - 2 * f );
            float a = Hash21( i ); float b = Hash21( i + float2( 1, 0 ) );
            float c = Hash21( i + float2( 0, 1 ) ); float d = Hash21( i + float2( 1, 1 ) );
            return lerp( lerp( a, b, f.x ), lerp( c, d, f.x ), f.y );
        }
        float FBM ( float2 p )
        {
            float v = 0; float amp = 0.5;
            for ( int j = 0; j < 3; j++ ) { v += ValueNoise( p ) * amp; p = p * 2.17 + float2( 2.7, 1.9 ); amp *= 0.5; }
            return v;
        }
        float Hash31 ( float3 p ) { return frac( sin( dot( p, float3( 12.9898, 78.233, 37.719 ) ) ) * 43758.5453 ); }

        // ------------------------------------------------------- strand flow field
        // Object-space hair direction: part line just right of centre (x ~ +0.006
        // on the crown), deep diagonal sweep to the left, collected into the
        // low back tail. Regions blend smoothly; everything is a function of
        // the bind-pose mesh coordinates, so it is rock solid under animation.
        float3 StrandFlow ( float3 p, float3 nObj )
        {
            float upness = smoothstep( 1.60, 1.72, p.y );          // crown vs nape
            float backness = smoothstep( 0.01, -0.05, p.z );       // behind the ear line

            // crown: flow sideways away from the part line, biased backwards
            float partX = 0.006 + 0.010 * ( 1.0 - upness );
            float sideSign = p.x > partX ? 1.0 : -1.0;
            float3 crown = normalize( float3( sideSign * 0.85, -0.35, -0.55 ) );

            // sides: down and back (temple sweep)
            float3 side = normalize( float3( 0.15 * sign( p.x + 1e-5 ), -0.8, -0.62 ) );

            // nape / back: straight down into the tail
            float3 down = normalize( float3( 0.0, -1.0, -0.18 ) );

            float3 flow = down;
            flow = lerp( flow, side, saturate( backness * 2.0 ) * ( 1.0 - upness ) );
            flow = lerp( flow, crown, upness );
            // keep the flow tangential to the surface so bands hug the form
            flow = normalize( flow - nObj * dot( flow, nObj ) );
            return flow;
        }

        // ------------------------------------------------------- Kajiya-Kay light
        half4 LightingHair ( SurfaceOutputHair s, half3 lightDir, half3 viewDir, half atten )
        {
            half3 T = normalize( s.StrandTangent );

            // wrapped diffuse: hair self-shadows softly
            half NdotL = dot( s.Normal, lightDir );
            half diff = saturate( ( NdotL + 0.45 ) / 1.45 );

            // Kajiya-Kay: sin(angle) between the strand tangent and L / H
            half TL = dot( T, lightDir );
            half sinTL = sqrt( saturate( 1.0 - TL * TL ) );
            half3 H = normalize( lightDir + viewDir );
            half TH = dot( T, H );
            half sinTH = sqrt( saturate( 1.0 - TH * TH ) );

            // two lobes: tight primary shifted toward the root, wider tinted secondary
            half spec1 = pow( saturate( sinTH + 0.10 ), 96.0 );
            half spec2 = pow( saturate( max( sinTH - 0.06, 0.0 ) ), 22.0 );
            half3 spec = ( spec1 * 0.55 + spec2 * 0.45 * _AnisoAmount )
                       * _HighlightColor.rgb * s.Smoothness;

            half4 c;
            c.rgb = s.Albedo * diff * _LightColor0.rgb + _LightColor0.rgb * spec;
            c.rgb *= atten;
            c.a = s.Alpha;
            return c;
        }

        half4 LightingHair_GI ( SurfaceOutputHair s, UnityGIInput data, inout UnityGI gi )
        {
            // indirect/ambient keeps the standard packing; direct light is KK above
            gi = UnityGlobalIllumination( data, s.Occlusion, s.Normal );
            return half4( 0, 0, 0, 0 );
        }

        void surf ( Input IN, inout SurfaceOutputHair o )
        {
            float3 p = IN.objPos;

            // rebuild the world normal from the interpolated frame, then to object space
            float3 wT = WorldNormalVector( IN, float3( 1, 0, 0 ) );
            float3 wN = WorldNormalVector( IN, float3( 0, 1, 0 ) );
            float3 wB = WorldNormalVector( IN, float3( 0, 0, 1 ) );
            float3 nObj = normalize( mul( unity_WorldToObject, float4( wN, 0.0 ) ) );

            float3 T = StrandFlow( p, nObj );
            float3 B = normalize( cross( T, nObj ) );

            // flow-frame coordinates
            float u = dot( p, T );
            float v = dot( p, B );

            // strand banding along the flow, warped by low-frequency noise so
            // bands wave and split naturally (two scales: bundles + flyaways)
            float warp = ( FBM( float2( u * 3.0, v * 3.0 ) ) - 0.5 ) * 0.9;
            float freq = _StrandScale;
            float band = sin( v * freq + warp * 4.0 );
            float fine = sin( v * freq * 2.37 + u * freq * 0.21 + warp * 7.0 ) * 0.5 + 0.5;
            float bundle = band * 0.5 + 0.5;

            // colour: base/var mix driven by bundles + patchy per-region tint
            float patch = Hash31( floor( p * 55.0 ) );
            float varMask = saturate( bundle * 0.45 + FBM( p.xy * 6.0 + p.z ) * 0.25 + patch * 0.20 );
            fixed3 albedo = lerp( _Color.rgb, _ColorVar.rgb, varMask * 0.7 );

            // root occlusion: darken toward hairline/roots (object-space heights
            // of the Vigil Sweep: front hairline ~1.73, ear line ~1.70, nape ~1.57)
            float hairline = 1.735 - 0.16 * smoothstep( 0.05, -0.10, p.z );
            float rootT = saturate( ( hairline - p.y ) / 0.05 );
            float valley = 1.0 - bundle;                        // between strands
            float ao = saturate( 1.0
                     - _RootDarkening * rootT * 0.9
                     - _OcclusionStrength * 0.22 * valley
                     - 0.10 * ( 1.0 - fine ) );

            // normal: tilt along the band profile (strand grooves), then to world
            float groove = cos( v * freq + warp * 4.0 );
            float3 nPertObj = normalize( nObj + B * ( groove * 0.22 * _FlowStrength )
                                              + T * ( ( fine - 0.5 ) * 0.06 ) );
            float3 nPertWorld = normalize( mul( ( float3x3 ) unity_ObjectToWorld, nPertObj ) );
            // express the world-space perturbed normal in the surface shader's
            // tangent frame (the frame WorldNormalVector builds from TtoW rows)
            o.Normal = float3( dot( nPertWorld, wT ), dot( nPertWorld, wN ), dot( nPertWorld, wB ) );

            // roughness varies with bundles/flyaways
            float roughVar = ( FBM( p.zy * 8.0 ) * 0.5 + fine * 0.3 + patch * 0.2 ) - 0.5;
            half smoothness = saturate( _Glossiness + roughVar * _GlossVar + bundle * 0.06 );

            o.Albedo = albedo * ao;
            o.Metallic = _Metallic;
            o.Smoothness = smoothness;
            o.StrandTangent = normalize( mul( ( float3x3 ) unity_ObjectToWorld, T ) );
            o.Occlusion = saturate( ao * 0.4 + 0.6 );
            o.Emission = 0;
            o.Alpha = 1;
        }
        ENDCG
    }
    FallBack "Standard"
}
