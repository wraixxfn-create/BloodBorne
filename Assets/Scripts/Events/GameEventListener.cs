using UnityEngine;
using UnityEngine.Events;

namespace Vespershade.Events
{
    /// <summary>
    /// Convenience component that listens to a GameEventChannelSO and forwards it
    /// to a UnityEvent, so designer-facing components can react without code.
    /// </summary>
    public class GameEventListener : MonoBehaviour
    {
        [SerializeField] private GameEventChannelSO channel;
        [SerializeField] private UnityEvent onResponse;

        private void OnEnable()
        {
            if (channel != null)
            {
                channel.Raised += HandleRaised;
            }
        }

        private void OnDisable()
        {
            if (channel != null)
            {
                channel.Raised -= HandleRaised;
            }
        }

        private void HandleRaised()
        {
            if (onResponse != null)
            {
                onResponse.Invoke();
            }
        }
    }
}
