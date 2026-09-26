using System.Collections;
using System.Collections.Generic;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.InputSystem;
using UnityEngine.InputSystem.LowLevel;
using UnityEngine.TestTools;
using Vespershade.Cameras;
using Vespershade.Data;
using Vespershade.GameInput;
using Vespershade.Gameplay;

namespace Vespershade.Tests
{
    /// <summary>
    /// Run in Test Runner > PlayMode, in an empty test scene. Uses virtual devices,
    /// not OS mouse input. Unexpected Unity errors fail tests; none are suppressed.
    /// </summary>
    public class InputCameraTests
    {
        private readonly List<GameObject> objects = new List<GameObject>();
        private readonly List<InputDevice> devices = new List<InputDevice>();
        private CoreInput input;
        private Mouse mouse;
        private Keyboard keyboard;
        private Gamepad gamepad;
        private ThirdPersonCameraRig rig;
        private GameObject target;
        private GameSettingsSO settings;
        private InputSettings.UpdateMode previousUpdateMode;
        private CursorLockMode previousCursorMode;
        private bool previousCursorVisible;

        [SetUp]
        public void SetUp()
        {
            previousUpdateMode = InputSystem.settings.updateMode;
            previousCursorMode = Cursor.lockState;
            previousCursorVisible = Cursor.visible;
            Assert.That(Object.FindObjectOfType<CoreInput>(), Is.Null, "Run in an empty test scene.");
            Assert.That(ThirdPersonCameraRig.Instance, Is.Null);
            InputSystem.settings.updateMode = InputSettings.UpdateMode.ProcessEventsManually;
            mouse = InputSystem.AddDevice<Mouse>();
            devices.Add(mouse);
            keyboard = InputSystem.AddDevice<Keyboard>();
            devices.Add(keyboard);
            gamepad = InputSystem.AddDevice<Gamepad>();
            devices.Add(gamepad);
            input = CoreInput.Instance;
            objects.Add(input.gameObject);
            input.Gameplay.devices = new InputDevice[] { mouse, keyboard, gamepad };

            settings = ScriptableObject.CreateInstance<GameSettingsSO>();
            settings.cameraObstructionLayers = 1 << 10;
            target = CreateObject("Camera target");
            GameObject camera = CreateObject("Test camera");
            camera.tag = "MainCamera";
            camera.AddComponent<Camera>().nearClipPlane = 0.1f;
            rig = camera.AddComponent<ThirdPersonCameraRig>();
            typeof(ThirdPersonCameraRig).GetField("settings", BindingFlags.Instance | BindingFlags.NonPublic)
                .SetValue(rig, settings);
            rig.SetTarget(target.transform);
            InputSystem.Update();
        }

        [TearDown]
        public void TearDown()
        {
            for (int i = objects.Count - 1; i >= 0; i--)
            {
                if (objects[i] != null) Object.DestroyImmediate(objects[i]);
            }
            objects.Clear();
            if (settings != null) Object.DestroyImmediate(settings);
            foreach (InputDevice device in devices) InputSystem.RemoveDevice(device);
            devices.Clear();
            InputSystem.settings.updateMode = previousUpdateMode;
            Cursor.lockState = previousCursorMode;
            Cursor.visible = previousCursorVisible;
        }

        [Test]
        public void ActionLayoutsBindingsAndLifetimeAreCorrect()
        {
            foreach (InputAction action in new[] { input.Move, input.Look })
            {
                Assert.That(action.type, Is.EqualTo(InputActionType.Value));
                Assert.That(action.expectedControlType, Is.EqualTo("Vector2"));
                foreach (InputBinding binding in action.bindings)
                    Assert.That(binding.path, Is.Not.EqualTo("Vector2"), "A layout is not a binding path.");
            }
            foreach (var control in input.Look.controls)
                Assert.That(control.valueType, Is.EqualTo(typeof(Vector2)));
            foreach (InputAction action in new[] { input.Attack, input.HeavyAttack, input.Sprint,
                input.Dodge, input.Interact, input.LockOn, input.Jump, input.Pause })
            {
                Assert.That(action.type, Is.EqualTo(InputActionType.Button));
                Assert.That(action.expectedControlType, Is.EqualTo("Button"));
            }
            Assert.That(input.Attack, Is.SameAs(input.LightAttack));
            input.enabled = false;
            Assert.That(input.Gameplay.enabled, Is.False);
            input.enabled = true;
            Assert.That(input.Gameplay.enabled, Is.True);
        }

