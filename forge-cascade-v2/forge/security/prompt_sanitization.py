"""
Forge Cascade V2 - Prompt Injection Prevention

SECURITY FIX (Audit 4): Sanitize user input before including in LLM prompts
to prevent prompt injection attacks.

Key techniques:
1. XML-style delimiters to mark user content as data (not instructions)
2. Escape injection patterns that could manipulate LLM behavior
3. Length limits to prevent context overflow attacks
4. Output validation against expected schemas
"""

from __future__ import annotations

import re
import json
from typing import Any, Optional
import structlog

logger = structlog.get_logger(__name__)


# Common prompt injection patterns to neutralize
INJECTION_PATTERNS = [
    # Direct instruction override attempts
    r"ignore\s+(previous|above|all)\s+(instructions?|prompts?)",
    r"disregard\s+(previous|above|all)",
    r"forget\s+(everything|all|previous)",
    r"new\s+instructions?:",
    r"system\s*:",
    r"assistant\s*:",
    r"human\s*:",
    r"user\s*:",
    # Role manipulation
    r"you\s+are\s+(now|actually)",
    r"pretend\s+(to\s+be|you\s+are)",
    r"act\s+as\s+if",
    r"roleplay\s+as",
    # Output manipulation
    r"output\s+only",
    r"respond\s+with\s+only",
    r"just\s+say",
    r"your\s+response\s+must\s+be",
    # Jailbreak attempts
    r"do\s+anything\s+now",
    r"dan\s+mode",
    r"developer\s+mode",
    r"bypass\s+(restrictions?|filters?|safety)",
]

# Compiled regex for efficiency
_INJECTION_REGEX = re.compile(
    "|".join(f"({p})" for p in INJECTION_PATTERNS),
    re.IGNORECASE | re.MULTILINE
)


def sanitize_for_prompt(
    user_input: str,
    max_length: int = 10000,
    field_name: str = "user_content",
    strict: bool = False,
) -> str:
    """
    Sanitize user input before including in LLM prompts.

    SECURITY FIX (Audit 4): Prevent prompt injection by:
    1. Wrapping in clear XML delimiters
    2. Escaping injection patterns
    3. Enforcing length limits

    Args:
        user_input: Raw user-provided string
        max_length: Maximum allowed length (default 10000 chars)
        field_name: Name for the XML delimiter (e.g., "title", "description")
        strict: If True, reject inputs with injection patterns; if False, neutralize them

    Returns:
        Sanitized string wrapped in XML delimiters

    Raises:
        ValueError: In strict mode, if injection patterns detected
    """
    if not user_input:
        return f"<{field_name}></{field_name}>"

    # Enforce length limit to prevent context overflow
    if len(user_input) > max_length:
        logger.warning(
            "prompt_input_truncated",
            field_name=field_name,
            original_length=len(user_input),
            max_length=max_length,
        )
        user_input = user_input[:max_length] + "... [TRUNCATED]"

    # Check for injection patterns
    matches = _INJECTION_REGEX.findall(user_input)
    if matches:
        flat_matches = [m for group in matches for m in group if m]
        logger.warning(
            "potential_prompt_injection_detected",
            field_name=field_name,
            patterns_found=flat_matches[:5],  # Log first 5 matches
        )

        if strict:
            raise ValueError(
                f"Potential prompt injection detected in {field_name}. "
                f"Patterns found: {flat_matches[:3]}"
            )

        # Neutralize by adding visible markers
        user_input = _INJECTION_REGEX.sub(r"[FILTERED: \g<0>]", user_input)

    # Escape XML-like tags that could confuse delimiters
    user_input = user_input.replace("<", "&lt;").replace(">", "&gt;")

    # Wrap in clear delimiters
    return f"<{field_name}>\n{user_input}\n</{field_name}>"


