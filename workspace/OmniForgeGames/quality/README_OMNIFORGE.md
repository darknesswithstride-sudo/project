# quality — OmniForge Unreal survival prototype

Brief: Persistent project brain notes:
- [user_goal] Build a complete Unreal Engine 5 zombie survival game. Create the game project, player, zombies, resource gathering, inventory, crafting, base building, day/night cycle, escalating night hordes, save system, environment, and UI. Implement the systems in the project itself, run the available verification checks, fix errors, and continue until the project builds or you identify a genuine blocker. make a custom map, analyze 7 days to die as reference, there should be 7 unique biomes, all meshes and artwork be unique but AAA title quality

Build a complete Unreal Engine 5 zombie survival game. Create the game project, player, zombies, resource gathering, inventory, crafting, base building, day/night cycle, escalating night hordes, save system, environment, and UI. Implement the systems in the project itself, run the available verification checks, fix errors, and continue until the project builds or you identify a genuine blocker. make a custom map, analyze 7 days to die as reference, there should be 7 unique biomes, all meshes and artwork be unique but AAA title quality

Generated project includes C++ source for player movement/health/stamina, melee combat, harvesting, wood/stone resources, barricade placement, chasing/attacking zombies, runtime-generated primitive terrain/resources, and night horde waves. The HUD and keyboard/mouse input are configured.

## Build on Windows
1. Install Unreal Engine 5.x through Epic Games Launcher and Visual Studio 2022 with the Game development with C++ workload.
2. Right-click `quality.uproject` → Generate Visual Studio project files.
3. Build the `qualityEditor` Development Editor target, then open the project in Unreal Editor.
4. The GameMode builds the prototype play area at runtime. Use Platforms → Windows → Package Project to make a Windows build.

Controls: WASD move, mouse look, LMB attack, E harvest, B barricade (5 wood), Shift sprint, F5 save player progress, F9 load saved player progress. Save data includes health, stamina, wood, stone, and player location.

## Honest status
This is a playable-systems vertical-slice scaffold, not a finished AAA/commercial game. Static project checks can be run without Unreal, but compilation, editor launch, packaging, final art/animation/audio, save/load, multiplayer, level navigation and balance require testing in your local Unreal installation. No Unreal Engine or paid assets are bundled.
