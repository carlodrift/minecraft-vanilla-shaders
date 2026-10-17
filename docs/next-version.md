# What changes in 26.4 (snapshots)

The rest of this repository documents **26.3**. This page tracks what the **26.4 snapshots** change for shader packs, so packs can get ready before the release. Snapshots change every week, so everything here may still move.

Last checked: **26.4-snapshot-4** (resource pack format **100**).

## Still true

- **The compiler options and include resolution are unchanged** *(code)*: shaderc, Vulkan 1.2 target, `#include` by identifier, `layout(location)`, `GL_ARB_separate_shader_objects`.
- **Every rule of [Writing shaders](writing-shaders.md) still holds:** all 43 experiments and 5 examples give their expected verdict with `tools/mcshaders check` against snapshot 4. They have not been loaded in game on 26.4 yet.

## What breaks packs

| Change | Impact | What to do |
|---|---|---|
| `core/screenquad.vsh` is removed, replaced by `core/screentriangle.vsh` | every post effect that uses `minecraft:core/screenquad` fails when first used, and that disables all packs | ship your own full-screen vertex shader ([Post effects](post-effects.md#the-vertex-shader)): it works in 26.3 and 26.4 |
| OIT samplers `Coeff0`, `Coeff1` renamed `Bins0`, `Bins1`; the OIT algorithm changes (depth bins) | a shader that declares `Coeff0`/`Coeff1` itself fails, since declared samplers must exist | include `minecraft:oit.glsl` instead of copying its code |
| OIT defines `OIT_WAVELET_RANK`, `OIT_COEFF_COUNT`, `OIT_COEFF_ATTACHMENT_COUNT` replaced by `OIT_NUMBER_OF_DEPTH_BINS`, `OIT_TRANSMITTANCE_TARGET_COUNT` | code testing the old names silently takes the wrong branch | same: rely on the vanilla OIT includes |
| Clouds no longer go through OIT: `core/clouds` lost its `OIT_*` variants, and a new `core/blit_clouds` composites them | packs that changed cloud transparency | start again from the 26.4 `clouds` / `blit_clouds` |
| Resource pack format 97 → 100 | the pack shows as incompatible | `"max_format": 100` (or a range) |

## New

- **`core/terrain` with `IMPROVED_FOG`**: three new samplers, `SkySampler`, `CloudsSampler` and `CloudsDepthSampler`. They are provided exactly in the pipelines that define `IMPROVED_FOG`: the `*_improved_fog*` terrain pipelines and `oit_accumulate_terrain*`. Declare them under `#ifdef IMPROVED_FOG`.
- **New programs:** `core/sky_occluder` (the lower part of the overworld sky, according to the [minecraft.wiki history](https://minecraft.wiki/w/Shader#History)), `core/blit_clouds`, `core/screentriangle`.
- **New include:** `include/fullscreen_triangle.glsl`.
- **New pipelines:** `*_with_depth_attachment` variants of the sky pipelines, `end_portal_gui`, `blit_sky`, and the improved-fog terrain pipelines. One of them is named `solid_terrain_improved_for`, with a typo in the game.
- **In the game code, pipeline validation moved to a new class, `PipelineValidator`**, with the same rules plus limits on the number of vertex attributes and vertex buffers *(code)*.

## How this page is made

```sh
python3 tools/vanilla.py diff 26.3 26.4-snapshot-4            # files
MC_VERSION=26.4-snapshot-4 tools/mcshaders pipelines           # pipelines, compared with reference/26.3/pipelines.json
```

`tools/mcshaders` works with both versions: it adapts to the classes that moved package in 26.4.
