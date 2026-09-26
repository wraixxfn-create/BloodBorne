# Input / camera repair audit

## Follow-up investigation (2026-09-26)

See [INVALID_CAST_INVESTIGATION.md](INVALID_CAST_INVESTIGATION.md) for the new
whole-project type audit. It found and repaired six bootstrap GameObject fields
that referenced prefab asset handles instead of prefab root GameObjects. This is
a concrete data defect but **not a runtime-verified cause of the exception**.
Unity remains unavailable; no Play Mode success is claimed.

## Status and evidence limits

- **Camera:** independently verified source defects repaired in the existing rig;
  runtime behaviour **not confirmed**. This workspace has no Unity Editor.
- **Input:** Unity Input System 1.7.0, one code-defined `Gameplay` map owned by
  `CoreInput`. `Look` is `InputActionType.Value` with `expectedControlType = Vector2`,
  bound to `<Mouse>/delta` and `<Gamepad>/rightStick`, read with
  `Look.ReadValue<Vector2>()` in `CoreInput.LookDelta`.
- **Exception:** **root cause unconfirmed because no stack trace was available**.
  The reported `InvalidCastException` remains an unresolved investigation item.
  It has neither been reproduced nor confirmed fixed. Its throwing script/method/
  line, cast variable, expected type and actual runtime type are **unknown**.
- No exceptions were caught, suppressed or filtered; no error handling or offending
  script was removed. No noisy runtime logging was added.
- No enemies, weapons, levels, missions, combat, dodge or lock-on gameplay added.

## Systematic source audit

| Area | Finding / action |
| --- | --- |
| Project configuration | Previously `activeInputHandler: 2` (Both). Package manifest installs Input System 1.7.0. No legacy `UnityEngine.Input` calls found in runtime scripts. Changed to `1` (Input System only). Unity may request an Editor restart. |
| Player Input component | No `PlayerInput` component is used. Input ownership is intentionally the existing `CoreInput` singleton; a second dispatcher was not added. |
| Input Actions asset | No `.inputactions` asset exists. `BuildGameplayMap()` is the authoritative definition. Retained instead of migrating/replacing it. |
| Move / Look declaration | Both used the third positional `AddAction` argument as though it were a control layout. That argument is actually a binding path. Corrected to the named `expectedControlLayout: "Vector2"` argument. |
| Move / Look reads | Already `ReadValue<Vector2>()`; retained. No `object` unboxing, Vector2/float conversion, `CallbackContext` cast or `InputActionReference` cast exists in this path. |
| Buttons | Use `InputActionType.Button` and explicit Button control metadata. Consumers use `IsPressed()` / `WasPressedThisFrame()`, not bool/float reinterpretation. Trigger bindings are handled by the action's button API. |
| Attack / LockOn contract | `Attack` aliases existing `LightAttack`; original name and bindings retained. Reserved `LockOn` action has middle mouse / R3 bindings. Neither creates gameplay behaviour. |
| Map lifecycle | Built in Awake; enabled/disabled with the owning component; disabled and disposed on destruction. Duplicate guard retained. |
| Gamepad processing | Removed duplicate binding-level StickDeadzone processors; built-in gamepad stick controls already apply a stick deadzone. |
| `PlayerController` | Audited Update, ComputeWishDirection, UpdateVerticalVelocity and UpdateFacing. Move is Vector2, world movement is constructed as Vector3, rotation as Quaternion. Camera.main forward/right are projected onto the ground plane. No incorrect casts found; movement code unchanged. Sprint and jump exist. Dodge and attack have no gameplay consumers. |
| `GameBootstrap` | Typed prefab `GetComponent<PlayerController>()` / `GetComponent<ThirdPersonCameraRig>()`, followed by null validation. Camera target is bound during startup, including a repeated bind during spawn. Error messages retained. |
| `GameManager` | Pause uses the button API and time scale. Added focused Game-view cursor recapture on the existing primary attack input when not paused. No attack mechanic added. |
| `ThirdPersonCameraRig` | Repaired device identification, vertical sign, orbit persistence, smoothing and collision order (details below). Vector2 is read directly; Quaternion is constructed, not cast from input. |
| `GameSettingsSO` / asset | Fields are strongly typed float/bool/LayerMask; references are serialized as the matching ScriptableObject. Added `invertY`; asset default is false. Zero camera pitch/sensitivity values are now valid rather than replaced with fallback tuning. |
| Other casts | `SingletonBehaviour<T>.Awake()` has `(T)this` at line 29. Both subclasses use the matching self type (`GameManager`, `SceneFlowManager`). No source evidence of a mismatch was found; the cast was not blindly changed or blamed for the exception. Event channel/listener references are also strongly typed. |
| Prefab/scene references | Player is on layer 8, camera is tagged MainCamera, world obstruction mask is Environment (10). Structural reference validation passed. Runtime assembly definition added solely to allow the test assembly to reference production code; script GUIDs remain unchanged. |

