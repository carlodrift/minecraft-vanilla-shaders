# Writing shaders for 26.3

The rules a core shader must follow to load in Minecraft 26.3, and why.

Each rule links to its evidence:
- **exp NN**: an [experiment](../experiments/) you can rerun. Results, in game on OpenGL and Vulkan, are in [RESULTS.md](../experiments/RESULTS.md).
- **code**: observed in the 26.3 client code. The repository contains no game code, only what was learned from it.

To check a pack against all of these at once, without launching the game, run `tools/mcshaders check <pack>` (see [tools](../tools/README.md)).

## How the game loads shaders

1. **Collect.** On resource reload, the game reads every `.vsh` and `.fsh` file under `assets/<namespace>/shaders/`, every `.glsl` file under `assets/<namespace>/shaders/include/`, and every post-effect JSON under `assets/<namespace>/post_effect/`. *(code)*
2. **Compile.** Each [render pipeline](reference/pipelines.md) names a vertex program, a fragment program and a set of defines. The game compiles both programs with **shaderc**, to **SPIR-V for Vulkan 1.2**, with that pipeline's defines. This happens on both backends. *(code)*
3. **Validate.** It then checks that the two programs fit together and fit the pipeline: vertex inputs, varyings, uniforms. *(code)*
4. **Hand over to the backend.**
   - **Vulkan:** the SPIR-V is used directly. On macOS this goes through MoltenVK.
   - **OpenGL:** the SPIR-V is translated back into GLSL 330 with SPIRV-Cross, renaming every variable after its location or binding, and that GLSL is given to the driver. *(code)*
5. **On failure.** If any required pipeline fails, the game logs `Caught error loading resourcepacks, removing all selected resourcepacks` and reloads **without any of the selected packs**, not just the faulty one. *(every failing experiment, in game)*

Steps 2 and 3 are the same on both backends, so a shader that loads on one almost always loads on the other. Every experiment gave the same result on OpenGL and Vulkan.

## Where files go

| What | Path | Referenced as |
|---|---|---|
| Core program | `assets/minecraft/shaders/core/<name>.vsh` / `.fsh` | `minecraft:core/<name>` by the game's pipelines |
| Include | `assets/<ns>/shaders/include/<path>.glsl` | `#include <ns:path.glsl>` |
| Post effect | `assets/<ns>/post_effect/<name>.json` | `<ns>:<name>` |

Vanilla pipelines always reference `minecraft:core/...`. To change how something is drawn, replace the vanilla file in the `minecraft` namespace. [core-shaders.md](reference/core-shaders.md) lists what each program draws through its pipelines.

## The first lines

```glsl
#version 330
#extension GL_ARB_separate_shader_objects : require
```

- **`#version` must come before any other directive.** Comments may precede it (exp 10), a `#define` may not (exp 11).
- **The version number is free.** `150`, `330` and `450` all compile (exp 12, 13), and `450` loads on both backends: on OpenGL, SPIRV-Cross rewrites the program as GLSL 330 anyway. Vanilla uses `330`.
- **`GL_ARB_separate_shader_objects` is required** as soon as a varying has a `layout(location)`, which is always (exp 14).

## Includes

```glsl
#include <minecraft:fog.glsl>      // assets/minecraft/shaders/include/fog.glsl
#include <fog.glsl>                // same: the namespace defaults to minecraft (exp 03)
#include "fog.glsl"                // same: quotes change nothing (exp 01)
#include <mylib:util/noise.glsl>   // assets/mylib/shaders/include/util/noise.glsl (exp 04)
```

- **The name is an identifier**, looked up in `shaders/include/` of its namespace. *(code)*
  - **Quotes do not mean "relative to this file":** a `"helper.glsl"` placed next to the shader in `core/` is not found (exp 02).
  - **Identifier rules apply:** lowercase letters, digits, `_ - . /` only. `DynamicTransforms.glsl` fails with `malformed id` (exp 05).
- **`#moj_import` no longer exists.** It fails with `invalid directive: moj_import` (exp 07).
- **An include may not contain `#version`.** It fails with `'#version' : must occur first in shader` (exp 09). Vanilla includes still had one in 26.2.
- **Vanilla includes have include guards**, so including one twice is harmless (exp 06). The exception is `terrainglobals.glsl`: a typo in its guard (`MINECRAFT_TERRAINGLOBLAS_GLSL`) breaks it, and including it twice fails with `Cannot reuse block name` (exp 08). Give your own includes guards too:

```glsl
#ifndef MYLIB_NOISE_GLSL
#define MYLIB_NOISE_GLSL
// ...
#endif
```

## Defines and variants

A program is compiled once **per pipeline** that uses it, with that pipeline's defines. `core/entity` is compiled in 37 variants, with defines such as `ALPHA_CUTOUT`, `EMISSIVE`, `NO_OVERLAY`, `PER_FACE_LIGHTING`, `DISSOLVE`, `GLINT`, and the `OIT_*` defines of the transparency passes. [core-shaders.md](reference/core-shaders.md) lists them for every program.