        [Test]
        public void MouseDeltaReadsIndependentVectorAxesAndResets()
        {
            MouseDelta(new Vector2(8f, 0f));
            Assert.That(input.LookDelta, Is.EqualTo(new Vector2(8f, 0f)));
            Assert.That(input.LookIsMouse, Is.True);
            MouseDelta(new Vector2(0f, -6f));
            Assert.That(input.LookDelta, Is.EqualTo(new Vector2(0f, -6f)));
            InputSystem.Update(); // delta controls reset on each input update.
            Assert.That(input.LookDelta, Is.EqualTo(Vector2.zero));
        }

        [Test]
        public void SmallMouseMotionUsesPixelSensitivityAndConsistentVerticalSign()
        {
            float initialPitch = rig.Pitch;
            MouseDelta(new Vector2(1f, 1f)); // Previously misclassified as a stick.
            Tick(1f / 30f);
            Assert.That(rig.Yaw, Is.EqualTo(settings.lookSensitivity).Within(0.0001f));
            Assert.That(rig.Pitch, Is.EqualTo(initialPitch - settings.lookSensitivity).Within(0.0001f));
            MouseDelta(new Vector2(1f, 1f));
            Tick(1f / 120f);
            Assert.That(rig.Yaw, Is.EqualTo(2f * settings.lookSensitivity).Within(0.0001f));
            Assert.That(rig.Pitch, Is.EqualTo(initialPitch - 2f * settings.lookSensitivity).Within(0.0001f));
            settings.invertY = true;
            MouseDelta(new Vector2(0f, 1f));
            Tick();
            Assert.That(rig.Pitch, Is.EqualTo(initialPitch - settings.lookSensitivity).Within(0.0001f));
        }

        [Test]
        public void StickUsesDeviceIdentityAndTimeScaledRate()
        {
            InputSystem.QueueStateEvent(gamepad, new GamepadState { rightStick = Vector2.right });
            InputSystem.Update();
            Assert.That(input.LookIsMouse, Is.False);
            Tick(0.1f);
            Assert.That(rig.Yaw, Is.EqualTo(settings.stickTurnSpeed * 0.1f).Within(0.001f));
            Tick(0.2f);
            Assert.That(rig.Yaw, Is.EqualTo(settings.stickTurnSpeed * 0.3f).Within(0.001f));
        }

        [Test]
        public void PitchClampsOrbitSmoothsAndRebindingDoesNotSnapBack()
        {
            MouseDelta(new Vector2(500f, 100000f));
            Tick();
            Assert.That(rig.Yaw, Is.EqualTo(90f).Within(0.001f));
            Assert.That(rig.Pitch, Is.EqualTo(settings.cameraPitchMin));
            Assert.That(Mathf.Abs(Mathf.DeltaAngle(rig.transform.eulerAngles.y, rig.Yaw)), Is.GreaterThan(1f));
            Vector3 before = rig.transform.position;
            rig.SetTarget(target.transform);
            Assert.That(rig.transform.position, Is.EqualTo(before));
            MouseDelta(Vector2.zero);
            for (int i = 0; i < 120; i++) Tick();
            Assert.That(rig.Yaw, Is.EqualTo(90f).Within(0.001f));
            Assert.That(Mathf.Abs(Mathf.DeltaAngle(rig.transform.eulerAngles.y, rig.Yaw)), Is.LessThan(0.01f));
            MouseDelta(new Vector2(0f, -100000f));
            Tick();
            Assert.That(rig.Pitch, Is.EqualTo(settings.cameraPitchMax));
            Assert.That(Vector3.Dot(rig.transform.up, Vector3.up), Is.GreaterThan(0f));
        }

