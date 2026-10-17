# OmniForge AI v4.7 — Autonomous Project Delivery Pipeline

OmniForge is a chat-first, local-first autonomous development environment. Describe an outcome in chat; it plans with registered tools, executes supported workflows, verifies results, and attempts bounded recovery.

## Start on Windows
1. Run `Setup-OmniForge.bat`.
2. Configure `.env` for local Ollama. Blender and TripoSR are optional dependencies for their workflows. Unreal Engine 5.x and Visual Studio 2022 are needed to compile/package generated Unreal projects.
3. Run `Launch-OmniForge.bat` and use the chat interface.

## v4.7 highlights
- **Delivery pipeline:** generated Unreal projects now include staged asset intake, an Unreal Editor Python importer and editable level blockout generator, a structured QA checklist, and a Windows build/cook/package runner.
- **Truthful stage reporting:** import, visual review, functional tests, and packaging remain explicitly unverified until their real engine-dependent steps run.
- **Delivery API:** `/api/unreal/deliver` prepares the pipeline for an existing project; `/api/unreal/delivery-tools` detects the local engine/toolchain.

## v4.6 foundation
- **Unreal game project factory:** ask for a zombie survival game and OmniForge generates a complete C++ project scaffold in `workspace/OmniForgeGames/` with player controls, health/stamina, melee combat, resource harvesting, inventory counters, barricade placement, primitive procedural terrain/props, zombie pursuit/attacks, a day/night lighting clock, escalating night hordes, and player save/load. Includes `.uproject`, C++ source, input configuration, build instructions, and a manifest.
- **Capability research:** optionally searches public GitHub repository metadata for solutions when the request explicitly asks for online research. It never installs arbitrary repositories automatically.
- **Capability development workflow:** uses the local coding agent to create an adapter candidate and tests in a separate workspace folder. It registers candidate metadata only after the configured test profile passes.
- **Verified capability registry:** records built-in capabilities and verified adapter candidates.
- **Candidate smoke-test gate:** smoke tests use a restricted assertion-only Python syntax; imports, attribute access, file/network/process APIs, loops, and arbitrary function calls are rejected. This is a narrow gate, not a general security sandbox for arbitrary executable code.
- Existing persistent chat memory, bounded self-correction, dependency setup, coding/build workflows, 3D asset production, and local-first behavior remain.

## Create a game
In chat, say something like:
> Build a playable Unreal Engine 5 zombie survival game with harvesting, crafting, barricade building, zombies, day/night, and increasingly difficult night hordes. Generate the project files and verify the project structure.

OmniForge writes the project under `workspace/OmniForgeGames/<ProjectName>/`. Open its `.uproject` in Unreal Engine. On Windows, generate Visual Studio project files and build the Editor target before packaging.

## Important limits
The Unreal factory creates a **playable-systems vertical-slice scaffold**, not a finished AAA/commercial game. The generated source and project structure are statically checked, but no Unreal Engine compiler/editor was available in this build environment, so actual compilation and packaging are not claimed. It does not yet generate high-quality bespoke art, polished animation/audio, world-state persistence, multiplayer/network replication, complete progression/economy, or a finished open-world map. Unreal Engine must be installed separately. No paid APIs or assets are required by OmniForge itself.

Capability development uses a separate candidate workspace and the existing local coding agent. A registered candidate is not automatically imported into OmniForge's main process or granted execution permissions; it must be reviewed and mapped to a fixed tool handler before the autonomous planner can execute it. This is deliberate supply-chain protection.

See `PROJECT_DELIVERY_4.7.md`, `CAPABILITY_EVOLUTION_4.6.md`, `UNREAL_GAME_FACTORY_4.6.md`, and `SELF_HEALING_4.5.md`.
