# Post effects in 26.3

A post effect is a chain of full-screen passes run over the rendered world, after the world and before the GUI. In 26.3 a resource pack can run one on every frame with `minecraft:end_of_frame`, and commands can add more with `/posteffect`.

Evidence works as in [Writing shaders](writing-shaders.md): **exp NN** is an [experiment](../experiments/RESULTS.md), and the post-effect ones come with screenshots. **code** means observed in the 26.3 client code.

## When post effects run

Each frame in which a world is rendered with a player, the game builds a list of post effects and applies them in this order *(code)*:

1. **`minecraft:end_of_frame`**, always requested. Vanilla does not ship one, so without a pack the log contains `Requested post effect does not exist: minecraft:end_of_frame`. This warning is harmless.
2. **The effects added with `/posteffect`**, in the order they were added.
3. **The effect of the mob being spectated:** `minecraft:creeper` for a creeper, `minecraft:spider` for a spider or cave spider, `minecraft:invert` for an enderman.

They run after the world, the hand and held item, and the glowing-entity outline, and before the GUI. The HUD, menus and chat are never affected *(code)*. Menu blur (`minecraft:blur`) and the glowing outline (`minecraft:entity_outline`) are separate, built-in uses of the same system.

An effect that fails is skipped for the rest of the session, until the next resource reload *(code)*.

### `end_of_frame`

Put a post effect at `assets/minecraft/post_effect/end_of_frame.json` and it applies to the world for as long as the pack is enabled. It needs no command and no "Fabulous" graphics. This makes it the replacement for the old trick of hijacking `transparency.json`, which no longer exists in 26.3 (exp 50).

### `/posteffect`

```
/posteffect add <players> <post effect>
/posteffect remove <players> <post effect>
/posteffect clear <players>
/posteffect list <player>
```

Requires permission level 2 *(code)*. The effect can live in any namespace, for example `mylib:grayscale` for `assets/mylib/post_effect/grayscale.json` (exp 51).

## The JSON file

`assets/<namespace>/post_effect/<name>.json`, referenced as `<namespace>:<name>`:

```json
{
  "targets": {
    "swap": {}
  },
  "passes": [
    {
      "vertex_shader": "minecraft:core/screenquad",
      "fragment_shader": "mylib:post/tint",
      "inputs": [
        { "sampler_name": "In", "target": "minecraft:main" }
      ],
      "output": "swap",
      "uniforms": {
        "TintConfig": [ { "type": "vec4", "value": [1.0, 0.45, 0.45, 1.0] } ]
      }
    },
    {
      "vertex_shader": "minecraft:core/screenquad",
      "fragment_shader": "mylib:post/copy",
      "inputs": [ { "sampler_name": "In", "target": "swap" } ],
      "output": "minecraft:main"
    }
  ]
}
```

### `targets`

Intermediate textures, by name. All their fields are optional *(code)*:

| Field | Default | Meaning |
|---|---|---|
| `width`, `height` | screen size | size in pixels |
| `persistent` | `false` | keep the content from one frame to the next (exp 65: motion trails) |
| `clear_color` | `0` (transparent black) | ARGB color the target is cleared to |

The format is always RGBA8 *(code)*.

The only game target a post effect may use is **`minecraft:main`**, the rendered world. An effect that reads or writes any other one, such as `minecraft:entity_outline`, is refused with `can not be used as a post effect because it uses targets inaccessible to post effects`. It is then not applied, but the pack stays enabled (exp 53).

A single pass may read `minecraft:main` and write `minecraft:main` (exp 54). You don't need a `swap` target for a one-pass effect.

### `passes`

| Field | |
|---|---|
| `vertex_shader`, `fragment_shader` | program identifiers. `minecraft:core/screenquad` is the vanilla full-screen vertex program |
| `inputs` | the textures the pass reads (see below) |
| `output` | the target the pass writes |
| `uniforms` | values for the pass's own uniform blocks (see below) |

There are two kinds of inputs. Each one becomes a sampler named `<sampler_name>Sampler` in the shader *(code)*:

| Kind | Fields |
|---|---|
| Target | `sampler_name`, `target`, optional `use_depth_buffer` (read the target's depth instead of its color) and `bilinear` |
| Texture | `sampler_name`, `location`, `width`, `height`, optional `bilinear`. `location` `ns:path` reads `assets/ns/textures/effect/path.png` (exp 64) |

Two inputs of one pass cannot share a `sampler_name` *(code)*.

**A texture input comes out upside down** with the `texCoord` of `minecraft:core/screenquad`. The top row of the PNG lands at the bottom of the screen, on both backends (exp 64). To show it the right way up, sample `vec2(texCoord.x, 1.0 - texCoord.y)`. Targets don't have this problem: `minecraft:main` and your own targets read straight.

### `uniforms`

Each key is the name of a uniform block declared by the fragment or vertex program. Its value lists the block's members **in declaration order**, each with a `type` and a `value`:

| `type` | `value` |
|---|---|
| `int`, `float` | a number |
| `ivec3`, `vec2`, `vec3`, `vec4` | an array |
| `matrix4x4` | an array of 16 numbers |

These are the types the game accepts *(code)*. The `name` field found in vanilla files is not needed (exp 55).

The values are fixed when the effect loads. For anything that changes over time, read the `Globals` block instead (below).

## The shaders

The rules of [Writing shaders](writing-shaders.md) apply: `#version` first, `GL_ARB_separate_shader_objects`, a `layout(location)` on every `in` and `out`, `#include`. Post programs live in `assets/<ns>/shaders/post/` or anywhere else under `shaders/`, since the JSON names them by identifier.

```glsl
#version 330
#extension GL_ARB_separate_shader_objects : require

uniform sampler2D InSampler;          // input "In"

layout(std140) uniform SamplerInfo {  // provided by the game
    vec2 OutSize;                     // size of the output target
    vec2 InSize;                      // one vec2 per input, in input order
};

layout(std140) uniform TintConfig {   // filled from the JSON "uniforms"
    vec4 Tint;
};

layout(location = 0) in vec2 texCoord;   // from minecraft:core/screenquad
layout(location = 0) out vec4 fragColor;

void main() {
    fragColor = vec4(texture(InSampler, texCoord).rgb * Tint.rgb, 1.0);
}
```

A pass can use exactly these uniforms *(code, and the message of exp 56)*:
- **`Globals`**: `GameTime`, `ScreenSize`, `CameraBlockPos`, `CameraOffset`… See [uniforms.md](reference/uniforms.md#globals). Include it with `#include <minecraft:globals.glsl>`.
- **`SamplerInfo`**: `vec2 OutSize`, then one `vec2` per input, in the order of `inputs` *(code)*.
- **One `<sampler_name>Sampler` per input.**
- **The blocks listed in the pass's `uniforms`.** A block the shader declares but the JSON doesn't list fails with `Unable to find shader defined uniform` (exp 56). Unused declarations count too, as for core shaders.

### Depth

With `"use_depth_buffer": true`, the sampler reads the target's depth. **26.3 uses a reversed depth buffer: 1 is nearest, 0 is the far plane, and the sky is 0.** This was verified on both backends, with the same orientation on each (exp 57).

## When an effect is broken

A post effect is compiled the first time it is used in game, not when the pack loads *(code)*. If it does not compile or validate, the game logs the error and **removes all selected resource packs**, just as for a broken core shader. The difference is that this happens in the middle of the game (exp 52, 56).

`tools/mcshaders check` compiles and validates every post effect of a pack beforehand, including the target rule of exp 53.
