# Immediate Play Mode InvalidCastException investigation

## Status (2026-09-26)

**InvalidCastException remains unresolved; root cause could not be verified.**

A concrete serialized-reference defect was found and repaired. It is a startup
suspect, **not a runtime-confirmed cause**. Unity 2022.3.20f1 is not installed in
this workspace (no Unity executable on PATH or in inspected installation paths;
no imported Library/package source cache). No Play Mode session, Inspector
inspection, component-isolation trial or initialization log capture was possible.
No exception handling, suppression, component removal or runtime workaround added.

## New finding: prefab asset handles in GameObject fields

All three scenes serialized the following on `GameBootstrap` object `&40004`:

| Field (declared type) | Before | Correct target |
| --- | --- | --- |
| `playerPrefab` (`GameObject`) | fileID `100100000`, Player prefab GUID | fileID `710000`, the Player prefab's `!u!1` root GameObject |
| `cameraRigPrefab` (`GameObject`) | fileID `100100000`, camera prefab GUID | fileID `720000`, the camera prefab's `!u!1` root GameObject |

`100100000` is used for the importer-owned prefab asset handle in
`PrefabInstance.m_SourcePrefab`. It is not either prefab's root GameObject ID.
Those source-prefab links are intentionally unchanged. The static auditor calls
this target `PrefabAssetHandle`; **that label is not an observed CLR runtime type**.
The actual object/type Unity returned at the reported exception remains unknown.

Startup path to investigate first:

1. `GameBootstrap.Start()` (line 41) -> `ResolvePlayer()` -> `SpawnPlayer()`.
2. `GameBootstrap.cs:70`: `GameObject spawned = Instantiate(playerPrefab, position, rotation);`
   infers `Instantiate<GameObject>`, whose return conversion is a potential
   internal cast site if the supplied reference resolves incompatibly.
3. Camera fallback at line 144: `GameObject created = Instantiate(cameraRigPrefab);`.
   Existing scene cameras normally mean this fallback is not reached.

No evidence yet distinguishes a failure during reference import/materialization,
instantiation, or an unrelated initialization operation. The wrapper-only error
cannot identify this line by itself.

### Repair and prevention

- Repointed **six fields in three scenes** to the actual prefab root GameObjects.
- Updated `Tools/generate_arena_scene.py` so regeneration cannot reintroduce these
  two bad references in the MeshKit scene.
- Added `Tools/audit_serialized_types.py`: resolves GUID **and fileID**, compares
  serialized MonoBehaviour object fields/array elements against C# declarations,
  and checks native component ownership and Transform links.
- Extended the existing serialized-field extractor with optional type information;
  its default set-of-field-names API is unchanged.
- Added seven offline regression tests for root-vs-handle, mixed arrays,
  concrete ScriptableObject types, Renderer subclasses, unknown IDs and extraction.
- Extended the existing Unity input test to check resolved button-control value
  types and float reads. **Unity tests have not been run.**

The old validator only confirmed that an external GUID existed, not that the
addressed object was assignable to the consuming field. It passed the old scenes.
The new type audit reproduced six static failures before the scene repair.

## Entire-project source audit

Reviewed all **17 runtime C# files**, the existing PlayMode test source, all three
scenes, prefabs, ScriptableObjects, package manifest and build settings. Structural
validation covers 142 YAML assets; the type audit checks their relevant references.

