import re
from typing import Optional

# Disarm closing or opening XML-like delimiter tags in prompt inputs
DELIMITER_TAGS_PATTERN = re.compile(
    r"</?\s*(?:user_dilemma|user_context|discussion_transcript|advisor_statement|user_input|system_override|prompt_injection)[^>]*>",
    re.IGNORECASE,
)

SAFE_MODEL_REGEX = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.:-]*$")
SAFE_IDENTIFIER_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")
SAFE_COLOR_REGEX = re.compile(r"^[a-zA-Z0-9_]+$")

def sanitize_prompt_input(text: Optional[str]) -> str:
    """
    Sanitize untrusted external text before embedding into LLM prompts.
    Defends against delimiter breakout (e.g. closing tags like </user_dilemma>)
    and prompt injection instruction patterns.
    """
    if not text:
        return ""
    # Disarm XML-like tags that could close prompt delimitation sections
    disarmed = DELIMITER_TAGS_PATTERN.sub("[filtered-tag]", str(text))
    return disarmed.strip()

def is_safe_model_name(model: str) -> bool:
    """Validate that model identifier does not start with '-' and contains only safe characters."""
    if not model or model.startswith("-"):
        return False
    return bool(SAFE_MODEL_REGEX.fullmatch(model))

def is_safe_identifier(identifier: str) -> bool:
    """Validate that identifier contains only alphanumeric characters, underscores, and dashes."""
    if not identifier:
        return False
    return bool(SAFE_IDENTIFIER_REGEX.fullmatch(identifier))

def is_safe_color(color: str) -> bool:
    """Validate that rich color name contains only safe characters."""
    if not color:
        return False
    return bool(SAFE_COLOR_REGEX.fullmatch(color))
