"""Assembles prompts"""

from agents.domain.roles import Role


class PromptBuilder:
    """Generate the initial prompt for the agent based on its role and tools."""

    def generate_initial_prompt(role: Role, tools: list[str]) -> str:
        #TODO: this is a legacy implementation and needs to be reworked
        #base_prompt = (PROMPTS_DIR / "base-prompt.md").read_text(encoding="utf-8").strip()
        #role_prompt = (PROMPTS_DIR / f"{role.value}.md").read_text(encoding="utf-8").strip()
        #tools_prompt = "\n".join(f"- {tool}" for tool in tools) if tools else "- None"
        #
        #return f"{base_prompt}\n\n---\n\n{role_prompt}\n\n## Available Tools\n{tools_prompt}"

        raise NotImplementedError("PromptBuilder is not implemented yet.")