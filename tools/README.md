# Tools

All tools run against a Minecraft installation from the official launcher. Install the version once from the launcher.

Requirements:
- Java 25 or newer, on `PATH` or in the `JAVA` environment variable.
- Python 3.
- macOS. The paths and the launch arguments assume macOS for now.

The tools load the game's own classes and libraries from `~/Library/Application Support/minecraft`, or from `$MINECRAFT_DIR` if set. Nothing from the game is copied into this repository.

## `fetch.py`

```sh
MINECRAFT_DIR=build/minecraft python3 tools/fetch.py 26.3
```

Downloads the vanilla client jar and its libraries from Mojang into `$MINECRAFT_DIR` (SHA-1 checked), without the official launcher. That is enough for `mcshaders`, `reference.py`, `vanilla.py`, `experiments.py` and `examples.py` without `--ingame` or `--screenshots`. Launching the game also needs the assets, which only the launcher installs. The [CI workflow](../.github/workflows/check.yml) uses it.

## `mcshaders check [pack]`

```sh
tools/mcshaders check path/to/resource-pack
```

This checks a resource pack's shaders the way the game loads them, in a few seconds, without launching the game. Without a pack, it checks vanilla.

**What it does:**
- **Compiles** every variant of every program the pack touches, with shaderc and the game's compiler options, once for each combination of the three device-dependent defines.
- **Validates** every pipeline as the game does after compiling: vertex inputs against the vertex format, varyings between the two programs, and uniforms against the pipeline.
- **Includes post effects**, both the vanilla ones and the pack's own `post_effect/*.json`.

Each problem is printed once, with the pipelines it breaks. The exit status is non-zero if anything fails.

## `mcshaders pipelines`

```sh
tools/mcshaders pipelines > pipelines.jsonl
```

Prints every render pipeline of the game as one JSON object per line: programs, defines, uniforms, vertex format and render state.

## `reference.py`

```sh
python3 tools/reference.py
```

Regenerates `reference/<version>/pipelines.json` and the pages in `docs/reference/` from the installed game.

## `launch.py`

```sh
python3 tools/launch.py --gamedir build/game --pack path/to/pack --backend vulkan
python3 tools/launch.py --gamedir build/game --pack path/to/pack --backend opengl --seconds 20
```

This starts the game offline, in its own game directory, so your worlds and settings are left alone.

**Options:**
- `--pack` copies the pack in and enables it.
- `--backend` picks OpenGL or Vulkan.
- `--seconds` stops the game after that many seconds and prints the shader-related lines of the log.
- `--world` joins a singleplayer world directly. The world must exist in the game directory's `saves/`.
- `--script` drives the game with the test agent (see below), for example to create a world, run commands and take screenshots.
- `--option KEY=VALUE` sets an `options.txt` entry, for example `--option 'graphicsPreset="custom"' --option improvedTransparency=true`. The graphics preset and Improved Transparency are reset to their defaults on every launch.
- `--size` sets the window size, for example `640x360`. The default is `854x480`. Screenshots come out at twice that on Retina screens.

## `gallery.py`

```sh
python3 tools/gallery.py                 # every program, plus a vanilla baseline
python3 tools/gallery.py terrain entity  # only these programs
```

For each core fragment program, this builds a pack that makes the vanilla program output magenta, loads it in a test scene, and saves screenshots with and without the HUD to `docs/images/programs/`. It is used by [How a frame is drawn](../docs/rendering.md).

## `agent/ShaderTestAgent.java`

A Java agent that `launch.py --script` loads into the game. It creates a fresh flat test world, runs commands, hides the HUD, takes screenshots with the game's own screenshot function, and quits. No mod is installed and no OS screen-capture permission is needed. The script format is in the file's header.

## `examples.py`

Checks, films and builds the [examples](../examples/). Run `python3 tools/examples.py --help` for the options.

## `vanilla.py`

```sh
python3 tools/vanilla.py extract 26.1.2 build/vanilla-26.1.2   # vanilla shaders of an installed version
python3 tools/vanilla.py diff 26.2 26.3 [-u]                   # what changed between two versions
```

Used by [Porting to 26.3](../docs/porting.md).

## `experiments.py`

```sh
python3 tools/experiments.py            # check every experiment
python3 tools/experiments.py --ingame   # also load each one in the game, on OpenGL and Vulkan
python3 tools/experiments.py 20 21      # only experiments whose id starts with 20 or 21
```

This builds each experiment's pack from the installed game's vanilla files, runs it, and rewrites [experiments/RESULTS.md](../experiments/RESULTS.md).

All tools default to version 26.3. Set `MC_VERSION` to use another version for `mcshaders`, or pass `--version` to the Python tools.
