using UnityEngine;

namespace Vespershade.Core
{
    /// <summary>
    /// Base class for persistent singletons.
    /// Derive from it instead of hand-writing the pattern in every manager.
    /// </summary>
    /// <typeparam name="T">The concrete MonoBehaviour type.</typeparam>
    public abstract class SingletonBehaviour<T> : MonoBehaviour where T : SingletonBehaviour<T>
    {
        private static T s_instance;

        /// <summary>Global access point. Can be null before Awake or after shutdown.</summary>
        public static T Instance => s_instance;

        /// <summary>Override to false when the singleton should die together with its scene.</summary>
        protected virtual bool PersistAcrossScenes => true;

        protected virtual void Awake()
        {
            if (s_instance != null && s_instance != this)
            {
                Debug.LogWarning($"[{GetType().Name}] Duplicate singleton on '{gameObject.name}' was destroyed.");
                Destroy(gameObject);
                return;
            }

            s_instance = (T)this;

            if (PersistAcrossScenes)
            {
                DontDestroyOnLoad(gameObject);
            }
        }

        protected virtual void OnDestroy()
        {
            if (s_instance == this)
            {
                s_instance = null;
            }
        }
    }
}
