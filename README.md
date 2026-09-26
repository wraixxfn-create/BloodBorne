# Vespershade

An **original** third-person dark fantasy action RPG foundation built in Unity.

The project draws its tone from gothic horror, oppressive fantasy and cosmic
mystery — but every name, system, placeholder asset and design decision here
is original. It contains **no** characters, monsters, environments, weapons,
architecture, animations, UI, names, lore, music, dialogue, textures or models
from Bloodborne, Dark Souls, Elden Ring or any other existing game.

This repository is intentionally *only* the technical foundation: a clean,
scalable base that later prompts will build gameplay on.

---

## Requirements

- **Unity 2022.3 LTS** (authored against 2022.3.20f1; any 2022.3.x works)
- Internet connection on first open (Unity resolves packages from the manifest)
- Render pipeline: **Built-in**, linear color space
- Input: **Unity Input System only** (`activeInputHandler: 1`; package 1.7.0)

## Opening & playing

1. In Unity Hub: **Add > Add project from disk**, select this repository root.
2. Open it with Unity 2022.3 LTS and let the initial import finish.
3. Open **`Assets/Scenes/Arena/Arena_RitualChamber_MeshKit.unity`** (build scene 0).
4. Press **Play**. The boss chamber has five lighting zones: a cold moon key,
   warm doorway/candle practicals, dim stained-glass spill, restrained cyan
   ritual accents, ground mist and sparse motes. **There is no boss or combat yet.**

A capsule placeholder spawns at the south doorway, the cursor locks, and you can:

| Input | Action |
| --- | --- |
| `WASD` / left stick | Move (camera relative) |
| Mouse / right stick | Orbit camera |
| `Left Shift` / L3 | Sprint |
| `Space` / A | Jump |
| `Esc` / Start | Pause (freezes time, unlocks cursor) |
| `E`, `Left Ctrl`, mouse buttons, triggers | Reserved input actions (Interact, Dodge, Light/Heavy Attack) — no gameplay implementation yet |
| Middle mouse / R3 | Reserved LockOn input — no lock-on behaviour yet |

Click the focused Game view to recapture the cursor if the Editor releases it.
Camera sensitivity, pitch limits and **Invert Y** are on
`Assets/ScriptableObjects/GameSettings.asset`.

The camera pulls itself in when the environment blocks it. The two arena scene
instances use a softer vignette/grain grade for visibility. For the earlier
primitive chamber open `Assets/Scenes/Arena/Arena_RitualChamber.unity`; for the
original fogged-plane movement sandbox open `Assets/Scenes/Main/Main.unity`.

## Project structure

```
Assets/
  Art/Shaders/        Fullscreen grade + arena haze/glass/particle shaders
  Audio/              Reserved for original audio
  Materials/          Player placeholders + original arena lighting materials
  Models/Arena/       Reusable modular stonework and two tiny VFX meshes
  Animations/         Reserved for original animation content
  Prefabs/Arena/      Both chambers + shared Arena_LightingRig.prefab
  Prefabs/            Player.prefab, MainCameraRig.prefab
  Scenes/Arena/       Playable boss room (MeshKit first in Build Settings)
  Scenes/Main/        Main.unity - separate movement sandbox
  Scripts/
    Core/             GameManager, SceneFlowManager, GameBootstrap, SingletonBehaviour
    Data/             GameSettingsSO, SceneFlowSO
    Events/           GameEventChannelSO, GameEventListener
    Input/            CoreInput (code-defined Input System action maps)
    Player/           PlayerController (CharacterController based)
    Camera/           ThirdPersonCameraRig (orbit/follow + collision)
    Rendering/        PostProcessController (OnRenderImage grade)
  VFX/                Reserved for original effects
  UI/                 Reserved for original UI
  Resources/          Reserved for Resources.Load content
  ScriptableObjects/  GameSettings.asset, SceneFlow.asset
```

## How it is put together

- **ScriptableObject architecture** — tuning data lives in assets
  (`GameSettings.asset`), scene tables in `SceneFlow.asset`; event channels
  (`GameEventChannelSO`) decouple systems. Behaviours consume data, they don't
  own it.
- **Prefabs workflow** — the player and the camera rig are prefabs; the scene
  spawns/references them instead of holding loose GameObjects, so later
  prompts iterate on the prefab, not the scene.
- **Input** — one `CoreInput` component owns a code-defined Input System map
  (`Move, Look, Sprint, Jump, Dodge, Interact, LightAttack, HeavyAttack,
  LockOn, Pause`; `Attack` aliases `LightAttack`) with keyboard+mouse and gamepad bindings.
- **Scene management** — `SceneFlowManager` loads scenes asynchronously with
  progress + events, ready for a future loading screen.
- **Boss-room lighting** — reusable five-zone lighting rig: one controlled
  soft-shadow moon key, steady Player/Enemy-only silhouette fill, dim local
  spots and candles, patterned glass pools, low mist and bounded dust. Built-in
  render pipeline; no volume package, boss or combat component. See
  [Docs/ARENA_Lighting.md](Docs/ARENA_Lighting.md) for zone map and QA notes.
- **Post-processing foundation** — dependency-free single pass
  (vignette, saturation/contrast/tint, animated grain). Arena camera instances
  override the grade gently so shadowed figures remain visible.

See [Docs/FOUNDATION.md](Docs/FOUNDATION.md) for core architecture and
[Docs/ARENA_Lighting.md](Docs/ARENA_Lighting.md) for lighting controls.

## Verification

This project was authored and verified without a Unity editor in the loop.
Tooling in `Tools/` performs the structural checks:

```bash
python3 Tools/generate_unity_guids.py  # deterministic GUIDs + .meta files
python3 Tools/validate_unity_project.py # YAML integrity + references (needs PyYAML)
python3 Tools/audit_serialized_types.py # object-reference type checks (needs PyYAML)
python3 Tools/test_serialized_types.py  # offline auditor regression tests (needs PyYAML)
python3 Tools/csharp_smoke_check.py     # delimiter balance + API symbols
python3 Tools/verify_arena_lighting.py  # zones, budgets, heights, scene wiring (needs PyYAML)
```

All checks pass in the authoring environment. There is no Unity editor here,
so visual/play-mode QA should be done on first open. Unity may re-serialize a
few files and download the packages in `Packages/manifest.json`.

### Input/camera repair verification

See [Docs/INPUT_CAMERA_AUDIT.md](Docs/INPUT_CAMERA_AUDIT.md) for the verified
source defects, exception investigation limits and the manual Play Mode checklist.
Regression tests are under `Assets/Tests/PlayMode`; run **Window > General > Test
Runner > PlayMode > Run All**. These tests use virtual Input System devices.
They have **not been executed in the authoring environment** (no Unity Editor).
The reported `InvalidCastException` remains unconfirmed/unresolved; static
checks are not evidence of an exception-free Unity Console.

The follow-up [InvalidCast investigation](Docs/INVALID_CAST_INVESTIGATION.md)
found and repaired bootstrap prefab-reference IDs in all three scenes and added
a serialized-reference type audit. This repair has **not** been tested in Unity;
the reported exception's root cause remains unverified.
