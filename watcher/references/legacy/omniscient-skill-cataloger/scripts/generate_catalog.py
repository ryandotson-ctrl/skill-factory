#!/usr/bin/env python3
import argparse
import json
import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


SKIP_PARTS = {"_p0_backups", ".backups", ".skill-backups", "__pycache__", ".pytest_cache"}
ROOT_ORDER = {"codex": 0, "antigravity": 1, "workspace_mirror": 2, "local": 3, "agents": 4}
ECOSYSTEM_CONTRACT_PATH = (
    Path(__file__).resolve().parents[2] / "skill_director" / "references" / "ecosystem_contract_v1.yaml"
)
FALLBACK_ECOSYSTEM_CONTRACT: Dict[str, Any] = {
    "inventory_roles": {
        "standard": {"path_prefixes": []},
        "system_hidden": {"path_prefixes": [".system/"]},
        "runtime_bundle": {"path_prefixes": ["codex-primary-runtime/"]},
        "backup_snapshot": {"path_prefixes": [".skill-backups/", "_p0_backups/", ".backups/"]},
    },
    "root_roles": {
        "codex": "canonical_authoring",
        "antigravity": "distribution_mirror",
        "workspace_mirror": "publication_mirror",
        "local": "workspace_local",
        "agents": "auxiliary_global",
    },
}


@dataclass(frozen=True)
class RootSpec:
    key: str
    path: Path


@lru_cache(maxsize=1)
def load_ecosystem_contract() -> Dict[str, Any]:
    if yaml is None or not ECOSYSTEM_CONTRACT_PATH.exists():
        return FALLBACK_ECOSYSTEM_CONTRACT
    try:
        loaded = yaml.safe_load(ECOSYSTEM_CONTRACT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return FALLBACK_ECOSYSTEM_CONTRACT
    if not isinstance(loaded, dict):
        return FALLBACK_ECOSYSTEM_CONTRACT
    return loaded


def classify_inventory_role(relative_skill_path: str) -> str:
    contract = load_ecosystem_contract()
    inventory_roles = contract.get("inventory_roles", {})
    if isinstance(inventory_roles, dict):
        for role_name, role_config in inventory_roles.items():
            if not isinstance(role_config, dict):
                continue
            prefixes = role_config.get("path_prefixes", [])
            if not isinstance(prefixes, list):
                continue
            for prefix in prefixes:
                if str(prefix).strip() and relative_skill_path.startswith(str(prefix).strip()):
                    return str(role_name)
    return "standard"


def classify_root_role(source: str) -> str:
    root_roles = load_ecosystem_contract().get("root_roles", {})
    if isinstance(root_roles, dict):
        mapped = root_roles.get(source)
        if mapped:
            return str(mapped)
    return "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a complete skill catalog with privacy-safe links.")
    parser.add_argument(
        "--roots",
        default="local,antigravity,codex,agents",
        help="Comma-separated roots: local,antigravity,codex,agents, or explicit absolute/relative paths.",
    )
    parser.add_argument(
        "--workspace-root",
        default=os.getcwd(),
        help="Workspace root used to resolve local skills and relative outputs.",
    )
    parser.add_argument(
        "--output",
        default="",
        help="Optional output markdown file path. If omitted, no file is written unless provided.",
    )
    parser.add_argument(
        "--link-mode",
        choices=["alias", "relative", "none"],
        default="alias",
        help="Link style for catalog entries.",
    )
    parser.add_argument(
        "--stdout-only",
        action="store_true",
        help="Print to stdout only; never write output file.",
    )
    return parser.parse_args()


def default_roots(workspace_root: Path) -> Dict[str, Path]:
    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    roots = {
        "local": (workspace_root / ".agent" / "skills").resolve(),
        "antigravity": (Path.home() / ".gemini" / "antigravity" / "skills").resolve(),
        "codex": (codex_home / "skills").resolve(),
        "agents": (Path.home() / ".agents" / "skills").resolve(),
    }
    if looks_like_workspace_mirror_root(workspace_root):
        roots["workspace_mirror"] = workspace_root.resolve()
    return roots


