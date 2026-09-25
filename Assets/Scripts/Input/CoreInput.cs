using UnityEngine;
using UnityEngine.InputSystem;

namespace Vespershade.GameInput
{
    /// <summary>
    /// Owns the game's Input System action maps.
    /// Actions are defined in code so the foundation stays dependency free; if
    /// designer-driven rebinding UI is needed later, the maps can be migrated to
    /// a .inputactions asset without changing the public API of this class.
    /// Access through CoreInput.Instance (creates itself lazily if missing).
    /// </summary>
    public sealed class CoreInput : MonoBehaviour
    {
        private static CoreInput s_instance;

        /// <summary>Global access point. Creates a runtime instance when none exists.</summary>
        public static CoreInput Instance
        {
            get
            {
                if (s_instance == null)
                {
                    GameObject owner = new GameObject("[CoreInput]");
                    s_instance = owner.AddComponent<CoreInput>();
                }
                return s_instance;
            }
        }

        /// <summary>The gameplay action map. Enabled while the game runs.</summary>
        public InputActionMap Gameplay { get; private set; }

        public InputAction Move { get; private set; }
        public InputAction Look { get; private set; }
        public InputAction Sprint { get; private set; }
        public InputAction Jump { get; private set; }
        public InputAction Dodge { get; private set; }
        public InputAction Interact { get; private set; }
        public InputAction LightAttack { get; private set; }
        public InputAction HeavyAttack { get; private set; }
        public InputAction Pause { get; private set; }

        private void Awake()
        {
            if (s_instance != null && s_instance != this)
            {
                Destroy(gameObject);
                return;
            }

            s_instance = this;
            DontDestroyOnLoad(gameObject);

            BuildGameplayMap();
            Gameplay.Enable();
        }

        private void OnDestroy()
        {
            if (s_instance != this)
            {
                return;
            }

            if (Gameplay != null)
            {
                Gameplay.Disable();
                Gameplay.Dispose();
                Gameplay = null;
            }

            s_instance = null;
        }

        private void BuildGameplayMap()
        {
            Gameplay = new InputActionMap("Gameplay");

            Move = Gameplay.AddAction("Move", InputActionType.Value, "Vector2");
            Move.AddCompositeBinding("2DVector")
                .With("Up", "<Keyboard>/w")
                .With("Down", "<Keyboard>/s")
                .With("Left", "<Keyboard>/a")
                .With("Right", "<Keyboard>/d");
            Move.AddBinding("<Gamepad>/leftStick", processors: "StickDeadzone");

            Look = Gameplay.AddAction("Look", InputActionType.Value, "Vector2");
            Look.AddBinding("<Mouse>/delta");
            Look.AddBinding("<Gamepad>/rightStick", processors: "StickDeadzone");

            Sprint = Gameplay.AddAction("Sprint", InputActionType.Button);
            Sprint.AddBinding("<Keyboard>/leftShift");
            Sprint.AddBinding("<Gamepad>/leftStickPress");

            Jump = Gameplay.AddAction("Jump", InputActionType.Button);
            Jump.AddBinding("<Keyboard>/space");
            Jump.AddBinding("<Gamepad>/buttonSouth");

            Dodge = Gameplay.AddAction("Dodge", InputActionType.Button);
            Dodge.AddBinding("<Keyboard>/leftCtrl");
            Dodge.AddBinding("<Gamepad>/buttonEast");

            Interact = Gameplay.AddAction("Interact", InputActionType.Button);
            Interact.AddBinding("<Keyboard>/e");
            Interact.AddBinding("<Gamepad>/buttonWest");

            LightAttack = Gameplay.AddAction("LightAttack", InputActionType.Button);
            LightAttack.AddBinding("<Mouse>/leftButton");
            LightAttack.AddBinding("<Gamepad>/rightTrigger");

            HeavyAttack = Gameplay.AddAction("HeavyAttack", InputActionType.Button);
            HeavyAttack.AddBinding("<Mouse>/rightButton");
            HeavyAttack.AddBinding("<Gamepad>/leftTrigger");

            Pause = Gameplay.AddAction("Pause", InputActionType.Button);
            Pause.AddBinding("<Keyboard>/escape");
            Pause.AddBinding("<Gamepad>/start");
        }

        // ------------------------------------------------------------------
        // Convenience accessors used by gameplay code.
        // ------------------------------------------------------------------

        /// <summary>Move stick / WASD as a Vector2 in -1..1 range.</summary>
        public Vector2 MoveAxis => Move != null ? Move.ReadValue<Vector2>() : Vector2.zero;

        /// <summary>Mouse delta (pixels) or right stick this frame.</summary>
        public Vector2 LookDelta => Look != null ? Look.ReadValue<Vector2>() : Vector2.zero;

        public bool SprintHeld => Sprint != null && Sprint.IsPressed();
        public bool JumpPressed => Jump != null && Jump.WasPressedThisFrame();
        public bool DodgePressed => Dodge != null && Dodge.WasPressedThisFrame();
        public bool InteractPressed => Interact != null && Interact.WasPressedThisFrame();
    }
}
