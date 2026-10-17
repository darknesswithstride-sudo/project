# OmniForge v3.9 — implementation notes

## Five requested upgrades

### 1. Local multimodal image understanding
`app/vision_director.py` validates workspace paths, file types, and image size, then sends base64 image data only to the configured local Ollama chat endpoint. It asks for structured JSON with material cues, visible features, uncertainty, modeling steps, surface profile, and budgets. This is a vision-guided recommendation stage, not a new 3D reconstruction model.

### 2. Optional advanced 3D backends
`app/advanced_3d.py` inventories TripoSR, TRELLIS, and Hunyuan3D installations using environment variables. It deliberately does not install repositories or download model weights automatically. GPU memory, Windows compatibility, dependencies, model licenses, and output conversion remain per-machine checks.

### 3. Disposable-copy build verification
`app/sandbox_runner.py` copies a project while excluding Git metadata, virtual environments, caches, node_modules, build outputs, and common secrets, then runs a fixed verification profile and deletes the copy by default. This is workspace-level containment only, **not OS-level sandboxing**. Build/test code is executable host code; untrusted repositories require a separate VM/container with appropriate permissions and network limits.

### 4. Git worktrees and reviewable diffs
`app/worktrees.py` creates named branches in managed worktrees and offers status/diff/removal operations. The UI keeps the worktree path visible for review. Worktree changes are not automatically merged into the primary branch.

### 5. Repeatable model smoke benchmark
`app/benchmark_suite.py` runs five fixed prompts against the configured local model, saves each answer, elapsed time, and a transparent heuristic score. The score is not an objective general intelligence measure; it is an inexpensive baseline for same-model/same-hardware regression checks.

## Validation boundary
Automated tests cover request logic, path validation, backend inventory, Git worktree lifecycle, and benchmark case stability. Actual vision inference requires a compatible local vision model; TRELLIS/Hunyuan3D require their own GPU stack and model weights; real project builds depend on installed toolchains. None of those hardware-dependent tasks is claimed to have been executed merely because the API unit tests pass.
