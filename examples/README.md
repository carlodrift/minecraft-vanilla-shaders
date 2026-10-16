# Examples

Complete packs, each checked with `tools/mcshaders check` and filmed in game (26.3, Vulkan).

| Example | Technique |
|---|---|
| [terrain-wave](terrain-wave/) | Core vertex shader: displace chunk geometry in `core/terrain.vsh` |
| [depth-outlines](depth-outlines/) | Post effect: edge detection on depth, applied on every frame through `end_of_frame` |
| [emissive-entities](emissive-entities/) | Core fragment shader + texture: pixels marked with alpha 254 ignore the lightmap |
| [atmosphere](atmosphere/) | Replaced vanilla include (`fog.glsl`, everywhere at once) + a sky gradient through a new varying |
| [emissive-glow](emissive-glow/) | Core + post: emissive pixels tag the main target's alpha, and a post effect blooms only them |

An example is built from your installed game: vanilla files plus the edits in its `example.json`, and its own files. This keeps vanilla files out of the repository.

```sh
python3 tools/examples.py                        # check every example
python3 tools/examples.py --screenshots          # refilm them
python3 tools/examples.py terrain-wave --out DIR # build a pack folder you can drop in resourcepacks/
```
