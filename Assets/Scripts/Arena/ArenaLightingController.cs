using UnityEngine;

namespace Vespershade.Arena
{
    /// <summary>
    /// Orchestrates the chamber's lighting: cold moon key, warm candle
    /// flicker, and faint ritual emissive pulse. Designed for gameplay
    /// readability: candles are point lights kept dim and warm to
    /// contrast the cold ambient without blowing out the combat disc.
    /// </summary>
    public class ArenaLightingController : MonoBehaviour
    {
        [Header("Moon Key")]
        [Tooltip("Directional moon light (cold, dim, soft shadows).")]
        public Light moonLight;

        [Header("Candles")]
        [Tooltip("All point lights parented under candle clusters. Flicker is applied per-light with phase offset.")]
        public Light[] candleLights;

        [Range(0f, 0.5f)]
        public float candleFlickerAmplitude = 0.12f;

        [Tooltip("Flicker speed for candle intensity.")]
        public float candleFlickerSpeed = 6.5f;

        [Header("Moon Shafts")]
        [Tooltip("Spot lights that act as volumetric shafts from shattered arch windows.")]
        public Light[] moonShafts;

        [Range(0f, 0.3f)]
        public float shaftBreathing = 0.08f;

        [Header("Ritual Pulse")]
        [Tooltip("Emissive renderer materials for the ritual ring; pulse scale drives emission intensity via shader.")]
        public Renderer[] ritualEmissiveRenderers;

        public float ritualPulseSpeed = 0.35f;
        public float ritualPulseStrength = 0.5f;

        private float[] candleBaseIntensities;
        private float[] shaftBaseIntensities;
        private float seed;

        private void Awake()
        {
            seed = Random.Range(0f, 100f);

            // Auto-discover lights/renderers if prefab wiring is empty.
            if (candleLights == null || candleLights.Length == 0)
            {
                var all = GetComponentsInChildren<Light>(true);
                var candles = new System.Collections.Generic.List<Light>();
                var shafts = new System.Collections.Generic.List<Light>();
                foreach (var l in all)
                {
                    if (l.type == LightType.Point && l.gameObject.name.Contains("Candle"))
                        candles.Add(l);
                    else if (l.type == LightType.Spot && l.gameObject.name.Contains("MoonShaft"))
                        shafts.Add(l);
                }
                if (candles.Count > 0) candleLights = candles.ToArray();
                if (shafts.Count > 0) moonShafts = shafts.ToArray();
            }

            if (ritualEmissiveRenderers == null || ritualEmissiveRenderers.Length == 0)
            {
                var allR = GetComponentsInChildren<Renderer>(true);
                var ritual = new System.Collections.Generic.List<Renderer>();
                foreach (var r in allR)
                {
                    if (r.gameObject.name.Contains("Ritual") || r.gameObject.name.Contains("Marking"))
                        ritual.Add(r);
                }
                if (ritual.Count > 0) ritualEmissiveRenderers = ritual.ToArray();
            }

            if (candleLights != null)
            {
                candleBaseIntensities = new float[candleLights.Length];
                for (int i = 0; i < candleLights.Length; i++)
                    candleBaseIntensities[i] = candleLights[i] != null ? candleLights[i].intensity : 1f;
            }

            if (moonShafts != null)
            {
                shaftBaseIntensities = new float[moonShafts.Length];
                for (int i = 0; i < moonShafts.Length; i++)
                    shaftBaseIntensities[i] = moonShafts[i] != null ? moonShafts[i].intensity : 1f;
            }
        }

        private void Update()
        {
            float t = Time.time;

            // Candle flicker: per-light phase offset so they don't pulse uniformly
            if (candleLights != null && candleBaseIntensities != null)
            {
                for (int i = 0; i < candleLights.Length; i++)
                {
                    if (candleLights[i] == null) continue;
                    float phase = seed + i * 0.73f;
                    // Combine two sine frequencies for irregular flicker
                    float n1 = Mathf.Sin(t * candleFlickerSpeed + phase) * 0.5f;
                    float n2 = Mathf.Sin(t * candleFlickerSpeed * 2.37f + phase * 1.4f) * 0.25f;
                    float flicker = (n1 + n2) * candleFlickerAmplitude;
                    candleLights[i].intensity = Mathf.Max(0f, candleBaseIntensities[i] + flicker);
                }
            }

            // Moon shafts: very slow breathing, almost imperceptible
            if (moonShafts != null && shaftBaseIntensities != null)
            {
                float breath = Mathf.Sin(t * 0.25f + seed) * 0.5f + 0.5f;
                for (int i = 0; i < moonShafts.Length; i++)
                {
                    if (moonShafts[i] == null) continue;
                    moonShafts[i].intensity = shaftBaseIntensities[i] * (1f + (breath - 0.5f) * shaftBreathing);
                }
            }

            // Ritual emissive pulse: modulate emission color multiplier
            if (ritualEmissiveRenderers != null)
            {
                float pulse = Mathf.Sin(t * ritualPulseSpeed + seed) * 0.5f + 0.5f;
                float emissionScale = 1f + pulse * ritualPulseStrength;
                Color baseEmission = new Color(0.22f, 0.48f, 0.52f, 1f) * emissionScale;
                for (int i = 0; i < ritualEmissiveRenderers.Length; i++)
                {
                    if (ritualEmissiveRenderers[i] == null) continue;
                    // MaterialPropertyBlock avoids instancing materials for the subtle pulse
                    var block = new MaterialPropertyBlock();
                    ritualEmissiveRenderers[i].GetPropertyBlock(block);
                    block.SetColor("_EmissionColor", baseEmission);
                    ritualEmissiveRenderers[i].SetPropertyBlock(block);
                }
            }
        }
    }
}
