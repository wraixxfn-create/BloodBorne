using UnityEngine;

namespace Vespershade.Arena
{
    /// <summary>
    /// Authored lighting landmarks, not gameplay volumes. Select the rig in the
    /// editor to see the five light zones. Actual lights are children of each
    /// zone, so artists can tune them without changing any combat code.
    /// </summary>
    [DisallowMultipleComponent]
    public sealed class ArenaLightingZones : MonoBehaviour
    {
        [Header("Five lighting zones")]
        public Transform entranceZone;
        public Transform centralArenaZone;
        public Transform cornersZone;
        public Transform elevatedPlatformZone;
        public Transform ritualAreaZone;

        [Header("Stable combat readability (never animated)")]
        [Tooltip("The ONLY shadow-casting light in the room.")]
        public Light moonKey;

        [Tooltip("Shadowless neutral fill, restricted to Player (8) and Enemy (9). No enemy is placed yet.")]
        public Light subjectFill;

        public Light centralArenaFill;
        public Light elevatedPlatformFill;

#if UNITY_EDITOR
        private void OnDrawGizmosSelected()
        {
            DrawZone(entranceZone, 5f, new Color(1f, 0.61f, 0.31f, 0.8f));
            DrawZone(centralArenaZone, 12f, new Color(0.65f, 0.8f, 1f, 0.8f));
            DrawZone(cornersZone, 17f, new Color(0.39f, 0.46f, 0.64f, 0.7f));
            DrawZone(elevatedPlatformZone, 5f, new Color(0.75f, 0.84f, 1f, 0.8f));
            DrawZone(ritualAreaZone, 3.5f, new Color(0.28f, 0.71f, 0.72f, 0.8f));
        }

        private static void DrawZone(Transform anchor, float radius, Color color)
        {
            if (anchor == null) return;
            UnityEditor.Handles.color = color;
            UnityEditor.Handles.DrawWireDisc(anchor.position + Vector3.up * 0.05f,
                Vector3.up, radius);
        }
#endif
    }
}
