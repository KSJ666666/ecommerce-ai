from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from langchain_core.prompts import PromptTemplate

_PROMPTS_DIR = Path(__file__).resolve().parent
_DEFAULT_SUFFIX = ".jinja2"


def _resolve_prompt_path(prompt_name: str) -> Path:
    normalized = str(prompt_name).strip()
    if not normalized:
        raise ValueError("Prompt name must not be empty.")

    candidate = Path(normalized)
    if candidate.is_absolute():
        raise ValueError(f"Prompt name must be relative: {prompt_name}")

    if candidate.suffix:
        relative_path = candidate
    else:
        relative_path = candidate.with_suffix(_DEFAULT_SUFFIX)

    path = (_PROMPTS_DIR / relative_path).resolve()
    if _PROMPTS_DIR.resolve() not in path.parents:
        raise ValueError(f"Prompt path escapes prompts directory: {prompt_name}")
    if not path.is_file():
        raise ValueError(f"Prompt file not found: {path}")
    return path


@lru_cache(maxsize=None)
def load_prompt_text(prompt_name: str) -> str:
    return _resolve_prompt_path(prompt_name).read_text(encoding="utf-8")


def load_prompt_template(
        prompt_name: str,
        template_format: str = "jinja2",
) -> PromptTemplate:
    return PromptTemplate.from_template(
        load_prompt_text(prompt_name),
        template_format=template_format,
    )
