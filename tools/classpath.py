"""Print the classpath (game jar + libraries) for a Minecraft version, macOS arm64."""
import json
import os
import sys

mc = os.environ.get("MINECRAFT_DIR", os.path.expanduser("~/Library/Application Support/minecraft"))
version = sys.argv[1]
with open(os.path.join(mc, "versions", version, version + ".json")) as f:
    meta = json.load(f)


def allowed(lib):
    rules = lib.get("rules")
    if not rules:
        return True
    ok = False
    for rule in rules:
        os_rule = rule.get("os", {})
        matches = not os_rule or (os_rule.get("name") == "osx" and os_rule.get("arch", "arm64") == "arm64")
        if matches:
            ok = rule["action"] == "allow"
    return ok


paths = []
for lib in meta["libraries"]:
    if not allowed(lib):
        continue
    artifact = lib.get("downloads", {}).get("artifact")
    if artifact:
        p = os.path.join(mc, "libraries", artifact["path"])
        if os.path.exists(p):
            paths.append(p)
paths.append(os.path.join(mc, "versions", version, version + ".jar"))
print(":".join(paths))
