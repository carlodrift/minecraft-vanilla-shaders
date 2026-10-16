"""Show what each core program draws: paint it magenta and take screenshots of a test scene.

    python3 tools/gallery.py [programs...] [--backend vulkan] [--version 26.3]

For each fragment program, builds a pack whose copy of the vanilla program outputs magenta (keeping
the vanilla code, so discards and variants behave as usual), loads it in a test world with the
scene below and saves two screenshots, with and without the HUD, to docs/images/programs/.
A baseline without any pack is saved as _vanilla.
"""
import argparse
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

# Programs that never draw into the world view (atlases, depth copies, OIT bookkeeping, title screen).
NOT_IN_SCENE = {"animate_sprite_blit", "animate_sprite_interpolate", "blit_depth", "integrate_depth", "lightmap",
                "oit_composite", "oit_depth_bounds_cull", "panorama"}

SCENE = """world shader-test
wait 2
command gamerule advance_time false
command time set 6000
command weather clear
command worldborder center 3 0
command worldborder set 34
command fill -3 3 6 -1 3 9 minecraft:water
command setblock 7 4 6 minecraft:light_blue_stained_glass
command setblock 8 4 8 minecraft:oak_leaves[persistent=true]
command fill 4 3 11 6 3 13 minecraft:iron_block
command setblock 5 4 12 minecraft:beacon
command setblock 0 4 11 minecraft:end_portal
command setblock 1 4 6 minecraft:chest
command setblock 3 4 4 minecraft:oak_sign[rotation=8]{front_text:{messages:["Shader","test","",""]}}
command setblock 7 4 4 minecraft:oak_fence
command summon pig 3 4 8 {NoAI:1b,Rotation:[160f,0f]}
command summon pig 7 4 5 {NoAI:1b,Rotation:[90f,0f],leash:[I;7,4,4]}
command summon cow 6 4 9 {NoAI:1b,Glowing:1b,Rotation:[200f,0f]}
command summon armor_stand 1 4 4 {CustomName:"Armor stand",CustomNameVisible:1b,ShowArms:1b}
command summon item 4 5 5 {Item:{id:"minecraft:diamond_sword",count:1,components:{"minecraft:enchantment_glint_override":true}},NoGravity:1b,Age:-32768,PickupDelay:32767}
command summon falling_block 8 7 10 {BlockState:"minecraft:red_sand",NoGravity:1b,Time:-2147483648}
command tp @s 3 6 0 0 15
command item replace entity @s weapon.mainhand with minecraft:golden_pickaxe
hud off
wait 4
command particle minecraft:end_rod 3 5.5 6 1.5 0.6 0.6 0 60 force
wait 0.3
screenshot world
hud on
wait 1
screenshot hud
quit
"""


def magenta(source):
    """Rename the vanilla main and add one that runs it, then writes magenta."""
    source, n = re.subn(r"void\s+main\s*\(\s*\)", "void vanilla_main()", source)
    if n != 1:
        raise ValueError("expected exactly one main()")
    return source + """
void main() {
    vanilla_main();
#ifndef OIT_ALPHA_ONLY
    fragColor = vec4(1.0, 0.0, 1.0, 1.0);
#endif
}
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("programs", nargs="*")
    p.add_argument("--backend", default="vulkan")
    p.add_argument("--version", default="26.3")
    args = p.parse_args()

    jar = zipfile.ZipFile(os.path.join(MC, "versions", args.version, args.version + ".jar"))
    pack_format = json.loads(jar.read("version.json"))["pack_version"]["resource_major"]
    programs = sorted(n.rsplit("/", 1)[1][:-4] for n in jar.namelist()
                      if n.startswith("assets/minecraft/shaders/core/") and n.endswith(".fsh"))
    programs = [p for p in programs if p not in NOT_IN_SCENE and (not args.programs or p in args.programs)]

    out = os.path.join(ROOT, "docs", "images", "programs")
    os.makedirs(out, exist_ok=True)
    gamedir = os.path.join(ROOT, "build", "game")
    work = tempfile.mkdtemp(prefix="mcshaders-gallery-")
    script = os.path.join(work, "scene.txt")
    with open(script, "w") as f:
        f.write(SCENE)

    for program in (["_vanilla"] if not args.programs else []) + programs:
        pack = os.path.join(work, "gallery_" + program.strip("_"))
        os.makedirs(pack)
        with open(os.path.join(pack, "pack.mcmeta"), "w") as f:
            json.dump({"pack": {"description": "magenta " + program, "min_format": pack_format, "max_format": pack_format}}, f)
        if program != "_vanilla":
            name = f"assets/minecraft/shaders/core/{program}.fsh"
            target = os.path.join(pack, name)
            os.makedirs(os.path.dirname(target))
            with open(target, "w") as f:
                f.write(magenta(jar.read(name).decode()))
        shots = os.path.join(gamedir, "screenshots")
        for shot in ("world", "hud"):
            if os.path.exists(os.path.join(shots, shot + ".png")):
                os.remove(os.path.join(shots, shot + ".png"))
        subprocess.run([sys.executable, "-I", os.path.join(ROOT, "tools", "launch.py"), "--gamedir", gamedir,
                        "--pack", pack, "--backend", args.backend, "--script", script, "--seconds", "120",
                        "--size", "640x360"], capture_output=True)
        shutil.rmtree(os.path.join(gamedir, "resourcepacks", os.path.basename(pack)), ignore_errors=True)
        with open(os.path.join(gamedir, "logs", "latest.log"), errors="replace") as f:
            failed = "Caught error loading resourcepacks" in f.read()
        saved = []
        for shot in ("world", "hud"):
            src = os.path.join(shots, shot + ".png")
            if os.path.exists(src) and not failed:
                dst = os.path.join(out, f"{program}-{shot}.jpg")
                subprocess.run(["sips", "-Z", "640", "-s", "format", "jpeg", "-s", "formatOptions", "80", src, "--out", dst],
                               capture_output=True)
                saved.append(shot)
        print(f"{program:28} {'FAILED TO LOAD' if failed else ' '.join(saved) or 'no screenshot'}")
    shutil.rmtree(work)


if __name__ == "__main__":
    main()
