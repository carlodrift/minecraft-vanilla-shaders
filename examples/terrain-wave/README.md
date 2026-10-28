# Terrain wave

![Terrain wave](screenshot.jpg)

The world's chunk geometry ripples, purely in the vertex shader. Blocks still sit where they always were: only their rendering moves.

## How

`core/terrain.vsh` draws every chunk mesh: ground, water, glass, signs… (see [How a frame is drawn](../../docs/rendering.md)). The example adds three lines right after the vanilla position computation:

```glsl
vec3 pos = Position + (ChunkPosition - CameraBlockPos) + CameraOffset;   // vanilla
// World position of the vertex: its position inside the chunk section plus the section origin.
vec3 worldPos = Position + vec3(ChunkPosition);
// GameTime goes from 0 to 1 every 24000 ticks, then wraps: a whole number of periods (200) keeps the loop seamless.
pos.y += 1.2 * sin(worldPos.x * 0.35 + GameTime * 6.2831853 * 200.0) * cos(worldPos.z * 0.35);
```

- **`pos` is relative to the camera.** `Position` is the vertex inside its chunk section, and `ChunkPosition` the section's origin in block coordinates. Their sum gives a world position that stays stable as the camera moves.
- **`ChunkPosition` exists in both terrain paths:** as a uniform (`ChunkSection` block) and, with `MULTIDRAW_TERRAIN`, as a vertex input. The same line works in both.
- **`GameTime`** comes from `Globals`, which `terrain.vsh` already includes. It goes from 0 to 1 over 24000 ticks, then wraps. Multiplying it by 2π × 200 gives a wave period of 120 ticks (6 seconds), with no jump at the wrap.
- **Only the geometry moves.** Lighting is baked into the vertex color, so slopes are not shaded, and collisions are unchanged.

`pos` also feeds the fog distances further down, so the fog follows the displaced geometry.

## With Sodium

No wave: Sodium draws terrain with its own shader. It has no game time, only a clock per 128-block region, and a wave that spans the world tears at the regions' borders with it ([exp 82](../../experiments/82-sodium-region-clock-late/), [Sodium](../../docs/sodium.md)).

## Try it

```sh
python3 tools/examples.py terrain-wave --out ~/Desktop   # builds ~/Desktop/terrain-wave, a resource pack folder
```

The pack is built from your installed 26.3: vanilla `terrain.vsh` plus the edit in [example.json](example.json).