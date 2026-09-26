#!/usr/bin/env python3
"""Deterministic GUID tooling for the Vespershade Unity project.

1. Substitutes {{G_TOKEN}} placeholders in hand-authored Unity YAML/ProjectSettings
   files with stable GUIDs derived from asset paths (uuid5), so every reference
   (script -> .meta, scene -> prefab, prefab -> asset) lines up.
2. Ensures every file and folder under Assets/ has a .meta file with the same
   deterministic GUID scheme and the correct importer block.

Safe to re-run: it is idempotent.
"""

import os
import re
import sys
import uuid

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "Assets")
NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "vespershade://unity-project")


def guid_for(relpath: str) -> str:
    relpath = relpath.replace(os.sep, "/")
    return uuid.uuid5(NAMESPACE, relpath).hex


# Token -> asset path that owns the GUID.
TOKEN_TARGETS = {
    "{{G_SCENE_MAIN}}": "Assets/Scenes/Main/Main.unity",
    "{{G_PREFAB_PLAYER}}": "Assets/Prefabs/Player/Player.prefab",
    "{{G_PREFAB_CAMERA}}": "Assets/Prefabs/Camera/MainCameraRig.prefab",
    "{{G_ASSET_GameSettings}}": "Assets/ScriptableObjects/GameSettings.asset",
    "{{G_ASSET_SceneFlow}}": "Assets/ScriptableObjects/SceneFlow.asset",
    "{{G_MAT_Ground}}": "Assets/Materials/M_GroundPlaceholder.mat",
    "{{G_MAT_Player}}": "Assets/Materials/M_PlayerPlaceholder.mat",
    "{{G_SHADER_PostGrade}}": "Assets/Art/Shaders/VespershadePostGrade.shader",
    "{{G_SCRIPT_GameManager}}": "Assets/Scripts/Core/GameManager.cs",
    "{{G_SCRIPT_SceneFlowManager}}": "Assets/Scripts/Core/SceneFlowManager.cs",
    "{{G_SCRIPT_GameBootstrap}}": "Assets/Scripts/Core/GameBootstrap.cs",
    "{{G_SCRIPT_GameSettingsSO}}": "Assets/Scripts/Data/GameSettingsSO.cs",
    "{{G_SCRIPT_SceneFlowSO}}": "Assets/Scripts/Data/SceneFlowSO.cs",
    "{{G_SCRIPT_PlayerController}}": "Assets/Scripts/Player/PlayerController.cs",
    "{{G_SCRIPT_ThirdPersonCameraRig}}": "Assets/Scripts/Camera/ThirdPersonCameraRig.cs",
    "{{G_SCRIPT_PostProcessController}}": "Assets/Scripts/Rendering/PostProcessController.cs",
}

TEMPLATED_FILES = [
    "Assets/Scenes/Main/Main.unity",
    "Assets/Prefabs/Player/Player.prefab",
    "Assets/Prefabs/Camera/MainCameraRig.prefab",
    "Assets/ScriptableObjects/GameSettings.asset",
    "Assets/ScriptableObjects/SceneFlow.asset",
    "ProjectSettings/EditorBuildSettings.asset",
]


def fill_tokens() -> None:
    for rel in TEMPLATED_FILES:
        path = os.path.join(ROOT, rel)
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()

        for token, target in TOKEN_TARGETS.items():
            text = text.replace(token, guid_for(target))

        leftovers = re.findall(r"\{\{[A-Za-z0-9_]+\}\}", text)
        if leftovers:
            sys.exit(f"ERROR: unresolved tokens {set(leftovers)} in {rel}")

        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"tokens filled: {rel}")


def meta_for_file(relpath: str, guid: str) -> str:
    ext = os.path.splitext(relpath)[1].lower()
    if ext == ".cs":
        return (
            "fileFormatVersion: 2\n"
            f"guid: {guid}\n"
            "MonoImporter:\n"
            "  externalObjects: {}\n"
            "  serializedVersion: 2\n"
            "  defaultReferences: []\n"
            "  executionOrder: 0\n"
            "  icon: {instanceID: 0}\n"
            "  userData:\n"
            "  assetBundleName:\n"
            "  assetBundleVariant:\n"
        )
    if ext == ".shader":
        return (
            "fileFormatVersion: 2\n"
            f"guid: {guid}\n"
            "ShaderImporter:\n"
            "  externalObjects: {}\n"
            "  defaultTextures: []\n"
            "  nonModifiableTextures: []\n"
            "  userData:\n"
            "  assetBundleName:\n"
            "  assetBundleVariant:\n"
        )
    if ext == ".txt":
        return (
            "fileFormatVersion: 2\n"
            f"guid: {guid}\n"
            "TextScriptImporter:\n"
            "  externalObjects: {}\n"
            "  userData:\n"
            "  assetBundleName:\n"
            "  assetBundleVariant:\n"
        )
    if ext == ".mat":
        return (
            "fileFormatVersion: 2\n"
            f"guid: {guid}\n"
            "NativeFormatImporter:\n"
            "  externalObjects: {}\n"
            "  mainObjectFileID: 2100000\n"
            "  userData:\n"
            "  assetBundleName:\n"
            "  assetBundleVariant:\n"
        )
    if ext == ".asset":
        return (
            "fileFormatVersion: 2\n"
            f"guid: {guid}\n"
            "NativeFormatImporter:\n"
            "  externalObjects: {}\n"
            "  mainObjectFileID: 11400000\n"
            "  userData:\n"
            "  assetBundleName:\n"
            "  assetBundleVariant:\n"
        )
    if ext == ".prefab":
        return (
            "fileFormatVersion: 2\n"
            f"guid: {guid}\n"
            "PrefabImporter:\n"
            "  externalObjects: {}\n"
            "  userData:\n"
            "  assetBundleName:\n"
            "  assetBundleVariant:\n"
        )
    return (
        "fileFormatVersion: 2\n"
        f"guid: {guid}\n"
        "DefaultImporter:\n"
        "  externalObjects: {}\n"
        "  userData:\n"
        "  assetBundleName:\n"
        "  assetBundleVariant:\n"
    )


def meta_for_folder(guid: str) -> str:
    return (
        "fileFormatVersion: 2\n"
        f"guid: {guid}\n"
        "folderAsset: yes\n"
        "DefaultImporter:\n"
        "  externalObjects: {}\n"
        "  userData:\n"
        "  assetBundleName:\n"
        "  assetBundleVariant:\n"
    )


def ensure_metas() -> None:
    created = 0
    for dirpath, dirnames, filenames in os.walk(ASSETS):
        for name in dirnames + filenames:
            if name.endswith(".meta"):
                continue
            full = os.path.join(dirpath, name)
            rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
            meta_path = full + ".meta"
            if os.path.exists(meta_path):
                continue
            guid = guid_for(rel)
            content = meta_for_folder(guid) if os.path.isdir(full) else meta_for_file(rel, guid)
            with open(meta_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            created += 1
            print(f"meta created: {rel}.meta")
    print(f"done: {created} meta file(s) created")


if __name__ == "__main__":
    fill_tokens()
    ensure_metas()
