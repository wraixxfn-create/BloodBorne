# Vespershade — Foundation Architecture

This document describes the technical foundation, its conventions, and the
extension points later prompts are expected to use.

## Guiding principles

1. **Originality first.** Every asset, name and design produced for this
   project must be original. Placeholder art is primitive shapes only.
2. **Data over code.** Tuning values live in ScriptableObjects
   (`Assets/ScriptableObjects/`). Code reads them with safe fallbacks, so a
   missing or partial asset never breaks play mode.
3. **Prefabs over scene objects.** Anything gameplay-relevant (player,
   camera rig) is a prefab. Scenes assemble, they don't author.
4. **Small, boring systems.** Each foundation system does one thing and
   exposes events/getters for the next layer instead of anticipating it.

## Runtime flow of the Main scene

```
Scene load
  └─ Awake: ThirdPersonCameraRig registers its Instance
  └─ Start (order independent):
       GameManager        -> locks cursor, owns pause state
       SceneFlowManager   -> reads SceneFlow.asset
       GameBootstrap      -> instantiates Player.prefab at SpawnPoint,
                             calls ThirdPersonCameraRig.SetTarget(player.CameraFocus)
  └─ Per frame:
       CoreInput          -> polls Input System actions
       PlayerController   -> camera-relative CharacterController movement
       ThirdPersonCameraRig (LateUpdate) -> orbit, smoothing, collision
       PostProcessController (OnRenderImage) -> fullscreen grade
```

## Systems

### Core (`Scripts/Core`)

| Type | Role |
| --- | --- |
| `SingletonBehaviour<T>` | Base for persistent managers (DontDestroyOnLoad, duplicate guard). |
| `GameManager` | Pause state (`SetPaused`, `PauseChanged`), cursor policy, `Settings` access. |
| `SceneFlowManager` | Async scene loads (`LoadScene`, `ReloadCurrentScene`, `LoadProgress`, `SceneLoadStarted/Finished`). |
| `GameBootstrap` | Spawns the player prefab at `SpawnPoint` and wires the camera. Extend here when more scene assembly is needed. |

### Input (`Scripts/Input`)

`CoreInput` builds one `InputActionMap` ("Gameplay") in code:

| Action | Keyboard/Mouse | Gamepad |
| --- | --- | --- |
| Move | WASD | Left stick |
| Look | Mouse delta | Right stick |
| Sprint | Left Shift | L3 |
| Jump | Space | South |
| Dodge | Left Ctrl | East |
| Interact | E | West |
| Light Attack | LMB | Right trigger |
| Heavy Attack | RMB | Left trigger |
| Pause | Esc | Start |

Migration path: if designer rebinding is needed, move the map into a
`.inputactions` asset and load it here — the rest of the codebase only sees
the `CoreInput` accessors (`MoveAxis`, `LookDelta`, `SprintHeld`, ...).

### Player (`Scripts/Player`)

`PlayerController` (CharacterController based):

- camera-relative movement on the horizontal plane,
- acceleration/deceleration with separate air control,
- sprint blend (`IsSprinting`), gravity + jump (`jumpHeight`),
- turn-toward-motion with configurable rotation speed,
- exposes `Velocity`, `SpeedRatio`, `IsGrounded`, `IsSprinting`, `CameraFocus`
  for a future animation/combat layer.

Planned extension: replace the direct movement code with a small state
machine (Locomotion / Airborne / Dodge / Combat) driven by the same input.

### Camera (`Scripts/Camera`)

`ThirdPersonCameraRig` sits on the camera GameObject itself and moves it in
`LateUpdate`:

- yaw/pitch orbit driven by `Look`,
- frame-rate independent exponential smoothing (pivot + distance),
- sphere-cast collision against the **Environment** layer pulls the camera in,
- all values come from `GameSettings.asset` with hard-coded fallbacks.

### Rendering (`Scripts/Rendering` + `Art/Shaders`)

`PostProcessController` runs `Hidden/Vespershade/PostGrade` via
`OnRenderImage`: vignette, saturation/contrast/tint grading, stepped film
grain. Defaults are tuned for a dark, oppressive look. Extend by adding
parameters + shader passes; if the project ever moves to URP, swap this
component for a Volume profile — the tuning values already live in one place.

### Data (`Scripts/Data`)

- `GameSettingsSO` — single global tuning asset (movement + camera).
- `SceneFlowSO` — boot scene + allowed scene name table.

### Events (`Scripts/Events`)

- `GameEventChannelSO` — raise/subscribe event channel asset.
- `GameEventListener` — forwards a channel to a `UnityEvent` for
  designer-facing wiring.

Create channels via **Assets > Create > Vespershade > Events**.

## Scene & layers

| Layer (index) | Name | Used by |
| --- | --- | --- |
| 8 | Player | player prefab |
| 9 | Enemy | reserved |
| 10 | Environment | ground/world; camera obstruction mask |
| 11 | Interactable | reserved |
| 12 | Trigger | reserved |

`Main.unity` lighting: directional key light (cold, 50°/-30°, soft shadows,
intensity 1.1), flat ambient `(0.12, 0.12, 0.16)`, exponential fog
(density 0.02), solid near-black camera background, no skybox.

## Conventions for the next prompts

- Namespaces: `Vespershade.Core / Data / Events / GameInput / Gameplay /
  Cameras / Rendering`. Add new ones per feature (e.g. `Vespershade.Combat`).
- New tuning knobs go into `GameSettingsSO` (or a new dedicated SO) — not
  into magic numbers.
- New scene-assembly steps go into `GameBootstrap` or a new manager derived
  from `SingletonBehaviour<T>`.
- Cross-system signals go through `GameEventChannelSO` assets, not direct
  `FindObjectOfType` lookups.
- Keep placeholder visuals as primitives until real original art exists.

## Tooling (`Tools/`)

- `generate_unity_guids.py` — deterministic GUID (uuid5 of the asset path) +
  .meta generation. Idempotent; run after adding hand-authored Unity files.
- `validate_unity_project.py` — project integrity checks (meta coverage, GUID
  uniqueness, YAML structure, reference resolution, MonoBehaviour field
  matching, build settings, manifest).
- `csharp_smoke_check.py` — delimiter balance + cross-file API symbol checks
  (substitute for a compiler in this sandbox).
