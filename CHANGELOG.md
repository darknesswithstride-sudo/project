# Changelog

## 4.7.0 — Project Delivery Pipeline
- Added a delivery orchestrator for generated Unreal projects: staged asset intake, editor-side import tasks, programmatic level blockout construction, QA checklist, and Windows build/cook/package script generation.
- Generated game tasks now automatically prepare delivery artifacts after project generation/build attempts.
- Added `/api/unreal/deliver` and `/api/unreal/delivery-tools` endpoints.
- Explicit status fields distinguish generated scripts from actual imports, visual review, functional tests, and package builds.
- Added automated tests for delivery preparation, workspace boundary enforcement, and asset staging.
- Limitations: Unreal Editor execution, rendered screenshot inspection, game functional testing and packaging require a configured local Unreal installation and have not been executed in this environment.


## 4.7.0 — Capability Evolution & Unreal Game Factory
- Added capability research, candidate adapter development, restricted smoke-test verification, and a metadata registry that keeps new candidates inactive until reviewed and mapped to a fixed handler.
- Added natural-language routing to a C++ Unreal Engine survival-game project factory.
- Generated game projects now include player movement/health/stamina, melee combat, resource harvesting, barricade placement, zombie pursuit/contact damage, day/night lighting, escalating night hordes, HUD, and F5/F9 player-progress save/load.
- Added optional brief-driven coding pass, Unreal build attempt, and one bounded targeted repair/rebuild when a local Unreal build tool and coding model are configured.
- Added explicit generated-vs-compiled status reporting and local-only limitations.
- Hardened capability smoke tests to a restricted assertion-oriented syntax rather than executing arbitrary candidate source.


## 4.7.0 — Capability Evolution & Unreal Game Factory
- Added a chat-routable Unreal Engine C++ survival-game project generator.
- Generated project includes player movement/health/stamina/melee, resource harvesting, barricade placement, zombie chase/attack behavior, procedural primitive test environment, day/night lighting clock, night horde escalation, HUD, project configuration, and build guide.
- Added capability research using optional public GitHub metadata search.
- Added candidate adapter development in a separate workspace directory using the local coding agent and test verification.
- Added verified capability registry and restricted smoke-test promotion API.
- Added `/api/capabilities`, `/api/capabilities/research`, `/api/capabilities/register-verified`, and `/api/unreal/installation`.
- Updated chat welcome prompts for Unreal project creation and capability discovery.
- Verified 81 automated tests, Python compilation, and generated-project static validation.
- Unreal Engine compilation/editor launch, TripoSR inference, Blender rendering, and Windows game packaging were not run in this environment.
