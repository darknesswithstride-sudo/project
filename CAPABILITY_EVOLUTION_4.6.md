# OmniForge AI 4.6 — Capability Evolution

## Research → candidate → verification → registry

- OmniForge can inspect its built-in capability registry before proposing new integrations.
- Online repository research is optional and limited to public GitHub repository metadata; it does not clone or install repositories automatically.
- The local coding agent can create an adapter candidate in `workspace/omniforge_assets/capability_sandbox/` with adapter source, deterministic tests, and a capability note.
- A candidate enters the metadata registry only after its configured test profile succeeds. It is marked inactive and unavailable for planning until a maintainer reviews it and maps it to a fixed, permissioned tool handler.
- The separate smoke-test registration endpoint permits only a small assertion-oriented Python syntax: no imports, loops, attribute access, file/network/process APIs, or arbitrary function calls. The smoke test runs in isolated Python mode with a temporary working directory and a timeout. This restricted runner is a risk-reduction measure, not a general-purpose OS sandbox.

## Why new integrations are not silently activated

Passing a smoke test does not establish that a tool is secure, licensed, compatible, or fit for production. Automatic imports or execution permissions would let a generated candidate expand its own privileges. OmniForge therefore records verified candidate metadata without allowing a candidate to become executable until a fixed handler and explicit review are in place.

## Local-first guarantees

- No paid AI API is required.
- Local planning and code generation require a configured Ollama model.
- Online research only occurs when requested by the task/planner.
- Tool selection remains an explicit allowlist; the model cannot submit arbitrary shell commands.
