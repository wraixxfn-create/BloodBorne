using UnityEngine;

namespace Vespershade.Arena
{
    /// <summary>
    /// Drives subtle supernatural atmosphere: slow drift and breathing
    /// opacity for ground fog planes, plus exponential fog density
    /// modulation. All motion is low-frequency to avoid distracting
    /// combat readability while selling the cold, abandoned rite.
    /// </summary>
    public class ArenaFogController : MonoBehaviour
    {
        [Header("Ground Fog")]
        [Tooltip("Fog plane transforms that drift slightly (usually the low mist quads).")]
        public Transform[] fogPlanes;

        [Tooltip("Maximum horizontal drift from start position in meters.")]
        public float driftAmplitude = 0.6f;

        [Tooltip("Breathing opacity multiplier for the fog material (modulates _Color.a conceptually via renderer).")]
        public float opacityBreathing = 0.15f;

        [Header("Exponential Fog")]
        [Tooltip("Base exponential fog density (RenderSettings.fogDensity).")]
        [Range(0f, 0.06f)]
        public float baseFogDensity = 0.015f;

        [Tooltip("Additional density when viewed from corners (simulated by vertical breathing).")]
        public float extraFogDensity = 0.006f;

        [Header("Timing")]
        public float driftSpeed = 0.12f;
        public float breathingSpeed = 0.22f;

        private Vector3[] basePositions;
        private float seed;

        private void Awake()
        {
            seed = Random.Range(0f, 100f);
            // Auto-discover fog planes by name if not wired (supports prefab-first workflow).
            if (fogPlanes == null || fogPlanes.Length == 0)
            {
                var found = new System.Collections.Generic.List<Transform>();
                foreach (Transform tr in GetComponentsInChildren<Transform>(true))
                {
                    if (tr.name.Contains("FogPlane") || tr.name.Contains("Mist"))
                        found.Add(tr);
                }
                if (found.Count > 0)
                    fogPlanes = found.ToArray();
            }

            if (fogPlanes != null && fogPlanes.Length > 0)
            {
                basePositions = new Vector3[fogPlanes.Length];
                for (int i = 0; i < fogPlanes.Length; i++)
                    basePositions[i] = fogPlanes[i] != null ? fogPlanes[i].position : Vector3.zero;
            }

            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Exponential;
            RenderSettings.fogDensity = baseFogDensity;
            RenderSettings.fogColor = new Color(0.03f, 0.035f, 0.05f, 1f);
        }

        private void Update()
        {
            float t = Time.time;

            // Drift fog planes in slow figure-eight
            if (fogPlanes != null && basePositions != null)
            {
                for (int i = 0; i < fogPlanes.Length; i++)
                {
                    if (fogPlanes[i] == null) continue;
                    float offset = seed + i * 1.37f;
                    float dx = Mathf.Sin((t * driftSpeed + offset) * 0.9f) * driftAmplitude;
                    float dz = Mathf.Cos((t * driftSpeed + offset) * 0.7f) * driftAmplitude * 0.6f;
                    float dy = Mathf.Sin(t * breathingSpeed + offset) * 0.04f;
                    fogPlanes[i].position = basePositions[i] + new Vector3(dx, dy, dz);
                }
            }

            // Subtle exponential fog breathing - denser in dark corners
            float breath = Mathf.Sin(t * breathingSpeed + seed) * 0.5f + 0.5f;
            RenderSettings.fogDensity = baseFogDensity + extraFogDensity * breath * 0.4f;
        }
    }
}
