#!/usr/bin/env python3
import os, json, datetime, pathlib

def main():
    today = datetime.date.today().isoformat()
    base = pathlib.Path.home() / "Desktop" / "Job Apply Runs" / today
    artifacts = base / "artifacts"
    jobs = base / "artifacts" / "jobs"
    extracted = base / "artifacts" / "extracted"

    for p in [artifacts, jobs, extracted]:
        p.mkdir(parents=True, exist_ok=True)

    # Seed empty files
    (base / "artifacts" / "attempt_log.md").touch(exist_ok=True)
    (base / "artifacts" / "conflicts.md").touch(exist_ok=True)

    profile_path = base / "artifacts" / "master_profile.json"
    if not profile_path.exists():
        profile_path.write_text(json.dumps({"status":"draft","source_folder":"~/Desktop/Resumes For Agents"}, indent=2))

    print(str(base))

if __name__ == "__main__":
    main()
