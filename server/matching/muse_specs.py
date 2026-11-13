"""Register Rishi's Muse tasks (M3, M4, M5, M8) with Adam's adapter registry.

Uses server.providers.contract_spec so payloads and outputs are schema-checked against
protocol.ts on both sides. Prompt text lives here (prompt owner), keyed by promptVersion.
"""
from __future__ import annotations

from server.matching import prompts, sky
from server.providers import MUSE_VOICE, TaskRegistry, contract_spec

FORMATION_TASKS = (
    ("theme_discovery", prompts.PROMPT_VERSION_M3, prompts.M3_INSTRUCTIONS, False),
    ("constellation_formation", prompts.PROMPT_VERSION_M4, prompts.M4_INSTRUCTIONS, False),
    ("constellation_naming", prompts.PROMPT_VERSION_M5, prompts.M5_INSTRUCTIONS, True),
    ("sky_narration", sky.PROMPT_VERSION_M8, sky.M8_INSTRUCTIONS, True),
)


def register_formation_specs(registry: TaskRegistry) -> TaskRegistry:
    """Player-visible tasks (names, headlines) also get Muse's voice rules."""
    for task, version, text, player_visible in FORMATION_TASKS:
        instructions = f"{text}\n\n{MUSE_VOICE}" if player_visible else text
        registry.register(contract_spec(task, version, instructions))  # type: ignore[arg-type]
    return registry
