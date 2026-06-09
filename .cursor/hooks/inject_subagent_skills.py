#!/usr/bin/env python
import json
import sys


DEFAULT_SKILLS = [
    "subagent-planner",
    "project-reviewer",
    "fastapi-expert",
    "sqlalchemy-orm-expert",
    "playwright-cursor-rules",
]
FRONTEND_SKILL = "frontend-design"
ANIMATION_SKILL = "animated-ui-designer"
FRONTEND_KEYWORDS = (
    "frontend",
    "front-end",
    "ui",
    "ux",
    "react",
    "vue",
    "component",
    "layout",
    "style",
    "css",
    "tailwind",
)
ANIMATION_KEYWORDS = (
    "animation",
    "animated",
    "motion",
    "transition",
    "micro-interaction",
    "microinteraction",
)


def _read_input() -> dict:
    raw = sys.stdin.read() or "{}"
    try:
        return json.loads(raw)
    except Exception:
        return {}


def _get_tool_input(payload: dict) -> dict:
    # Cursor hook payloads may expose tool input under slightly different keys.
    for key in ("tool_input", "input", "arguments"):
        value = payload.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _extract_subagent_type(tool_input: dict) -> str:
    value = tool_input.get("subagent_type") or tool_input.get("type")
    return value if isinstance(value, str) else ""


def _extract_prompt(tool_input: dict) -> str:
    value = tool_input.get("prompt")
    return value if isinstance(value, str) else ""


def _build_skill_list(prompt: str) -> list[str]:
    skills = list(DEFAULT_SKILLS)
    lowered = prompt.lower()
    if any(word in lowered for word in FRONTEND_KEYWORDS):
        skills.append(FRONTEND_SKILL)
    if any(word in lowered for word in ANIMATION_KEYWORDS):
        skills.append(ANIMATION_SKILL)
    return skills


def _inject_skills(prompt: str) -> str:
    skills_line = ", ".join(_build_skill_list(prompt))
    injection = (
        "\n\nUse project skills: "
        f"{skills_line}. "
        "If relevant, follow them before implementation."
    )

    if "Use project skills:" in prompt:
        return prompt
    return prompt + injection


def main() -> None:
    payload = _read_input()
    tool_input = _get_tool_input(payload)

    if not tool_input:
        print(json.dumps({"permission": "allow"}))
        return

    subagent_type = _extract_subagent_type(tool_input)
    prompt = _extract_prompt(tool_input)

    if not prompt:
        print(json.dumps({"permission": "allow"}))
        return

    # Apply only to the most common autonomous code/search subagents.
    if subagent_type and subagent_type not in {"generalPurpose", "explore", "shell"}:
        print(json.dumps({"permission": "allow"}))
        return

    updated = dict(tool_input)
    updated["prompt"] = _inject_skills(prompt)

    print(
        json.dumps(
            {
                "permission": "allow",
                "updated_input": updated,
            }
        )
    )


if __name__ == "__main__":
    main()
