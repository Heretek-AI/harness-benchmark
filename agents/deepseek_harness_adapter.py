"""Adapter for the ``deepseek-harness`` and ``DeepSeek-Reasonix`` CLI.

Both harnesses support OpenAI-compatible and LiteLLM endpoints, routing
``LLM_API`` to ``OPENAI_BASE`` and ``LLM_KEY`` to ``OPENAI_API_KEY``.
Subprocess invocation executes ``deepseek --task <prompt>``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from agents.base import AdapterContext, BaseAgentAdapter


class DeepSeekHarnessAdapter(BaseAgentAdapter):
    """Harness adapter for DeepSeek CLI harness."""

    name = "deepseek-harness"
    cli_binary = "deepseek"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        api_base, api_key, model = self.get_llm_config(ctx)

        # Bridge environment variables
        if api_base:
            ctx.extra_env["OPENAI_BASE"] = api_base
            ctx.extra_env["OPENAI_BASE_URL"] = api_base
            ctx.extra_env["DEEPSEEK_BASE_URL"] = api_base
        if api_key:
            ctx.extra_env["OPENAI_API_KEY"] = api_key
            ctx.extra_env["DEEPSEEK_API_KEY"] = api_key
        if model:
            ctx.extra_env["DEEPSEEK_MODEL"] = model

        # Materialize .deepseek/config.json in workspace
        deepseek_dir = ctx.workspace_dir / ".deepseek"
        deepseek_dir.mkdir(parents=True, exist_ok=True)
        config = {
            "api_base": api_base,
            "api_key": api_key,
            "model": model,
        }
        (deepseek_dir / "config.json").write_text(json.dumps(config, indent=2))

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "-p", prompt, "--output-format", "json"]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("deepseek") or shutil.which("dsh")


class DeepSeekReasonixAdapter(DeepSeekHarnessAdapter):
    """Specialized adapter for DeepSeek-Reasonix harness variant."""

    name = "DeepSeek-Reasonix"
    cli_binary = "reasonix"

    def _on_setup(
        self,
        ctx: AdapterContext,
        plugins: list[str],
        mcp_servers: list[str],
    ) -> None:
        api_base, api_key, model = self.get_llm_config(ctx)
        target_model = model or "deepseek-chat"
        base_url = api_base or "https://api.deepseek.com"

        # Bridge environment variables
        if api_key:
            ctx.extra_env["REASONIX_API_KEY"] = api_key
            ctx.extra_env["DEEPSEEK_API_KEY"] = api_key
            ctx.extra_env["OPENAI_API_KEY"] = api_key
        if api_base:
            ctx.extra_env["OPENAI_BASE"] = api_base
            ctx.extra_env["OPENAI_BASE_URL"] = api_base
            ctx.extra_env["DEEPSEEK_BASE_URL"] = api_base
        if model:
            ctx.extra_env["REASONIX_MODEL"] = model
            ctx.extra_env["DEEPSEEK_MODEL"] = model

        ctx.extra_env["REASONIX_HOME"] = str(ctx.workspace_dir)

        dotenv_content = f"REASONIX_API_KEY={api_key}\nDEEPSEEK_API_KEY={api_key}\nOPENAI_API_KEY={api_key}\n"
        (ctx.workspace_dir / ".env").write_text(dotenv_content)
        home_reasonix = Path.home() / ".reasonix"
        home_reasonix.mkdir(parents=True, exist_ok=True)
        (home_reasonix / ".env").write_text(dotenv_content)

        # Materialize reasonix.toml and config.toml in workspace and home
        toml_content = f"""# Reasonix benchmark configuration
default_model = "litellm"

[agent]
temperature = 0.0
compact_ratio = 0.80

[sandbox]
bash = "off"
network = true

[[providers]]
name = "litellm"
kind = "openai"
base_url = "{base_url}"
model = "{target_model}"
models = ["{target_model}"]
default = "{target_model}"
api_key_env = "REASONIX_API_KEY"
"""
        (ctx.workspace_dir / "reasonix.toml").write_text(toml_content)
        (ctx.workspace_dir / "config.toml").write_text(toml_content)
        (home_reasonix / "config.toml").write_text(toml_content)

    def _build_command(self, prompt: str, workspace_dir) -> list[str]:
        return [self.cli_binary, "run", "--auto", "--output-format", "json", prompt]

    @staticmethod
    def resolve_cli() -> str | None:
        return shutil.which("reasonix") or shutil.which("deepseek")
