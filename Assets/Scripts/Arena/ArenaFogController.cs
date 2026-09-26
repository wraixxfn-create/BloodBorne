using System.Collections.Generic;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace Vespershade.Arena
{
    /// <summary>
    /// Thin ground mist plus distance fog. This is deliberately not a full-screen
    /// volumetric effect: the floor, silhouettes and the ritual ring stay clear.
    /// Each fog renderer keeps its authored alpha; property blocks only dim it.
    /// </summary>
    public class ArenaFogController : MonoBehaviour
    {
        [Header("Ground mist (visual only; no colliders)")]
        public Transform[] fogPlanes;

        [Range(0f, 0.5f)]
        public float driftAmplitude = 0.25f;

        [Range(0f, 0.25f)]
        public float opacityBreathing = 0.1f;

        [Header("Distance fog (keep the combat disc readable)")]
        [Range(0f, 0.03f)]
        public float baseFogDensity = 0.01f;

        [Range(0f, 0.005f)]
        [Tooltip("Small GLOBAL breathing variation, not a corner-specific darkness multiplier.")]
        public float extraFogDensity = 0.0015f;

        public Color fogColor = new Color(0.027f, 0.033f, 0.05f, 1f);

        [Header("Timing")]
        public float driftSpeed = 0.11f;
        public float breathingSpeed = 0.19f;

        private Vector3[] baseLocalPositions;
        private Renderer[] fogRenderers;
        private Color[] baseColors;
        private MaterialPropertyBlock propertyBlock;
        private bool previousFogEnabled;
        private FogMode previousFogMode;
        private float previousFogDensity;
        private Color previousFogColor;
        private bool configuredFog;

        private void Awake()
        {
            if (fogPlanes == null || fogPlanes.Length == 0)
            {
                var found = new List<Transform>();
                foreach (Transform tr in GetComponentsInChildren<Transform>(true))
                {
                    if (tr.name.Contains("FogPlane") || tr.name.Contains("Fog_Volume") ||
                        tr.name.Contains("MistVolume"))
                        found.Add(tr);
                }
                fogPlanes = found.ToArray();
            }

            baseLocalPositions = new Vector3[fogPlanes.Length];
            fogRenderers = new Renderer[fogPlanes.Length];
            baseColors = new Color[fogPlanes.Length];
            propertyBlock = new MaterialPropertyBlock();
            for (int i = 0; i < fogPlanes.Length; i++)
            {
                if (fogPlanes[i] == null) continue;
                baseLocalPositions[i] = fogPlanes[i].localPosition;
                fogRenderers[i] = fogPlanes[i].GetComponent<Renderer>();
                Material material = fogRenderers[i] != null ? fogRenderers[i].sharedMaterial : null;
                baseColors[i] = material != null && material.HasProperty("_Color")
                    ? material.GetColor("_Color") : Color.clear;
            }
        }

        private void OnEnable()
        {
            previousFogEnabled = RenderSettings.fog;
            previousFogMode = RenderSettings.fogMode;
            previousFogDensity = RenderSettings.fogDensity;
            previousFogColor = RenderSettings.fogColor;
            configuredFog = true;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.Exponential;
            RenderSettings.fogDensity = baseFogDensity;
            RenderSettings.fogColor = fogColor;
        }

        private void Update()
        {
            float time = Time.time;
            float breath = 0.5f + 0.5f * Mathf.Sin(time * breathingSpeed);
            RenderSettings.fogDensity = Mathf.Max(0f,
                baseFogDensity + extraFogDensity * (breath - 0.5f));

            if (baseLocalPositions == null || propertyBlock == null) return;
            for (int i = 0; i < fogPlanes.Length; i++)
            {
                Transform plane = fogPlanes[i];
                if (plane == null) continue;
                float phase = 1.37f * i;
                plane.localPosition = baseLocalPositions[i] + new Vector3(
                    Mathf.Sin(time * driftSpeed + phase) * driftAmplitude,
                    Mathf.Sin(time * breathingSpeed + phase) * 0.012f,
                    Mathf.Cos(time * driftSpeed * 0.78f + phase) * driftAmplitude * 0.5f);

                Renderer renderer = fogRenderers[i];
                if (renderer == null) continue;
                Color color = baseColors[i];
                color.a *= 1f - opacityBreathing * breath;
                renderer.GetPropertyBlock(propertyBlock);
                propertyBlock.SetColor("_Color", color);
                renderer.SetPropertyBlock(propertyBlock);
            }
        }

        private void OnDisable()
        {
            if (baseLocalPositions != null)
            {
                for (int i = 0; i < fogPlanes.Length; i++)
                {
                    if (fogPlanes[i] != null) fogPlanes[i].localPosition = baseLocalPositions[i];
                    if (fogRenderers[i] == null) continue;
                    fogRenderers[i].GetPropertyBlock(propertyBlock);
                    propertyBlock.SetColor("_Color", baseColors[i]);
                    fogRenderers[i].SetPropertyBlock(propertyBlock);
                }
            }

            // Do not overwrite a newly loaded scene's RenderSettings on unload.
            if (configuredFog && gameObject.scene.isLoaded &&
                SceneManager.GetActiveScene().handle == gameObject.scene.handle)
            {
                RenderSettings.fog = previousFogEnabled;
                RenderSettings.fogMode = previousFogMode;
                RenderSettings.fogDensity = previousFogDensity;
                RenderSettings.fogColor = previousFogColor;
            }
            configuredFog = false;
        }
    }
}
