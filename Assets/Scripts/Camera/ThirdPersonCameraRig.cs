using UnityEngine;
using Vespershade.Data;
using Vespershade.GameInput;

namespace Vespershade.Cameras
{
    /// <summary>
    /// Existing third-person orbit/follow rig. Owns persistent orbit angles,
    /// smooths the pivot and angles, then collision-constrains the final position.
    /// </summary>
    [DisallowMultipleComponent]
    [RequireComponent(typeof(Camera))]
    public class ThirdPersonCameraRig : MonoBehaviour
    {
        private const float DefaultPivotHeight = 1.5f;
        private const float DefaultDistance = 4.5f;
        private const float DefaultMinDistance = 1.8f;
        private const float DefaultMaxDistance = 8f;
        private const float DefaultPitchMin = -20f;
        private const float DefaultPitchMax = 65f;
        private const float DefaultSensitivity = 0.18f;
        private const float DefaultSmoothing = 12f;
        private const float DefaultStickTurnSpeed = 240f;
        private const int DefaultObstructionLayers = 1 << 10; // Environment; excludes Player.
        private const float MinimumCollisionRadius = 0.25f;
        private const float CollisionPadding = 0.05f;
        private const float InitialPitch = 15f;

        public static ThirdPersonCameraRig Instance { get; private set; }

        [Header("Data")]
        [Tooltip("Optional tuning asset; otherwise the built-in defaults are used.")]
        [SerializeField] private GameSettingsSO settings;

        [Header("Target")]
        [Tooltip("Transform the camera orbits around. Assigned at runtime by GameBootstrap.")]
        [SerializeField] private Transform target;

        private Camera attachedCamera;
        private float yaw;
        private float pitch;
        private float smoothedYaw;
        private float smoothedPitch;
        private float currentDistance;
        private Vector3 smoothedPivot;
        private bool targetInitialized;

        public float Yaw => yaw;
        public float Pitch => pitch;
        public Transform Target => target;

        private float PivotHeight => settings != null ? settings.cameraPivotHeight : DefaultPivotHeight;
        private float MinDistanceSetting => Mathf.Max(0f, settings != null ? settings.cameraMinDistance : DefaultMinDistance);
        private float MaxDistanceSetting => Mathf.Max(MinDistanceSetting, settings != null ? settings.cameraMaxDistance : DefaultMaxDistance);
        private float Distance => Mathf.Clamp(settings != null ? settings.cameraDistance : DefaultDistance, MinDistanceSetting, MaxDistanceSetting);
        // Even misconfigured assets must not let the orbit flip over a pole. Zero is valid tuning.
        private float PitchMin => Mathf.Clamp(settings != null ? settings.cameraPitchMin : DefaultPitchMin, -89f, 89f);
        private float PitchMax => Mathf.Clamp(settings != null ? settings.cameraPitchMax : DefaultPitchMax, PitchMin, 89f);
        private float LookSensitivity => Mathf.Max(0f, settings != null ? settings.lookSensitivity : DefaultSensitivity);
        private bool InvertY => settings != null && settings.invertY;
        private float Smoothing => Mathf.Max(0.01f, settings != null ? settings.cameraSmoothing : DefaultSmoothing);
        private float StickTurnSpeed => Mathf.Max(0f, settings != null ? settings.stickTurnSpeed : DefaultStickTurnSpeed);
        private int ObstructionLayers => settings != null && settings.cameraObstructionLayers.value != 0
            ? settings.cameraObstructionLayers.value : DefaultObstructionLayers;

        // Enclose the near clip plane, not just the camera's point position.
        private float CollisionRadius
        {
            get
            {
                float near = attachedCamera.nearClipPlane;
                float halfHeight = near * Mathf.Tan(attachedCamera.fieldOfView * 0.5f * Mathf.Deg2Rad);
                float halfWidth = halfHeight * attachedCamera.aspect;
                return Mathf.Max(MinimumCollisionRadius,
                    Mathf.Sqrt(near * near + halfHeight * halfHeight + halfWidth * halfWidth));
            }
        }

        private void Awake()
        {
            if (Instance != null && Instance != this)
            {
                Debug.LogWarning("[ThirdPersonCameraRig] Duplicate rig destroyed.");
                Destroy(gameObject);
                return;
            }

            Instance = this;
            attachedCamera = GetComponent<Camera>();
            yaw = smoothedYaw = transform.eulerAngles.y;
            pitch = smoothedPitch = Mathf.Clamp(InitialPitch, PitchMin, PitchMax);
            if (target != null)
            {
                SetTarget(target);
            }
        }

