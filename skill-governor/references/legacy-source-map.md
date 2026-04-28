# Legacy Source Map

This map preserves every old skill as source intelligence during the consolidation.

Migration mode: `additive_overlay`

Rules:
- Do not delete old skills during this phase.
- Treat old skills as detailed references until compatibility stubs are generated.
- Use `legacy-source-map.json` as the machine-readable source of truth.
- If a skill appears in both a core capability and a project profile, keep the general behavior in the core skill and the project-specific behavior in the profile.

Current core target count: `18`

Current preserved legacy map:
- `watcher`: ecosystem intelligence, inventory, drift, and workspace goals
- `skill-governor`: evolution, portability, hygiene, mirror, and regression gates
- `skill-builder`: skill/plugin creation, installation, and tool generation
- `engineering`: software execution, QA, audit, design, receipts, readiness
- `reliability`: incidents, runtime failures, performance, async, lifecycle, logs
- `security`: AppSec, threat modeling, privacy, ownership, macOS, network hardening
- `git-release`: git, repo sync, release, CI, comments, issues
- `research`: currentness, official docs, web grounding, BI, SOTA
- `knowledge`: wisdom, knowledge graphs, context, experiment ledgers
- `ml`: MLX, model optimization, model logistics, quantization, tensor, quantum
- `rag-data`: RAG, schemas, contracts, telemetry, evals, compatibility
- `ux`: UX, visual systems, handoff, model UX
- `automation`: browser, desktop, screenshot, Atlas, Chronicle
- `artifacts`: PDF, slides, spreadsheets, image/logo assets, ChatGPT Apps
- `apple`: Apple bootstrap, Xcode harness, Apple release
- `edge-platforms`: Jarvis, OpenClaw, Pi, Wi-Fi sensing, Foundry recovery
- `pfe-profile`: Project Free Energy-specific runtime and product wisdom
- `special-missions`: bounded autonomous mission packs
