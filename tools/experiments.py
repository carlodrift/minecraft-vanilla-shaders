"""Build and run the experiments in experiments/.

    python3 tools/experiments.py                 # run `check` on every experiment
    python3 tools/experiments.py --ingame        # also load each pack in the game, OpenGL and Vulkan
    python3 tools/experiments.py 08 14 --ingame  # only experiments whose id starts with 08 or 14

Each experiment is a directory with an experiment.json:

    {
      "title": "...",
      "expect": "pass" | "fail",
      "files": [
        {"path": "assets/minecraft/shaders/core/position_color.fsh",
         "vanilla": "assets/minecraft/shaders/core/position_color.fsh",   # start from the game's file
         "edits": [{"find": "...", "replace": "..."}]},                    # each find must match once
        {"path": "assets/mylib/shaders/include/x.glsl", "content": "..."} # or a file written as-is
      ],
      "scene": {                       # optional: in game, join a test world and take a screenshot
        "commands": ["posteffect add @s mylib:gray"],
        "log_pass": ["regex that must appear in the log"],
        "log_fail": ["regex that must not appear"]
      }
    }

Packs are built from the installed game jar, so the repository contains no copy of vanilla files.
Results are written to experiments/RESULTS.md.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MC = os.path.expanduser("~/Library/Application Support/minecraft")


def build(exp_dir, jar, out_dir, pack_format):
    with open(os.path.join(exp_dir, "experiment.json")) as f:
        exp = json.load(f)
    pack = os.path.join(out_dir, os.path.basename(exp_dir))
    shutil.rmtree(pack, ignore_errors=True)
    os.makedirs(pack)
    with open(os.path.join(pack, "pack.mcmeta"), "w") as f:
        json.dump({"pack": {"description": exp["title"], "min_format": pack_format, "max_format": pack_format}}, f)
    for spec in exp["files"]:
        if "vanilla" in spec:
            text = jar.read(spec["vanilla"]).decode()
            for edit in spec.get("edits", []):
                count = text.count(edit["find"])
                if count != 1:
                    raise SystemExit(f"{exp_dir}: edit matches {count} times in {spec['vanilla']}: {edit['find']!r}")
                text = text.replace(edit["find"], edit["replace"])
        else:
            text = spec["content"]
        target = os.path.join(pack, spec["path"])
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as f:
            f.write(text)
    return exp, pack


def run_check(pack, env):
    r = subprocess.run([os.path.join(ROOT, "tools", "mcshaders"), "check", pack], capture_output=True, text=True, env=env)
    problems = [l[4:] for l in r.stdout.splitlines() if l.startswith("  | ")]
    return ("pass" if r.returncode == 0 else "fail"), (problems[0] if problems else "")


SCENE = """world shader-test
wait 2
command time set noon
command setblock 2 4 5 minecraft:red_wool
command setblock 3 4 5 minecraft:lime_wool
command setblock 4 4 5 minecraft:blue_wool
command setblock 3 5 5 minecraft:glowstone
command tp @s 3 6 0 0 20
hud off
wait 3
"""


def run_game(exp, exp_dir, pack, backend, gamedir, env):
    """Load the pack in the game. With a "scene", join a test world, run its commands and take a screenshot."""
    name = os.path.basename(pack)
    cmd = [sys.executable, "-I", os.path.join(ROOT, "tools", "launch.py"), "--gamedir", gamedir,
           "--pack", pack, "--backend", backend]
    scene = exp.get("scene")
    if scene is not None:
        script = os.path.join(gamedir, "script.txt")
        with open(script, "w") as f:
            f.write(SCENE)
            for command in scene.get("commands", []):
                f.write(f"command {command}\nwait 1\n")
            f.write("wait 2\nscreenshot experiment\nwait 1\nquit\n")
        shot = os.path.join(gamedir, "screenshots", "experiment.png")
        if os.path.exists(shot):
            os.remove(shot)
        cmd += ["--script", script, "--seconds", "90", "--size", "640x360"]
    else:
        cmd += ["--seconds", "20"]
    subprocess.run(cmd, capture_output=True, env=env)
    shutil.rmtree(os.path.join(gamedir, "resourcepacks", name), ignore_errors=True)
    with open(os.path.join(gamedir, "logs", "latest.log"), errors="replace") as f:
        log = f.read()
    device = re.search(r"Using graphics backend (\w+), using drivers: (.*)", log)
    device = device.groups() if device else None
    if "Caught error loading resourcepacks" in log:
        m = re.search(r"(ShaderCompileException: .*|Couldn't parse GLSL: .*)", log)
        return "fail", (m.group(1) if m else "packs removed"), device
    if f"file/{name}" not in log:
        return "not loaded", "", device
    if scene is not None:
        shot = os.path.join(gamedir, "screenshots", "experiment.png")
        if os.path.exists(shot):
            target = os.path.join(exp_dir, f"{backend}.png")
            subprocess.run(["sips", "-Z", "640", shot, "--out", target], capture_output=True)
        for pattern in scene.get("log_fail", []):
            m = re.search(pattern + ".*", log)
            if m:
                return "fail", m.group(0)[:200], device
        for pattern in scene.get("log_pass", []):
            if not re.search(pattern, log):
                return "fail", f"log never matched: {pattern}", device
    return "pass", "", device


def main():
    p = argparse.ArgumentParser()
    p.add_argument("ids", nargs="*")
    p.add_argument("--ingame", action="store_true")
    p.add_argument("--version", default="26.3")
    args = p.parse_args()

    env = dict(os.environ, MC_VERSION=args.version)
    jar_path = os.path.join(MC, "versions", args.version, args.version + ".jar")
    jar = zipfile.ZipFile(jar_path)
    pack_format = json.loads(jar.read("version.json"))["pack_version"]["resource_major"]
    exp_root = os.path.join(ROOT, "experiments")
    dirs = sorted(d for d in os.listdir(exp_root)
                  if os.path.isfile(os.path.join(exp_root, d, "experiment.json"))
                  and (not args.ids or any(d.startswith(i) for i in args.ids)))

    out_dir = tempfile.mkdtemp(prefix="mcshaders-exp-")
    gamedir = os.path.join(ROOT, "build", "game")
    os.makedirs(gamedir, exist_ok=True)
    results_path = os.path.join(exp_root, "results.json")
    results = {}
    if os.path.exists(results_path):
        with open(results_path) as f:
            results = json.load(f)

    for d in dirs:
        exp, pack = build(os.path.join(exp_root, d), jar, out_dir, pack_format)
        row = results.get(d, {})
        row.update(title=exp["title"], expect=exp["expect"], version=args.version)
        row["check"], row["check_message"] = run_check(pack, env)
        line = f"{d:40} expect={exp['expect']:4} check={row['check']:4}"
        if args.ingame:
            for backend in ("opengl", "vulkan"):
                verdict, message, device = run_game(exp, os.path.join(exp_root, d), pack, backend, gamedir, env)
                row[backend] = verdict
                row[backend + "_message"] = message
                if device:
                    row[backend + "_device"] = f"{device[0]} {device[1]}"
                row["ingame_date"] = datetime.date.today().isoformat()
                line += f" {backend}={verdict}"
        mismatch = {row.get(k) for k in ("check", "opengl", "vulkan") if row.get(k)} != {exp["expect"]}
        print(line + ("   <-- MISMATCH" if mismatch else ""))
        results[d] = row

    with open(results_path, "w") as f:
        json.dump(results, f, indent=2, sort_keys=True)
        f.write("\n")
    write_markdown(results, os.path.join(exp_root, "RESULTS.md"))
    shutil.rmtree(out_dir)


def write_markdown(results, path):
    devices = sorted({r[k] for r in results.values() for k in ("opengl_device", "vulkan_device") if r.get(k)})
    lines = [
        "# Experiment results",
        "",
        "Generated by `tools/experiments.py`. `check` is `tools/mcshaders check`; the OpenGL and Vulkan",
        "columns come from loading the pack in the game and reading `logs/latest.log`.",
        "",
        "Tested on: " + "; ".join(devices) if devices else "Not run in game yet.",
        "",
        "| Experiment | Expected | check | OpenGL | Vulkan | Message | Screenshot |",
        "|---|---|---|---|---|---|---|",
    ]
    for d, r in sorted(results.items()):
        message = r.get("check_message") or r.get("opengl_message") or ""
        message = message.replace("|", "\\|")
        if len(message) > 140:
            message = message[:137] + "..."
        shots = " · ".join(f"[{b}]({d}/{b.lower()}.png)" for b in ("OpenGL", "Vulkan")
                           if os.path.exists(os.path.join(os.path.dirname(path), d, f"{b.lower()}.png")))
        lines.append(f"| [{d}]({d}/) {r['title']} | {r['expect']} | {r['check']} | {r.get('opengl', '-')} | {r.get('vulkan', '-')} | {message} | {shots} |")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
