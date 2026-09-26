using UnityEngine;
using Vespershade.Cameras;
using Vespershade.Gameplay;

namespace Vespershade.Core
{
    /// <summary>
    /// Boots the playable test scene: locates (or spawns) the player prefab at the spawn
    /// point and makes sure exactly one third person camera rig is following it.
    /// Later prompts can extend this into a full gameplay assembly step.
    /// </summary>
    /// <remarks>
    /// Startup order. The scene loads, every <see cref="ThirdPersonCameraRig"/> registers
    /// itself in Awake, then this component's Start assembles the scene in a fixed order,
    /// so player and camera can never race each other:
    /// 1. locate an existing player controller (never spawn a second one),
    /// 2. spawn the player prefab when requested and no player exists yet,
    /// 3. locate the camera rig already in the scene, or create it from the fallback
    ///    prefab when the scene has none,
    /// 4. hand the rig the player's camera focus so the camera follows.
    /// </remarks>
    public class GameBootstrap : MonoBehaviour
    {
        [Header("Player")]
        [SerializeField] private GameObject playerPrefab;
        [SerializeField] private Transform spawnPoint;
        [SerializeField] private bool spawnPlayerOnStart = true;

        [Header("Camera")]
        [Tooltip("Prefab carrying a ThirdPersonCameraRig. Only instantiated when the scene contains no rig.")]
        [SerializeField] private GameObject cameraRigPrefab;
        [Tooltip("When disabled, a missing camera rig only logs a warning instead of being created from the fallback prefab.")]
        [SerializeField] private bool createCameraRigWhenMissing = true;

        /// <summary>The player controller this bootstrap is using, if any.</summary>
        public PlayerController Player { get; private set; }

        /// <summary>The camera rig that follows the player, if one is present or could be created.</summary>
        public ThirdPersonCameraRig CameraRig { get; private set; }

        private void Start()
        {
            // Locate before creating: the sequence must never leave two players or two cameras.
            Player = ResolvePlayer();
            CameraRig = ResolveCameraRig();
            BindCameraToPlayer();
        }

        /// <summary>
        /// Spawns the player prefab at the spawn point and wires the camera to it.
        /// Idempotent: once this bootstrap owns a player the existing instance is returned
        /// instead of spawning a second one. A destroyed player is respawned on the next call.
        /// </summary>
        public PlayerController SpawnPlayer()
        {
            if (Player != null)
            {
                return Player;
            }

            if (playerPrefab == null)
            {
                Debug.LogError("[GameBootstrap] Cannot spawn the player: playerPrefab is not assigned.");
                return null;
            }

            Vector3 position = spawnPoint != null ? spawnPoint.position : Vector3.zero;
            Quaternion rotation = spawnPoint != null ? spawnPoint.rotation : Quaternion.identity;

            GameObject spawned = Instantiate(playerPrefab, position, rotation);
            Player = spawned.GetComponent<PlayerController>();

            if (Player == null)
            {
                Debug.LogError("[GameBootstrap] playerPrefab has no PlayerController component; the player cannot be driven.");
            }

            CameraRig = ResolveCameraRig();
            BindCameraToPlayer();

            return Player;
        }

        /// <summary>Returns the player already in the scene, or spawns the prefab when allowed.</summary>
        private PlayerController ResolvePlayer()
        {
            if (Player != null)
            {
                return Player;
            }

            PlayerController existing = FindFirstInScene<PlayerController>();
            if (existing != null)
            {
                return existing;
            }

            if (!spawnPlayerOnStart)
            {
                return null;
            }

            if (playerPrefab == null)
            {
                Debug.LogWarning("[GameBootstrap] No player prefab assigned. The scene will run empty.");
                return null;
            }

            return SpawnPlayer();
        }

        /// <summary>
        /// Returns the scene's camera rig, creating one from <c>cameraRigPrefab</c> when the
        /// scene contains none. Existing rigs always win, so the camera is never duplicated.
        /// </summary>
        private ThirdPersonCameraRig ResolveCameraRig()
        {
            if (CameraRig != null)
            {
                return CameraRig;
            }

            // Registered in ThirdPersonCameraRig.Awake, so a rig placed in the scene is
            // already available here: Start runs after every Awake in the loaded scene.
            ThirdPersonCameraRig rig = ThirdPersonCameraRig.Instance;
            if (rig == null)
            {
                rig = FindFirstInScene<ThirdPersonCameraRig>();
            }

            if (rig != null)
            {
                return rig;
            }

            if (!createCameraRigWhenMissing || cameraRigPrefab == null)
            {
                Debug.LogWarning("[GameBootstrap] No ThirdPersonCameraRig found. The camera will not follow the player.");
                return null;
            }

            // Deliberate fallback for scenes that rely on dynamic assembly. Awake of the
            // instantiated rig runs during this call, so it is ready before it is returned.
            GameObject created = Instantiate(cameraRigPrefab);
            rig = created.GetComponent<ThirdPersonCameraRig>();

            if (rig == null)
            {
                Debug.LogError("[GameBootstrap] cameraRigPrefab has no ThirdPersonCameraRig component. The camera will not follow the player.");
                Destroy(created);
                return null;
            }

            return rig;
        }

        /// <summary>Points the existing rig at the player so the camera orbits the player.</summary>
        private void BindCameraToPlayer()
        {
            if (CameraRig == null || Player == null)
            {
                return;
            }

            CameraRig.SetTarget(Player.CameraFocus);
        }

        /// <summary>Scene lookup that stays warning free across the supported Unity versions.</summary>
        private static T FindFirstInScene<T>() where T : Object
        {
#if UNITY_2023_1_OR_NEWER
            return FindFirstObjectByType<T>();
#else
            return FindObjectOfType<T>();
#endif
        }
    }
}
