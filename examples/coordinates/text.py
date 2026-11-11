"""Add what the coordinates text needs to a pack: the game's font as a post-effect texture, and text.glsl.

The font PNG comes from the installed game's jar, so the repository has no copy of it. Used by the
coordinates example and by both minimaps, which print the coordinates under the map.

Called by tools/experiments.py when it builds the example: generate(jar, pack).
"""
import os
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))


def generate(jar, pack):
    # A texture input "coordinates:ascii" reads assets/coordinates/textures/effect/ascii.png.
    font = os.path.join(pack, "assets", "coordinates", "textures", "effect", "ascii.png")
    os.makedirs(os.path.dirname(font), exist_ok=True)
    with open(font, "wb") as f:
        f.write(jar.read("assets/minecraft/textures/font/ascii.png"))
    include = os.path.join(pack, "assets", "coordinates", "shaders", "include", "text.glsl")
    os.makedirs(os.path.dirname(include), exist_ok=True)
    shutil.copy(os.path.join(HERE, "text.glsl"), include)