        private void OnDestroy()
        {
            if (Instance == this)
            {
                Instance = null;
            }
        }

        /// <summary>Repeated bootstrap binding must not reset the user's orbit.</summary>
        public void SetTarget(Transform newTarget)
        {
            if (target == newTarget && targetInitialized)
            {
                return;
            }

            target = newTarget;
            targetInitialized = target != null;
            if (!targetInitialized)
            {
                return;
            }

            smoothedPivot = ComputePivot();
            smoothedYaw = yaw;
            smoothedPitch = pitch;
            Quaternion rotation = Quaternion.Euler(smoothedPitch, smoothedYaw, 0f);
            Vector3 backward = rotation * Vector3.back;
            currentDistance = ComputeCollisionDistance(smoothedPivot, backward, Distance);
            transform.SetPositionAndRotation(smoothedPivot + backward * currentDistance, rotation);
        }

        private void LateUpdate()
        {
            UpdateCamera(Time.deltaTime, Cursor.lockState == CursorLockMode.Locked);
        }

        private void UpdateCamera(float deltaTime, bool acceptLook)
        {
            // Do not accumulate hidden mouse rotation during pause or while using the editor/UI.
            if (target == null || deltaTime <= 0f)
            {
                return;
            }

            if (acceptLook)
            {
                UpdateOrbit(deltaTime);
            }

            float blend = 1f - Mathf.Exp(-Smoothing * deltaTime);
            pitch = Mathf.Clamp(pitch, PitchMin, PitchMax);
            smoothedYaw = Mathf.LerpAngle(smoothedYaw, yaw, blend);
            smoothedPitch = Mathf.Clamp(Mathf.Lerp(smoothedPitch, pitch, blend), PitchMin, PitchMax);

            Vector3 pivot = ComputePivot();
            smoothedPivot = Vector3.Lerp(smoothedPivot, pivot, blend);
            // Pivot lag must not leave the camera looking through a wall the player has rounded.
            Vector3 pivotOffset = smoothedPivot - pivot;
            float pivotLag = pivotOffset.magnitude;
            if (pivotLag > 0.0001f)
            {
                smoothedPivot = pivot + pivotOffset / pivotLag *
                    ComputeCollisionDistance(pivot, pivotOffset / pivotLag, pivotLag);
            }

            Quaternion orbitRotation = Quaternion.Euler(smoothedPitch, smoothedYaw, 0f);
            Vector3 backward = orbitRotation * Vector3.back;
            float safeDistance = ComputeCollisionDistance(smoothedPivot, backward, Distance);
            // Obstructions pull in immediately. Only return to the full orbit is smoothed.
            float distanceBlend = 1f - Mathf.Exp(-Smoothing * 2f * deltaTime);
            currentDistance = safeDistance < currentDistance ? safeDistance :
                Mathf.Lerp(currentDistance, safeDistance, distanceBlend);

            // No position Lerp after the cast: it could interpolate back inside the obstruction.
            transform.SetPositionAndRotation(smoothedPivot + backward * currentDistance, orbitRotation);
        }

        private void UpdateOrbit(float deltaTime)
        {
            CoreInput input = CoreInput.Instance;
            Vector2 look = input.LookDelta; // Look is always read as Vector2.
            // Mouse delta is already pixels/frame; multiplying by deltaTime would be incorrect.
            // A stick expresses deflection, so it needs degrees/second * deltaTime.
            float scale = input.LookIsMouse ? LookSensitivity : StickTurnSpeed * deltaTime;
            yaw = Mathf.Repeat(yaw + look.x * scale, 360f);
            pitch = Mathf.Clamp(pitch + look.y * scale * (InvertY ? 1f : -1f), PitchMin, PitchMax);
        }

        private Vector3 ComputePivot()
        {
            return target.position + Vector3.up * PivotHeight;
        }

        private float ComputeCollisionDistance(Vector3 pivot, Vector3 direction, float desired)
        {
            int layers = ObstructionLayers;
            float radius = CollisionRadius;
            // SphereCast does not report colliders overlapping its starting sphere.
            // Collapse the arm rather than incorrectly treating that path as unobstructed.
            if (Physics.CheckSphere(pivot, radius, layers, QueryTriggerInteraction.Ignore))
            {
                return 0f;
            }

            if (Physics.SphereCast(pivot, radius, direction, out RaycastHit hit, desired,
                layers, QueryTriggerInteraction.Ignore))
            {
                // Never enforce the desired minimum orbit distance through a nearby wall.
                return Mathf.Max(0f, hit.distance - CollisionPadding);
            }

            return desired;
        }
    }
}
