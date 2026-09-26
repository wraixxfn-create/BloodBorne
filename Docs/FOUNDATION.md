# Vespershade — Foundation Architecture

This document describes the original technical foundation and its conventions.
The default build scene is now the lit MeshKit boss chamber. `Main.unity` remains
a separate movement sandbox; the playable room lighting, masks and zones are
documented in [ARENA_Lighting.md](ARENA_Lighting.md). There is no boss or combat.

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
       GameBootstrap      -> locates the player (or instantiates Player.prefab at
                             SpawnPoint), locates the scene's ThirdPersonCameraRig
                             (or creates one from cameraRigPrefab), then calls
                             ThirdPersonCameraRig.SetTarget(player.CameraFocus) once
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
| `GameBootstrap` | Locates or spawns the player prefab at `SpawnPoint` and makes sure exactly one `ThirdPersonCameraRig` follows it (`cameraRigPrefab` is the fallback used only when the scene has no rig). Locates before creating, so initialization can never produce two players or two cameras. Extend here when more scene assembly is needed. |

### Input (`Scripts/Input`)

`CoreInput` builds one `InputActionMap` ("Gameplay") in code. The project uses
**Input System only** (`activeInputHandler: 1`), not the legacy Input Manager.
There is intentionally no `PlayerInput` component or `.inputactions` asset;
adding another owner would duplicate this existing architecture.

`Move` and `Look` are `Value` / `Vector2` actions, constructed with the named
`expectedControlLayout` argument and read with `ReadValue<Vector2>()`.
Buttons use `IsPressed()` / `WasPressedThisFrame()`, never `ReadValue<bool>()`.
The map follows the owner's enable/disable/dispose lifecycle.

Bindings:

| Action | Keyboard/Mouse | Gamepad |
| --- | --- | --- |
| Move | WASD | Left stick |
| Look | Mouse delta | Right stick |
| Sprint | Left Shift | L3 |
| Jump | Space | South |
| Dodge | Left Ctrl | East |
| Interact | E | West |
| Light Attack (`Attack` alias) | LMB | Right trigger |
| Heavy Attack | RMB | Left trigger |
| LockOn (reserved) | Middle mouse | R3 |
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

- persistent yaw/pitch driven by `Look`; rebinding the same target does not reset the orbit,
- mouse pixels use sensitivity without delta time; the right stick uses degrees/second,
- the active control's device identifies mouse versus stick (never value magnitude),
- configurable invert-Y and pitch limits clamped inside ±89 degrees,
- exponential smoothing for pivot, yaw, pitch and outward distance recovery,
- near-plane-aware sphere casts against **Environment**; immediate inward collision
  correction, including overlap handling and obstruction checks along pivot lag,
- pause/cursor-release gating; click the focused Game view to restore capture,
- tuning comes from `GameSettings.asset`, with defaults when no asset is assigned.

See [INPUT_CAMERA_AUDIT.md](INPUT_CAMERA_AUDIT.md) for test coverage and the
unresolved exception status. No dodge/attack/lock-on gameplay is implemented.

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

`Main.unity` is the original placeholder-plane test scene (cold directional,
flat ambient, exponential fog, near-black background). In **both** chamber
scenes the shared `Arena_LightingRig` replaces the scene directional and groups
entrance, central arena, corners/glass, elevated platform and ritual lights.
It keeps one soft shadow key and a neutral fill restricted to Player (8) and
reserved Enemy (9). See [ARENA_Lighting.md](ARENA_Lighting.md) for the scene
settings, atmosphere impostors, culling masks and performance budget.

## Conventions for the next prompts

- Namespaces: `Vespershade.Core / Data / Events / GameInput / Gameplay /
  Cameras / Rendering`. Add new ones per feature (e.g. `Vespershade.Combat`).
- New tuning knobs go into `GameSettingsSO` (or a new dedicated SO) — not
  into magic numbers.
- New scene-assembly steps go into `GameBootstrap` or a new manager derived
  from `SingletonBehaviour<T>`.
- Cross-system signals go through `GameEventChannelSO` assets, not direct
  lookups. One-time scene assembly is the exception: `GameBootstrap` locates the
  player and the camera rig before it creates anything, so it never duplicates
  what the scene already contains.
- Prefab references always use the prefab asset handle: `m_SourcePrefab:
  {fileID: 100100000, guid: <prefab guid>, type: 3}` in a `PrefabInstance`, and
  `{fileID: 100100000, guid: <prefab guid>, type: 3}` for a prefab assigned to a
  component field. An id that only exists *inside* the prefab (its root
  GameObject, a child, a component) does not resolve for those fields — Unity
  then reports `Missing Prefab with guid: <guid>` and the instance is lost.
  `Tools/validate_unity_project.py` rejects that form.
- Keep placeholder visuals as primitives until real original art exists.

## Tooling (`Tools/`)

- `generate_unity_guids.py` — deterministic GUID (uuid5 of the asset path) +
  .meta generation. Idempotent; run after adding hand-authored Unity files.
- `validate_unity_project.py` — project integrity checks (meta coverage, GUID
  uniqueness, YAML structure, reference resolution, MonoBehaviour field
  matching, build settings, manifest).
- `csharp_smoke_check.py` — delimiter balance + cross-file API symbol checks
  (substitute for a compiler in this sandbox).
- `generate_arena_lighting.py`, `generate_arena_master.py`,
  `generate_arena_scene.py`, `tune_legacy_arena_lighting.py` — deterministic
  scene lighting assets and both playable chamber variants.
- `verify_arena_lighting.py` — zone/reference checks, shadows, fog, floor
  heights, camera grade, light count and future-subject culling mask (PyYAML).
