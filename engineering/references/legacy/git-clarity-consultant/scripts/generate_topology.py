#!/usr/bin/env python3
"""
Git Clarity Consultant - Topology Generator

Generates mermaid diagrams showing:
- Branch hierarchy and ancestry
- Divergence points
- Remote tracking relationships
- Partner activity summary
"""

import subprocess
import json
from datetime import datetime, timedelta
from collections import defaultdict


def run_git(args: list[str]) -> str:
    """Run a git command and return stdout."""
    result = subprocess.run(
        ["git"] + args,
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout.strip()


def get_all_branches() -> dict:
    """Get all local and remote branches."""
    branches = {"local": [], "origin": [], "shared": []}
    
    raw = run_git(["branch", "-a", "--format=%(refname:short)"])
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("origin/"):
            branches["origin"].append(line)
        elif line.startswith("shared/"):
            branches["shared"].append(line)
        else:
            branches["local"].append(line)
    
    return branches


def get_recent_commits(days: int = 7) -> list[dict]:
    """Get commits from the last N days with author info."""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    raw = run_git([
        "log", "--all", f"--since={since}",
        "--pretty=format:%H|%an|%ad|%s",
        "--date=short"
    ])
    
    commits = []
    for line in raw.split("\n"):
        if not line:
            continue
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append({
                "hash": parts[0][:7],
                "author": parts[1],
                "date": parts[2],
                "subject": parts[3]
            })
    return commits


def get_partner_activity(commits: list[dict]) -> dict:
    """Summarize commits by author."""
    activity = defaultdict(lambda: {"commits": 0, "branches": set()})
    
    for commit in commits:
        author = commit["author"]
        activity[author]["commits"] += 1
    
    # Get branches per author
    for author in activity:
        raw = run_git([
            "log", "--all", "--author", author,
            "--format=%D", "-n", "50"
        ])
        for line in raw.split("\n"):
            for ref in line.split(","):
                ref = ref.strip()
                if ref and not ref.startswith("tag:"):
                    # Extract branch name
                    if " -> " in ref:
                        ref = ref.split(" -> ")[1]
                    activity[author]["branches"].add(ref)
    
    return {k: {"commits": v["commits"], "branches": list(v["branches"])} 
            for k, v in activity.items()}


def get_remote_sync_status() -> list[dict]:
    """Check sync status between origin and shared for common branches."""
    status = []
    
    # Skip fetch if it would block on SSH passphrase
    # Users can run 'git fetch --all' manually before invoking this skill
    # try:
    #     run_git(["fetch", "--all", "--quiet"])
    # except subprocess.CalledProcessError:
    #     pass
    
    # Check main branch sync
    for branch in ["main"]:
        for remote in ["origin", "shared"]:
            try:
                ahead_behind = run_git([
                    "rev-list", "--left-right", "--count",
                    f"HEAD...{remote}/{branch}"
                ])
                ahead, behind = map(int, ahead_behind.split())
                
                if ahead == 0 and behind == 0:
                    sync = "✅ Synced"
                elif behind > 0:
                    sync = f"⚠️ Behind by {behind} commits"
                else:
                    sync = f"📤 Ahead by {ahead} commits"
                
                status.append({
                    "remote": remote,
                    "branch": branch,
                    "status": sync,
                    "behind": behind
                })
            except subprocess.CalledProcessError:
                status.append({
                    "remote": remote,
                    "branch": branch,
                    "status": "❌ Not found",
                    "behind": -1
                })
    
    return status


def generate_mermaid_gitgraph() -> str:
    """Generate a mermaid gitGraph diagram."""
    # Get branch structure
    branches = get_all_branches()
    
    # Build a simplified gitGraph
    mermaid = ["```mermaid", "gitGraph"]
    mermaid.append('    commit id: "init"')
    
    # Add main branch commits
    try:
        main_commits = run_git(["log", "main", "--oneline", "-n", "3"])
        for line in reversed(main_commits.split("\n")):
            if line:
                hash_id = line.split()[0]
                mermaid.append(f'    commit id: "{hash_id}"')
    except subprocess.CalledProcessError:
        pass
    
    # Add other branches
    for branch in branches["local"]:
        if branch != "main" and branch != "HEAD":
            mermaid.append(f"    branch {branch}")
            try:
                commits = run_git(["log", branch, "--oneline", "-n", "2", "--not", "main"])
                for line in reversed(commits.split("\n")):
                    if line:
                        hash_id = line.split()[0]
                        mermaid.append(f'    commit id: "{hash_id}"')
            except subprocess.CalledProcessError:
                pass
            mermaid.append("    checkout main")
    
    mermaid.append("```")
    return "\n".join(mermaid)


def main():
    print("# 🗺️ Git Clarity Report\n")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Branch Topology
    print("## Branch Topology\n")
    print(generate_mermaid_gitgraph())
    print()
    
    # Partner Activity
    print("## Partner Activity (Last 7 Days)\n")
    commits = get_recent_commits(7)
    activity = get_partner_activity(commits)
    
    print("| Author | Commits | Active Branches |")
    print("| :--- | ---: | :--- |")
    for author, data in sorted(activity.items(), key=lambda x: x[1]["commits"], reverse=True):
        branches = ", ".join(f"`{b}`" for b in data["branches"][:3])
        if len(data["branches"]) > 3:
            branches += f" (+{len(data['branches']) - 3} more)"
        print(f"| {author} | {data['commits']} | {branches} |")
    print()
    
    # Remote Sync Status
    print("## Remote Sync Status\n")
    status = get_remote_sync_status()
    
    print("| Remote | Branch | Status |")
    print("| :--- | :--- | :--- |")
    for s in status:
        print(f"| `{s['remote']}` | `{s['branch']}` | {s['status']} |")
    print()
    
    # Emit Pulse Bus events (write to ecosystem_state.json)
    events = []
    for s in status:
        if s["behind"] > 0:
            events.append({
                "event": "repo:drift_detected",
                "payload": {
                    "remote": s["remote"],
                    "branch": s["branch"],
                    "behind_by": s["behind"]
                }
            })
    
    if events:
        print("## ⚠️ Pulse Bus Events Emitted\n")
        for e in events:
            print(f"- `{e['event']}`: {e['payload']}")


if __name__ == "__main__":
    main()
