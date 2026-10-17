# Minecraft vanilla shaders (26.3)

A guide to writing core and post-processing shaders for Minecraft Java Edition **26.3** with a resource pack, no mods.

Every statement here is either checked against the game's code, reproduced by an [experiment](experiments/) you can run yourself, or explicitly marked as unverified.

## Contents

- [Writing shaders for 26.3](docs/writing-shaders.md): how the game loads shaders, and the rules a shader must follow to load.
- [Post effects](docs/post-effects.md): `end_of_frame`, `/posteffect`, the JSON format, samplers, uniforms and depth.
- [How a frame is drawn](docs/rendering.md): the drawing order, and what each core program draws, with screenshots.
- [Techniques](docs/techniques.md): texture markers, telling GUI from world, translucency with Improved Transparency, tagging pixels for post effects, replacing includes, animating, depth, displacement.
- [Porting to 26.3](docs/porting.md): method, checklist, and what changed version by version since 1.21.8.
- [What changes in 26.4](docs/next-version.md): what the 26.4 snapshots break or add, tracked ahead of the release.
- Reference, generated from the game:
  - [Core shader programs](docs/reference/core-shaders.md): for each program, its pipelines, defines, available uniforms (with the `#ifdef` that guards each one) and vertex inputs.
  - [Uniforms](docs/reference/uniforms.md): every uniform block (with its std140 layout) and sampler.
  - [Render pipelines](docs/reference/pipelines.md): all 192 of them.
- [Examples](examples/): complete packs with screenshots (terrain wave, depth outlines, emissive entities, emissive glow, atmosphere).
- [Experiments](experiments/) and their [results](experiments/RESULTS.md), in game on OpenGL and Vulkan.
- [Tools](tools/): `mcshaders check` validates a pack the way the game does, without launching it.

## Quick start

Requirements: macOS, Java 25+, Python 3, and Minecraft 26.3 installed once with the official launcher.

```sh
tools/mcshaders check path/to/your/pack        # compile and validate your shaders like the game does
python3 tools/examples.py emissive-glow --out ~/Desktop   # build an example pack to try in game
```

## Status

Tested on macOS (Apple M4 Pro): OpenGL 4.1 Metal and Vulkan through MoltenVK. Other GPUs and drivers are not covered yet. The tools run on macOS only for now.

A [GitHub Actions workflow](.github/workflows/check.yml) downloads the 26.3 client from Mojang. It then checks, without launching the game, that vanilla shaders and every example pass `tools/mcshaders check`, that every experiment still gets its expected verdict, that the generated reference is up to date, and that every link resolves. The in-game results come from local runs and are recorded in [RESULTS.md](experiments/RESULTS.md).

## License

Tools under MIT, documentation under CC BY 4.0, example and experiment shader code under CC0. Details in [LICENSE.md](LICENSE.md).

Not an official Minecraft product. Not approved by or associated with Mojang or Microsoft. This repository contains no vanilla Minecraft files: the tools read them from your own installation.