def looks_like_workspace_mirror_root(workspace_root: Path) -> bool:
    if not workspace_root.exists() or not workspace_root.is_dir():
        return False
    sentinel_paths = [
        workspace_root / "skill_director" / "SKILL.md",
        workspace_root / ".system" / "skill-creator" / "SKILL.md",
    ]
    if not any(path.exists() for path in sentinel_paths):
        return False

    exported_skill_count = 0
    for child in workspace_root.iterdir():
        if child.name in {".agent", ".git", "__pycache__"}:
            continue
        if not child.is_dir():
            continue
        if (child / "SKILL.md").exists():
            exported_skill_count += 1
            continue
        if child.name in {".system", "codex-primary-runtime"}:
            exported_skill_count += sum(1 for nested in child.iterdir() if (nested / "SKILL.md").exists())
    return exported_skill_count >= 10


def resolve_roots(roots_arg: str, workspace_root: Path) -> List[RootSpec]:
    defaults = default_roots(workspace_root)
    out: List[RootSpec] = []

    for token in [t.strip() for t in roots_arg.split(",") if t.strip()]:
        if token in defaults:
            out.append(RootSpec(token, defaults[token]))
            continue

        p = Path(token).expanduser()
        if not p.is_absolute():
            p = (workspace_root / p).resolve()
        key = f"path{len(out)+1}"
        out.append(RootSpec(key, p))

    # dedupe by absolute path
    dedup: Dict[Path, RootSpec] = {}
    for spec in out:
        dedup[spec.path] = spec
    if "workspace_mirror" in defaults and defaults["workspace_mirror"] not in dedup:
        dedup[defaults["workspace_mirror"]] = RootSpec("workspace_mirror", defaults["workspace_mirror"])
    return list(dedup.values())


def parse_frontmatter(content: str) -> Dict[str, Any]:
    match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not match:
        return {}
    if yaml is None:
        return {}
    try:
        parsed = yaml.safe_load(match.group(1))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def parse_manifest(skill_dir: Path) -> Dict[str, Any]:
    for name in ("manifest.v2.json", "manifest.json"):
        p = skill_dir / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return {}


def parse_skill_file(file_path: Path, root: RootSpec) -> Dict[str, Any]:
    content = file_path.read_text(encoding="utf-8", errors="replace")
    frontmatter = parse_frontmatter(content)
    relative_skill_path = file_path.parent.relative_to(root.path).as_posix()
    inventory_role = classify_inventory_role(relative_skill_path)

    trigger = "See SKILL.md"
    trigger_match = re.search(r"## (?:When to use|Trigger|Activati)", content, re.IGNORECASE)
    if trigger_match:
        start = trigger_match.end()
        snippet = content[start:start + 300].strip().split("\n##")[0].strip()
        trigger = (snippet[:200] + "...") if len(snippet) > 200 else snippet.replace("\n", " ")

    return {
        "skill_id": relative_skill_path,
        "leaf_skill_id": file_path.parent.name,
        "relative_skill_path": relative_skill_path,
        "inventory_role": inventory_role,
        "root_role": classify_root_role(root.key),
        "name": frontmatter.get("name", file_path.parent.name),
        "description": frontmatter.get("description", "No description provided."),
        "trigger": trigger,
        "source": root.key,
        "path": file_path.resolve(),
        "manifest": parse_manifest(file_path.parent),
    }


def iter_skill_files(root: RootSpec) -> Iterable[Path]:
    if not root.path.exists():
        return
    for p in root.path.rglob("SKILL.md"):
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        yield p


def sanitize_node_id(name: str) -> str:
    base = re.sub(r"[^0-9A-Za-z_]", "_", name).strip("_") or "skill"
    return f"skill_{base}" if base[0].isdigit() else base


def pick_primary(copies: List[Dict[str, Any]]) -> Dict[str, Any]:
    return sorted(copies, key=lambda c: (ROOT_ORDER.get(c["source"], 99), str(c["path"])))[0]


def render_link(entry: Dict[str, Any], link_mode: str, workspace_root: Path) -> str:
    if link_mode == "none":
        return entry["name"]

    if link_mode == "alias":
        return f"[{entry['name']}](skills://{entry['source']}/{entry['skill_id']})"

    # relative
    path = Path(entry["path"])
    try:
        rel = path.relative_to(workspace_root)
        href = rel.as_posix()
    except Exception:
        href = f"{entry['source']}/{entry['skill_id']}/SKILL.md"
    return f"[{entry['name']}]({href})"


