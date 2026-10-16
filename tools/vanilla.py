"""Extract or compare the vanilla shaders of installed Minecraft versions.

    python3 tools/vanilla.py extract 26.1.2 DIR      # shaders/ and post_effect/ of 26.1.2 into DIR
    python3 tools/vanilla.py diff 26.2 26.3          # files added, removed and changed between two versions
    python3 tools/vanilla.py diff 26.2 26.3 -u       # with a unified diff of the changed files

Versions must be installed by the launcher (~/Library/Application Support/minecraft/versions),
or in MINECRAFT_DIR (see tools/fetch.py).
"""
import argparse
import difflib
import os
import zipfile

# The launcher's directory; MINECRAFT_DIR overrides it (e.g. for a client fetched by tools/fetch.py).
MC = os.environ.get("MINECRAFT_DIR", os.path.expanduser("~/Library/Application Support/minecraft"))
PREFIXES = ("assets/minecraft/shaders/", "assets/minecraft/post_effect/")


def files(version):
    jar = zipfile.ZipFile(os.path.join(MC, "versions", version, version + ".jar"))
    return {n.removeprefix("assets/minecraft/"): jar.read(n).decode()
            for n in jar.namelist() if n.startswith(PREFIXES) and not n.endswith("/")}


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract")
    e.add_argument("version")
    e.add_argument("dir")
    d = sub.add_parser("diff")
    d.add_argument("old")
    d.add_argument("new")
    d.add_argument("-u", action="store_true", help="print a unified diff of changed files")
    args = p.parse_args()

    if args.cmd == "extract":
        for name, text in files(args.version).items():
            path = os.path.join(args.dir, name)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
        return

    old, new = files(args.old), files(args.new)
    for name in sorted(set(old) | set(new)):
        if name not in new:
            print(f"removed  {name}")
        elif name not in old:
            print(f"added    {name}")
        elif old[name] != new[name]:
            print(f"changed  {name}")
            if args.u:
                print("".join(difflib.unified_diff(old[name].splitlines(True), new[name].splitlines(True),
                                                   f"{args.old}/{name}", f"{args.new}/{name}")))


if __name__ == "__main__":
    main()
