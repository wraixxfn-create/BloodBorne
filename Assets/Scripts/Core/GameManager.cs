using System;
using UnityEngine;
using Vespershade.Data;
using Vespershade.GameInput;

namespace Vespershade.Core
{
    /// <summary>
    /// Owns application level game state: pause, global settings access, cursor policy.
    /// Gameplay systems should query GameManager instead of keeping their own copies of global state.
    /// </summary>
    public class GameManager : SingletonBehaviour<GameManager>
    {
        [Header("Data")]
        [SerializeField] private GameSettingsSO gameSettings;
        [SerializeField] private bool lockCursorOnStart = true;

        /// <summary>Raised whenever the pause state changes. Argument is the new pause state.</summary>
        public event Action<bool> PauseChanged;

        /// <summary>Global tuning data. May be null when nothing is assigned in the scene.</summary>
        public GameSettingsSO Settings => gameSettings;

        public bool IsPaused { get; private set; }

        private void Start()
        {
            if (lockCursorOnStart)
            {
                SetCursorLocked(true);
            }
        }

        private void Update()
        {
            CoreInput input = CoreInput.Instance;
            if (input != null && input.Pause != null && input.Pause.WasPressedThisFrame())
            {
                SetPaused(!IsPaused);
            }

            // Unity/editor focus changes can release the cursor without pausing the game.
            // A click in the focused Game view restores capture instead of leaving look disabled.
            if (lockCursorOnStart && !IsPaused && Application.isFocused &&
                Cursor.lockState != CursorLockMode.Locked && input.Attack.WasPressedThisFrame())
            {
                SetCursorLocked(true);
            }
        }

        public void SetPaused(bool paused)
        {
            if (IsPaused == paused)
            {
                return;
            }

            IsPaused = paused;
            Time.timeScale = paused ? 0f : 1f;
            SetCursorLocked(!paused && lockCursorOnStart);
            PauseChanged?.Invoke(paused);
        }

        public void SetCursorLocked(bool locked)
        {
            Cursor.lockState = locked ? CursorLockMode.Locked : CursorLockMode.None;
            Cursor.visible = !locked;
        }
    }
}
