using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Vespershade.Arena
{
    /// <summary>
    /// Small, bounded motes in the window light and a few ash flecks by the
    /// altar. Created only in Play mode; no particle collisions, lights or
    /// screen-space effects. All emitters are destroyed when the rig unloads.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class ArenaAtmosphereParticles : MonoBehaviour
    {
        [Header("Window dust")]
        public Transform[] moteAnchors;
        public Material moteMaterial;
        [Range(0f, 3f)] public float motesPerSecond = 1.15f;

        [Header("Ritual ash")]
        public Transform ritualAshAnchor;
        public Material ashMaterial;
        [Range(0f, 2f)] public float ashPerSecond = 0.55f;

        private readonly List<GameObject> runtimeEmitters = new List<GameObject>();

        private void OnEnable()
        {
            if (!Application.isPlaying) return;
            if (moteAnchors != null && moteMaterial != null)
            {
                foreach (Transform anchor in moteAnchors)
                    if (anchor != null)
                        CreateEmitter(anchor, moteMaterial, "Dust motes", motesPerSecond,
                            new Vector3(2.8f, 2.5f, 2.4f), 24, 0.035f, 0.07f);
            }
            if (ritualAshAnchor != null && ashMaterial != null)
                CreateEmitter(ritualAshAnchor, ashMaterial, "Ritual ash", ashPerSecond,
                    new Vector3(2.5f, 1.5f, 2.5f), 16, 0.025f, 0.055f);
        }

        private void CreateEmitter(Transform anchor, Material material, string label,
            float rate, Vector3 size, int maxParticles, float minSize, float maxSize)
        {
            GameObject go = new GameObject(label + " (runtime)");
            go.transform.SetParent(anchor, false);
            ParticleSystem system = go.AddComponent<ParticleSystem>();
            system.Stop(true, ParticleSystemStopBehavior.StopEmittingAndClear);

            var main = system.main;
            main.playOnAwake = false;
            main.loop = true;
            main.simulationSpace = ParticleSystemSimulationSpace.World;
            main.startLifetime = new ParticleSystem.MinMaxCurve(6f, 11f);
            main.startSize = new ParticleSystem.MinMaxCurve(minSize, maxSize);
            main.startSpeed = new ParticleSystem.MinMaxCurve(0.02f, 0.075f);
            main.startColor = Color.white;
            main.maxParticles = maxParticles;

            var emission = system.emission;
            emission.rateOverTime = new ParticleSystem.MinMaxCurve(rate);

            var shape = system.shape;
            shape.shapeType = ParticleSystemShapeType.Box;
            shape.scale = size;

            // Fade both ends of life instead of letting small bright specks pop.
            var overLife = system.colorOverLifetime;
            overLife.enabled = true;
            var fade = new Gradient();
            fade.SetKeys(new[] {
                new GradientColorKey(Color.white, 0f),
                new GradientColorKey(Color.white, 1f)
            }, new[] {
                new GradientAlphaKey(0f, 0f),
                new GradientAlphaKey(0.65f, 0.22f),
                new GradientAlphaKey(0.65f, 0.8f),
                new GradientAlphaKey(0f, 1f)
            });
            overLife.color = new ParticleSystem.MinMaxGradient(fade);

            ParticleSystemRenderer particleRenderer = system.GetComponent<ParticleSystemRenderer>();
            particleRenderer.renderMode = ParticleSystemRenderMode.Billboard;
            particleRenderer.sharedMaterial = material;
            particleRenderer.shadowCastingMode = ShadowCastingMode.Off;
            particleRenderer.receiveShadows = false;

            runtimeEmitters.Add(go);
            system.Play();
        }

        private void OnDisable()
        {
            foreach (GameObject emitter in runtimeEmitters)
                if (emitter != null) Destroy(emitter);
            runtimeEmitters.Clear();
        }
    }
}
