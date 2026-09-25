using UnityEngine;

namespace Vespershade.Arena
{
    /// <summary>
    /// Defines the soft and hard boundaries of the ritual chamber.
    /// Hard boundary is enforced by wall colliders on Environment layer;
    /// this component provides gameplay queries (IsInsideCombatArea) and
    /// debug draw for the circular arena. It also enforces a fall-back
    /// soft push for anything that somehow breaches the wall ring.
    /// </summary>
    public class ArenaBounds : MonoBehaviour
    {
        [Header("Arena Dimensions (meters)")]
        [Tooltip("Playable radius to the inner face of the outer walls.")]
        public float playableRadius = 19f;

        [Tooltip("Central combat-safe radius that readably stays empty of heavy clutter.")]
        public float clearCombatRadius = 12f;

        [Tooltip("Radius of the elevated central platform (top tier).")]
        public float centralPlatformRadius = 5f;

        [Tooltip("Height of the outer wall colliders (gameplay wall, not visual).")]
        public float wallHeight = 6f;

        [Tooltip("Center of the arena in world space. Defaults to this transform.")]
        public Transform arenaCenter;

        public Vector3 Center => arenaCenter != null ? arenaCenter.position : transform.position;

        /// <summary>True when point is inside the overall playable disc.</summary>
        public bool IsInsidePlayable(Vector3 point)
        {
            Vector2 flat = new Vector2(point.x - Center.x, point.z - Center.z);
            return flat.magnitude <= playableRadius;
        }

        /// <summary>True when point is inside the clutter-free central combat circle.</summary>
        public bool IsInsideClearCombat(Vector3 point)
        {
            Vector2 flat = new Vector2(point.x - Center.x, point.z - Center.z);
            return flat.magnitude <= clearCombatRadius;
        }

        /// <summary>Returns the closest point on or inside the playable boundary.</summary>
        public Vector3 ClampToPlayable(Vector3 point)
        {
            Vector2 flat = new Vector2(point.x - Center.x, point.z - Center.z);
            float dist = flat.magnitude;
            if (dist <= playableRadius)
                return point;

            Vector2 dir = flat / Mathf.Max(dist, 0.001f);
            Vector2 clamped = dir * playableRadius;
            return new Vector3(Center.x + clamped.x, point.y, Center.z + clamped.y);
        }

        private void OnDrawGizmosSelected()
        {
            Gizmos.color = new Color(0.35f, 0.55f, 0.85f, 0.18f);
            Vector3 c = Center;
            // Playable disc
            UnityEditor_DrawDisc(c, Vector3.up, playableRadius);
            Gizmos.color = new Color(0.95f, 0.72f, 0.2f, 0.22f);
            UnityEditor_DrawDisc(c + Vector3.up * 0.02f, Vector3.up, clearCombatRadius);
            Gizmos.color = new Color(0.9f, 0.4f, 0.35f, 0.5f);
            UnityEditor_DrawDisc(c + Vector3.up * 0.62f, Vector3.up, centralPlatformRadius);
        }

        // Lightweight gizmo disc helper without requiring UnityEditor namespace at runtime.
        private void UnityEditor_DrawDisc(Vector3 center, Vector3 normal, float radius)
        {
#if UNITY_EDITOR
            UnityEditor.Handles.color = Gizmos.color;
            UnityEditor.Handles.DrawWireDisc(center, normal, radius);
#endif
            // Fallback rough wire for builds: draw via Gizmos sphere approximation
            const int seg = 48;
            Vector3 prev = center + new Vector3(radius, 0f, 0f);
            for (int i = 1; i <= seg; i++)
            {
                float a = (float)i / seg * Mathf.PI * 2f;
                Vector3 next = center + new Vector3(Mathf.Cos(a) * radius, 0f, Mathf.Sin(a) * radius);
                Gizmos.DrawLine(prev, next);
                prev = next;
            }
        }

        // Soft clamp for CharacterControllers that somehow slip past colliders (rare).
        private void OnTriggerStay(Collider other)
        {
            if (!other.CompareTag("Player"))
                return;

            Vector3 pos = other.transform.position;
            if (!IsInsidePlayable(pos))
            {
                Vector3 clamped = ClampToPlayable(pos);
                // Nudge via CharacterController if present
                var cc = other.GetComponent<CharacterController>();
                if (cc != null)
                {
                    Vector3 delta = clamped - pos;
                    delta.y = 0f;
                    cc.Move(delta * Time.deltaTime * 8f);
                }
            }
        }
    }
}
