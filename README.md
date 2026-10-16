# Minecraft vanilla shaders (26.3)

A guide to writing core and post-processing shaders for Minecraft Java Edition **26.3** with a resource pack, no mods.

Every statement here is either checked against the game's code, reproduced by an [experiment](experiments/) you can run yourself, or explicitly marked as unverified.

## Contents

- [Writing shaders for 26.3](docs/writing-shaders.md): how the game loads shaders, and the rules a shader must follow to load.
- Reference, generated from the game:
  - [Core shader programs](docs/reference/core-shaders.md): for each program, its pipelines, defines, available uniforms (with the `#ifdef` that guards each one) and vertex inputs.
  - [Uniforms](docs/reference/uniforms.md): every uniform block (with its std140 layout) and sampler.
  - [Render pipelines](docs/reference/pipelines.md): all 192 of them.
- [Experiments](experiments/) and their [results](experiments/RESULTS.md), in game on OpenGL and Vulkan.
- [Tools](tools/): `mcshaders check` validates a pack the way the game does, without launching it.

## Status

Work in progress. Tested on macOS (Apple M4 Pro): OpenGL 4.1 Metal and Vulkan through MoltenVK. Other GPUs and drivers are not covered yet.
