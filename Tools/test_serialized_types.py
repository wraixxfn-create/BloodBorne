"""Regression tests for the offline audit; these are NOT Unity Play Mode tests."""
import tempfile
import unittest
from pathlib import Path
from audit_serialized_types import TypeAudit
from validate_unity_project import extract_serialized_fields


class SerializedTypeTests(unittest.TestCase):
    def setUp(self):
        self.audit = TypeAudit({
            'player.prefab': {
                710000: (1, {'m_Name': 'Player'}),
                710001: (4, {'m_GameObject': {'fileID': 710000}}),
                710003: (23, {}),
            },
            'settings.asset': {11400000: (114, {'m_Script': {'guid': 'settings-script'}})},
        }, {'player': 'player.prefab', 'settings': 'settings.asset',
            'settings-script': 'GameSettingsSO.cs'}, {})

    def test_prefab_handle_is_not_gameobject(self):
        self.audit.check('scene', 'playerPrefab', 'GameObject',
                         {'fileID': 100100000, 'guid': 'player'})
        self.assertEqual(len(self.audit.errors), 1)
        self.assertIn('expected GameObject, actual PrefabAssetHandle', self.audit.errors[0])

    def test_root_gameobject_reference_is_valid(self):
        self.audit.check('scene', 'playerPrefab', 'GameObject',
                         {'fileID': 710000, 'guid': 'player'})
        self.assertEqual(self.audit.errors, [])
        self.assertEqual(self.audit.checked, 1)

    def test_mixed_array_detects_wrong_element(self):
        self.audit.check('player.prefab', 'anchors', 'Transform[]',
                         [{'fileID': 710001}, {'fileID': 710000}])
        self.assertEqual(len(self.audit.errors), 1)
        self.assertIn('anchors[1]: expected Transform, actual GameObject', self.audit.errors[0])

    def test_scriptableobject_concrete_type_is_checked(self):
        ref = {'fileID': 11400000, 'guid': 'settings'}
        self.audit.check('scene', 'settings', 'GameSettingsSO', ref)
        self.audit.check('scene', 'sceneFlow', 'SceneFlowSO', ref)
        self.assertEqual(len(self.audit.errors), 1)
        self.assertIn('expected SceneFlowSO, actual GameSettingsSO', self.audit.errors[0])

    def test_renderer_subclass_is_valid(self):
        self.audit.check('player.prefab', 'renderer', 'Renderer', {'fileID': 710003})
        self.assertEqual(self.audit.errors, [])

    def test_unknown_fileid_is_not_certified(self):
        self.audit.check('scene', 'playerPrefab', 'GameObject',
                         {'fileID': 999, 'guid': 'player'})
        self.assertEqual(len(self.audit.unverified), 1)
        self.assertEqual(self.audit.checked, 0)

    def test_extractor_preserves_default_api_and_types(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'Test.cs'
            path.write_text('[SerializeField] private GameObject playerPrefab;\n'
                            'public Transform[] anchors;\nprivate int hidden;\n')
            self.assertEqual(extract_serialized_fields(path), {'playerPrefab', 'anchors'})
            self.assertEqual(extract_serialized_fields(path, True),
                             {'playerPrefab': 'GameObject', 'anchors': 'Transform[]'})


if __name__ == '__main__':
    unittest.main()
