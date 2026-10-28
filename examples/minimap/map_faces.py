"""Add a map face to every vanilla block model: a copy of the model's top face, inside the model, at a
height that no vanilla model uses. terrain.vsh recognizes these faces by that height and draws them
into the capture square instead of the world (see minimap.glsl).

Called by tools/experiments.py when it builds the example: generate(jar, pack).
"""
import json
import os

# Heights (in model pixels, 0 to 16) that no vanilla block model uses on any axis, and whose
# opposite (16 - h) is free too, so a model turned by its blockstate still lands on a free value.
# Checked against 26.3; minimap.glsl lists the same values as MAP_MARKS.
MARKS = [0.75, 1.25, 1.75, 2.25, 2.75, 3.25, 6.25, 6.75, 7.25,
         8.75, 9.25, 9.75, 12.75, 13.25, 13.75, 14.25, 14.75, 15.25]

PREFIX = "assets/minecraft/models/block/"


def map_element(model):
    """The map element for a model, or None: its highest unrotated element with an up face gets a
    copy of that face, at the highest free height strictly inside the element, so it stays hidden."""
    tops = [e for e in model.get("elements", []) if "up" in e.get("faces", {}) and "rotation" not in e]
    if not tops:
        return None
    top = max(tops, key=lambda e: e["to"][1])
    low, high = top["from"][1], top["to"][1]
    inside = [m for m in MARKS if low < m < high]
    if not inside:
        return None   # too thin to hide a face: rails, redstone dust, lily pads, tripwires...
    mark = inside[-1]
    face = {k: v for k, v in top["faces"]["up"].items() if k in ("texture", "uv", "rotation", "tintindex", "cullface")}
    if "uv" not in face:
        # Default UVs follow the element's extent: keep the top element's, not the new element's.
        face["uv"] = [top["from"][0], top["from"][2], top["to"][0], top["to"][2]]
    element = {"from": [top["from"][0], mark, top["from"][2]], "to": [top["to"][0], mark, top["to"][2]],
               "faces": {"up": face}}
    if "shade" in top:
        element["shade"] = top["shade"]
    return element


def generate(jar, pack):
    for name in jar.namelist():
        if not (name.startswith(PREFIX) and name.endswith(".json")):
            continue
        model = json.loads(jar.read(name))
        element = map_element(model)
        if element is None:
            continue
        model["elements"].append(element)
        target = os.path.join(pack, name)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w") as f:
            json.dump(model, f, indent=1)
