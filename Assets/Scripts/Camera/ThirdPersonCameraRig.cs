using UnityEngine;
using Vespershade.Data;
using Vespershade.GameInput;

namespace Vespershade.Cameras
{
    /// <summary>
    /// Foundation orbit / follow camera for a third person action game.
    /// Place it on the GameObject that carries the Camera component; it moves
    /// itself each LateUpdate: orbit via Look input, smoothed pivot follow, and a
    /// sphere cast that pulls the camera in when world geometry gets in the way.
    /// </summary>
    [DisallowMultipleComponent]
    [RequireComponent(typeof(Camera))]
    public class ThirdPersonCameraRig : MonoBehaviour
    {
        // Fallback tuning used when no GameSettingsSO is assigned (or a value is 0).
        private const float DefaultPivotHeight = 1.5f;
        private const float DefaultDistance = 4.5f;
        private const float DefaultMinDistance = 1.8f;
        private const float DefaultMaxDistance = 8f;
        private const float DefaultPitchMin = -20f;
        private const float DefaultPitchMax = 65f;
        private const float DefaultSensitivity = 0.18f;
        private const float DefaultSmoothing = 12f;
        private const float DefaultStickTurnSpeed = 240f;
        private const int DefaultObstructionLayers = 1 << 10; // Environment layer.
        private const float CollisionRadius = 0.25f;
        private const float CollisionPadding = 0.05f;
        private const float MinCollisionDistance = 0.3f;
        private const float InitialPitch = 15f;

        // Look values at or below this magnitude are treated as gamepad stick, not mouse delta.
        private const float StickMagnitudeThreshold = 1.5f;

        /// <summary>The active rig in the scene. Assigned in Awake.</summary>
        public static ThirdPersonCameraRig Instance { get; private set; }

        [Header("Data")]
        [Tooltip("Optional tuning asset. When assigned, its values win over the built-in defaults.")]
        [SerializeField] private GameSettingsSO settings;

        [Header("Target")]
        [Tooltip("Transform the camera orbits around. Usually assigned at runtime by GameBootstrap.")]
        [SerializeField] private Transform target;

        private float yaw;
        private float pitch = InitialPitch;
        private float currentDistance;
        private Vector3 smoothedPivot;

        /// <summary>Current orbit yaw in degrees. Useful for camera relative movement systems.</summary>
        public float Yaw => yaw;

        public Transform Target => target;

        private float PivotHeight => Resolve(settings != null ? settings.cameraPivotHeight : 0f, DefaultPivotHeight);
        private float Distance => Mathf.Clamp(Resolve(settings != null ? settings.cameraDistance : 0f, DefaultDistance), MinDistanceSetting, MaxDistanceSetting);
        private float MinDistanceSetting => Resolve(settings != null ? settings.cameraMinDistance : 0f, DefaultMinDistance);
        private float MaxDistanceSetting => Resolve(settings != null ? settings.cameraMaxDistance : 0f, DefaultMaxDistance);
        private float PitchMin => Resolve(settings != null ? settings.cameraPitchMin : 0f, DefaultPitchMin);
        private float PitchMax => Resolve(settings != null ? settings.cameraPitchMax : 0f, DefaultPitchMax);
        private float LookSensitivity => Resolve(settings != null ? settings.lookSensitivity : 0f, DefaultSensitivity);
        private float Smoothing => Resolve(settings != null ? settings.cameraSmoothing : 0f, DefaultSmoothing);
        private float StickTurnSpeed => Resolve(settings != null ? settings.stickTurnSpeed : 0f, DefaultStickTurnSpeed);

        private int ObstructionLayers
        {
            get
            {
                if (settings != null && settings.cameraObstructionLayers.value != 0)
                {
                    return settings.cameraObstructionLayers.value;
                }
                return DefaultObstructionLayers;
            }
        }