**A replacement shader must compile and validate in every variant**, not only the one you are looking at. The usual approach is to start from the vanilla file and keep its `#ifdef` structure.

The game also adds up to three defines that depend on the device. *(code)*

| Define | Meaning |
|---|---|
| `RENDERPEARL_DEPTH_IS_ZERO_TO_ONE` | The backend's depth range is [0, 1] |
| `RENDERPEARL_EXPLICIT_DEPTH_INVARIANCE` | The device needs depth written explicitly for invariance |
| `RENDERPEARL_INSTANCE_INDEX_INCLUDES_BASE_INSTANCE` | The instance index already includes the base instance |

`tools/mcshaders check` compiles every variant under all 8 combinations of these.

## Varyings (vertex → fragment)

```glsl
// .vsh
layout(location = 0) out vec4 vertexColor;
// .fsh
layout(location = 0) in vec4 vertexColor;
```

- **Every `in` and `out` needs `layout(location = N)`.** Otherwise: `SPIR-V requires location for user input/output` (exp 20).
- **Outputs and inputs are matched by location only.** The names may differ (exp 21). On OpenGL they are renamed after their location anyway. *(code)*
- **At a given location, both sides must agree** on base type, vector size and `flat` (exp 22).
- **Every fragment input needs a vertex output** at its location (exp 23). The reverse is fine: unused vertex outputs are allowed (exp 24).
- **`layout(component = N)` is rejected.** *(code)*
- **A program can be linked with more than one partner.** For example, `core/position_color.fsh` is also used with `core/debug_point.vsh`. Changing its inputs must still match every partner. The partners are listed in [core-shaders.md](reference/core-shaders.md).

## Vertex inputs

```glsl
layout(location = 0) in vec3 Position;
layout(location = 1) in vec4 Color;
```

- **Inputs are matched to the pipeline's vertex format by name.** `Position`, `Color`, `UV0`, `UV1`, `UV2`, `Normal`… must keep their exact names (exp 30). The location you give is used for binding. Each program's names and formats are in [core-shaders.md](reference/core-shaders.md).
- **The base type must match the format.** Float and normalized formats need `float`/`vec*`, signed integer formats `int`/`ivec*`, unsigned ones `uint`/`uvec*` (exp 31).
- **You may read fewer components than the format provides**, for example `vec3` from an RGBA color (exp 32), but not more. *(code)*

## Quads and moving vertices

Most of the game's geometry is quads: 4 vertices each, drawn as two triangles.

- **`gl_VertexIndex / 4` is the index of the quad**, and `gl_VertexIndex % 4` the corner within it. [text-effects](../examples/text-effects/) uses it to animate each glyph separately.
- **Back faces are culled** in most pipelines (`"cull": true` in [pipelines.json](../reference/26.3/pipelines.json)). A vertex shader that moves vertices must keep the triangles **counter-clockwise on screen** (NDC, `y` up). In [world-anchor](../examples/world-anchor/), corners placed at (0, 0), (1, 0), (1, 1), (0, 1) for `gl_VertexIndex % 4` = 0, 1, 2, 3 are drawn on both backends, while the reverse order disappears.
- **NDC (-1, -1) is the bottom-left corner of the screen** on both backends, in the world and in the GUI ([exp 72](../experiments/72-gui-bottom/)).
- **A `flat` varying takes its value from a different vertex of the triangle on OpenGL and on Vulkan.** Give all vertices of a primitive the same value if it matters.

## Uniforms and samplers

- **Plain uniforms are gone.** `uniform float x;` fails with `non-opaque uniforms outside a block` (exp 40). Only samplers can be declared alone.
- **A core shader can only declare the uniform blocks and samplers its pipeline provides, by name.** A new block fails (exp 41), and so does a sampler the pipeline does not bind (exp 43). The error is `Unable to find shader defined uniform (Name)`.
- **This applies to unused declarations too.** Declaring `uniform sampler2D Sampler9;` without ever reading it still fails (exp 42). Every declared uniform must exist in **every** pipeline the program is compiled for.
- **Some uniforms only exist in some variants.** For example, `Sampler2` (the lightmap) is not bound for emissive entities. Declare those only under the define that guarantees them. [core-shaders.md](reference/core-shaders.md) gives the guard for each one, such as `#if !defined(EMISSIVE) && !defined(OIT_ALPHA_ONLY)` for `Sampler2` in `core/entity`.
- **Vanilla blocks may be declared by hand** instead of included, if every member is there in the vanilla order (exp 44). The layouts are in [uniforms.md](reference/uniforms.md). Prefer including the vanilla file, because these layouts change between versions: `Globals` and `DynamicTransforms` were reordered between 26.2 and 26.3, so a hand-written copy from 26.2 silently reads the wrong values.
- **Only 2D, cube, rectangle and buffer textures are supported.** 1D and 3D textures are rejected. *(code)*

## Checking a pack

```sh
tools/mcshaders check path/to/pack
```

This compiles and validates every pipeline that uses a file from the pack, the way the game does, and prints each problem once with the pipelines it breaks. It agrees with the game on every experiment in this repository. To see a pack in the game, use `tools/launch.py` (see [tools](../tools/README.md)).
