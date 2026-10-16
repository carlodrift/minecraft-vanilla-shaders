# Porting shaders to 26.3

How to bring a pack written for 1.21.x, 26.1 or 26.2 to 26.3. 26.3 changed how shaders are compiled (see [Writing shaders](writing-shaders.md)), so almost every older core shader fails to load as is.

## Method: start from vanilla 26.3

Don't patch your old file until it compiles. Instead:

1. **Find what your shader changes.** Diff it against the vanilla file of the version it was written for:

   ```sh
   python3 tools/vanilla.py extract 26.1.2 build/vanilla-26.1.2
   diff -u build/vanilla-26.1.2/shaders/core/entity.fsh my-pack/assets/minecraft/shaders/core/entity.fsh
   ```

   Often only a few lines are really yours. The rest of the diff is vanilla code from an older version, or workarounds that are no longer needed.
2. **Re-apply those lines to the 26.3 vanilla file** (`python3 tools/vanilla.py extract 26.3 build/vanilla-26.3`).
3. **Check every variant:** `tools/mcshaders check my-pack`.
4. **Look at it in game**, on both backends if you can: `python3 tools/launch.py --gamedir build/game --pack my-pack --backend opengl` (or `vulkan`).

To see what vanilla changed between two versions: `python3 tools/vanilla.py diff 26.2 26.3`, or add `-u` for the full diff.

## Checklist

### Every version before 26.3

| Change | What to do | Evidence |
|---|---|---|
| `pack.mcmeta` | `"min_format": 97, "max_format": 97` | `version.json` of 26.3 |
| `#moj_import <x>` | `#include <x>` | [exp 07](../experiments/07-moj-import/) |
| `#version` at the top of an include | remove it. Includes may not contain `#version` (vanilla includes had one until 26.2) | [exp 09](../experiments/09-include-with-version/) |
| No `layout(location)` on `in`/`out` | add one to every varying, the same on both sides | [exp 20](../experiments/20-varying-without-location/) |
| No `#extension GL_ARB_separate_shader_objects : require` | add it after `#version` | [exp 14](../experiments/14-no-separate-shader-objects/) |
| Wrong type on a vertex input (e.g. `vec2 UV1`) | use the format's type: `ivec2 UV1`, `ivec2 UV2` | [exp 31](../experiments/31-attribute-wrong-base-type/) |
| Uniforms declared without the variant's guard | declare `Sampler1`, `Sampler2`, `Lighting`… only under the guard given in [core-shaders.md](reference/core-shaders.md) | [exp 42](../experiments/42-unused-sampler/) |
| `Globals` or `DynamicTransforms` declared by hand | include the vanilla file: both were reordered in 26.3 | [uniforms.md](reference/uniforms.md) |
| Transparency through `post_effect/transparency.json` ("Fabulous") | removed in 26.3; use `post_effect/end_of_frame.json` | [Post effects](post-effects.md) |
| Shaders that ignore the `OIT_*` defines | keep vanilla's `#ifdef OIT_ALPHA_ONLY` / `OIT_ACCUMULATE` structure: they are compiled even when Improved Transparency is off | [core-shaders.md](reference/core-shaders.md) |

### Renamed and removed files

| Version | Change |
|---|---|
| 26.3 | `rendertype_clouds` → `clouds`, `rendertype_world_border` → `world_border`. `text_background` removed. `post/transparency.fsh` removed. New: `oit_*`, `blit_depth`, `integrate_depth`, `include/oit*.glsl`, `include/terrainglobals.glsl`, `include/texture_sampling.glsl` |
| 26.2 | `rendertype_text*` merged into `text` (defines `IS_GUI`, `IS_SEE_THROUGH`, `IS_GRAYSCALE`). `rendertype_text_background*` merged into `text_background` |
| 26.1 | New `item` program for all item models. `rendertype_entity_alpha` and `rendertype_entity_decal` merged into `entity` (`DISSOLVE`). `rendertype_item_entity_translucent_cull` and `rendertype_translucent_moving_block` removed. New `include/sample_lightmap.glsl` |
| 1.21.11 | New `block`, `animate_sprite*`, `debug_point`, `include/chunksection.glsl` |
| 1.21.9–1.21.10 | `post/*.vsh` and `core/blit_screen.vsh` replaced by `core/screenquad.vsh`. `position_color_lightmap` and `position_color_tex_lightmap` removed |

Generated with `tools/vanilla.py diff` between the installed versions 1.21.8, 1.21.10, 1.21.11, 26.1.2, 26.2 and 26.3. The defines come from the [minecraft.wiki history](https://minecraft.wiki/w/Shader#History).

### Behavior changes that don't break compilation

- **26.2 — item lighting moves to the fragment shader**, as entities already did. `item.vsh` now outputs `lightMapColor` and `overlayColor`, and `item.fsh` multiplies them. To make a texel ignore lighting, skip `color *= lightMapColor` in the fragment shader. Replacing the color in the vertex shader no longer works. See [emissive-entities](../examples/emissive-entities/).
- **26.2 — the depth buffer is reversed** ([minecraft.wiki history](https://minecraft.wiki/w/Shader#History)): 1 is near, 0 is far, as measured in 26.3 ([exp 57](../experiments/57-depth-input/)). Tests like `depth > 0.99` for "far away" are now inverted.
- **In 26.3, entity previews in the GUI use their own lightmap**, so they stay lit at night ([How a frame is drawn](rendering.md)). Workarounds from older packs for a black lightmap in inventory previews can go.

## A worked port

Porting the shaders of a real pack (an "emissive" system for entities, items and particles: four programs and an include library) taught the following:

- **Most of the old file was not the pack's own code.** It was vanilla from an older version, or a workaround that no longer applied. The pack's own changes came down to a few dozen lines.
- **An include library had a `#version`**, which is fine before 26.3 but fails now (exp 09).
- **The old files also hid bugs** that the port fixed for free: arguments to `apply_fog` in the wrong order, and a vertex input with the wrong type.
- **Once `check` passed, the pack worked on both backends** at the first try.
