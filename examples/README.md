# Examples

Complete packs, each checked with `tools/mcshaders check` and filmed in game (26.3, Vulkan).

| Example | Technique |
|---|---|
| [terrain-wave](terrain-wave/) | Core vertex shader: displace chunk geometry in `core/terrain.vsh` |
| [depth-outlines](depth-outlines/) | Post effect: edge detection on depth, applied on every frame through `end_of_frame` |
| [emissive-entities](emissive-entities/) | Core fragment shader + texture: pixels marked with alpha 254 ignore the lightmap |
| [atmosphere](atmosphere/) | Replaced vanilla include (`fog.glsl`, everywhere at once) + a sky gradient through a new varying |
| [text-effects](text-effects/) | Data from commands: an exact text color selects a rainbow or wave effect in `core/text.vsh`, in the world and in the GUI |
| [gui-theme](gui-theme/) | Core fragment shader: recolor the neutral greys of GUI textures, GUI only (orthographic test) |
| [world-anchor](world-anchor/) | Core + post: an `item_display` sends its screen position to a post effect through control pixels |
| [procedural-sprite](procedural-sprite/) | Custom item model whose texture encodes its coordinates; `core/item.fsh` draws a procedural glowing orb |
| [thick-outlines](thick-outlines/) | Post effect: replace `minecraft:entity_outline` for thick, crisp, tinted outlines on glowing entities |
| [emissive-glow](emissive-glow/) | Core + post: emissive pixels tag the main target's alpha, and a post effect blooms only them |
| [scattered-sky](scattered-sky/) | Core + post: a physically based sky drawn by a post effect, with vanilla's fog turned toward it, exposure and tonemapping |
| [screen-shadows](screen-shadows/) | Post: shadows from the sun, by marching rays toward it against the depth buffer, cutting the relit terrain's direct light |
| [sun-lighting](sun-lighting/) | Core + post: opaque terrain writes its light levels in alpha, and a post effect relights it by the sun, the moon and the sky, with bloom |
| [water-reflections](water-reflections/) | Core + post: the terrain shaders mark water through translucent blending, and a post effect draws waves, screen-space reflections, refraction and Fresnel |
| [data-bus](data-bus/) | Core + post: a reserved screen column carries the projection, the view rotation, the sky and fog colors and the sun direction to a post effect |

With the Sodium mod, the examples that change terrain shaders behave differently: see [Sodium](../docs/sodium.md#the-examples-under-sodium).

An example is built from your installed game: vanilla files plus the edits in its `example.json`, and its own files. This keeps vanilla files out of the repository.

```sh
python3 tools/examples.py                        # check every example
python3 tools/examples.py --screenshots          # refilm them
python3 tools/examples.py terrain-wave --out DIR # build a pack folder you can drop in resourcepacks/
```
