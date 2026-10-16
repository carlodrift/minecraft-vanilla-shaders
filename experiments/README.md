# Experiments

Each experiment changes one thing in a vanilla shader and records whether the game still loads it. Results: [RESULTS.md](RESULTS.md).

An experiment is a directory with an `experiment.json`. It has three fields:
- **`title`**: the question it answers.
- **`expect`**: `pass` or `fail`.
- **`files`**: the pack to build. A file either starts from the installed game's vanilla file and applies `edits` (`find` / `replace`; each `find` must match exactly once), or gives its full `content`.

Building packs from the installed game keeps vanilla files out of this repository. It also flags an experiment as soon as a new version changes the vanilla file it edits, because the `find` no longer matches.

```sh
python3 tools/experiments.py            # tools/mcshaders check on every experiment
python3 tools/experiments.py --ingame   # also load each pack in the game, OpenGL then Vulkan (~20 s each)
```

In game, a pack **fails** when the log contains `Caught error loading resourcepacks`. It **passes** when the game finishes loading with the pack enabled.

Numbering:

| Range | Topic |
|---|---|
| 0x | includes |
| 1x | the first lines (`#version`, extensions) |
| 2x | varyings |
| 3x | vertex inputs |
| 4x | uniforms and samplers |