| Area | Result |
| --- | --- |
| Explicit reference casts / `as` | Runtime reference cast: `SingletonBehaviour<T>.Awake`, line 29, `(T)this`. Both concrete users are correctly self-typed: `GameManager : SingletonBehaviour<GameManager>` and `SceneFlowManager : SingletonBehaviour<SceneFlowManager>`. No runtime `as` casts found. Numeric `(float)i` in ArenaBounds is not an object cast. |
| Generic Unity APIs | Audited bootstrap `Instantiate` and scene searches; CoreInput `AddComponent`; player `GetComponent<CharacterController>`; camera `GetComponent<Camera>`; lighting/fog `GetComponentsInChildren<Light/Renderer/Transform>`; particle `AddComponent<ParticleSystem>` and `GetComponent<ParticleSystemRenderer>`. Requested types are appropriate at source level. Prefab references above were not. |
| Player / character | `Awake` gets required CharacterController. `Update` reads Vector2 Move, boolean Sprint/Jump, applies camera-relative motion. No combat, dodge, weapon or animation controller exists. |
| Camera | `Awake` obtains Camera and initializes orbit; `LateUpdate` consumes Vector2 Look. Persistent yaw/pitch, no per-frame target rebinding; mouse uses pixels, stick uses time-scaled rate. Source review only, no visual verification. |
| Scene initialization | GameManager and SceneFlowManager inherit singleton Awake. Bootstrap assembles player/camera in Start. CoreInput is lazily created on first access. No guaranteed relative Awake order among unrelated components. |
| Additional startup suspects | ArenaLightingController.Awake discovers Light/Renderer arrays; ArenaFogController.Awake resolves Transform/Renderer/material data, OnEnable modifies fog; ArenaAtmosphereParticles.OnEnable creates native particle components. These must be included in runtime isolation, not just input. |
| Rendering | PostProcessController is ExecuteAlways and creates a Material on first OnRenderImage. Shader reference resolves to the shader asset, not a Material. Cannot rule out import/render-time errors without Unity. |
| ScriptableObjects | Settings references resolve to GameSettingsSO, scene-flow references to SceneFlowSO. Assets have the corresponding script GUIDs. No serialized event-channel instances found. |
| Events / callbacks | GameEventListener subscribes/unsubscribes a parameterless Action and invokes a parameterless UnityEvent. No serialized persistent listener calls found in scenes/prefabs. Pause/scene-flow events are typed Action<bool>/Action<string>. No input CallbackContext callbacks. |
| UI / Animator / interfaces | No UI controller, Animator controller/parameters or custom gameplay interfaces present. UI/animation folders are placeholders. No serialized PlayerInput component. |
| Collections / reflection | Runtime collections are typed Light/Renderer/GameObject/string lists and typed arrays. No object dictionaries, dynamic, runtime reflection or heterogeneous object collections. Test-only reflection injects GameSettingsSO and invokes UpdateCamera(float, bool) with matching arguments. |
| Missing/old references | No additional mismatched non-null typed references found. No orphan serialized MonoBehaviour field names under the existing extractor. Optional camera target/focus are null by design (bootstrap assignment / player-transform fallback); optional empty environment arrays trigger typed discovery. Imported/editor-local stale state cannot be audited here. |

## Every Input Action

Package: Input System **1.7.0**, `activeInputHandler: 1`. No `.inputactions` asset,
PlayerInput, generated input wrapper, InputActionReference or installed project DLL
exists in this checkout. `CoreInput.BuildGameplayMap` is the actual definition.

| Action | Action/layout | Actual configured paths and value shape | Consumer |
| --- | --- | --- | --- |
| Move | Value / Vector2 | WASD 2DVector composite -> Vector2; gamepad leftStick -> Vector2. Individual WASD composite parts are float keys, correctly combined by 2DVector. | ReadValue<Vector2> |
| Look | Value / Vector2 | Mouse delta; gamepad rightStick -> Vector2 | ReadValue<Vector2> |
| Sprint | Button / Button | Left Shift; leftStickPress -> float | IsPressed |
| Jump | Button / Button | Space; buttonSouth -> float | WasPressedThisFrame |
| Dodge | Button / Button | Left Ctrl; buttonEast -> float | Accessor only; no dodge gameplay |
| Interact | Button / Button | E; buttonWest -> float | Accessor only |
| LightAttack / Attack alias | Button / Button | Mouse leftButton; rightTrigger -> float | Cursor recapture uses press; no attack gameplay |
| HeavyAttack | Button / Button | Mouse rightButton; leftTrigger -> float | Reserved |
| LockOn | Button / Button | Mouse middleButton; rightStickPress -> float | Reserved |
| Pause | Button / Button | Escape; start -> float | WasPressedThisFrame |

