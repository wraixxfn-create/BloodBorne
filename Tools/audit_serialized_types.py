#!/usr/bin/env python3
"""Read-only type audit for this project's serialized MonoBehaviour PPtrs.

Unlike existence checks, resolves the GUID AND fileID and compares the target
class with the C# field type (including each array element). Also checks native
GameObject/component/Transform links. Not a Unity importer or a C# compiler:
imported subassets, built-ins and prefab property overrides are reported as
limitations, not certified. Run alongside validate_unity_project.py.
"""
from pathlib import Path
import validate_unity_project as project


class TypeAudit:
    def __init__(self, docs, paths, fields):
        self.docs = docs
        self.paths = paths
        self.fields = fields
        self.errors = []
        self.unverified = set()
        self.checked = 0
        self.nulls = 0

    def resolve(self, owner, ref):
        guid = str(ref.get('guid', ''))
        path = self.paths.get(guid) if guid else owner
        if guid in project.BUILTIN_GUIDS:
            return None  # Importer-owned reference, not a YAML document.
        if path and path.endswith('.shader') and ref['fileID'] == 4800000:
            return 'Shader'
        if path and path.endswith('.cs') and ref['fileID'] == 11500000:
            return 'MonoScript'
        # m_SourcePrefab uses this importer handle; a GameObject field must
        # instead address a real !u!1 object inside the prefab.
        if path and path.endswith('.prefab') and ref['fileID'] == project.PREFAB_ASSET_HANDLE:
            return 'PrefabAssetHandle'
        doc = self.docs.get(path, {}).get(ref['fileID'])
        if doc is None:
            return None
        class_id, data = doc
        if class_id == 114:
            script = self.paths.get(str(data.get('m_Script', {}).get('guid', '')))
            if script:
                return Path(script).stem
            # Stripped prefab MonoBehaviour; follow its source object.
            source = data.get('m_CorrespondingSourceObject')
            if source and source.get('fileID'):
                return self.resolve(path, source)
            return None
        return project.CLASS_NAMES.get(class_id)

    @staticmethod
    def compatible(expected, actual):
        if expected == actual:
            return True
        return expected == 'Renderer' and actual in {
            'MeshRenderer', 'SkinnedMeshRenderer', 'ParticleSystemRenderer',
            'LineRenderer', 'TrailRenderer', 'SpriteRenderer',
        }

    def check(self, owner, label, expected, value):
        if isinstance(value, list):
            for index, item in enumerate(value):
                self.check(owner, f'{label}[{index}]', expected.removesuffix('[]'), item)
            return
        if not isinstance(value, dict) or 'fileID' not in value:
            return
        if value['fileID'] == 0:
            self.nulls += 1
            return
        actual = self.resolve(owner, value)
        if actual is None:
            self.unverified.add(f'{owner}: {label} -> {value}')
            return
        self.checked += 1
        if not self.compatible(expected, actual):
            self.errors.append(f'{owner}: {label}: expected {expected}, actual {actual} ({value})')

    def run(self):
        for path, docs in self.docs.items():
            for file_id, (class_id, data) in docs.items():
                label = f'&{file_id}'
                if class_id == 114:
                    script = self.paths.get(str(data.get('m_Script', {}).get('guid', '')))
                    for field, expected in self.fields.get(script, {}).items():
                        if field in data:
                            self.check(path, f'{label}.{field}', expected, data[field])
                if 'm_GameObject' in data:
                    self.check(path, f'{label}.m_GameObject', 'GameObject', data['m_GameObject'])
                if class_id == 4:
                    self.check(path, f'{label}.m_Father', 'Transform', data.get('m_Father'))
                    self.check(path, f'{label}.m_Children', 'Transform[]', data.get('m_Children'))
                if class_id == 1:
                    for entry in data.get('m_Component', []):
                        ref = entry['component']
                        component = docs.get(ref['fileID'])
                        # Every serialized native or managed component here has m_GameObject.
                        if component is None or 'm_GameObject' not in component[1]:
                            self.errors.append(f'{path}: {label}.m_Component: not a component: {ref}')
                        elif component[1]['m_GameObject'].get('fileID') != file_id:
                            self.errors.append(f'{path}: {label}.m_Component: wrong owner: {ref}')
                if class_id == 1001:
                    for modification in data.get('m_Modification', {}).get('m_Modifications', []):
                        ref = modification.get('objectReference', {})
                        if ref.get('fileID'):
                            self.unverified.add(f'{path}: {label} reference override {modification}')
        return self.errors


def main():
    metas, paths = project.collect_metas()
    fields = {path: project.extract_serialized_fields(str(Path(project.ROOT) / path), True)
              for path in metas if path.endswith('.cs')}
    docs = {}
    for path in metas:
        if path.endswith(('.unity', '.prefab', '.asset', '.mat')):
            docs[path] = {fid: (cid, data) for cid, fid, data in
                          project.parse_documents(str(Path(project.ROOT) / path))}
    audit = TypeAudit(docs, paths, fields)
    audit.run()
    for message in project.ERRORS + audit.errors:
        print('ERROR', message)
    for message in sorted(audit.unverified):
        print('UNVERIFIED', message)
    print(f'{audit.checked} non-null typed references checked; {audit.nulls} null references; '
          f'{len(audit.unverified)} unresolved/importer-owned references or overrides; '
          f'{len(project.ERRORS) + len(audit.errors)} errors.')
    print('Static audit only. Null references require contextual review. '
          'No Unity import, Inspector, lifecycle or Play Mode verification performed.')
    return int(bool(project.ERRORS or audit.errors))


if __name__ == '__main__':
    raise SystemExit(main())
