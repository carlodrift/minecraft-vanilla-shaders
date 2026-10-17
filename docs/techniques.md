# Techniques (26.3)

Recurring tricks of vanilla shader packs, checked in 26.3. Each one links to the experiment or example that shows it working.

## Mark texels in a texture

A shader can't know which object it is drawing, but it can read the texture. Packs therefore mark special texels with a value nobody would paint by accident.

- **Marker alpha:** for example 254 instead of 255. It's invisible in an opaque texture, and easy to test: `abs(texel.a * 255.0 - 254.0) < 0.5`. See [emissive-entities](../examples/emissive-entities/).
- **Exact colors:** compare the texel's color with a list of colors, with a small tolerance.

Read the texel without mipmapping, with `textureLod(Sampler0, uv, 0.0)`, so neighbouring texels don't change the value. This works for entities and items (examples above).

**Terrain is different.** Its `Sampler0` uses linear filtering, and vanilla's `sampleNearest()` (`texture_sampling.glsl`) still blends neighbouring texels near texel edges, for anti-aliasing *(code)*. To read one exact texel, use `texelFetch(Sampler0, ivec2(uv * vec2(TextureSize)), 0)`, where `TextureSize` comes from the `TerrainUniform` block. In [exp 68](../experiments/68-terrain-texelfetch/), a quarter of the red wool texture recolored #FE0102 turns magenta with sharp edges, on every face.

## Pass data from a datapack

Commands can set colors that reach a shader unchanged, in the `Color` vertex input. A shader that compares the raw `Color` with an exact value can react to it, and the other 24 bits of the color can carry data.

- **Text color:** a `text_display`, `/title` or any text with `"color": "#FE0102"` reaches `core/text.vsh` in `Color` (exp 66).
- **Item tint:** an item tinted with `dyed_color` (here a `leather_horse_armor` in an `item_display`) reaches `core/item.vsh` in `Color` (exp 67).

```glsl
// In the vertex shader, before Color is multiplied by lighting.
if (all(lessThan(abs(Color.rgb * 255.0 - vec3(254.0, 1.0, 2.0)), vec3(0.5)))) {
    // this vertex carries the marker #FE0102
}
```

In both experiments, a control in `#FE0103` is left untouched. [text-effects](../examples/text-effects/) uses this to trigger rainbow and wave effects on any text. Compare in the vertex shader, on the raw `Color`: the fragment shader only sees it after lighting and the lightmap.

## Tell the GUI from the world

The same program draws an item in the world, in hand and in the hotbar. GUI drawing uses an orthographic projection, the world a perspective one:

```glsl
#include <minecraft:projection.glsl>   // ProjMat; the Projection block is available to item, entity, text, gui…

bool inGui = ProjMat[2][3] == 0.0;
```

In [exp 59](../experiments/59-gui-or-world/), `core/item.fsh` turns magenta only when `inGui` is true. The hotbar icons turn magenta, while the dropped sword and the one held in hand are unchanged, on both backends. [gui-theme](../examples/gui-theme/) uses the same test to recolor the GUI textures only.

## Isolate an element of the GUI

**Item icons in the GUI are drawn twice** *(the game has a `GuiItemAtlas` class)*:
1. **`core/item` draws them into an atlas** of item icons. There, `gl_Position` is a position **in the atlas**, not on the screen ([exp 71](../experiments/71-gui-item-atlas/): a left-to-right rainbow in `item.vsh` colors the hotbar icons in no particular order).
2. **`core/position_tex_color` copies them to the screen**, together with every other GUI texture: hotbar, hearts, toasts, containers. There, `gl_Position` is the real screen position ([exp 70](../experiments/70-gui-position/): the same rainbow follows the hotbar slots, icons included).

