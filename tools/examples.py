"""Build, check and film the examples in examples/.

    python3 tools/examples.py                       # check every example
    python3 tools/examples.py --screenshots         # also film each one in game (Vulkan) into examples/<name>/
    python3 tools/examples.py terrain-wave --out ~/Desktop   # build a ready-to-use pack folder
    python3 tools/examples.py --sodium JAR [--screenshots]   # check (and film) with Sodium's terrain pipelines;
                                                             # screenshots go to build/sodium-shots/

An example uses the experiment format (see tools/experiments.py): files built from the installed game's
vanilla files plus edits, and a "scene" with commands to run before the screenshot.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import experiments  # noqa: E402

ROOT = experiments.ROOT
MC = experiments.MC


def main():
    p = argparse.ArgumentParser()
    p.add_argument("names", nargs="*")
    p.add_argument("--screenshots", action="store_true")
    p.add_argument("--out", help="write the built packs here instead of a temporary directory")
    p.add_argument("--version", default="26.3")
    p.add_argument("--sodium", metavar="JAR", help="also check Sodium's terrain pipelines, and film with Fabric and Sodium")
    args = p.parse_args()

    env = dict(os.environ, MC_VERSION=args.version)
    jar = zipfile.ZipFile(os.path.join(MC, "versions", args.version, args.version + ".jar"))
    pack_format = json.loads(jar.read("version.json"))["pack_version"]["resource_major"]
    root = os.path.join(ROOT, "examples")
    names = sorted(d for d in os.listdir(root) if os.path.isfile(os.path.join(root, d, "example.json"))
                   and (not args.names or d in args.names))
    out_dir = os.path.abspath(os.path.expanduser(args.out)) if args.out else tempfile.mkdtemp(prefix="mcshaders-examples-")
    os.makedirs(out_dir, exist_ok=True)
    gamedir = os.path.join(ROOT, "build", "game")
    os.makedirs(gamedir, exist_ok=True)

    failed = 0
    for name in names:
        src = os.path.join(root, name)
        with open(os.path.join(src, "example.json")) as f:
            exp, pack = experiments.build(json.load(f), name, jar, out_dir, pack_format)
        sodium = os.path.abspath(args.sodium) if args.sodium else None
        verdict, message = experiments.run_check(pack, env, sodium)
        line = f"{name:24} check={verdict}" + (f" ({message})" if message else "")
        if args.screenshots:
            game_verdict, game_message, _ = experiments.run_game(exp, src, pack, "vulkan", gamedir, env, sodium)
            shot = os.path.join(src, "vulkan-sodium.png" if sodium else "vulkan.png")
            if sodium and os.path.exists(shot):
                os.makedirs(os.path.join(ROOT, "build", "sodium-shots"), exist_ok=True)
                shutil.move(shot, os.path.join(ROOT, "build", "sodium-shots", name + ".png"))
            elif os.path.exists(shot):
                subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "85", shot,
                                "--out", os.path.join(src, "screenshot.jpg")], capture_output=True)
                os.remove(shot)
            line += f" game={game_verdict}" + (f" ({game_message})" if game_message else "")
        if args.out:
            line += f" -> {pack}"
        print(line)
        failed += verdict != "pass"
    if not args.out:
        shutil.rmtree(out_dir)
    if failed:
        raise SystemExit(f"{failed} example(s) failed tools/mcshaders check")


if __name__ == "__main__":
    main()
