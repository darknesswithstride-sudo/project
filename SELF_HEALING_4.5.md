# OmniForge AI v4.5 — Self-Healing Autonomous Agent

## What changed

OmniForge now treats registered-tool failures as recovery opportunities instead of assuming that a returned response means success. Failed actions are recorded, classified, and passed through bounded recovery strategies.

### Recovery flow

1. Execute the selected registered tool and inspect its result/status/exit code.
2. When output resembles a missing Python dependency, attempt setup from a recognized `requirements.txt` or `pyproject.toml` manifest, then retry that action once if setup succeeded.
3. When a coding or build action fails verification, run a targeted repair loop with the original user request and captured failure evidence.
4. Independently rerun the configured verifier before marking recovery successful.
5. If recovery cannot verify success, collect local diagnostics, preserve the failure details in the job manifest, and report a blocker rather than claiming success.
6. The repair loop restores the original pre-repair file snapshot when all repair candidates fail verification.

## Safety and limits

- Recovery uses only registered OmniForge tools and fixed build profiles; the language model cannot issue arbitrary shell commands through this engine.
- Recovery is bounded. Missing dependencies get at most one setup-and-retry sequence; coding/build failures get a targeted repair with two attempts and an independent verification.
- Python dependency installation can run the package manager against a project's declared manifest. Only run projects and manifests you trust.
- npm lifecycle scripts are not executed automatically.
- System-level prerequisites such as Blender, Unreal Engine, CUDA drivers, or model weights may require user action. OmniForge diagnoses these blockers but does not silently download arbitrary executables or bypass installer prompts.
- A passing compile/test profile verifies only that profile. It does not prove every feature behaves correctly.
- No agent can guarantee completion when hardware, credentials, proprietary software, external services, model capability, or missing inputs block the task.

## Audit trail

Each autonomous job stores original action results, recovery attempts, dependency setup outcomes, targeted repair output, verification results, and final blockers in its JSON job manifest under `workspace/omniforge_assets/autonomous_runs/`.

## Version

4.5.0 — Self-Healing Autonomous Agent