        [Test]
        public void PauseAndReleasedCursorDoNotAccumulateLook()
        {
            MouseDelta(new Vector2(100f, 100f));
            float yaw = rig.Yaw;
            float pitch = rig.Pitch;
            Tick(0f);
            Tick(1f / 60f, false);
            Assert.That(rig.Yaw, Is.EqualTo(yaw));
            Assert.That(rig.Pitch, Is.EqualTo(pitch));
        }

        [Test]
        public void CollisionRetractsImmediatelyAndReturnsSmoothly()
        {
            Vector3 pivot = target.transform.position + Vector3.up * settings.cameraPivotHeight;
            Vector3 backward = -rig.transform.forward;
            GameObject wall = CreateObject("Obstruction", true);
            wall.layer = 10;
            wall.transform.position = pivot + backward * 2f;
            wall.transform.rotation = rig.transform.rotation;
            wall.transform.localScale = new Vector3(8f, 8f, 0.2f);
            Physics.SyncTransforms();
            Tick();
            float blockedDistance = Vector3.Distance(pivot, rig.transform.position);
            Assert.That(blockedDistance, Is.LessThan(1.7f));
            Assert.That(Physics.CheckSphere(rig.transform.position, 0.25f, 1 << 10), Is.False);
            wall.SetActive(false);
            Physics.SyncTransforms();
            Tick();
            float returningDistance = Vector3.Distance(pivot, rig.transform.position);
            Assert.That(returningDistance, Is.GreaterThan(blockedDistance));
            Assert.That(returningDistance, Is.LessThan(settings.cameraDistance));
            for (int i = 0; i < 120; i++) Tick();
            Assert.That(Vector3.Distance(pivot, rig.transform.position),
                Is.EqualTo(settings.cameraDistance).Within(0.01f));
        }

        [Test]
        public void ObstructionAtPivotDoesNotGetMissedAndTriggersDoNotBlock()
        {
            GameObject obstacle = CreateObject("Pivot obstacle", true);
            obstacle.layer = 10;
            obstacle.transform.position = Vector3.up * settings.cameraPivotHeight;
            Physics.SyncTransforms();
            Tick();
            Assert.That(Vector3.Distance(rig.transform.position, obstacle.transform.position), Is.LessThan(0.001f));
            obstacle.GetComponent<Collider>().isTrigger = true;
            Physics.SyncTransforms();
            for (int i = 0; i < 120; i++) Tick();
            Assert.That(Vector3.Distance(rig.transform.position, obstacle.transform.position),
                Is.EqualTo(settings.cameraDistance).Within(0.01f));
        }

        [Test]
        public void WasdAndReservedButtonsReachTheirTypedActions()
        {
            InputSystem.QueueStateEvent(keyboard, new KeyboardState(Key.W, Key.LeftShift, Key.LeftCtrl, Key.E));
            InputSystem.QueueStateEvent(mouse, new MouseState().WithButton(MouseButton.Left).WithButton(MouseButton.Middle));
            InputSystem.Update();
            Assert.That(input.MoveAxis, Is.EqualTo(Vector2.up));
            Assert.That(input.SprintHeld, Is.True);
            Assert.That(input.DodgePressed, Is.True); // Input only; no dodge behaviour exists.
            Assert.That(input.InteractPressed, Is.True);
            Assert.That(input.Attack.WasPressedThisFrame(), Is.True); // Input only; no combat exists.
            Assert.That(input.LockOn.WasPressedThisFrame(), Is.True);
            Key[] keys = { Key.A, Key.S, Key.D };
            Vector2[] expected = { Vector2.left, Vector2.down, Vector2.right };
            for (int i = 0; i < keys.Length; i++)
            {
                InputSystem.QueueStateEvent(keyboard, new KeyboardState(keys[i]));
                InputSystem.Update();
                Assert.That(input.MoveAxis, Is.EqualTo(expected[i]));
            }
            InputSystem.QueueStateEvent(keyboard, new KeyboardState());
            InputSystem.QueueStateEvent(mouse, new MouseState());
            InputSystem.Update();
            Assert.That(input.MoveAxis, Is.EqualTo(Vector2.zero));
            Assert.That(input.SprintHeld, Is.False);
            Assert.That(input.DodgePressed, Is.False);
            Assert.That(input.Attack.IsPressed(), Is.False);
        }

