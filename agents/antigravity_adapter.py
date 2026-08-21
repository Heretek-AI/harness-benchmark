"""Adapter for the ``antigravity-cli`` harness.

SKELETON — the CLI's real flag set lives in ``review/agents/antigravity-cli``
and should be filled in once we wire that harness for real. For now this
adapter writes a stub config file so the runner exercises the full
setup/execute/teardown path. Subprocess spawning + ExecutionResult
construction are inherited from ``BaseAgentAdapter``; we only override
``_on_setup`` (config-file materialisation) and ``_build_command`` (the
``antigravity run <prompt>`` argv shape).
"""

from __future__ import annotations

import json
import shutil

from agents.base import AdapterContext, BaseAgentAdapter


class AntigravityAdapter(BaseAgentAdapter):
    name = "antigravity-cli"
    cli_binary = "antigravity"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        config = {
            "api_base": "${LLM_API}",
            "model": "${LLM_MODEL}",
            "workspace": str(ctx.workspace_dir),
        }
        config_dir = ctx.workspace_dir / ".antigravity"
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps(config, indent=2))

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "run", prompt]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("antigravity")