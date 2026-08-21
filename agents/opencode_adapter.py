"""Adapter for the ``opencode`` harness.

SKELETON — OpenCode reads its config from ``~/.config/opencode/config.json``
or the path in ``OPENCODE_CONFIG``. See ``review/agents/opencode/`` for the
real schema. Subprocess spawning + ExecutionResult construction are
inherited from ``BaseAgentAdapter``; we only override ``_on_setup``
(config-file materialisation + ``OPENCODE_CONFIG`` env) and
``_build_command`` (the ``opencode --non-interactive <prompt>`` argv shape).
"""

from __future__ import annotations

import json
import shutil

from agents.base import AdapterContext, BaseAgentAdapter


class OpenCodeAdapter(BaseAgentAdapter):
    name = "opencode"
    cli_binary = "opencode"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        cfg = {
            "provider": {
                "name": "litellm",
                "api_base": "${LLM_API}",
                "api_key": "${LLM_KEY}",
                "model": "${LLM_MODEL}",
            },
            "mcp_servers": list(mcp_servers),
        }
        cfg_path = ctx.workspace_dir / "opencode.json"
        cfg_path.write_text(json.dumps(cfg, indent=2))
        ctx.extra_env["OPENCODE_CONFIG"] = str(cfg_path)

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "--non-interactive", prompt]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("opencode")