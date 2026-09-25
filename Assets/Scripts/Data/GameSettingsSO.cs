using UnityEngine;

namespace Vespershade.Data
{
    /// <summary>
    /// Central tuning data for the foundation systems (movement + camera).
    /// Systems read from an instance of this asset so gameplay feel can be
    /// tweaked from the Inspector without touching code.
    /// Default instance lives at Assets/ScriptableObjects/GameSettings.asset.
    /// </summary>
    [CreateAssetMenu(fileName = "GameSettings", menuName = "Vespershade/Core/Game Settings")]
    public class GameSettingsSO : ScriptableObject
    {
        [Header("Player Movement")]
        [Tooltip("Walking speed in meters per second.")]
        public float walkSpeed = 3.2f;

        [Tooltip("Sprinting speed in meters per second.")]
        public float runSpeed = 6.6f;

        [Tooltip("How quickly the player accelerates toward the desired velocity (m/s^2).")]
        public float acceleration = 30f;

        [Tooltip("How quickly the player slows down when input stops (m/s^2).")]
        public float deceleration = 40f;

        [Tooltip("Degrees per second the character turns to face its movement direction.")]
        public float rotationSpeed = 720f;

        [Tooltip("Vertical gravity applied to the player (m/s^2, negative is down).")]
        public float gravity = -22f;

        [Tooltip("Peak height of a jump in meters.")]
        public float jumpHeight = 1.1f;

        [Tooltip("Fraction of ground acceleration available while airborne (0..1).")]
        [Range(0f, 1f)]
        public float airControl = 0.35f;

        [Header("Third Person Camera")]
        [Tooltip("Height of the camera pivot above the player's origin.")]
        public float cameraPivotHeight = 1.5f;

        [Tooltip("Desired distance from pivot to camera in meters.")]
        public float cameraDistance = 4.5f;

        [Tooltip("Closest the camera is allowed to come to the pivot.")]
        public float cameraMinDistance = 1.8f;

        [Tooltip("Farthest the camera is allowed to sit from the pivot.")]
        public float cameraMaxDistance = 8f;

        [Tooltip("Minimum camera pitch in degrees (negative looks up from below).")]
        public float cameraPitchMin = -20f;

        [Tooltip("Maximum camera pitch in degrees.")]
        public float cameraPitchMax = 65f;

        [Tooltip("Degrees of camera rotation per pixel of mouse delta.")]
        public float lookSensitivity = 0.18f;

        [Tooltip("Exponential follow rate. Higher values make the camera snappier.")]
        public float cameraSmoothing = 12f;

        [Tooltip("Gamepad stick turn rate in degrees per second at full tilt.")]
        public float stickTurnSpeed = 240f;

        [Tooltip("Layers that block the camera. Usually Environment.")]
        public LayerMask cameraObstructionLayers = 0;
    }
}
