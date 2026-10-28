# Sodium

[Sodium](https://github.com/CaffeineMC/sodium) is the most widely used rendering mod. It draws the world's terrain itself, with its own shaders, so a resource pack that changes terrain shaders does nothing, or breaks, for every Sodium player. This page covers what Sodium changes and how a pack can support it.

Tested with Sodium 0.9.2 for 26.3, on Fabric Loader 0.20.0 and 0.20.1, OpenGL and Vulkan. Sodium Extra 0.9.5 needs Fabric Loader 0.20.1 or later: with 0.20.0 the game doesn't start ("Incompatible mods found"); the tools now use 0.20.1. Its shader files are identical in 0.9.3-beta.1 and on its development branch (2026-10-16).

## What Sodium changes

- **Terrain is drawn by `sodium:blocks/block_layer_opaque`**, not by `core/terrain`. The `core/terrain` pipelines are not used, so edits to `terrain.vsh` and `terrain.fsh` have no effect: [terrain-wave](../examples/terrain-wave/) shows no wave under Sodium (observed).
- **Its terrain shader has its own includes.** A pack that replaces `minecraft:fog.glsl` doesn't reach the terrain, which uses `sodium:fog.glsl`: the terrain fog of [atmosphere](../examples/atmosphere/) stays vanilla under Sodium (observed).
- **Everything else is drawn by the game's programs:** entities, items, particles, text, the GUI, the sky, clouds, and post effects. The other examples render the same with and without Sodium (observed).
- **The fog values are the game's.** Sodium reads them from the game's fog setup *(code)*, so a post effect that recomputes the fog ([scattered-sky](../examples/scattered-sky/)) gives the same result.
- **The sky is not drawn while the camera is in a fluid** (water, lava…), to fix [MC-152504](https://bugs.mojang.com/browse/MC-152504) *(code)*. A [data bus](techniques.md#give-post-effects-the-camera-a-data-bus) written by the sky is then absent.

## Replacing Sodium's terrain shader

Since Sodium 0.9 (Minecraft 26.2), Sodium builds its pipelines with the game's pipeline system, and the game loads their shaders from resource packs like any other *(code)*. A pack replaces them by shipping:

```
assets/sodium/shaders/blocks/block_layer_opaque.vsh
assets/sodium/shaders/blocks/block_layer_opaque.fsh
assets/sodium/shaders/include/*.glsl            (chunk_vertex, chunk_material, fog, globals)
```

Earlier versions needed the Sodium Core Shader Support mod. According to its Modrinth page, it is no longer updated for that reason.

Start from the files of the Sodium version you target (they are in its jar) and keep the changes small. Sodium's pipelines, read from its code *(code)*:

| | |
|---|---|
| Pipelines | `sodium:pipeline/solid_terrain`, `cutout_terrain`, `translucent_terrain`; with Improved Transparency, `minecraft:pipeline/oit_{depth_bounds,transmittance,accumulate}_sodium_terrain` |
| Defines | `USE_VERTEX_COMPRESSION`, `USE_FOG`; `ALPHA_CUTOUT` 0.5 for cutout, 0.01 for translucent; the usual `OIT_*` |
| Samplers | `u_BlockTex` (the block atlas), `u_LightTex` (the lightmap; not in the OIT alpha passes), `u_SectionTimeInfo` (an `isamplerBuffer`, for the chunk fade-in) |
| Uniform block | `u_Globals`: `u_ProjectionMatrix`, `u_ModelViewMatrix`, `u_FogColor`, `u_EnvironmentFog` and `u_RenderFog` (start, end), `u_TexelSize`, `u_TexCoordShrink`, `u_FadePeriodInv`, `u_UseRGSS` |
| Push constants | `u_RegionOffset` (the region's origin, relative to the camera), `u_CurrentTime`, `u_RegionID` |

**None of the game's uniform blocks are available**: no `Globals`, `Fog`, `Projection`… The game rejects a shader that declares a block its pipeline doesn't have ([Writing shaders](writing-shaders.md)). In particular:

- **There is no game time, but there is a clock.** `u_CurrentTime` is the real time in milliseconds since the region was created *(code: `System.currentTimeMillis() - region.getCreationTime()`)*, so it starts at a different moment in each region. Turned into a wrapping clock, `float(u_CurrentTime % 1200000) / 1200000.0` goes from 0 to 1 every 1200 s like `GameTime`, and with a whole number of cycles per wrap nothing jumps. Each region then has its own phase. That is invisible for things that don't cross a region's border, such as plants swaying (below), but a pattern that spans the world tears at the borders, even with a wavelength that divides 128 so that it is continuous in space ([exp 81](../experiments/81-sodium-region-clock/), [exp 82](../experiments/82-sodium-region-clock-late/), on both backends): thin cracks between regions created together at world load, and a tear showing the sky between regions created a few seconds apart, which is what happens while exploring. It is real time: it keeps running when the game is paused, unlike `GameTime`.
- **There is no camera position.** But regions are 8 × 4 × 8 chunk sections (128 × 64 × 128 blocks), aligned on the world grid. So in `block_layer_opaque.vsh`, `_vert_position + _get_draw_translation(_draw_id)` is the world position modulo (128, 64, 128).
- **The light levels are the game's:** `_vert_tex_light_coord` is `UV2 / 256` *(code, and [sun-lighting](../examples/sun-lighting/) in game)*.
- **The projection is the game's**, so tests like `u_ProjectionMatrix[2][3] != 0.0` (perspective) work as with `ProjMat`.

## Making a pack work with Sodium

1. **Make the same change in `core/terrain` and in Sodium's shader**, and ship both. To pass a vertex value to the fragment shader, add an output to `block_layer_opaque.vsh` (its free locations start at 4), as [water-reflections](../examples/water-reflections/) does with the vertex color. **But Sodium Extra takes 4 and 5:** its fog patch inserts `v_PlanarDistance` and `v_SodiumExtraCylindricalDistance` there, after the `v_TexCoord` line of both shaders *(code)*. A pack that also uses 4 or 5 makes the pipeline fail to compile, and the game crashes when a world opens, with `overlapping use of location 4` in the log (observed with Sodium Extra 0.9.4). The examples here start at 10, and all render with Sodium Extra too (observed on OpenGL). Without Sodium, the `assets/sodium/` files are simply not used. [data-bus](../examples/data-bus/) and [scattered-sky](../examples/scattered-sky/) do this, and render the same with and without Sodium (observed).
2. **Test against the Sodium version you ship for.** A Sodium shader that doesn't compile crashes the game when a world opens, because Sodium compiles its pipelines then (observed). A broken core shader, by contrast, only gets the packs removed.
3. **Silence Sodium's warning.** Sodium shows a red "incompatible" message for any pack with a file named `terrain.vsh` or `terrain.fsh` (or the old `rendertype_solid`, `rendertype_cutout`, `rendertype_cutout_mipped`, `rendertype_translucent`, `rendertype_tripwire` files), and a "may be incompatible" one for `fog.glsl` or `light.glsl` *(code, and seen in game)*. A pack that supports Sodium lists those files in its `pack.mcmeta`:

   ```json
   {
     "pack": { "description": "…", "min_format": 97, "max_format": 97 },
     "sodium": { "ignored_shaders": ["terrain.fsh"] }
   }
   ```

4. **Mind the license.** Sodium is under the [PolyForm Shield 1.0.0](https://github.com/CaffeineMC/sodium/blob/dev/LICENSE.md) license. It allows distributing modified copies, with the license terms and not as part of a product that competes with Sodium. The examples here store only their edits, and the tools add the license to the pack they build.

A vertex effect such as [terrain-wave](../examples/terrain-wave/) can't be ported as it is: its wave spans the world, and the per-region clock above tears it at the region borders, every 128 blocks ([exp 82](../experiments/82-sodium-region-clock-late/)). Local motion ports well: waving plants work with Sodium alone and with Sodium Extra 0.9.4 and 0.9.5, measured on both backends (about 17 % of the grass pixels change between two moments, none of the ground).

## Testing with Sodium

```sh
python3 tools/fetch.py sodium                                # newest Sodium release for 26.3, into build/mods/
python3 tools/fetch.py mod sodium-extra                      # any other Modrinth project, the same way
tools/mcshaders check path/to/pack --sodium build/mods/sodium-fabric-0.9.2+mc26.3.jar
python3 tools/launch.py --gamedir build/game --pack path/to/pack \
    --fabric 0.20.1 --mod build/mods/sodium-fabric-0.9.2+mc26.3.jar
python3 tools/examples.py --sodium build/mods/sodium-fabric-0.9.2+mc26.3.jar --screenshots   # into build/sodium-shots/
```

With `--sodium`, `mcshaders check` builds Sodium's terrain pipelines with Sodium's own code, read from the jar, and checks them like the game's: it reports the broken shader of step 2 before the crash. `launch.py --fabric` runs the game with that Fabric Loader version and exactly the `--mod` jars, and `--script` keeps working.

## The examples under Sodium

| Example | Under Sodium |
|---|---|
| [data-bus](../examples/data-bus/), [scattered-sky](../examples/scattered-sky/), [water-reflections](../examples/water-reflections/), [sun-lighting](../examples/sun-lighting/), [screen-shadows](../examples/screen-shadows/), [temporal-accumulation](../examples/temporal-accumulation/), [waving-plants](../examples/waving-plants/) | Same, thanks to their edit of Sodium's terrain shader. Without it, terrain covers the bus and the effect is gone, and water isn't marked |
| [terrain-wave](../examples/terrain-wave/) | No wave: `core/terrain` is not used |
| [minimap](../examples/minimap/) | No map: Sodium's terrain shader has neither the screen size nor the camera's block, which the capture needs. Its edit only hides the map faces. [minimap-sodium](../examples/minimap-sodium/) does without both, at a cost |
| [minimap-sodium](../examples/minimap-sodium/) | Same, but with Sodium's "Use Block Face Culling" on (the default), terrain above the camera's chunk section is missing from the map |
| [atmosphere](../examples/atmosphere/) | The sky is the same; the terrain keeps the vanilla fog |
| [depth-outlines](../examples/depth-outlines/), [emissive-entities](../examples/emissive-entities/), [emissive-glow](../examples/emissive-glow/), [gui-theme](../examples/gui-theme/), [procedural-sprite](../examples/procedural-sprite/), [text-effects](../examples/text-effects/), [thick-outlines](../examples/thick-outlines/), [world-anchor](../examples/world-anchor/) | Same |
