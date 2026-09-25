using System;
using UnityEngine;

namespace Vespershade.Events
{
    /// <summary>
    /// ScriptableObject based event channel.
    /// Any system can raise the event, any listener can subscribe, and neither
    /// side needs a direct reference to the other - only to this shared asset.
    /// Create channels via Assets > Create > Vespershade > Events > Game Event Channel.
    /// </summary>
    [CreateAssetMenu(fileName = "GameEventChannel", menuName = "Vespershade/Events/Game Event Channel")]
    public class GameEventChannelSO : ScriptableObject
    {
        /// <summary>Invoked whenever Raise is called.</summary>
        public event Action Raised;

        /// <summary>Broadcast the event to every subscriber.</summary>
        public void Raise()
        {
            Raised?.Invoke();
        }
    }
}
