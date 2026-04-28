#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
from pathlib import Path


def default_run_root() -> Path:
    env_root = os.environ.get("JOB_APPLY_RUN_ROOT")
    if env_root:
        return Path(env_root).expanduser()
    return Path.home() / "Desktop" / "Job Apply Runs" / "current"


def resolve_artifacts_root(run_root: Path) -> Path:
    if (run_root / "jobs").exists() and (run_root / "master_profile.json").exists():
        return run_root
    return run_root / "artifacts"


def default_maker_script() -> Path:
    env_script = os.environ.get("JOB_APPLY_MAKER_SCRIPT")
    if env_script:
        return Path(env_script).expanduser()

    local = Path(__file__).resolve().parent / "ag_jobapply_make_resume.py"
    if local.exists():
        return local

    codex_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))).expanduser()
    codex = codex_home / "skills" / "job-apply-autonomous" / "scripts" / "ag_jobapply_make_resume.py"
    if codex.exists():
        return codex

    antigravity = Path.home() / ".gemini" / "antigravity" / "skills" / "job-apply-autonomous" / "scripts" / "ag_jobapply_make_resume.py"
    return antigravity


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate tailored resumes for captured job folders.")
    parser.add_argument("--run-root", default=str(default_run_root()), help="Run root or artifacts root.")
    parser.add_argument("--jobs-dir", default="", help="Explicit jobs directory override.")
    parser.add_argument("--profile-path", default="", help="Explicit master_profile.json override.")
    parser.add_argument("--maker-script", default=str(default_maker_script()), help="Path to ag_jobapply_make_resume.py")
    return parser.parse_args()


def generate_resumes() -> int:
    args = parse_args()

    run_root = Path(args.run_root).expanduser()
    artifacts_root = resolve_artifacts_root(run_root)

    jobs_dir = Path(args.jobs_dir).expanduser() if args.jobs_dir else artifacts_root / "jobs"
    profile_path = Path(args.profile_path).expanduser() if args.profile_path else artifacts_root / "master_profile.json"
    maker_script = Path(args.maker_script).expanduser()

    if not jobs_dir.exists():
        print(f"Jobs directory not found: {jobs_dir}")
        return 2
    if not profile_path.exists():
        print(f"Profile not found: {profile_path}")
        return 2
    if not maker_script.exists():
        print(f"Maker script not found: {maker_script}")
        return 2

    job_dirs = [d for d in sorted(jobs_dir.iterdir()) if d.is_dir()]
    print(f"Found {len(job_dirs)} job directories.")

    failures = 0
    for job_dir in job_dirs:
        job_json_path = job_dir / "job.json"
        if not job_json_path.exists():
            print(f"Skipping {job_dir.name}: job.json not found")
            continue

        try:
            job_data = json.loads(job_json_path.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Error reading {job_json_path}: {exc}")
            failures += 1
            continue

        context_lines = [job_data.get("role", ""), job_data.get("company", "")]
        highlights = job_data.get("highlights", [])
        if isinstance(highlights, list):
            context_lines.extend(str(h) for h in highlights)
        elif isinstance(highlights, str):
            context_lines.append(highlights)

        context_path = job_dir / "context.txt"
        context_path.write_text("\n".join(context_lines), encoding="utf-8")

        out_pdf = job_dir / "resume.pdf"
        cmd = [
            "python3",
            str(maker_script),
            "--profile",
            str(profile_path),
            "--posting",
            str(context_path),
            "--out",
            str(out_pdf),
        ]

        print(f"Generating resume for {job_dir.name}...")
        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            print(f"  -> Generated: {out_pdf}")
        except subprocess.CalledProcessError as exc:
            print(f"  -> FAILED: {exc.stderr.strip() or exc.stdout.strip()}")
            failures += 1

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(generate_resumes())
