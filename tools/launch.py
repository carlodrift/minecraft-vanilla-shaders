"""Launch an installed Minecraft version offline, in an isolated game directory, with a test pack.

    python3 tools/launch.py --gamedir DIR [--pack PACK_DIR] [--backend opengl|vulkan|default]
                            [--seconds N] [--world NAME] [--version 26.3]

The pack is linked into DIR/resourcepacks and enabled in DIR/options.txt. With --seconds, the game
is stopped after N seconds and the shader-related lines of DIR/logs/latest.log are printed.
Requires Java 25+ (JAVA environment variable, or java on PATH).
"""
import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
import zipfile

# The launcher's directory; MINECRAFT_DIR overrides it (e.g. for a client fetched by tools/fetch.py).
MC = os.environ.get("MINECRAFT_DIR", os.path.expanduser("~/Library/Application Support/minecraft"))


def allowed(rules):
    if not rules:
        return True
    ok = False
    for rule in rules:
        os_rule = rule.get("os", {})
        if not os_rule or os_rule.get("name") == "osx":
            ok = rule["action"] == "allow"
    return ok


def flatten(args, values):
    out = []
    for arg in args:
        if isinstance(arg, dict):
            if not allowed(arg.get("rules")):
                continue
            arg = arg["value"]
        for a in [arg] if isinstance(arg, str) else arg:
            out.append(re.sub(r"\$\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), a))
    return out


def set_options(path, pack_name, backend, data_version, extra=()):
    # Without a version line the game treats options.txt as very old and resets these settings.
    lines = [f"version:{data_version}"]
    if os.path.exists(path):
        with open(path) as f:
            lines = [l.rstrip("\n") for l in f]
    wanted = {
        "resourcePacks": json.dumps(["vanilla"] + ([f"file/{pack_name}"] if pack_name else [])),
        "preferredGraphicsBackend": f'"{backend}"',
        "onboardAccessibility": "false",
        "skipMultiplayerWarning": "true",
        "tutorialStep": "none",
        "joinedFirstServer": "true",
        "pauseOnLostFocus": "false",
        # Reset on every launch so a previous --option does not leak into the next run. A named
        # graphics preset re-applies its own values on load: use graphicsPreset="custom" to change them.
        "graphicsPreset": '"fancy"',
        "improvedTransparency": "false",
    }
    # Undo the --option values of the previous launch, then remember the values this launch replaces.
    saved_path = os.path.join(os.path.dirname(path), "launch-options-backup.json")
    current = dict(l.split(":", 1) for l in lines if ":" in l)
    if os.path.exists(saved_path):
        with open(saved_path) as f:
            for key, value in json.load(f).items():
                wanted.setdefault(key, value)
    backup = {k: current[k] for k, _ in extra if k in current and k not in ("graphicsPreset", "improvedTransparency")}
    with open(saved_path, "w") as f:
        json.dump(backup, f)
    wanted.update(extra)
    seen = set()
    for i, line in enumerate(lines):
        key = line.split(":", 1)[0]
        if key in wanted:
            lines[i] = f"{key}:{wanted[key]}"
            seen.add(key)
    lines += [f"{k}:{v}" for k, v in wanted.items() if k not in seen]
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version", default="26.3")
    p.add_argument("--gamedir", required=True)
    p.add_argument("--pack")
    p.add_argument("--backend", default="default", choices=["default", "opengl", "vulkan"])
    p.add_argument("--seconds", type=int)
    p.add_argument("--world", help="quick-play into this singleplayer world (must exist in DIR/saves)")
    p.add_argument("--script", help="drive the game with tools/agent/ShaderTestAgent.java and this script; "
                                    "with --seconds, waits for the game to quit (or the timeout)")
    p.add_argument("--size", default="854x480", help="window size, WIDTHxHEIGHT")
    p.add_argument("--option", action="append", default=[], metavar="KEY=VALUE",
                   help="set an options.txt entry, e.g. improvedTransparency=true (repeatable)")
    args = p.parse_args()

    gamedir = os.path.abspath(args.gamedir)
    os.makedirs(os.path.join(gamedir, "resourcepacks"), exist_ok=True)
    pack_name = None
    if args.pack:
        # Copied, not linked: the game ignores symlinked packs unless allowed_symlinks.txt lists them.
        pack_name = os.path.basename(os.path.normpath(args.pack))
        target = os.path.join(gamedir, "resourcepacks", pack_name)
        if os.path.islink(target) or os.path.isfile(target):
            os.remove(target)
        elif os.path.isdir(target):
            shutil.rmtree(target)
        shutil.copytree(args.pack, target)
    jar = os.path.join(MC, "versions", args.version, args.version + ".jar")
    with zipfile.ZipFile(jar) as z:
        data_version = json.loads(z.read("version.json"))["world_version"]
    set_options(os.path.join(gamedir, "options.txt"), pack_name, args.backend, data_version,
                [tuple(o.split("=", 1)) for o in args.option])

    with open(os.path.join(MC, "versions", args.version, args.version + ".json")) as f:
        meta = json.load(f)
    classpath = []
    for lib in meta["libraries"]:
        artifact = lib.get("downloads", {}).get("artifact")
        if artifact and allowed(lib.get("rules")):
            path = os.path.join(MC, "libraries", artifact["path"])
            if os.path.exists(path):
                classpath.append(path)
    classpath.append(os.path.join(MC, "versions", args.version, args.version + ".jar"))
    natives = os.path.join(gamedir, "natives")
    values = {
        "auth_player_name": "ShaderTest",
        "version_name": args.version,
        "game_directory": gamedir,
        "assets_root": os.path.join(MC, "assets"),
        "assets_index_name": meta["assetIndex"]["id"],
        "auth_uuid": str(uuid.uuid3(uuid.NAMESPACE_DNS, "ShaderTest")),
        "auth_access_token": "0",
        "clientid": "0",
        "auth_xuid": "0",
        "user_type": "legacy",
        "version_type": meta.get("type", "release"),
        "natives_directory": natives,
        "launcher_name": "minecraft-vanilla-shaders",
        "launcher_version": "1",
        "classpath": ":".join(classpath),
    }
    jvm = flatten(meta["arguments"]["jvm"], values)
    game = [a for a in flatten([a for a in meta["arguments"]["game"] if isinstance(a, str)], values)]
    if args.world:
        game += ["--quickPlaySingleplayer", args.world]
    width, height = args.size.split("x")
    game += ["--width", width, "--height", height]
    java = os.environ.get("JAVA", "java")
    agent = []
    if args.script:
        agent = [f"-javaagent:{build_agent(java, classpath)}={os.path.abspath(args.script)}"]
    cmd = [java, "-Xmx4G"] + agent + jvm + [meta["mainClass"]] + game

    log = os.path.join(gamedir, "logs", "latest.log")
    if os.path.exists(log):
        os.remove(log)
    with open(os.path.join(gamedir, "stdout.log"), "w") as out:
        proc = subprocess.Popen(cmd, cwd=gamedir, stdout=out, stderr=subprocess.STDOUT)
    if args.seconds is None:
        print(f"started pid {proc.pid}")
        return
    # Agent output goes to stdout.log; a script ending with "quit" stops the game before the timeout.
    deadline = time.time() + args.seconds
    while time.time() < deadline and proc.poll() is None:
        time.sleep(1)
    if proc.poll() is None:
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(20)
        except subprocess.TimeoutExpired:
            proc.kill()
    if os.path.exists(log):
        with open(log, errors="replace") as f:
            for line in f:
                if re.search(r"shader|pipeline|GLSL|Vulkan|OpenGL|backend|Reloading ResourceManager|ERROR|post effect|post chain", line, re.I):
                    print(line.rstrip()[:400])
    else:
        print("no latest.log; see", os.path.join(gamedir, "stdout.log"))
    with open(os.path.join(gamedir, "stdout.log"), errors="replace") as f:
        for line in f:
            if line.startswith("[shader-test-agent]"):
                print(line.rstrip())


def build_agent(java, classpath):
    """Compile tools/agent/ShaderTestAgent.java against the game into build/agent/, if out of date."""
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    source = os.path.join(root, "tools", "agent", "ShaderTestAgent.java")
    out = os.path.join(root, "build", "agent")
    jar = os.path.join(out, "shader-test-agent.jar")
    if os.path.exists(jar) and os.path.getmtime(jar) > os.path.getmtime(source):
        return jar
    os.makedirs(os.path.join(out, "classes"), exist_ok=True)
    bindir = os.path.dirname(java) if os.path.dirname(java) else ""
    javac = os.path.join(bindir, "javac") if bindir else "javac"
    jartool = os.path.join(bindir, "jar") if bindir else "jar"
    subprocess.run([javac, "-cp", ":".join(classpath), "-d", os.path.join(out, "classes"), source], check=True)
    with open(os.path.join(out, "MANIFEST.MF"), "w") as f:
        f.write("Premain-Class: ShaderTestAgent\n")
    subprocess.run([jartool, "cfm", jar, os.path.join(out, "MANIFEST.MF"), "-C", os.path.join(out, "classes"), "."], check=True)
    return jar


if __name__ == "__main__":
    sys.exit(main())
