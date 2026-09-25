using UnityEngine;
using Vespershade.Cameras;
using Vespershade.Gameplay;

namespace Vespershade.Core
{
    /// <summary>
    /// Boots the playable test scene: spawns the player prefab at the spawn point
    /// and hands the camera rig its follow target.
    /// Later prompts can extend this into a full gameplay assembly step.
    /// </summary>
    public class GameBootstrap : MonoBehaviour
    {
        [Header("Spawn")]
        [SerializeField] private GameObject playerPrefab;
        [SerializeField] private Transform spawnPoint;
        [SerializeField] private bool spawnPlayerOnStart = true;

        /// <summary>The spawned player controller, if any.</summary>
        public PlayerController Player { get; private set; }

        private void Start()
        {
            if (!spawnPlayerOnStart)
            {
                return;
            }

            if (playerPrefab == null)
            {
                Debug.LogWarning("[GameBootstrap] No player prefab assigned. The scene will run empty.");
                return;
            }

            SpawnPlayer();
        }

        /// <summary>Spawns the player prefab and wires the third person camera to it.</summary>
        public PlayerController SpawnPlayer()
        {
            if (playerPrefab == null)
            {
                Debug.LogError("[GameBootstrap] Cannot spawn the player: playerPrefab is not assigned.");
                return null;
            }

            Vector3 position = spawnPoint != null ? spawnPoint.position : Vector3.zero;
            Quaternion rotation = spawnPoint != null ? spawnPoint.rotation : Quaternion.identity;

            GameObject spawned = Instantiate(playerPrefab, position, rotation);
            Player = spawned.GetComponent<PlayerController>();

            ThirdPersonCameraRig cameraRig = ThirdPersonCameraRig.Instance;
            if (cameraRig != null && Player != null)
            {
                cameraRig.SetTarget(Player.CameraFocus);
            }
            else if (cameraRig == null)
            {
                Debug.LogWarning("[GameBootstrap] No ThirdPersonCameraRig found. The camera will not follow the player.");
            }

            return Player;
        }
    }
}
