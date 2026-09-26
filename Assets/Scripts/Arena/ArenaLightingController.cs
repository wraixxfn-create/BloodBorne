using System.Collections.Generic;
using UnityEngine;

namespace Vespershade.Arena
{
    /// <summary>
    /// Animates the practical lights and emissive stone on the environment prefab.
    /// The steady moon key and combat fills live in the separate Arena_LightingRig:
    /// they deliberately NEVER flicker, so subjects remain readable.
    /// </summary>
    public class ArenaLightingController : MonoBehaviour
    {
        [Header("Practical candles (no realtime shadows)")]
        [Tooltip("Only enabled candle point lights. Falls back to a child search for older prefabs.")]
        public Light[] candleLights;

        [Range(0f, 0.3f)]
        [Tooltip("Fraction of each candle's authored intensity, not a fixed brightness offset.")]
        public float candleFlickerAmplitude = 0.12f;

        public float candleFlickerSpeed = 5.2f;

        [Header("Cold window spots (shadowless)")]
        public Light[] moonShafts;

        [Range(0f, 0.15f)]
        public float shaftBreathing = 0.035f;

        [Header("Ritual stone (not a combat telegraph)")]
        public Renderer[] ritualEmissiveRenderers;

        public float ritualPulseSpeed = 0.32f;

        [Range(0f, 0.3f)]
        public float ritualPulseStrength = 0.14f;

        private float[] candleBaseIntensities;
        private float[] shaftBaseIntensities;
        private Color[] ritualBaseEmissions;
        private MaterialPropertyBlock propertyBlock;

        private void Awake()
        {
            // Discover each category independently. An authored candle array must not
            // prevent discovery of window spots (or vice versa).
            if (candleLights == null || candleLights.Length == 0 ||
                moonShafts == null || moonShafts.Length == 0)
            {
                var candles = new List<Light>();
                var shafts = new List<Light>();
                foreach (Light light in GetComponentsInChildren<Light>(true))
                {
                    if (!light.enabled) continue;
                    if (light.type == LightType.Point && light.name.Contains("Candle"))
                        candles.Add(light);
                    else if (light.type == LightType.Spot && light.name.Contains("MoonShaft"))
                        shafts.Add(light);
                }

                if (candleLights == null || candleLights.Length == 0)
                    candleLights = candles.ToArray();
                if (moonShafts == null || moonShafts.Length == 0)
                    moonShafts = shafts.ToArray();
            }

            if (ritualEmissiveRenderers == null || ritualEmissiveRenderers.Length == 0)
            {
                var ritual = new List<Renderer>();
                foreach (Renderer renderer in GetComponentsInChildren<Renderer>(true))
                {
                    string name = renderer.name;
                    if (name.StartsWith("Ritual_Plate_") || name.StartsWith("Ritual_Rune_") ||
                        name.StartsWith("Ritual_Center_") || name.StartsWith("RitualMarking_") ||
                        name.StartsWith("RitualRuneInner_") || name.StartsWith("RitualCircle_"))
                        ritual.Add(renderer);
                }
                ritualEmissiveRenderers = ritual.ToArray();
            }

            candleBaseIntensities = CaptureIntensities(candleLights);
            shaftBaseIntensities = CaptureIntensities(moonShafts);
            ritualBaseEmissions = new Color[ritualEmissiveRenderers.Length];
            for (int i = 0; i < ritualEmissiveRenderers.Length; i++)
            {
                Renderer renderer = ritualEmissiveRenderers[i];
                if (renderer == null) continue;
                foreach (Material material in renderer.sharedMaterials)
                {
                    if (material != null && material.IsKeywordEnabled("_EMISSION") &&
                        material.HasProperty("_EmissionColor"))
                    {
                        ritualBaseEmissions[i] = material.GetColor("_EmissionColor");
                        break;
                    }
                }
            }
            propertyBlock = new MaterialPropertyBlock();
        }

        private static float[] CaptureIntensities(Light[] lights)
        {
            float[] result = new float[lights.Length];
            for (int i = 0; i < lights.Length; i++)
                if (lights[i] != null) result[i] = lights[i].intensity;
            return result;
        }

        private void Update()
        {
            float t = Time.time;
            for (int i = 0; i < candleLights.Length; i++)
            {
                Light light = candleLights[i];
                if (light == null || !light.enabled) continue;
                float phase = i * 1.73f;
                float flicker = 0.65f * Mathf.Sin(t * candleFlickerSpeed + phase) +
                                0.35f * Mathf.Sin(t * candleFlickerSpeed * 2.31f + phase * 1.41f);
                light.intensity = candleBaseIntensities[i] *
                                  Mathf.Max(0.75f, 1f + flicker * candleFlickerAmplitude);
            }

            // A few percent of slow movement in the window light, not a flashing key.
            for (int i = 0; i < moonShafts.Length; i++)
            {
                Light light = moonShafts[i];
                if (light == null || !light.enabled) continue;
                light.intensity = shaftBaseIntensities[i] *
                                  (1f + shaftBreathing * Mathf.Sin(t * 0.23f + i * 0.61f));
            }

            if (propertyBlock == null) return;
            float pulse = 1f + ritualPulseStrength * Mathf.Sin(t * ritualPulseSpeed);
            for (int i = 0; i < ritualEmissiveRenderers.Length; i++)
            {
                Renderer renderer = ritualEmissiveRenderers[i];
                if (renderer == null) continue;
                renderer.GetPropertyBlock(propertyBlock);
                propertyBlock.SetColor("_EmissionColor", ritualBaseEmissions[i] * pulse);
                renderer.SetPropertyBlock(propertyBlock);
            }
        }

        private void OnDisable()
        {
            // Do not leave modified intensity/property blocks behind when exiting Play.
            if (candleBaseIntensities != null)
                for (int i = 0; i < candleLights.Length; i++)
                    if (candleLights[i] != null) candleLights[i].intensity = candleBaseIntensities[i];
            if (shaftBaseIntensities != null)
                for (int i = 0; i < moonShafts.Length; i++)
                    if (moonShafts[i] != null) moonShafts[i].intensity = shaftBaseIntensities[i];
            if (ritualBaseEmissions == null || propertyBlock == null) return;
            for (int i = 0; i < ritualEmissiveRenderers.Length; i++)
            {
                Renderer renderer = ritualEmissiveRenderers[i];
                if (renderer == null) continue;
                renderer.GetPropertyBlock(propertyBlock);
                propertyBlock.SetColor("_EmissionColor", ritualBaseEmissions[i]);
                renderer.SetPropertyBlock(propertyBlock);
            }
        }
    }
}
