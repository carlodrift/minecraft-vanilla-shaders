# Working on a shader pack

A short loop for writing shaders without losing time to reloads and silent failures.

## 1. Start from the vanilla file of your version

```sh
python3 tools/vanilla.py extract 26.3 build/vanilla-26.3
```

Copy the program you want to change into your pack (`assets/minecraft/shaders/core/…`), and change as little as possible. Keeping vanilla's `#ifdef` structure is what keeps all the variants compiling ([Writing shaders](writing-shaders.md#defines-and-variants)).

## 2. Check before launching the game

```sh
tools/mcshaders check path/to/pack
```

This takes a few seconds. It compiles every variant of every pipeline your files touch, the way the game does, and runs the game's validation. Every problem is printed with the pipelines it breaks. Fix until it reports `0 problems`: in game, a single failure disables every pack.

## 3. Reload in game

- **F3 + T reloads resource packs, and with them the shaders.** No restart is needed.
- **If a pack disappears from the selected packs after a reload, a shader failed.** The game removed every selected pack ([Writing shaders](writing-shaders.md#how-the-game-loads-shaders)). Re-enable it after fixing.
- **A post effect fails later**, the first time it is used, and also removes the packs ([Post effects](post-effects.md#when-an-effect-is-broken)).

## 4. Read the errors

The game writes them to `logs/latest.log` in the game directory:

| Look for | Means |
|---|---|
| `Couldn't parse GLSL` | a compile error, with the file and line |
| `ShaderCompileException` | a validation error: varyings, vertex inputs, uniforms |
| `Couldn't compile pipeline (minecraft:pipeline/…)` | which pipeline failed |
| `Caught error loading resourcepacks` | the packs were removed because of the above |
| `Failed to load post chain` | a post effect failed |

## 5. Test both backends

Video Settings → Graphics API: "Prefer OpenGL" or "Prefer Vulkan (Experimental)". The game must be restarted for the change to apply. The compiler and the validation are the same on both, so a shader that loads on one loads on the other. Every experiment in this repository agrees on both. Rendering can still differ, for example in which vertex a `flat` varying comes from ([Writing shaders](writing-shaders.md#quads-and-moving-vertices)). Look at your effect on both.

## Automating it

`tools/launch.py` starts the game offline with your pack, in a separate game directory, on the backend of your choice. With `--script`, it can also create a test world, run commands and take screenshots. See [tools](../tools/README.md).
