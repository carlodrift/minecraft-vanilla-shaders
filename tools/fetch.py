"""Download a vanilla client (jar and libraries, no assets) from Mojang, for tools/mcshaders without the launcher.

    MINECRAFT_DIR=build/minecraft python3 tools/fetch.py 26.3
    MINECRAFT_DIR=build/minecraft python3 tools/fetch.py latest-snapshot   # prints the version it fetched

Files go to $MINECRAFT_DIR in the launcher's layout (versions/, libraries/), with their SHA-1 checked.
Enough for `mcshaders check` and `mcshaders pipelines`; launching the game also needs the assets, which
the official launcher installs. Libraries are fetched for macOS arm64, like the rest of the tools.
"""
import concurrent.futures
import hashlib
import json
import os
import sys
import urllib.request

MANIFEST = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"


def get(url):
    with urllib.request.urlopen(url) as response:
        return response.read()


def save(url, sha1, path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            if hashlib.sha1(f.read()).hexdigest() == sha1:
                return
    data = get(url)
    if hashlib.sha1(data).hexdigest() != sha1:
        raise SystemExit(f"SHA-1 mismatch for {url}")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


def allowed(rules):
    if not rules:
        return True
    ok = False
    for rule in rules:
        os_rule = rule.get("os", {})
        if not os_rule or (os_rule.get("name") == "osx" and os_rule.get("arch", "arm64") == "arm64"):
            ok = rule["action"] == "allow"
    return ok


def main():
    version = sys.argv[1]
    mc = os.environ.get("MINECRAFT_DIR")
    if not mc:
        raise SystemExit("Set MINECRAFT_DIR to the directory to download into (not your launcher's).")
    manifest = json.loads(get(MANIFEST))
    if version == "latest-snapshot":
        version = manifest["latest"]["snapshot"]
    entry = next((v for v in manifest["versions"] if v["id"] == version), None)
    if entry is None:
        raise SystemExit(f"Unknown version {version}")
    meta_bytes = get(entry["url"])
    meta = json.loads(meta_bytes)
    version_dir = os.path.join(mc, "versions", version)
    os.makedirs(version_dir, exist_ok=True)
    with open(os.path.join(version_dir, version + ".json"), "wb") as f:
        f.write(meta_bytes)

    jobs = [(meta["downloads"]["client"]["url"], meta["downloads"]["client"]["sha1"], os.path.join(version_dir, version + ".jar"))]
    for lib in meta["libraries"]:
        artifact = lib.get("downloads", {}).get("artifact")
        if artifact and allowed(lib.get("rules")):
            jobs.append((artifact["url"], artifact["sha1"], os.path.join(mc, "libraries", artifact["path"])))
    with concurrent.futures.ThreadPoolExecutor(8) as pool:
        list(pool.map(lambda job: save(*job), jobs))
    print(f"{version}: client and {len(jobs) - 1} libraries in {mc}", file=sys.stderr)
    print(version)


if __name__ == "__main__":
    main()
