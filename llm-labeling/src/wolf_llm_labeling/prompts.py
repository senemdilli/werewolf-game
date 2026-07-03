import json
from pathlib import Path
from string import Template

class PromptSet:
    def __init__(self, prompt_dir: str | Path = "./prompts") -> None:
        self.prompt_dir = Path(prompt_dir)
        self.prompts: dict[str, str] = {}
        self.raw_mapping: dict[str, str] = {}

    def load(self, path: str | Path) -> None:
        """
        Loads the prompts from a JSON file.
        The JSON contains a dictionary of prompt_id -> path/to/prompt entries.
        Paths are resolved relative to self.prompt_dir.
        """
        json_path = Path(path)
        with open(json_path, "r", encoding="utf-8") as f:
            mapping = json.load(f)
        
        self.raw_mapping = mapping
        for prompt_id, relative_path in mapping.items():
            if prompt_id in ("system_prompt", "system_prompt_legacy", "system_prompt_numeric"):
                target_id = f"labeling__{prompt_id}"
            else:
                target_id = prompt_id
            
            full_path = self.prompt_dir / relative_path
            if not full_path.exists():
                alt_path = None
                if relative_path.endswith(".md"):
                    alt_path = self.prompt_dir / relative_path.replace(".md", ".txt")
                elif relative_path.endswith(".txt"):
                    alt_path = self.prompt_dir / relative_path.replace(".txt", ".md")
                
                if alt_path and alt_path.exists():
                    full_path = alt_path
            
            with open(full_path, "r", encoding="utf-8") as pf:
                self.prompts[target_id] = pf.read()

    def get_prompt(self, prompt_id: str, args: dict[str, str], default_prompt: str | None = None) -> str:
        """
        Returns a filled out prompt using string.Template for templating.
        If the prompt does not exist in the internal prompt storage, use the default prompt as a fallback.
        If that also doesn't exist, an error is thrown.
        """
        template_str = self.prompts.get(prompt_id, default_prompt)
        if template_str is None:
            raise KeyError(f"Prompt '{prompt_id}' not found in PromptSet and no default_prompt was provided.")
        
        t = Template(template_str)
        return t.safe_substitute(args)

    def __str__(self) -> str:
        """Prints all prompt templates"""
        lines = []
        for pid, template in self.prompts.items():
            lines.append(f"=== {pid} ===\n{template}\n")
        return "\n".join(lines)
