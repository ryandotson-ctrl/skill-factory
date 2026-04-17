#!/usr/bin/env python3
"""
Quick validation script for skills.
"""

import re
import sys
from pathlib import Path

import yaml

MAX_SKILL_NAME_LENGTH = 64
HYPHEN_CASE_NAME = re.compile(r"^[a-z0-9-]+$")
DISPLAY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 ._:&'()/+-]*$")
ALLOWED_PROPERTIES = {
    "name",
    "description",
    "license",
    "allowed-tools",
    "metadata",
    "version",
    "scope",
    "portability_tier",
    "requires_env",
    "project_profiles",
}
REQUIRED_CONTRACT_FIELDS = ("scope", "portability_tier", "requires_env", "project_profiles")


def _validate_optional_list(name, value):
    if not isinstance(value, list):
        return False, f"'{name}' must be a list when present"
    if not all(isinstance(item, str) for item in value):
        return False, f"'{name}' must contain only strings"
    return True, ""


def _metadata_block(frontmatter):
    metadata = frontmatter.get("metadata")
    return metadata if isinstance(metadata, dict) else {}


def _field_present(frontmatter, key):
    if key in frontmatter:
        return True
    metadata = _metadata_block(frontmatter)
    return key in metadata


def _field_value(frontmatter, key):
    if key in frontmatter:
        return frontmatter.get(key)
    metadata = _metadata_block(frontmatter)
    return metadata.get(key)


def _is_trigger_only_sidecar_skill(skill_path, frontmatter):
    observed_keys = set(frontmatter.keys())
    if observed_keys != {"name", "description"}:
        return False
    return (Path(skill_path) / "agents" / "openai.yaml").exists()


def validate_skill(skill_path):
    """Basic validation of a skill."""
    skill_path = Path(skill_path)

    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return False, "SKILL.md not found"

    content = skill_md.read_text()
    if not content.startswith("---"):
        return False, "No YAML frontmatter found"

    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return False, "Invalid frontmatter format"

    frontmatter_text = match.group(1)

    try:
        frontmatter = yaml.safe_load(frontmatter_text)
        if not isinstance(frontmatter, dict):
            return False, "Frontmatter must be a YAML dictionary"
    except yaml.YAMLError as e:
        return False, f"Invalid YAML in frontmatter: {e}"

    unexpected_keys = set(frontmatter.keys()) - ALLOWED_PROPERTIES
    if unexpected_keys:
        allowed = ", ".join(sorted(ALLOWED_PROPERTIES))
        unexpected = ", ".join(sorted(unexpected_keys))
        return (
            False,
            f"Unexpected key(s) in SKILL.md frontmatter: {unexpected}. Allowed properties are: {allowed}",
        )

    if "name" not in frontmatter:
        return False, "Missing 'name' in frontmatter"
    if "description" not in frontmatter:
        return False, "Missing 'description' in frontmatter"

    name = frontmatter.get("name", "")
    if not isinstance(name, str):
        return False, f"Name must be a string, got {type(name).__name__}"
    name = name.strip()
    if name:
        if name.startswith("-") or name.endswith("-") or "--" in name:
            return (
                False,
                f"Name '{name}' cannot start/end with hyphen or contain consecutive hyphens",
            )
        if not (HYPHEN_CASE_NAME.match(name) or DISPLAY_NAME.match(name)):
            return (
                False,
                f"Name '{name}' must be a hyphen-case skill id or a compact display name",
            )
        if len(name) > MAX_SKILL_NAME_LENGTH:
            return (
                False,
                f"Name is too long ({len(name)} characters). "
                f"Maximum is {MAX_SKILL_NAME_LENGTH} characters.",
            )

    description = frontmatter.get("description", "")
    if not isinstance(description, str):
        return False, f"Description must be a string, got {type(description).__name__}"
    description = description.strip()
    if description:
        if "<" in description or ">" in description:
            return False, "Description cannot contain angle brackets (< or >)"
        if len(description) > 1024:
            return (
                False,
                f"Description is too long ({len(description)} characters). Maximum is 1024 characters.",
            )

    metadata = frontmatter.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        return False, "'metadata' must be a dictionary when present"

    trigger_only_sidecar = _is_trigger_only_sidecar_skill(skill_path, frontmatter)
    missing_contract_fields = [key for key in REQUIRED_CONTRACT_FIELDS if not _field_present(frontmatter, key)]
    if missing_contract_fields and not trigger_only_sidecar:
        return (
            False,
            "Missing portability contract field(s): "
            + ", ".join(missing_contract_fields)
            + ". Provide them in frontmatter or metadata, or keep trigger-only frontmatter with agents/openai.yaml.",
        )

    for optional_key in ("version", "scope", "portability_tier"):
        value = _field_value(frontmatter, optional_key)
        if value is not None and not isinstance(value, str):
            return False, f"'{optional_key}' must be a string when present"

    for optional_key in ("requires_env", "project_profiles"):
        value = _field_value(frontmatter, optional_key)
        if value is not None:
            ok, message = _validate_optional_list(optional_key, value)
            if not ok:
                return False, message

    return True, "Skill is valid!"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python quick_validate.py <skill_directory>")
        sys.exit(1)

    valid, message = validate_skill(sys.argv[1])
    print(message)
    sys.exit(0 if valid else 1)
