using UnityEngine;
using Vespershade.Core;
using Vespershade.Data;
using Vespershade.GameInput;

namespace Vespershade.Gameplay
{
    /// <summary>
    /// Foundation third person player controller built on CharacterController:
    /// camera relative movement, sprint, jump, gravity and turn-toward-motion.
    /// Exposes state (IsGrounded, IsSprinting, SpeedRatio) that a future
    /// animation layer can consume without changing this component.
    /// </summary>
    [RequireComponent(typeof(CharacterController))]
    public class PlayerController : MonoBehaviour
    {
        // Fallback tuning used when no GameSettingsSO is assigned (or a value is 0).
        private const float DefaultWalkSpeed = 3.2f;
        private const float DefaultRunSpeed = 6.6f;
        private const float DefaultAcceleration = 30f;
        private const float DefaultDeceleration = 40f;
        private const float DefaultRotationSpeed = 720f;
        private const float DefaultGravity = -22f;
        private const float DefaultJumpHeight = 1.1f;
        private const float DefaultAirControl = 0.35f;
        private const float MaxFallSpeed = -40f;
        private const float GroundStickSpeed = -2f;
        private const float MinInputMagnitude = 0.01f;

        [Header("Data")]
        [Tooltip("Optional tuning asset. When assigned, its values win over the built-in defaults.")]
        [SerializeField] private GameSettingsSO settings;

        [Header("References")]
        [Tooltip("Point the camera focuses on (e.g. a chest bone). Falls back to this transform when empty.")]
        [SerializeField] private Transform cameraFocus;

        private CharacterController character;
        private Vector3 horizontalVelocity;
        private float verticalVelocity;

        public bool IsGrounded { get; private set; }
        public bool IsSprinting { get; private set; }

        /// <summary>Full velocity including the vertical component.</summary>
        public Vector3 Velocity => horizontalVelocity + Vector3.up * verticalVelocity;

        /// <summary>Point the camera should orbit around.</summary>
        public Transform CameraFocus => cameraFocus != null ? cameraFocus : transform;

        /// <summary>0..1 blend of current speed relative to run speed. Useful for future animation blending.</summary>
        public float SpeedRatio => Mathf.Clamp01(horizontalVelocity.magnitude / Mathf.Max(0.001f, RunSpeed));

        private float WalkSpeed => Resolve(settings != null ? settings.walkSpeed : 0f, DefaultWalkSpeed);
        private float RunSpeed => Resolve(settings != null ? settings.runSpeed : 0f, DefaultRunSpeed);
        private float Acceleration => Resolve(settings != null ? settings.acceleration : 0f, DefaultAcceleration);
        private float Deceleration => Resolve(settings != null ? settings.deceleration : 0f, DefaultDeceleration);
        private float RotationSpeed => Resolve(settings != null ? settings.rotationSpeed : 0f, DefaultRotationSpeed);
        private float Gravity => Resolve(settings != null ? settings.gravity : 0f, DefaultGravity);
        private float JumpHeight => Resolve(settings != null ? settings.jumpHeight : 0f, DefaultJumpHeight);
        private float AirControl => Resolve(settings != null ? settings.airControl : 0f, DefaultAirControl);

        private static float Resolve(float primary, float fallback)
        {
            return Mathf.Abs(primary) > 1e-5f ? primary : fallback;
        }

        private void Awake()
        {
            character = GetComponent<CharacterController>();
        }

        private void Update()
        {
            GameManager game = GameManager.Instance;
            if (game != null && game.IsPaused)
            {
                return;
            }

            float deltaTime = Time.deltaTime;
            CoreInput input = CoreInput.Instance;

            Vector2 moveAxis = input != null ? input.MoveAxis : Vector2.zero;
            bool sprintHeld = input != null && input.SprintHeld;
            bool jumpPressed = input != null && input.JumpPressed;

            Vector3 wishDirection = ComputeWishDirection(moveAxis);
            float axisMagnitude = Mathf.Clamp01(moveAxis.magnitude);

            IsSprinting = sprintHeld && axisMagnitude > 0.5f;

            float targetSpeed = (IsSprinting ? RunSpeed : WalkSpeed) * axisMagnitude;
            Vector3 targetVelocity = wishDirection * targetSpeed;

            bool slowingDown = targetVelocity.magnitude < horizontalVelocity.magnitude;
            float acceleration = slowingDown ? Deceleration : Acceleration;
            if (!character.isGrounded)
            {
                acceleration *= AirControl;
            }
            horizontalVelocity = Vector3.MoveTowards(horizontalVelocity, targetVelocity, acceleration * deltaTime);

            UpdateVerticalVelocity(jumpPressed && character.isGrounded, deltaTime);

            character.Move((horizontalVelocity + Vector3.up * verticalVelocity) * deltaTime);
            IsGrounded = character.isGrounded;

            UpdateFacing(wishDirection, deltaTime);
        }

        /// <summary>Translates 2D input into a world space direction relative to the active camera.</summary>
        private Vector3 ComputeWishDirection(Vector2 moveAxis)
        {
            if (moveAxis.sqrMagnitude <= MinInputMagnitude * MinInputMagnitude)
            {
                return Vector3.zero;
            }

            Transform reference = Camera.main != null ? Camera.main.transform : transform;

            Vector3 forward = reference.forward;
            Vector3 right = reference.right;
            forward.y = 0f;
            right.y = 0f;
            forward.Normalize();
            right.Normalize();

            Vector3 direction = forward * moveAxis.y + right * moveAxis.x;
            return direction.sqrMagnitude > 1e-6f ? direction.normalized : Vector3.zero;
        }

        private void UpdateVerticalVelocity(bool jumpRequested, float deltaTime)
        {
            float gravity = Gravity;

            if (character.isGrounded)
            {
                if (jumpRequested)
                {
                    // v = sqrt(2 * g * h)
                    verticalVelocity = Mathf.Sqrt(2f * Mathf.Abs(gravity) * JumpHeight);
                }
                else
                {
                    // Small downward speed keeps the controller snapped to slopes and stairs.
                    verticalVelocity = GroundStickSpeed;
                }
                return;
            }

            verticalVelocity += gravity * deltaTime;
            if (verticalVelocity < MaxFallSpeed)
            {
                verticalVelocity = MaxFallSpeed;
            }
        }

        private void UpdateFacing(Vector3 wishDirection, float deltaTime)
        {
            if (wishDirection.sqrMagnitude <= 1e-6f)
            {
                return;
            }

            float targetYaw = Mathf.Atan2(wishDirection.x, wishDirection.z) * Mathf.Rad2Deg;
            float yaw = Mathf.MoveTowardsAngle(transform.eulerAngles.y, targetYaw, RotationSpeed * deltaTime);
            transform.rotation = Quaternion.Euler(0f, yaw, 0f);
        }
    }
}