So **to select GUI elements by where they are, work in `position_tex_color.vsh`**, in normalized device coordinates. `x` goes from -1 on the left to 1 on the right, and `y` from **-1 at the bottom** to 1 at the top, on both backends. In [exp 72](../experiments/72-gui-bottom/), `gl_Position.y / gl_Position.w < -0.6` tints exactly the hotbar area. To select by *what* they are, use the texture: texel markers ([above](#mark-texels-in-a-texture)) work on GUI sprites too.

Positions in normalized coordinates don't depend on the window size, but the size of GUI elements does, since it follows the GUI scale.

## Change the color of translucent things (Improved Transparency)

With the **Improved Transparency** graphics option, translucent terrain, entities, particles and clouds go through order-independent transparency (OIT). The same program then runs in three passes, selected by defines (see [How a frame is drawn](rendering.md)):
- `OIT_DEPTH_BOUNDS` and `OIT_TRANSMITTANCE`, together `OIT_ALPHA_ONLY`: only the alpha counts, and there is no `fragColor`;
- `OIT_ACCUMULATE`: the color is weighted by `sampleColorForAccumulation()` inside vanilla's `calculateFinalColor()`.

**Change `color` before `calculateFinalColor()`, never `fragColor` after it.**

| | Improved Transparency off | Improved Transparency on |
|---|---|---|
| Red tint applied to `color` before `calculateFinalColor()` | ![](../experiments/60-tint-translucent-before/vulkan.png) exp 60 | ![](../experiments/61-tint-translucent-before-oit/vulkan.png) exp 61 |
| `fragColor` overwritten after `calculateFinalColor()` | ![](../experiments/62-overwrite-translucent-after/vulkan.png) exp 62 | ![](../experiments/63-overwrite-translucent-after-oit/vulkan.png) exp 63 |

- **Changed before**, the tint looks the same with the option on or off.
- **Overwritten after**, the color skips the OIT weighting. The water and glass come out brighter and more opaque with the option on.

If you change alpha, change it in the `OIT_ALPHA_ONLY` path too, so the transmittance passes see the same alpha as the color pass *(code)*.

The option is off by default. To turn it on from `options.txt`, also set `graphicsPreset:"custom"`: a named preset ("fancy"…) re-applies its own values when the options load. `tools/launch.py --option` handles this.

## Tag pixels for a post effect

A post effect only sees the final image. To let it treat some pixels differently, the core shader that draws them writes a **tag in the alpha channel of `minecraft:main`**.

- **After the world is drawn, alpha is 1 almost everywhere:** terrain, sky, entities, water and glass alike. It is 0 only where nothing was drawn, such as the band at the horizon of a flat world ([exp 58](../experiments/58-main-alpha/)). A value like 0.5 is therefore free.
- **Only tag from pipelines without blending.** Solid and cutout pipelines (`entity_solid`, `entity_cutout`, `item_cutout`, `solid_terrain`, `cutout_terrain`…) store the alpha as written. Translucent ones blend it. The blend state of every pipeline is in [pipelines.json](../reference/26.3/pipelines.json) (`color_targets`).
- **The post effect tests the tag**, for example `abs(color.a - 0.5) < 0.1`. It should write alpha 1 when it is done.

Example: [emissive-glow](../examples/emissive-glow/) tags emissive texels and blooms only them.

## Send a value or a position to a post effect

Tagging pixels ([above](#tag-pixels-for-a-post-effect)) tells a post effect *which* pixels matter. To send a **value**, such as the screen position of a point in the world, a core shader writes it into **control pixels**, at a fixed place on the screen:

- **In the vertex shader,** recognize the source, for example an item tinted with a marker color ([exp 67](../experiments/67-data-item-tint/)). Compute the value, pass it in a `flat` varying, and move the vertex onto a small strip in a corner.
- **In the fragment shader,** write a marker and the value, as bytes with alpha 1.
- **In the post effect,** find the marker with `texelFetch`, decode the value, then paint over the strip.

[world-anchor](../examples/world-anchor/) does this end to end, and lists what had to be found out along the way. NDC (-1, -1) is the bottom-left corner on both backends. The moved quad must stay front-facing, since back faces are culled. And the vertex a `flat` varying comes from differs between OpenGL and Vulkan.

## Change something everywhere: replace a vanilla include

A pack file at `assets/minecraft/shaders/include/<name>.glsl` replaces the vanilla include for every program that includes it. For example, a modified `fog.glsl` changes the fog of terrain, entities, items, particles, sky and clouds at once. See [atmosphere](../examples/atmosphere/).

- **Keep every block and function the vanilla file declares**, with the same signatures. Other programs call them.
- **Run `tools/mcshaders check`:** a mistake in an include breaks every program that uses it.

## Restyle glowing outlines

Replace the post effect `assets/minecraft/post_effect/entity_outline.json`. It reads the silhouettes of glowing entities from the `minecraft:entity_outline` target (team color in RGB, coverage in alpha), and must write the outline back into that target, alpha included. The game then composites it onto the world. See [thick-outlines](../examples/thick-outlines/).

## Read light levels

The vertex input `UV2` (`ivec2`) holds the two light levels of the vertex, multiplied by 16 *(code: `sample_lightmap.glsl` reads `UV2 / 256`)*:

```glsl
float blockLight = float(UV2.x) / 16.0;   // 0..15: torches, glowstone, lava...
float skyLight   = float(UV2.y) / 16.0;   // 0..15: light from the sky
```

- **The levels don't depend on the time of day.** In [exp 69](../experiments/69-light-levels/), `terrain.vsh` shows block light in red and sky light in green. At midnight, open ground is still full green (sky light 15), and only the area around glowstone gets red. Day and night are applied afterwards, by the lightmap texture (`Sampler2`) that `sample_lightmap()` reads.
- **With smooth lighting, the values are interpolated** between levels, so compare with thresholds rather than exact levels.
- **`UV2` reaches the vertex programs that have it in their vertex format:** `terrain`, `block`, `entity`, `item`, `particle`, `text`, `rendertype_leash`… ([core-shaders.md](reference/core-shaders.md)). To use it in the fragment shader, pass it through a varying.

Use it for light-dependent effects that vanilla's lightmap can't express, like emissive parts that only glow in the dark, or a custom day/night curve, using `GameTime` for the time of day.

## Animate

- **Use `GameTime` from `Globals`**, available to almost every core program (see [core-shaders.md](reference/core-shaders.md)) and to every post pass. It is `((game ticks % 24000) + partial tick) / 24000`: it goes from 0 to 1 every 24000 ticks (20 minutes), then **wraps back to 0** *(code)*. For a seamless loop, use a whole number of periods: `sin(GameTime * 6.2831853 * N)` repeats N times per wrap, that is every 24000 / N ticks. See [terrain-wave](../examples/terrain-wave/).
- **`CameraOffset` and `CameraBlockPos` give the camera position:** `CameraBlockPos` is the block the camera is in, and `CameraOffset` is `CameraBlockPos - camera position`, between -1 and 0 on each axis *(code)*.
- **Post-effect uniforms from the JSON are constants**, so they can't drive an animation ([Post effects](post-effects.md)).

## Camera, world position and field of view

| What | How | Evidence |
|---|---|---|
| Camera position (world) | `vec3(CameraBlockPos) - CameraOffset` (`Globals`) | *(code)* |
| World position, entities | `Position + vec3(CameraBlockPos) - CameraOffset`: their `Position` is relative to the camera | [exp 74](../experiments/74-entity-world-position/) |
| World position, terrain | `Position + vec3(ChunkPosition)` | [terrain-wave](../examples/terrain-wave/) |
| Vertical field of view | `degrees(2.0 * atan(1.0 / ProjMat[1][1]))`: 70 with the default FOV option | [exp 73](../experiments/73-fov-from-projection/) |

In `entity.vsh`, the `PER_FACE_LIGHTING` variants (`entity_cutout` and others: mobs, for example) output `vertexPerFaceColorFront` and `vertexPerFaceColorBack` instead of `vertexColor`. An effect on the vertex color has to change both outputs, or it won't show on most mobs.

## Read depth in a post effect

Use `"use_depth_buffer": true` on an input. Depth is reversed: 1 near, 0 far and sky ([exp 57](../experiments/57-depth-input/)). It is roughly proportional to 1 / distance, so compare relative differences. See [depth-outlines](../examples/depth-outlines/). The hand is not in that depth while a post effect is active ([How a frame is drawn](rendering.md)).

## Displace geometry

A vertex shader can move vertices freely. Only the rendering changes: collisions are unaffected, and terrain lighting, which is baked into the vertex color, does not follow the new shape. For terrain, rebuild the world position as `Position + vec3(ChunkPosition)`. See [terrain-wave](../examples/terrain-wave/).
