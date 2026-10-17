# Unreal Game Factory — OmniForge 4.6

## Natural-language workflow

In the OmniForge chat, describe the game and its core loop. Example:

> Build a playable Unreal Engine 5 zombie survival game with harvesting, crafting, barricade building, zombie pursuit, day/night, escalating night hordes, save/load, and a Windows build. Add the systems to the project, compile it, fix compiler errors, and report anything that still blocks completion.

The deterministic fallback routes Unreal/game creation requests to the `unreal_game` registered tool. The factory creates a separate project under `workspace/OmniForgeGames/<ProjectName>/` rather than overwriting an existing project.

## Generated baseline systems

- Unreal `.uproject`, game/editor targets, module build rules, source files, and input/configuration.
- First-person movement and mouse look, stamina-based sprint, health, melee attacks, harvesting, wood/stone counters, and a simple barricade placement action.
- Runtime-generated primitive ground/props/resources, a basic day/night light cycle, zombie pursuit and contact damage, and increasingly large night horde waves.
- HUD text, player-progress save/load for health, stamina, resources, and player location (F5/F9).
- A manifest, project readme, Windows build helper, and static generated-project verifier.

The baseline uses built-in primitive engine meshes as placeholders. It does not bundle bespoke art, animation, audio, or paid assets.

## Automatic implementation and build recovery

When `UNREAL_BUILD_TOOL` is configured, OmniForge runs a brief-driven coding pass against the generated project, invokes the fixed Unreal build profile, and attempts one targeted coding repair if the first build fails. It runs the build verifier again before marking `build_verified=true`. Build output and repair results are saved in the game manifest. If Unreal is not installed/configured, the factory reports `ENGINE_OR_BUILD_TOOL_NOT_CONFIGURED` and does not claim the project compiled.

## What “complete” means here

OmniForge can create the project files and attempt to implement and compile a playable vertical slice. It cannot guarantee a finished commercial game from a single prompt. Full production still requires playtesting and balancing, authored character/environment assets, polished animation and audio, complete crafting/economy/progression, robust world persistence, multiplayer/network replication, performance profiling, platform packaging, and QA. The generated C++ source has not been compiled in the development environment used to prepare this release.

## Local prerequisites

- Unreal Engine version compatible with the generated project (default association: 5.4; configure a version installed locally).
- Visual Studio 2022 with the Game development with C++ workload on Windows.
- `UNREAL_BUILD_TOOL` configured in `.env` to the appropriate Unreal build tool or wrapper if automatic compilation is wanted.
- A configured local Ollama coding model for brief-driven code generation and targeted repair.

No engine installation or model assets are bundled in the OmniForge ZIP.