These are built-in control-layout expectations from the configured paths, not a
capture of the user's live devices. Tests now assert resolved button `valueType`
as well as declarations; existing tests assert resolved Look controls. No runtime
float read on Vector2, wrong CallbackContext cast or new action rebuild warranted
by the source audit. Prior input/camera changes were already in the starting commit;
this investigation does not claim them as new fixes.

## Executed checks

Use Python 3 with PyYAML installed (a virtual environment was used here):

```sh
python Tools/audit_serialized_types.py
python Tools/test_serialized_types.py
python Tools/validate_unity_project.py
python Tools/csharp_smoke_check.py
python Tools/verify_arena_lighting.py
```

Type audit after repair: **3,763 non-null typed references checked, 121 null
references, 0 unverified references in its covered scope, 0 errors**. The tool is
not a full Unity serializer: it does not certify arbitrary imported subassets,
all native engine fields or runtime-constructed values. It reports unresolved
references and non-null prefab reference overrides rather than silently approving
them. The C# smoke check is delimiter/API inspection, **not compilation**.

## Runtime work still blocked, not performed

1. Open with Unity 2022.3.20f1 in a clean editor, allow imports to finish, open
   MeshKit scene. Inspect the two bootstrap prefab fields, then baseline Play
   **with every component enabled**. Run the existing PlayMode test suite too.
2. If the exception persists, use disposable scene/prefab copies to isolate one
   subsystem per trial, restoring the baseline each time. Include bootstrap,
   singleton managers, input, camera, player, particles, fog, lighting and grade.
   Disabling a MonoBehaviour does **not** prevent its Awake on an active object;
   deactivate its owning object before entry when isolating Awake. Account for
   dependencies: removing CoreInput alone triggers its lazy recreation; removing
   a camera can trigger bootstrap fallback. Do not interpret those trials as
   valid isolation unless the recreation path is controlled in the disposable copy.
3. Once narrowed, temporarily add paired entry/completion markers around the
   suspect Awake/OnEnable/Start operations only. Record the last completed marker
   and first entered-but-uncompleted operation. No per-frame logging and no
   catch/filter. Remove markers after identification. No such logs were added
   here since they cannot yield runtime evidence in this environment.
4. Verify horizontal/vertical mouse orbit while moving, camera-relative movement,
   sprint, pitch limits, no freeze/snap-back, and an error-free Console. **Dodge
   and attack gameplay cannot pass: this foundation has neither implementation.**
   Input delivery tests do not substitute for those gameplay checks.
5. Stop Play, enter again; repeat for all three scenes. Include exit/re-entry while
   paused. Record domain/scene reload settings. No claim about repeated-entry
   stability is justified until these tests pass.

## Requested final-report fields

1. **Exact causing component:** not verified; GameBootstrap has the new concrete defect.
2. **Exact operation:** serialized prefab references feeding generic Instantiate at
   GameBootstrap.cs:70 (player), :144 (camera fallback); candidate, not observed throw site.
3. **Actual type:** serialized prefab asset handle, rather than the authored root
   GameObject; actual throwing runtime object's CLR type unknown.
4. **Expected type:** UnityEngine.GameObject.
5. **Root cause:** scene authoring confused prefab source handles with GameObject
   references; whether it caused the reported exception remains unverified.
6. **Fix applied:** correct six GameObject PPtrs, fix generator, add type regression audit.
7. **Camera/input fix:** camera fallback reference repaired; no speculative orbit/input
   rewrite. Button control-type test expanded. Camera/gameplay runtime checks blocked.
8. **Modified assets/components:** three scene instances of GameBootstrap; no prefab
   component disabled or removed. Tooling, tests and documentation also updated.
9. **Exception gone after repeated Play Mode:** unknown; **zero sessions executed**.