        [UnityTest]
        public IEnumerator PlayerMovesAndSprintsRelativeToCameraAndCameraFollows()
        {
            GameObject floor = CreateObject("Floor", true);
            floor.layer = 10;
            floor.transform.position = Vector3.down * 0.5f;
            floor.transform.localScale = new Vector3(100f, 1f, 100f);
            target.layer = 8;
            CharacterController character = target.AddComponent<CharacterController>();
            character.height = 2f;
            character.center = Vector3.up;
            PlayerController player = target.AddComponent<PlayerController>();
            MouseDelta(new Vector2(500f, 0f));
            Tick();
            MouseDelta(Vector2.zero);
            for (int i = 0; i < 120; i++) Tick(); // Face +X before starting movement.
            Physics.SyncTransforms();
            InputSystem.QueueStateEvent(keyboard, new KeyboardState(Key.W));
            InputSystem.Update();
            Vector3 start = target.transform.position;
            for (float elapsed = 0f; elapsed < 0.5f; elapsed += Time.deltaTime) yield return null;
            Assert.That(target.transform.position.x, Is.GreaterThan(start.x));
            Assert.That(Mathf.Abs(target.transform.position.z - start.z), Is.LessThan(0.1f));
            Assert.That(player.IsSprinting, Is.False);
            InputSystem.QueueStateEvent(keyboard, new KeyboardState(Key.W, Key.LeftShift));
            InputSystem.Update();
            for (float elapsed = 0f; elapsed < 0.5f; elapsed += Time.deltaTime) yield return null;
            Assert.That(player.IsSprinting, Is.True);
            Assert.That(player.Velocity.x, Is.GreaterThan(settings.walkSpeed));
            InputSystem.QueueStateEvent(keyboard, new KeyboardState());
            InputSystem.Update();
            for (float elapsed = 0f; elapsed < 0.5f; elapsed += Time.deltaTime) yield return null;
            for (int i = 0; i < 120; i++) Tick();
            Vector3 pivot = target.transform.position + Vector3.up * settings.cameraPivotHeight;
            Assert.That(Vector3.Distance(rig.transform.position + rig.transform.forward * settings.cameraDistance, pivot),
                Is.LessThan(0.05f));
            LogAssert.NoUnexpectedReceived();
        }

        private GameObject CreateObject(string name, bool cube = false)
        {
            GameObject created = cube ? GameObject.CreatePrimitive(PrimitiveType.Cube) : new GameObject(name);
            created.name = name;
            objects.Add(created);
            return created;
        }

        private void MouseDelta(Vector2 value)
        {
            InputSystem.QueueStateEvent(mouse, new MouseState { delta = value });
            InputSystem.Update();
        }

        private void Tick(float deltaTime = 1f / 60f, bool acceptLook = true)
        {
            // Exercise the exact LateUpdate implementation with a deterministic timestep and
            // capture state, without relying on an OS cursor/window in a batch test runner.
            typeof(ThirdPersonCameraRig).GetMethod("UpdateCamera", BindingFlags.Instance | BindingFlags.NonPublic)
                .Invoke(rig, new object[] { deltaTime, acceptLook });
        }
    }
}