### Exact verified declaration defect (not an exception attribution)

Original revision `d76f29e`, `Assets/Scripts/Input/CoreInput.cs`,
`BuildGameplayMap()`, lines **80 and 88**:

```csharp
Gameplay.AddAction("Move", InputActionType.Value, "Vector2");
Gameplay.AddAction("Look", InputActionType.Value, "Vector2");
```

In Input System 1.7.0 the signature is:

```csharp
AddAction(InputActionMap map, string name, InputActionType type,
    string binding, string interactions, string processors,
    string groups, string expectedControlLayout)
```

Verified against the [package's versioned source](https://github.com/Unity-Technologies/InputSystem/blob/1.7.0/Packages/com.unity.inputsystem/InputSystem/Actions/InputActionSetupExtensions.cs).
The string `"Vector2"` was assigned to a binding path and the expected control
layout was left null. This is an API argument error, **not a verified failing
runtime cast**. Current lines **98 and 106** use the named layout argument;
current line **152** reads Look as Vector2.

## Camera repairs

`Assets/Scripts/Camera/ThirdPersonCameraRig.cs` retains the existing component,
serialized target/settings, singleton, `SetTarget` entry point and LateUpdate loop.

- Removed magnitude-based device guessing (original UpdateOrbit lines 169–178).
  Small mouse deltas previously entered the stick path, changing speed and even
  the vertical direction. `CoreInput.LookIsMouse` checks `Look.activeControl.device`.
- Mouse pixels are multiplied only by `lookSensitivity` (degrees/pixel).
  Gamepad deflection uses `stickTurnSpeed * deltaTime`. Both axes use the same
  convention: upward input looks up unless `invertY` is enabled.
- Persistent yaw wraps around 360 degrees; pitch clamps to configured limits,
  themselves bounded within −89 to +89 degrees to prevent pole flips.
- Exponential angle smoothing replaces indirect rotation via a position Lerp.
  Pivot follow is smoothed; repeated binding to the same target is idempotent.
- No look is accumulated at zero time scale or while cursor capture is released.
- Collision casts use the smoothed orbit and a radius covering the near clip plane.
  Pivot lag is also checked for obstruction. Triggers are ignored.
- Inward correction is immediate; only outward recovery is smoothed. The old
  second position Lerp after the cast (original LateUpdate line 145) could place
  the camera back inside blocked geometry and has been removed.
- Removed the forced 0.3-metre collision-distance floor, which could push the
  camera through very close walls. Overlap at the pivot collapses the arm instead
  of treating the cast as clear. A pivot physically inside solid world geometry
  cannot provide a guaranteed clear view; this fallback is not player depenetration.

Tune `Assets/ScriptableObjects/GameSettings.asset`: Look Sensitivity, Invert Y,
Camera Pitch Min/Max, Camera Smoothing, Stick Turn Speed and obstruction mask.
No visual grading/lighting/art changes were made.

## Verification performed here

| Check | Result |
| --- | --- |
| C# delimiter / cross-file API smoke check (18 files, including tests) | PASS — not a C# compilation |
| Unity YAML / GUID / reference validation (313 assets, 142 YAML files) | PASS |
| Existing arena lighting verification | PASS — regression check only; no lighting edits |
| `git diff --check` | PASS |
| Unity import / compilation | NOT RUN — Unity Editor unavailable |
| Added Play Mode tests | NOT RUN — Unity Editor unavailable |
| Physical mouse, WASD, sprint and Console inspection | NOT RUN — Unity Editor unavailable |
| Dodge / attack gameplay | NOT IMPLEMENTED in the pre-existing foundation; only bindings can be tested |

### Added regression tests

`Assets/Tests/PlayMode/InputCameraTests.cs` contains 10 tests using virtual
Input System devices. They cover action layouts/lifecycle, independent mouse
axes and delta reset, one-pixel mouse motion at different timesteps, invert-Y,
stick rate, pitch bounds, smoothed yaw, repeated target binding, pause/capture
gating, obstruction pull-in/recovery, initial overlap, trigger exclusion,
WASD/button reads, camera-relative player movement, sprint and follow.
Unexpected Unity errors are not ignored and should fail the tests.

The tests drive the same camera update method with a deterministic timestep and
capture state; they do not demonstrate OS cursor capture or real hardware input.
No test outcomes are claimed until they have run in Unity.

## Required Unity acceptance run (pending)

1. Open with Unity 2022.3.20f1; allow package resolution, compilation and any
   requested restart for Input System-only handling.
2. Open **Window > General > Test Runner > PlayMode > Run All**. Inspect failures
   and Console output; do not treat static validation as a replacement.
3. Open `Assets/Scenes/Arena/Arena_RitualChamber_MeshKit.unity`. Clear the Console,
   turn Collapse off and enter Play Mode. Click the Game view to capture the mouse.
4. Open **Window > Analysis > Input Debugger** and inspect enabled Gameplay actions:
   move the mouse horizontally and vertically and verify Look reads Vector2 values
   with the corresponding x/y changing. Tests inject `(8, 0)` and `(0, -6)` as
   examples, but those are not measurements from a physical mouse.
5. Verify horizontal yaw and vertical pitch at both tiny and large deltas. Release
   the mouse: no snap-back. Sweep pitch to both limits: no flip. Toggle Invert Y
   during Play Mode, then restore false; confirm the vertical direction reverses.
6. Walk using W/A/S/D at several camera headings; hold Shift to sprint. Rotate the
   character independently and verify camera yaw is not reset.
7. Move/orbit beside walls and pillars; verify prompt inward obstruction correction,
   no wall penetration, and smooth outward recovery. Repeat in Main and the legacy
   arena scene. Check low ceilings and doorway corners visually.
8. Pause/resume with Esc. Release Game-view focus and click back to recapture;
   confirm no hidden orbit accumulates while paused or unlocked.
9. Press Left Ctrl, LMB and RMB. Confirm Dodge / LightAttack / HeavyAttack button
   activity in Input Debugger. **No dodge or attack animation/movement/combat is
   expected**, since those mechanics do not exist and were not added.
10. Exit Play Mode and inspect the complete Console for red errors, including
    `InvalidCastException`. Repeat entry/exit to check singleton/action cleanup.

**Acceptance remains pending.** Without this run, camera runtime correctness and
an exception-free Console cannot be confirmed. If `InvalidCastException` appears,
it remains unresolved; these source repairs must not be reported as fixing it.

## Changed files

Runtime/settings:
- `Assets/Scripts/Input/CoreInput.cs`
- `Assets/Scripts/Camera/ThirdPersonCameraRig.cs`
- `Assets/Scripts/Core/GameManager.cs`
- `Assets/Scripts/Data/GameSettingsSO.cs`
- `Assets/ScriptableObjects/GameSettings.asset`
- `ProjectSettings/ProjectSettings.asset`

Tests/tooling/docs:
- `Assets/Scripts/Vespershade.Runtime.asmdef` (+ meta)
- `Assets/Tests/PlayMode/Vespershade.PlayModeTests.asmdef` (+ meta)
- `Assets/Tests/PlayMode/InputCameraTests.cs` (+ file/folder metas)
- `Tools/csharp_smoke_check.py` (includes test sources, avoids mistaking
  `InputSystem.settings` for the game's `settings` variable)
- `README.md`, `Docs/FOUNDATION.md`, `Docs/INPUT_CAMERA_AUDIT.md`
