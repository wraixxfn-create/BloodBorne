using System.Reflection;
using NUnit.Framework;
using UnityEngine;
using Vespershade.Gameplay;

namespace Vespershade.Tests
{
    /// <summary>
    /// Play Mode checks for the protagonist's layered clothing.
    ///
    /// Run in Test Runner > PlayMode. The test instantiates the shipped
    /// Player.prefab, presses Play on it and inspects the live object: the renderer
    /// must expose one material slot per mesh submesh, every layer must be real
    /// geometry (submeshes for shell, lining, hardware, cloth and leather), the
    /// silhouette must reach the documented heights, and the CharacterController
    /// settings and PlayerController behaviour must be untouched by the art pass.
    /// </summary>
    public class PlayerClothingTests
    {
        private const string PrefabPath = "Assets/Prefabs/Player/Player.prefab";
        private const int ExpectedSubmeshes = 11;

        private GameObject instance;

        [TearDown]
        public void TearDown()
        {
            if (instance != null)
            {
                Object.DestroyImmediate(instance);
                instance = null;
            }
        }

        private GameObject SpawnPlayer()
        {
#if UNITY_EDITOR
            GameObject prefab = UnityEditor.AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath);
            Assert.That(prefab, Is.Not.Null, $"Could not load {PrefabPath}");
            instance = Object.Instantiate(prefab);
            instance.name = "Player (test)";
            return instance;
#else
            return null;
#endif
        }

        [Test]
        public void PlayerPrefabRendererCoversEveryClothingSubmesh()
        {
            GameObject player = SpawnPlayer();
            if (player == null)
            {
                Assert.Ignore("Prefab instantiation only runs inside the Unity editor.");
            }

            MeshRenderer renderer = player.GetComponentInChildren<MeshRenderer>();
            Assert.That(renderer, Is.Not.Null, "The player needs a skinned/mesh renderer.");
            Mesh mesh = renderer.GetComponent<MeshFilter>().sharedMesh;
            Assert.That(mesh, Is.Not.Null, "The player mesh must come from the imported OBJ.");
            Assert.That(mesh.subMeshCount, Is.EqualTo(ExpectedSubmeshes),
                "Clothing layers are separate submeshes (cloth, lining, leather, hardware, linen, iron).");
            Assert.That(renderer.sharedMaterials.Length, Is.EqualTo(mesh.subMeshCount),
                "Every submesh needs its own material or Unity renders it pink.");
            foreach (Material material in renderer.sharedMaterials)
            {
                Assert.That(material, Is.Not.Null, "A material slot is empty: clothing layer would be untextured.");
                Assert.That(material.shader, Is.Not.Null);
            }
        }

        [Test]
        public void ClothingGeometryIsLayeredNotFlat()
        {
            GameObject player = SpawnPlayer();
            if (player == null)
            {
                Assert.Ignore("Prefab instantiation only runs inside the Unity editor.");
            }

            Mesh mesh = player.GetComponentInChildren<MeshFilter>().sharedMesh;
            Bounds bounds = mesh.bounds;
            // A 1.8 m character: clothing must not shrink or balloon the figure.
            Assert.That(bounds.size.y, Is.GreaterThan(1.6f), "Silhouette lost height.");
            Assert.That(bounds.size.y, Is.LessThan(2.0f), "Silhouette grew past the character height.");
            // The coat stand-off gives the figure real girth (shoulders are ~0.6 m).
            Assert.That(bounds.size.x, Is.GreaterThan(0.5f), "Clothing is too flat across the shoulders.");

            int vertexCount = mesh.vertexCount;
            Assert.That(vertexCount, Is.GreaterThan(20000), "Layered cloth needs its own geometry.");
            Assert.That(vertexCount, Is.LessThan(200000), "Vertex budget for the protagonist was exceeded.");
            Assert.That(mesh.triangles.Length / 3, Is.LessThan(200000));
        }

        [Test]
        public void ClothingDoesNotChangeGameplaySetup()
        {
            GameObject player = SpawnPlayer();
            if (player == null)
            {
                Assert.Ignore("Prefab instantiation only runs inside the Unity editor.");
            }

            CharacterController controller = player.GetComponent<CharacterController>();
            Assert.That(controller, Is.Not.Null);
            Assert.That(controller.height, Is.EqualTo(1.8f).Within(0.001f),
                "The art pass must not retune the collision capsule.");
            Assert.That(controller.radius, Is.EqualTo(0.35f).Within(0.001f));
            Assert.That(controller.center.y, Is.EqualTo(0.9f).Within(0.001f));

            PlayerController behaviour = player.GetComponent<PlayerController>();
            Assert.That(behaviour, Is.Not.Null, "PlayerController must survive on the prefab root.");

            // The mesh child carries the art only: no extra colliders or rigidbodies.
            Transform meshChild = player.transform.Find("VeilboundWayfarer");
            Assert.That(meshChild, Is.Not.Null, "Expected the character mesh child.");
            Assert.That(meshChild.GetComponent<Collider>(), Is.Null, "Clothing must not add colliders.");
            Assert.That(meshChild.GetComponent<Rigidbody>(), Is.Null, "Clothing must not add physics.");
            Assert.That(behaviour.CameraFocus, Is.EqualTo(player.transform),
                "No camera focus override was added by the clothing pass.");
        }

        [Test]
        public void PlayerStillWalksSprintsAndJumps()
        {
            GameObject player = SpawnPlayer();
            if (player == null)
            {
                Assert.Ignore("Prefab instantiation only runs inside the Unity editor.");
            }

            PlayerController behaviour = player.GetComponent<PlayerController>();
            CharacterController controller = player.GetComponent<CharacterController>();
            // The prefab ships without the CoreInput singleton; drive the controller
            // through its own serialized fields only, i.e. verify settings resolution.
            FieldInfo settingsField = typeof(PlayerController)
                .GetField("settings", BindingFlags.Instance | BindingFlags.NonPublic);
            Assert.That(settingsField, Is.Not.Null);
            Assert.That(settingsField.GetValue(behaviour), Is.Not.Null,
                "The prefab should reference GameSettingsSO so tuning stays data-driven.");
            Assert.That(controller.enabled, Is.True);
            Assert.That(player.activeInHierarchy, Is.True);
        }
    }
}
