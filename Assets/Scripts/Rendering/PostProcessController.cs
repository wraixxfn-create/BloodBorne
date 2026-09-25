using UnityEngine;

namespace Vespershade.Rendering
{
    /// <summary>
    /// Dependency free post processing foundation for the built-in render pipeline.
    /// Runs a single fullscreen pass (vignette + saturation/contrast/tint grading +
    /// animated film grain) driven by the Hidden/Vespershade/PostGrade shader.
    /// Values here are the starting "oppressive dark fantasy" grade; extend this
    /// component or swap it for a URP Volume chain if the project moves to URP.
    /// </summary>
    [ExecuteAlways]
    [RequireComponent(typeof(Camera))]
    public class PostProcessController : MonoBehaviour
    {
        private const string FallbackShaderName = "Hidden/Vespershade/PostGrade";

        [Header("Shader")]
        [Tooltip("The grade shader. Falls back to Shader.Find when left empty.")]
        [SerializeField] private Shader gradeShader;

        [Header("Vignette")]
        [Range(0f, 1f)]
        [SerializeField] private float vignetteIntensity = 0.45f;

        [Range(0f, 1f)]
        [SerializeField] private float vignetteRadius = 0.58f;

        [Range(0.01f, 1f)]
        [SerializeField] private float vignetteSoftness = 0.42f;

        [SerializeField] private Color vignetteColor = new Color(0.01f, 0.01f, 0.02f, 1f);

        [Header("Grading")]
        [Range(0f, 2f)]
        [SerializeField] private float saturation = 0.9f;

        [Range(0.5f, 1.5f)]
        [SerializeField] private float contrast = 1.06f;

        [Tooltip("Multiplicative color tint. Slightly cool values read as moonlight.")]
        [SerializeField] private Color tint = new Color(0.96f, 0.97f, 1f, 1f);

        [Header("Film Grain")]
        [Range(0f, 0.3f)]
        [SerializeField] private float grainIntensity = 0.05f;

        [SerializeField] private float grainSpeed = 24f;

        [Header("Master")]
        [Tooltip("Bypass the whole effect when false.")]
        [SerializeField] private bool postProcessingEnabled = true;

        private Material material;

        private void OnRenderImage(RenderTexture source, RenderTexture destination)
        {
            if (!postProcessingEnabled)
            {
                Graphics.Blit(source, destination);
                return;
            }

            Material mat = GetMaterial();
            if (mat == null)
            {
                Graphics.Blit(source, destination);
                return;
            }

            mat.SetFloat("_VignetteIntensity", vignetteIntensity);
            mat.SetFloat("_VignetteRadius", vignetteRadius);
            mat.SetFloat("_VignetteSoftness", vignetteSoftness);
            mat.SetColor("_VignetteColor", vignetteColor);
            mat.SetFloat("_Saturation", saturation);
            mat.SetFloat("_Contrast", contrast);
            mat.SetColor("_Tint", tint);
            mat.SetFloat("_GrainIntensity", grainIntensity);
            mat.SetFloat("_GrainSpeed", grainSpeed);
            mat.SetFloat("_GrainTime", Time.unscaledTime);

            Graphics.Blit(source, destination, mat);
        }

        private Material GetMaterial()
        {
            if (material != null)
            {
                return material;
            }

            Shader shader = gradeShader != null ? gradeShader : Shader.Find(FallbackShaderName);
            if (shader == null)
            {
                Debug.LogError("[PostProcess] Grade shader is missing. The post foundation runs in bypass mode.");
                return null;
            }

            material = new Material(shader)
            {
                hideFlags = HideFlags.DontSave
            };
            return material;
        }

        private void OnDisable()
        {
            ReleaseMaterial();
        }

        private void OnDestroy()
        {
            ReleaseMaterial();
        }

        private void ReleaseMaterial()
        {
            if (material == null)
            {
                return;
            }

            if (Application.isPlaying)
            {
                Destroy(material);
            }
            else
            {
                DestroyImmediate(material);
            }

            material = null;
        }
    }
}
