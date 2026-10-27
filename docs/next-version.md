# What changes in 26.4 (snapshots)

The rest of this repository documents **26.3**. This page tracks what the **26.4 snapshots** change for shader packs, so packs can get ready before the release. Snapshots change every week, so everything here may still move.

Last checked: **26.4-snapshot-6** (resource pack format **101**).

## Still true

- **The compiler options and include resolution are unchanged** *(code)*: shaderc, Vulkan 1.2 target, `#include` by identifier, `layout(location)`, `GL_ARB_separate_shader_objects`.
- **Every rule of [Writing shaders](writing-shaders.md) still holds:** all 54 experiments and 14 examples give their expected verdict with `tools/mcshaders check` against snapshots 4, 5 and 6. The examples are rebuilt from each version's own vanilla files, so this says their edits still apply, not that a copy of a 26.3 file still works (see the text shader below). They have not been loaded in game on 26.4 yet.

## What breaks packs

| Change | Impact | What to do |
|---|---|---|
| `core/screenquad.vsh` is removed, replaced by `core/screentriangle.vsh` | every post effect that uses `minecraft:core/screenquad` fails when first used, and that disables all packs | ship your own full-screen vertex shader ([Post effects](post-effects.md#the-vertex-shader)): it works in 26.3 and 26.4 |
| OIT samplers `Coeff0`, `Coeff1` renamed `Bins0`, `Bins1`; the OIT algorithm changes (depth bins) | a shader that declares `Coeff0`/`Coeff1` itself fails, since declared samplers must exist | include `minecraft:oit.glsl` instead of copying its code |
| OIT defines `OIT_WAVELET_RANK`, `OIT_COEFF_COUNT`, `OIT_COEFF_ATTACHMENT_COUNT` replaced by `OIT_NUMBER_OF_DEPTH_BINS`, `OIT_TRANSMITTANCE_TARGET_COUNT` | code testing the old names silently takes the wrong branch | same: rely on the vanilla OIT includes |
| Clouds no longer go through OIT: `core/clouds` lost its `OIT_*` variants, and a new `core/blit_clouds` composites them | packs that changed cloud transparency | start again from the 26.4 `clouds` / `blit_clouds` |
| `core/text` no longer gets the `IS_GUI` and `IS_SEE_THROUGH` defines (snapshot 5). Its world pipelines define `AFFECTED_BY_FOG_AND_LIGHT` instead, and only those have `Sampler2` (the lightmap) and `UV2` | a 26.3 `text.vsh` or `text.fsh` tests `!defined(IS_GUI) && !defined(IS_SEE_THROUGH)`, so it declares `UV2` and `Sampler2` in the GUI and see-through pipelines, which don't provide them: the pack fails to load (`mcshaders check` on the 26.3 files: "vertex attribute UV2 is not in the pipeline's vertex format") | test `AFFECTED_BY_FOG_AND_LIGHT` in 26.4, or start from the 26.4 files |
| `core/particle` no longer gets `Sampler2` in its `OIT_ALPHA_ONLY` variants (snapshot 5) | a `particle.vsh` that declares `Sampler2` unconditionally, like 26.3's, fails in those pipelines (`mcshaders check`: "uniform Sampler2 is not provided by this pipeline") | declare it under `#ifndef OIT_ALPHA_ONLY`, as the 26.4 file does |
| Resource pack format 97 → 100 (snapshots 4 and 5) → 101 (snapshot 6) | the pack shows as incompatible | `"max_format": 101` (or a range) |

## New

- **`core/terrain` with `IMPROVED_FOG`**: three new samplers, `SkySampler`, `CloudsSampler` and `CloudsDepthSampler`. They are provided exactly in the pipelines that define `IMPROVED_FOG`: the `*_improved_fog*` terrain pipelines and `oit_accumulate_terrain*`. Declare them under `#ifdef IMPROVED_FOG`.
- **New programs:** `core/sky_occluder` (the lower part of the overworld sky, according to the [minecraft.wiki history](https://minecraft.wiki/w/Shader#History)), `core/blit_clouds`, `core/screentriangle`.
- **New include:** `include/fullscreen_triangle.glsl`.
- **New pipelines:** `end_portal_gui`, `blit_sky`, `blit_clouds`, `sky_occluder`, and the improved-fog terrain pipelines.
- **Most pipelines are renamed** (snapshot 5): `solid_terrain` is now `terrainsolid`, `cutout_terrain` is `terraincutout`, `sky` is `sky_disc`, `text` is `text_world`, `gui_text` is `text_gui`, `opaque_particle` is `particles_opaque`… Packs name programs, not pipelines, so this only matters to tools and documentation.
- **Debug shapes no longer go through OIT:** `core/position_color` and `core/debug_point` lost their `OIT_*` pipelines, and `core/debug_point` is gone.
- **In the game code, pipeline validation moved to a new class, `PipelineValidator`**, with the same rules plus limits on the number of vertex attributes and vertex buffers *(code)*.
- **In the game code, most pipelines are built from parameters** (snapshot 5) *(code)*: `RenderPipelines` moved to `net.minecraft.client.renderer.pipeline`, and lost its fixed lists. The game compiles `staticPipelinesToPrecompile()` and `dynamicPipelinesToPrecompile(context)`, where the context holds the options that change pipelines: Improved Transparency, multidraw terrain, and the cloud quality. From snapshot 6, those lists hold one entry per pipeline and render subpass.

## How this page is made

```sh
python3 tools/snapshot_report.py 26.3 26.4-snapshot-6         # everything below, in Markdown
python3 tools/vanilla.py diff 26.4-snapshot-5 26.4-snapshot-6  # files, between two snapshots
MC_VERSION=26.4-snapshot-6 tools/mcshaders pipelines           # pipelines, compared with reference/26.3/pipelines.json
```

`tools/mcshaders` works with 26.3 and the 26.4 snapshots: it adapts its imports to the classes that moved package, and `tools/src/GamePipelines.java` lists the pipelines with whichever API the version has. With each API change, the snapshot watch report says that the tools need updating.

Every week, the [snapshot watch workflow](../.github/workflows/snapshot.yml) runs `tools/snapshot_report.py` on the latest snapshot and opens an issue for each new one.
