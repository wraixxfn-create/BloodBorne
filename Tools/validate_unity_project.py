#!/usr/bin/env python3
"""Structural validator for the hand-authored Vespershade Unity project.

The sandbox has no Unity editor, so this script enforces the invariants that
would otherwise be caught by opening the project:

  * every file/folder under Assets/ has a .meta, all GUIDs unique + well formed
  * every Unity YAML file (scene/prefab/asset/mat) parses, and each document's
    class id matches its expected type name
  * all in-file object references (m_GameObject, m_Father, m_Children,
    m_Component) resolve to anchors inside the same file
  * every cross-file PPtr GUID resolves to an existing .meta (or a built-in)
  * MonoBehaviour components point at real script GUIDs, and every serialized
    field present in YAML exists on the C# class (typo detection)
  * EditorBuildSettings lists a real scene whose GUID matches the scene's meta
  * Packages/manifest.json is valid JSON and contains the Input System
  * no unresolved {{TOKEN}} placeholders remain anywhere
"""

import json
import os
import re
import sys

try:
    import yaml
except ImportError:
    sys.exit("PyYAML is required: pip3 install pyyaml")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "Assets")

BUILTIN_GUIDS = {
    "0000000000000000e000000000000000",  # built-in meshes etc.
    "0000000000000000f000000000000000",  # built-in shaders/materials
}

# A .prefab asset is addressed through the prefab asset handle Unity creates at
# import time. PrefabInstance.m_SourcePrefab must use this id (plus the prefab's
# GUID); pointing it at an object id that only exists inside the prefab file
# leaves the instance unresolved and makes Unity log
# "Missing Prefab with guid: <guid>".
PREFAB_ASSET_HANDLE = 100100000

CLASS_NAMES = {
    1: "GameObject",
    4: "Transform",
    20: "Camera",
    21: "Material",
    23: "MeshRenderer",
    29: "OcclusionCullingSettings",
    33: "MeshFilter",
    56: "SphereCollider",
    64: "MeshCollider",
    65: "BoxCollider",
    78: "TagManager",
    81: "AudioListener",
    104: "RenderSettings",
    108: "Light",
    114: "MonoBehaviour",
    129: "PlayerSettings",
    136: "CapsuleCollider",
    143: "CharacterController",
    157: "LightmapSettings",
    196: "NavMeshSettings",
    1001: "PrefabInstance",
    1045: "EditorBuildSettings",
}

ERRORS = []
WARNINGS = []


def error(msg: str) -> None:
    ERRORS.append(msg)


def warning(msg: str) -> None:
    WARNINGS.append(msg)


# --------------------------------------------------------------------------
# YAML loading with tolerance for Unity's custom tags.
# --------------------------------------------------------------------------

class UnityLoader(yaml.SafeLoader):
    pass


