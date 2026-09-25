using System;
using System.Collections;
using UnityEngine;
using UnityEngine.SceneManagement;
using Vespershade.Data;

namespace Vespershade.Core
{
    /// <summary>
    /// Central entry point for all scene transitions.
    /// Loads scenes asynchronously and exposes progress + events so a future
    /// loading screen / fade system can hook in without touching callers.
    /// </summary>
    public class SceneFlowManager : SingletonBehaviour<SceneFlowManager>
    {
        [SerializeField] private SceneFlowSO sceneFlow;

        /// <summary>Raised when a scene load starts. Argument is the scene name.</summary>
        public event Action<string> SceneLoadStarted;

        /// <summary>Raised when a scene load finishes. Argument is the scene name.</summary>
        public event Action<string> SceneLoadFinished;

        public bool IsLoading { get; private set; }

        /// <summary>Normalized 0..1 loading progress, suitable for a future loading screen.</summary>
        public float LoadProgress { get; private set; }

        public SceneFlowSO Flow => sceneFlow;

        public string BootSceneName
        {
            get
            {
                if (sceneFlow != null && !string.IsNullOrEmpty(sceneFlow.bootSceneName))
                {
                    return sceneFlow.bootSceneName;
                }
                return SceneManager.GetActiveScene().name;
            }
        }

        /// <summary>True when the scene name is registered in the SceneFlow asset.</summary>
        public bool IsRegisteredScene(string sceneName)
        {
            return sceneFlow != null
                && sceneFlow.sceneNames != null
                && sceneFlow.sceneNames.Contains(sceneName);
        }

        /// <summary>Request a scene load by name. Safe to call from anywhere.</summary>
        public void LoadScene(string sceneName)
        {
            if (string.IsNullOrEmpty(sceneName))
            {
                Debug.LogError("[SceneFlow] LoadScene called with an empty scene name.");
                return;
            }

            if (IsLoading)
            {
                Debug.LogWarning($"[SceneFlow] Ignoring LoadScene('{sceneName}') because a load is already in progress.");
                return;
            }

            if (!IsRegisteredScene(sceneName))
            {
                Debug.LogWarning($"[SceneFlow] Scene '{sceneName}' is not registered in the SceneFlow asset. It will still be attempted.");
            }

            StartCoroutine(LoadSceneRoutine(sceneName));
        }

        /// <summary>Reload the currently active scene (future: respawn flow).</summary>
        public void ReloadCurrentScene()
        {
            LoadScene(SceneManager.GetActiveScene().name);
        }

        private IEnumerator LoadSceneRoutine(string sceneName)
        {
            IsLoading = true;
            LoadProgress = 0f;
            SceneLoadStarted?.Invoke(sceneName);

            AsyncOperation operation = SceneManager.LoadSceneAsync(sceneName);
            if (operation == null)
            {
                Debug.LogError($"[SceneFlow] Could not start async load of '{sceneName}'. Is the scene in Build Settings?");
                IsLoading = false;
                yield break;
            }

            while (!operation.isDone)
            {
                // Unity reports 0..0.9 while loading, the last 0.1 is activation.
                LoadProgress = Mathf.Clamp01(operation.progress / 0.9f);
                yield return null;
            }

            LoadProgress = 1f;
            IsLoading = false;
            SceneLoadFinished?.Invoke(sceneName);
        }
    }
}
