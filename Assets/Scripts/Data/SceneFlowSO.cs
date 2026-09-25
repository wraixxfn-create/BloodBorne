using System.Collections.Generic;
using UnityEngine;

namespace Vespershade.Data
{
    /// <summary>
    /// Declares the scenes the game knows about and which one it boots into.
    /// Consumed by SceneFlowManager. Keeping the table in an asset (instead of
    /// hardcoding names in code) makes adding scenes a data change, not a code change.
    /// Default instance lives at Assets/ScriptableObjects/SceneFlow.asset.
    /// </summary>
    [CreateAssetMenu(fileName = "SceneFlow", menuName = "Vespershade/Core/Scene Flow")]
    public class SceneFlowSO : ScriptableObject
    {
        [Tooltip("Scene the game boots into. Must exist in Build Settings.")]
        public string bootSceneName = "Main";

        [Tooltip("Every scene this project is allowed to load, by scene name.")]
        public List<string> sceneNames = new List<string>();
    }
}