def _construct_unknown(loader, tag_suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return loader.construct_scalar(node)
    if isinstance(node, yaml.SequenceNode):
        return loader.construct_sequence(node, deep=True)
    return loader.construct_mapping(node, deep=True)


UnityLoader.add_multi_constructor(None, _construct_unknown)

DOC_HEADER = re.compile(r"^--- !u!(\d+) &(\d+)( stripped)?:?\s*$")


def split_documents(text: str):
    docs = []
    current_id = None
    current_class = None
    lines = []
    for line in text.splitlines():
        m = DOC_HEADER.match(line)
        if m:
            if current_id is not None:
                docs.append((current_class, current_id, "\n".join(lines)))
            current_class = int(m.group(1))
            current_id = int(m.group(2))
            lines = []
        elif current_id is not None:
            lines.append(line)
    if current_id is not None:
        docs.append((current_class, current_id, "\n".join(lines)))
    return docs


def parse_documents(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    parsed = []
    for class_id, file_id, body in split_documents(text):
        try:
            data = yaml.load(body, Loader=UnityLoader)
        except yaml.YAMLError as exc:
            error(f"{path}: YAML parse failure in object &{file_id}: {exc}")
            continue
        if not isinstance(data, dict) or len(data) != 1:
            error(f"{path}: object &{file_id} does not contain exactly one root mapping")
            continue
        type_name = next(iter(data))
        expected = CLASS_NAMES.get(class_id)
        if expected is None:
            error(f"{path}: unknown class id {class_id} on &{file_id}")
        elif type_name != expected:
            error(f"{path}: class id {class_id} maps to '{expected}' but object is '{type_name}'")
        parsed.append((class_id, file_id, data[type_name]))
    return parsed


# --------------------------------------------------------------------------
# 1. Meta coverage + GUID uniqueness.
# --------------------------------------------------------------------------

def collect_metas():
    metas = {}
    guid_to_path = {}
    for dirpath, dirnames, filenames in os.walk(ASSETS):
        for name in list(dirnames) + list(filenames):
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            if name.endswith(".meta"):
                continue
            meta_path = full + ".meta"
            if not os.path.exists(meta_path):
                error(f"missing .meta for {rel}")
                continue
            with open(meta_path, "r", encoding="utf-8") as fh:
                meta_text = fh.read()
            m = re.search(r"^guid: ([0-9a-fA-F]{32})\s*$", meta_text, re.MULTILINE)
            if not m:
                error(f"{rel}.meta has no valid guid line")
                continue
            guid = m.group(1).lower()
            metas[rel] = guid
            if guid in guid_to_path:
                error(f"duplicate guid {guid} between {guid_to_path[guid]} and {rel}")
            else:
                guid_to_path[guid] = rel
    return metas, guid_to_path


# --------------------------------------------------------------------------
# 2. Reference walking.
# --------------------------------------------------------------------------

PPTR_KEYS = ("fileID",)


def walk_refs(node, refs):
    if isinstance(node, dict):
        if "fileID" in node:
            refs.append(node)
        for value in node.values():
            walk_refs(value, refs)
    elif isinstance(node, list):
        for value in node:
            walk_refs(value, refs)


STANDARD_MB_KEYS = {
    "m_ObjectHideFlags", "m_CorrespondingSourceObject", "m_PrefabInstance",
    "m_PrefabAsset", "m_GameObject", "m_Enabled", "m_EditorHideFlags",
    "m_Script", "m_Name", "m_EditorClassIdentifier",
}


def check_unity_file(path: str, metas, guid_to_path, script_fields):
    rel = os.path.relpath(path, ROOT).replace(os.sep, "/")
    own_guid = metas.get(rel, "")
    docs = parse_documents(path)
    anchors = {file_id for _, file_id, _ in docs}

    for class_id, file_id, data in docs:
        if not isinstance(data, dict):
            continue

        refs = []
        walk_refs(data, refs)
        for ref in refs:
            file_ref = ref.get("fileID")
            guid = str(ref.get("guid", "")).lower() if "guid" in ref else ""
            if guid:
                if guid in BUILTIN_GUIDS:
                    continue
                if guid not in guid_to_path:
                    error(f"{rel}: &{file_id} references missing guid {guid}")
                continue
            if isinstance(file_ref, int) and file_ref > 0 and file_ref not in anchors:
                error(f"{rel}: &{file_id} has dangling in-file reference to &{file_ref}")

        # MonoBehaviour: verify script exists and serialized fields match.
        if class_id == 114 and isinstance(data.get("m_Script"), dict):
            script_guid = str(data["m_Script"].get("guid", "")).lower()
            script_rel = guid_to_path.get(script_guid)
            if script_rel is None:
                error(f"{rel}: MonoBehaviour &{file_id} points at unknown script guid {script_guid}")
            elif not script_rel.endswith(".cs"):
                error(f"{rel}: MonoBehaviour &{file_id} script guid resolves to non-script {script_rel}")
            else:
                fields = script_fields.get(script_rel)
                if fields is None:
                    error(f"{rel}: could not parse C# fields for {script_rel}")
                else:
                    for key in data.keys():
                        if key in STANDARD_MB_KEYS:
                            continue
                        if key not in fields:
                            error(f"{rel}: &{file_id} serializes '{key}' but {script_rel} has no such serialized field")

    return docs


# --------------------------------------------------------------------------
# 3. C# serialized field extraction (regex based, covers this codebase).
# --------------------------------------------------------------------------

DECL_RE = re.compile(
    r"^(?P<access>public|private|protected|internal)?\s*"
    r"(?P<mods>(?:(?:static|const|readonly|event|volatile)\s+)*)"
    r"(?P<type>[\w\.<>\[\], ]+?)\s+"
    r"(?P<name>\w+)\s*(?:=|;)"
)

FIELD_SKIP_TYPES = {"class", "struct", "enum", "interface", "void", "delegate"}


ATTR_CHUNK = re.compile(r"^\[[^\]]*\]\s*")


def extract_serialized_fields(cs_path: str):
    try:
        with open(cs_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return None

    fields = set()
    pending_serialize = False
    for raw in text.splitlines():
        line = raw.strip()

        if not line or line.startswith("//") or line.startswith("*") or line.startswith("/*"):
            if not line:
                pending_serialize = False
            continue

        # Strip attribute chunks like [SerializeField] / [Range(0f, 1f)],
        # remembering whether any of them marks the member as serialized.
        serialize_attr = pending_serialize
        while True:
            m = ATTR_CHUNK.match(line)
            if not m:
                break
            if "SerializeField" in m.group(0):
                serialize_attr = True
            line = line[m.end():]
            if not line:
                break

        if not line:
            pending_serialize = serialize_attr
            continue

        pending_serialize = False

        if "=>" in line:  # property, not a field
            continue

        # Only look at the part before the initializer / terminator:
        # parentheses there mean it is a method, not a field.
        head = re.split(r"[=;]", line, 1)[0]
        if "(" in head:
            continue

        m = DECL_RE.match(line)
        if not m:
            continue

        mods = m.group("mods") or ""
        access = m.group("access") or ""
        type_name = m.group("type").strip()

        is_field = (
            "static" not in mods
            and "const" not in mods
            and "event" not in mods
            and type_name.split(" ")[0] not in FIELD_SKIP_TYPES
        )
        if is_field and (serialize_attr or access == "public"):
            fields.add(m.group("name"))

    return fields


# --------------------------------------------------------------------------
# Main.
# --------------------------------------------------------------------------

def main() -> int:
    metas, guid_to_path = collect_metas()

    script_fields = {}
    for rel in metas:
        if rel.endswith(".cs"):
            script_fields[rel] = extract_serialized_fields(os.path.join(ROOT, rel))

    yaml_files = [rel for rel in metas if rel.endswith((".unity", ".prefab", ".asset", ".mat"))]
    if not yaml_files:
        error("no Unity YAML assets found")

    all_docs = {}
    for rel in sorted(yaml_files):
        docs = check_unity_file(os.path.join(ROOT, rel), metas, guid_to_path, script_fields)
        all_docs[rel] = docs

    # Prefab instances must reference the prefab asset itself: the prefab asset
    # handle (fileID 100100000) plus the prefab GUID. Referencing an object id
    # that only exists inside the prefab file (the root GameObject, a component,
    # ...) does not resolve at load time and Unity reports the prefab as missing.
    for rel, docs in all_docs.items():
        for class_id, file_id, data in docs:
            if class_id != 1001:
                continue
            source = data.get("m_SourcePrefab")
            if not isinstance(source, dict):
                error(f"{rel}: PrefabInstance &{file_id} lacks m_SourcePrefab")
                continue
            version = data.get("serializedVersion")
            if version not in (None, 2):
                warning(f"{rel}: PrefabInstance &{file_id} has serializedVersion {version}; Unity writes 2")
            guid = str(source.get("guid", "")).lower()
            source_rel = guid_to_path.get(guid)
            if source_rel is None:
                continue  # already reported
            if not source_rel.endswith(".prefab"):
                error(f"{rel}: PrefabInstance &{file_id} points at {source_rel}, which is not a prefab asset")
                continue
            if source.get("fileID") != PREFAB_ASSET_HANDLE:
                error(
                    f"{rel}: PrefabInstance &{file_id} m_SourcePrefab must use the prefab asset handle "
                    f"(fileID {PREFAB_ASSET_HANDLE}) but references &{source.get('fileID')} in {source_rel}"
                )

    # EditorBuildSettings consistency.
    ebs_path = os.path.join(ROOT, "ProjectSettings", "EditorBuildSettings.asset")
    if os.path.exists(ebs_path):
        docs = parse_documents(ebs_path)
        found = False
        for class_id, _, data in docs:
            if class_id != 1045:
                continue
            for entry in data.get("m_Scenes", []) or []:
                found = True
                scene_path = entry.get("path", "")
                scene_guid = str(entry.get("guid", "")).lower()
                if not scene_path or not os.path.exists(os.path.join(ROOT, scene_path)):
                    error(f"EditorBuildSettings: scene path '{scene_path}' does not exist")
                    continue
                rel_scene = scene_path.replace(os.sep, "/")
                actual = metas.get(rel_scene)
                if actual != scene_guid:
                    error(f"EditorBuildSettings: guid mismatch for {scene_path} (settings={scene_guid}, meta={actual})")
        if not found:
            error("EditorBuildSettings contains no scenes")
    else:
        error("ProjectSettings/EditorBuildSettings.asset missing")

    # Packages manifest.
    manifest_path = os.path.join(ROOT, "Packages", "manifest.json")
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as fh:
                manifest = json.load(fh)
            deps = manifest.get("dependencies", {})
            if "com.unity.inputsystem" not in deps:
                error("manifest.json does not include com.unity.inputsystem")
        except json.JSONDecodeError as exc:
            error(f"manifest.json is not valid JSON: {exc}")
    else:
        error("Packages/manifest.json missing")

    # Leftover template tokens in project content (Tools/ defines the tokens themselves).
    token_re = re.compile(r"\{\{[A-Za-z0-9_]+\}\}")
    scan_dirs = [ASSETS, os.path.join(ROOT, "ProjectSettings"), os.path.join(ROOT, "Packages")]
    for scan_dir in scan_dirs:
      for dirpath, dirnames, filenames in os.walk(scan_dir):
        if ".git" in dirpath.split(os.sep):
            continue
        for name in filenames:
            if name.endswith(".meta"):
                continue
            full = os.path.join(dirpath, name)
            try:
                with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                    sample = fh.read()
            except OSError:
                continue
            if token_re.search(sample):
                rel = os.path.relpath(full, ROOT)
                error(f"unresolved template token left in {rel}")

    for msg in WARNINGS:
        print(f"WARN  {msg}")
    for msg in ERRORS:
        print(f"ERROR {msg}")

    print(f"\n{len(metas)} assets tracked, {len(guid_to_path)} unique guids, "
          f"{len(yaml_files)} Unity YAML files checked")
    if ERRORS:
        print(f"VALIDATION FAILED: {len(ERRORS)} error(s)")
        return 1
    print("VALIDATION PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