def sanitize_dict_for_prompt(
    data: dict[str, Any],
    max_total_length: int = 20000,
    strict: bool = False,
) -> str:
    """
    Sanitize a dictionary of user data for inclusion in prompts.

    Args:
        data: Dictionary with user-provided values
        max_total_length: Maximum total length of output
        strict: If True, reject inputs with injection patterns

    Returns:
        Sanitized JSON string wrapped in delimiters
    """
    # Deep sanitize string values
    def sanitize_value(v: Any, path: str) -> Any:
        if isinstance(v, str):
            # Don't wrap individual values, just neutralize
            if _INJECTION_REGEX.search(v):
                if strict:
                    raise ValueError(f"Potential prompt injection at {path}")
                return _INJECTION_REGEX.sub(r"[FILTERED]", v)
            return v
        elif isinstance(v, dict):
            return {k: sanitize_value(vv, f"{path}.{k}") for k, vv in v.items()}
        elif isinstance(v, list):
            return [sanitize_value(vv, f"{path}[{i}]") for i, vv in enumerate(v)]
        return v

    sanitized = sanitize_value(data, "root")
    json_str = json.dumps(sanitized, indent=2, default=str)

    if len(json_str) > max_total_length:
        logger.warning(
            "prompt_dict_truncated",
            original_length=len(json_str),
            max_length=max_total_length,
        )
        json_str = json_str[:max_total_length] + "\n... [TRUNCATED]"

    return f"<context_data>\n{json_str}\n</context_data>"


def create_safe_user_message(
    template: str,
    user_values: dict[str, str],
    strict: bool = False,
) -> str:
    """
    Create a prompt message with safely interpolated user values.

    Instead of f-strings, use explicit placeholders and sanitize each value.

    Args:
        template: Template string with {placeholder} markers
        user_values: Dict mapping placeholder names to user-provided values
        strict: If True, reject inputs with injection patterns

    Returns:
        Template with sanitized values interpolated

    Example:
        template = "Analyze the proposal titled {title}:\\n\\n{description}"
        values = {"title": user_title, "description": user_desc}
        safe_msg = create_safe_user_message(template, values)
    """
    safe_values = {}
    for key, value in user_values.items():
        if isinstance(value, str):
            safe_values[key] = sanitize_for_prompt(
                value,
                field_name=key,
                strict=strict,
            )
        else:
            safe_values[key] = str(value)

    return template.format(**safe_values)


def validate_llm_output(
    response: str,
    expected_schema: dict[str, type],
    required_fields: Optional[list[str]] = None,
) -> tuple[bool, dict[str, Any], list[str]]:
    """
    Validate LLM output against expected schema.

    SECURITY FIX (Audit 4): Ensure LLM output matches expected structure
    to detect if injection caused unexpected output.

    Args:
        response: Raw LLM response string
        expected_schema: Dict mapping field names to expected types
        required_fields: List of fields that must be present

    Returns:
        Tuple of (is_valid, parsed_data, errors)
    """
    errors = []
    required_fields = required_fields or list(expected_schema.keys())

    # Try to extract JSON from response
    content = response.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        content = "\n".join(lines[1:-1])

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON: {e}")
        return False, {}, errors

    if not isinstance(data, dict):
        errors.append(f"Expected dict, got {type(data).__name__}")
        return False, {}, errors

    # Check required fields
    for field in required_fields:
        if field not in data:
            errors.append(f"Missing required field: {field}")

    # Type validation
    for field, expected_type in expected_schema.items():
        if field in data:
            value = data[field]
            # Handle Union types and None
            if expected_type is type(None):
                continue
            if not isinstance(value, expected_type):
                # Allow int for float
                if expected_type == float and isinstance(value, int):
                    data[field] = float(value)
                else:
                    errors.append(
                        f"Field '{field}' expected {expected_type.__name__}, "
                        f"got {type(value).__name__}"
                    )

    return len(errors) == 0, data, errors


# Convenience exports
__all__ = [
    "sanitize_for_prompt",
    "sanitize_dict_for_prompt",
    "create_safe_user_message",
    "validate_llm_output",
    "INJECTION_PATTERNS",
]