def generate_mermaid(aggregated: List[Dict[str, Any]]) -> str:
    graph = ["graph TD"]
    used: set[str] = set()
    node_ids: Dict[str, str] = {}

    for s in aggregated:
        base = sanitize_node_id(s["skill_id"])
        node = base
        i = 2
        while node in used:
            node = f"{base}_{i}"
            i += 1
        used.add(node)
        node_ids[s["skill_id"]] = node
        graph.append(f"    {node}[{s['name']}]")

    for s in aggregated:
        node = node_ids[s["skill_id"]]
        for inp in s.get("manifest", {}).get("inputs", []):
            event_type = str(inp.get("event_type", ""))
            if "system_log_error" in event_type:
                graph.append(f"    SystemLogs -->|error| {node}")
                continue
            if event_type.endswith("_finding"):
                source_skill = event_type[:-8]
                if source_skill in node_ids:
                    graph.append(f"    {node_ids[source_skill]} -->|{event_type}| {node}")

    return "\n".join(graph)


def build_output(aggregated: List[Dict[str, Any]], link_mode: str, workspace_root: Path) -> str:
    mermaid = generate_mermaid(aggregated)
    rows: List[str] = []
    role_counts: Dict[str, int] = {}
    for entry in aggregated:
        role = str(entry.get("inventory_role", "") or "standard")
        role_counts[role] = role_counts.get(role, 0) + 1

    for s in aggregated:
        link = render_link(s, link_mode, workspace_root)
        inputs = len(s.get("manifest", {}).get("inputs", []))
        outputs = len(s.get("manifest", {}).get("outputs", []))
        sources = ", ".join(s.get("sources", []))

        section = f"### {link}\n"
        section += f"**Sources**: {sources}\n"
        section += f"**Inventory Role**: {s.get('inventory_role', 'standard')}\n"
        section += f"**Connectivity**: Inputs={inputs} | Outputs={outputs}\n\n"
        section += f"**Description**:\n{s['description']}\n\n"
        section += f"**Trigger**:\n{s['trigger']}\n\n---\n"
        rows.append(section)

    output = f"# Omniscient Skill Catalog\n\nTotal Skills: {len(aggregated)}\n\n"
    if role_counts:
        role_line = ", ".join(f"{role}={count}" for role, count in sorted(role_counts.items()))
        output += f"Inventory Roles: {role_line}\n\n"
    output += "## Brain Graph\n\n"
    output += "```mermaid\n" + mermaid + "\n```\n\n"
    output += "".join(rows)
    return output


def main() -> int:
    args = parse_args()
    workspace_root = Path(args.workspace_root).expanduser().resolve()
    roots = resolve_roots(args.roots, workspace_root)

    discovered: List[Dict[str, Any]] = []
    for root in roots:
        if not root.path.exists():
            continue
        for skill_md in iter_skill_files(root):
            discovered.append(parse_skill_file(skill_md, root))

    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for entry in discovered:
        grouped.setdefault(entry["skill_id"], []).append(entry)

    aggregated: List[Dict[str, Any]] = []
    for skill_id, copies in grouped.items():
        primary = pick_primary(copies)
        primary["sources"] = sorted({c["source"] for c in copies}, key=lambda k: ROOT_ORDER.get(k, 99))
        aggregated.append(primary)

    aggregated.sort(key=lambda x: (x["name"].lower(), x["skill_id"].lower()))

    output = build_output(aggregated, args.link_mode, workspace_root)

    print(f"Scanning roots: {[f'{r.key}:{r.path}' for r in roots]}")
    print(f"Found {len(aggregated)} unique skills from {len(discovered)} copies.\n")
    print(output)

    if not args.stdout_only and args.output:
        output_path = Path(args.output).expanduser()
        if not output_path.is_absolute():
            output_path = (workspace_root / output_path).resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output, encoding="utf-8")
        print(f"\nCatalog saved to: {output_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