        private static float Resolve(float primary, float fallback)
        {
            return Mathf.Abs(primary) > 1e-5f ? primary : fallback;
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
            smoothedPivot = transform.position;
            currentDistance = Distance;
        }

        private void OnDestroy()
        {
            if (Instance == this)
            {
                Instance = null;
            }
        }

        /// <summary>Assigns the orbit target and snaps the camera to a sane starting position.</summary>
        public void SetTarget(Transform newTarget)
        {
            target = newTarget;
            if (target == null)
            {
                return;
            }

            yaw = transform.eulerAngles.y;
            pitch = InitialPitch;
            currentDistance = Distance;
            smoothedPivot = ComputePivot();
            SnapToIdealPosition();
        }

        private void LateUpdate()
        {
            if (target == null)
            {
                return;
            }

            float deltaTime = Time.deltaTime;
            float smoothing = Smoothing;
            float followBlend = 1f - Mathf.Exp(-smoothing * deltaTime);

            UpdateOrbit(deltaTime);

            smoothedPivot = Vector3.Lerp(smoothedPivot, ComputePivot(), followBlend);

            Quaternion orbitRotation = Quaternion.Euler(pitch, yaw, 0f);
            Vector3 backward = orbitRotation * Vector3.back;

            float desiredDistance = ComputeCollisionDistance(smoothedPivot, backward);
            float distanceBlend = 1f - Mathf.Exp(-smoothing * 2f * deltaTime);
            currentDistance = Mathf.Lerp(currentDistance, desiredDistance, distanceBlend);

            Vector3 desiredPosition = smoothedPivot + backward * currentDistance;
            transform.position = Vector3.Lerp(transform.position, desiredPosition, followBlend);

            Vector3 lookVector = smoothedPivot - transform.position;
            if (lookVector.sqrMagnitude > 1e-6f)
            {
                transform.rotation = Quaternion.LookRotation(lookVector, Vector3.up);
            }
        }

        private void UpdateOrbit(float deltaTime)
        {
            CoreInput input = CoreInput.Instance;
            if (input == null || input.Look == null)
            {
                return;
            }

            Vector2 lookDelta = input.LookDelta;
            if (lookDelta.sqrMagnitude <= 1e-8f)
            {
                return;
            }

            Vector2 applied;
            if (lookDelta.magnitude <= StickMagnitudeThreshold)
            {
                // Gamepad stick: values are roughly -1..1, so turn at a fixed rate.
                // Stick up should look up, hence the inverted y relative to mouse.
                applied = new Vector2(lookDelta.x, -lookDelta.y) * StickTurnSpeed * deltaTime;
            }
            else
            {
                // Mouse: values are pixels of delta since the previous frame.
                applied = lookDelta * LookSensitivity;
            }

            yaw += applied.x;
            pitch = Mathf.Clamp(pitch + applied.y, PitchMin, PitchMax);
        }

        private Vector3 ComputePivot()
        {
            return target.position + Vector3.up * PivotHeight;
        }

        private float ComputeCollisionDistance(Vector3 pivot, Vector3 direction)
        {
            float desired = Distance;
            int layers = ObstructionLayers;
            if (layers == 0)
            {
                return desired;
            }

            RaycastHit hit;
            if (Physics.SphereCast(pivot, CollisionRadius, direction, out hit, desired, layers, QueryTriggerInteraction.Ignore))
            {
                return Mathf.Max(hit.distance - CollisionPadding, MinCollisionDistance);
            }

            return desired;
        }

        private void SnapToIdealPosition()
        {
            Vector3 pivot = ComputePivot();
            Quaternion orbitRotation = Quaternion.Euler(pitch, yaw, 0f);
            transform.position = pivot + orbitRotation * Vector3.back * Distance;

            Vector3 lookVector = pivot - transform.position;
            if (lookVector.sqrMagnitude > 1e-6f)
            {
                transform.rotation = Quaternion.LookRotation(lookVector, Vector3.up);
            }
        }
    }
}
