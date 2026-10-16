# Techniques (26.3)

Recurring tricks of vanilla shader packs, checked in 26.3. Each one links to the experiment or example that shows it working.

## Mark texels in a texture

A shader can't know which object it is drawing, but it can read the texture. Packs therefore mark special texels with a value nobody would paint by accident.

- **Marker alpha:** for example 254 instead of 255. It's invisible in an opaque texture, and easy to test: `abs(texel.a * 255.0 - 254.0) < 0.5`. See [emissive-entities](../examples/emissive-entities/).
- **Exact colors:** compare the texel's color with a list of colors, with a small tolerance.

Read the texel without filtering or mipmapping, with `textureLod(Sampler0, uv, 0.0)`, so neighbouring texels don't change the value. This is reliable for entities and items. **Terrain is a different case:** its `Sampler0` uses linear filtering since 1.21.11, so a texel can be blended with its neighbours at its edges *(code, and the [minecraft.wiki history](https://minecraft.wiki/w/Shader#History))*. Markers on terrain textures are therefore unreliable near texel edges.

## Tell the GUI from the world

The same program draws an item in the world, in hand and in the hotbar. GUI drawing uses an orthographic projection, the world a perspective one:

```glsl
#include <minecraft:projection.glsl>   // ProjMat; the Projection block is available to item, entity, text, gui…

bool inGui = ProjMat[2][3] == 0.0;
```

In [exp 59](../experiments/59-gui-or-world/), `core/item.fsh` turns magenta only when `inGui` is true. The hotbar icons turn magenta, while the dropped sword and the one held in hand are unchanged, on both backends.

## Tag pixels for a post effect

A post effect only sees the final image. To let it treat some pixels differently, the core shader that draws them writes a **tag in the alpha channel of `minecraft:main`**.

- **After the world is drawn, alpha is 1 almost everywhere:** terrain, sky, entities, water and glass alike. It is 0 only where nothing was drawn, such as the band at the horizon of a flat world ([exp 58](../experiments/58-main-alpha/)). A value like 0.5 is therefore free.
- **Only tag from pipelines without blending.** Solid and cutout pipelines (`entity_solid`, `entity_cutout`, `item_cutout`, `solid_terrain`, `cutout_terrain`…) store the alpha as written. Translucent ones blend it. The blend state of every pipeline is in [pipelines.json](../reference/26.3/pipelines.json) (`color_targets`).
- **The post effect tests the tag**, for example `abs(color.a - 0.5) < 0.1`. It should write alpha 1 when it is done.

Example: [emissive-glow](../examples/emissive-glow/) tags emissive texels and blooms only them.

## Animate

- **Use `GameTime` from `Globals`**, available to every core program and every post pass. It is `((game ticks % 24000) + partial tick) / 24000`: it goes from 0 to 1 every 24000 ticks (20 minutes), then **wraps back to 0** *(code)*. For a seamless loop, use a whole number of periods: `sin(GameTime * 6.2831853 * N)` repeats N times per wrap, that is every 24000 / N ticks. See [terrain-wave](../examples/terrain-wave/).
- **`CameraOffset` and `CameraBlockPos` give the camera position:** `CameraBlockPos` is the block the camera is in, and `CameraOffset` is `CameraBlockPos - camera position`, between -1 and 0 on each axis *(code)*.
- **Post-effect uniforms from the JSON are constants**, so they can't drive an animation ([Post effects](post-effects.md)).

## Read depth in a post effect

Use `"use_depth_buffer": true` on an input. Depth is reversed: 1 near, 0 far and sky ([exp 57](../experiments/57-depth-input/)). It is roughly proportional to 1 / distance, so compare relative differences. See [depth-outlines](../examples/depth-outlines/). The hand is not in that depth while a post effect is active ([How a frame is drawn](rendering.md)).

## Displace geometry

A vertex shader can move vertices freely. Only the rendering changes: collisions are unaffected, and terrain lighting, which is baked into the vertex color, does not follow the new shape. For terrain, rebuild the world position as `Position + vec3(ChunkPosition)`. See [terrain-wave](../examples/terrain-wave/).
