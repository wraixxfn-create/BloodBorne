#!/usr/bin/env python3
"""C# smoke check used in place of a compiler (no Unity / mono in this sandbox).

  * strips comments, string and char literals, then verifies delimiter balance
  * verifies each file has a namespace and matching braces for it
  * verifies the cross-file symbols the foundation relies on actually exist
    (public API consumed by other classes, serialized fields consumed by YAML)
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "Assets", "Scripts")

ERRORS = []


def strip_literals(text: str) -> str:
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        # line comment
        if c == "/" and i + 1 < n and text[i + 1] == "/":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        # block comment
        if c == "/" and i + 1 < n and text[i + 1] == "*":
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        # verbatim string
        if c == "@" and i + 1 < n and text[i + 1] == '"':
            j = i + 2
            while j < n:
                if text[j] == '"':
                    if j + 1 < n and text[j + 1] == '"':
                        j += 2
                        continue
                    break
                j += 1
            i = j + 1
            out.append('""')
            continue
        # interpolated or normal string
        if c == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    break
                j += 1
            i = j + 1
            out.append('""')
            continue
        # char literal
        if c == "'":
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == "'":
                    break
                j += 1
            i = j + 1
            out.append("''")
            continue
        out.append(c)
        i += 1
    return "".join(out)


def check_balance(path: str, text: str) -> str:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for idx, c in enumerate(text):
        if c in "([{":
            stack.append(c)
        elif c in ")]}":
            if not stack or stack[-1] != pairs[c]:
                line = text.count("\n", 0, idx) + 1
                ERRORS.append(f"{path}: unbalanced '{c}' at line {line}")
                return text
            stack.pop()
    if stack:
        ERRORS.append(f"{path}: unclosed delimiters {stack[-3:]} at end of file")
    return text


def members_of(text: str, class_name: str):
    """Crude member name extractor for one class body."""
    m = re.search(rf"\bclass\s+{class_name}\b", text)
    if not m:
        return None
    start = text.find("{", m.end())
    if start == -1:
        return None
    depth = 0
    end = start
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                end = i
                break
    body = text[start:end]
    names = set(re.findall(r"\b(?:class|void|float|int|bool|string|Vector2|Vector3|Transform|GameObject|InputAction|InputActionMap|GameSettingsSO|SceneFlowSO|PlayerController|Quaternion|Color|Shader|Material|LayerMask|Camera|CharacterController|CoreInput|GameManager|ThirdPersonCameraRig)\s+(\w+)\b", body))
    names |= set(re.findall(r"\b(?:event\s+\w+(?:<[^>]*>)?)\s+(\w+)\b", body))
    names |= set(re.findall(r"(\w+)\s*(?:=>|\()", body))  # properties & methods
    return names


def main() -> int:
    files = {}
    for dirpath, _, filenames in os.walk(SCRIPTS):
        for name in filenames:
            if name.endswith(".cs"):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, ROOT)
                with open(full, "r", encoding="utf-8") as fh:
                    raw = fh.read()
                stripped = strip_literals(raw)
                check_balance(rel, stripped)
                files[rel] = stripped
                if not re.search(r"^\s*namespace\s+Vespershade\.", stripped, re.MULTILINE):
                    ERRORS.append(f"{rel}: no Vespershade namespace declaration")

    joined = "\n".join(files.values())

    # Cross-file API expectations: (symbol, defining file substring)
    expectations = [
        (r"class\s+PlayerController", "Player/PlayerController.cs"),
        (r"Transform\s+CameraFocus", "Player/PlayerController.cs"),
        (r"bool\s+IsGrounded", "Player/PlayerController.cs"),
        (r"bool\s+IsSprinting", "Player/PlayerController.cs"),
        (r"float\s+SpeedRatio", "Player/PlayerController.cs"),
        (r"static\s+ThirdPersonCameraRig\s+Instance", "Camera/ThirdPersonCameraRig.cs"),
        (r"void\s+SetTarget\s*\(", "Camera/ThirdPersonCameraRig.cs"),
        (r"static\s+CoreInput\s+Instance", "Input/CoreInput.cs"),
        (r"InputAction\s+Pause", "Input/CoreInput.cs"),
        (r"InputAction\s+Look", "Input/CoreInput.cs"),
        (r"Vector2\s+MoveAxis", "Input/CoreInput.cs"),
        (r"Vector2\s+LookDelta", "Input/CoreInput.cs"),
        (r"bool\s+SprintHeld", "Input/CoreInput.cs"),
        (r"bool\s+JumpPressed", "Input/CoreInput.cs"),
        (r"static\s+T\s+Instance", "Core/SingletonBehaviour.cs"),
        (r"bool\s+IsPaused", "Core/GameManager.cs"),
        (r"void\s+SetPaused\s*\(", "Core/GameManager.cs"),
        (r"void\s+LoadScene\s*\(", "Core/SceneFlowManager.cs"),
        (r"void\s+ReloadCurrentScene\s*\(", "Core/SceneFlowManager.cs"),
        (r"string\s+bootSceneName", "Data/SceneFlowSO.cs"),
        (r"List<string>\s+sceneNames", "Data/SceneFlowSO.cs"),
        (r"float\s+walkSpeed", "Data/GameSettingsSO.cs"),
        (r"float\s+stickTurnSpeed", "Data/GameSettingsSO.cs"),
        (r"LayerMask\s+cameraObstructionLayers", "Data/GameSettingsSO.cs"),
        (r"event\s+Action\s+Raised", "Events/GameEventChannelSO.cs"),
    ]

    for pattern, where in expectations:
        match = re.search(pattern, joined)
        if not match:
            ERRORS.append(f"expected symbol /{pattern}/ (in {where}) not found")

    # Every GameSettingsSO field consumed by code must exist on the class.
    consumed = set(re.findall(r"settings\.(\w+)", joined))
    gs_members = members_of(files["Assets/Scripts/Data/GameSettingsSO.cs"], "GameSettingsSO")
    if gs_members is None:
        ERRORS.append("could not locate GameSettingsSO class body")
    else:
        for name in sorted(consumed):
            if name not in gs_members:
                ERRORS.append(f"GameSettingsSO has no member '{name}' but it is consumed via settings.{name}")

    for msg in ERRORS:
        print("ERROR", msg)
    print(f"\n{len(files)} C# files scanned")
    if ERRORS:
        print(f"SMOKE CHECK FAILED: {len(ERRORS)} error(s)")
        return 1
    print("SMOKE CHECK PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
