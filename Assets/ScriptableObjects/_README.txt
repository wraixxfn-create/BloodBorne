Vespershade - ScriptableObjects

Data-driven foundation. Current instances:
  GameSettings.asset  - global movement + camera tuning (Vespershade.Data.GameSettingsSO)
  SceneFlow.asset     - scene table + boot scene (Vespershade.Data.SceneFlowSO)

Create more via Assets > Create > Vespershade in the Project window.
Pattern: data lives in ScriptableObjects, behaviour lives in MonoBehaviours
that consume them. Event channels live under Vespershade.Events.
