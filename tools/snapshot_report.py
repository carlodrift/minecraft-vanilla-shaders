"""Report, in Markdown, what a newer version changes for shader packs compared with a base version.

    python3 tools/snapshot_report.py 26.3 26.4-snapshot-4 > report.md

Both versions must be installed (launcher or MINECRAFT_DIR, see tools/fetch.py). The report covers:
the resource pack format, vanilla shader files added/removed/changed, render pipelines and the
uniforms and defines of each program, and the verdict of `tools/mcshaders check` for every
experiment and example built against the new version. Nothing in the repository is modified.
Exit status 1 if an experiment or example no longer gets its expected verdict.
"""
import glob
import json
import os
import subprocess
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import experiments  # noqa: E402
import vanilla  # noqa: E402

ROOT = experiments.ROOT


def jar(version):
    return zipfile.ZipFile(os.path.join(experiments.MC, "versions", version, version + ".jar"))


def pipelines(version):
    out = subprocess.run([os.path.join(ROOT, "tools", "mcshaders"), "pipelines"], capture_output=True, text=True,
                         env=dict(os.environ, MC_VERSION=version))
    if out.returncode != 0:
        return None, out.stderr.strip().splitlines()[-1] if out.stderr.strip() else "failed"
    return {p["location"]: p for p in map(json.loads, (l for l in out.stdout.splitlines() if l.startswith("{")))}, None


def programs(pls):
    result = {}
    for p in pls.values():
        for stage in ("vertex", "fragment"):
            if stage in p:
                uniforms, defines = result.setdefault(f"{p[stage].removeprefix('minecraft:')}.{stage[0]}sh", (set(), set()))
                uniforms |= {u["name"] for u in p["uniforms"]}
                defines |= set(p["flags"]) | set(p["defines"])
    return result


def main():
    old, new = sys.argv[1], sys.argv[2]
    out = [f"# Shader changes: {old} → {new}", ""]

    formats = [json.loads(jar(v).read("version.json"))["pack_version"]["resource_major"] for v in (old, new)]
    out += [f"Resource pack format: {formats[0]} → {formats[1]}", ""]

    a, b = vanilla.files(old), vanilla.files(new)
    out += ["## Vanilla files", ""]
    for label, names in (("Added", sorted(b.keys() - a.keys())), ("Removed", sorted(a.keys() - b.keys())),
                         ("Changed", sorted(n for n in a.keys() & b.keys() if a[n] != b[n]))):
        out.append(f"- **{label}** ({len(names)}): " + (", ".join(f"`{n}`" for n in names) or "none"))
    out.append("")

    out += ["## Pipelines", ""]
    pa, err_a = pipelines(old)
    pb, err_b = pipelines(new)
    if pa is None or pb is None:
        out += [f"`mcshaders pipelines` failed: {err_a or err_b}. The tools need updating for this version.", ""]
    else:
        short = lambda loc: loc.split("/", 1)[1]
        out.append(f"- **Added** ({len(pb.keys() - pa.keys())}): " + (", ".join(f"`{short(x)}`" for x in sorted(pb.keys() - pa.keys())) or "none"))
        out.append(f"- **Removed** ({len(pa.keys() - pb.keys())}): " + (", ".join(f"`{short(x)}`" for x in sorted(pa.keys() - pb.keys())) or "none"))
        out.append("")
        ga, gb = programs(pa), programs(pb)
        rows = []
        for name in sorted(ga.keys() | gb.keys()):
            ua, da = ga.get(name, (set(), set()))
            ub, db = gb.get(name, (set(), set()))
            if name not in ga or name not in gb or ua != ub or da != db:
                change = "new program" if name not in ga else "removed program" if name not in gb else ""
                diff = lambda x, y: " ".join([f"+`{n}`" for n in sorted(y - x)] + [f"−`{n}`" for n in sorted(x - y)])
                rows.append(f"| `{name}` | {change or diff(ua, ub)} | {'' if change else diff(da, db)} |")
        if rows:
            out += ["| Program | Uniforms | Defines |", "|---|---|---|"] + rows + [""]

    out += ["## Experiments and examples (`tools/mcshaders check`)", ""]
    new_jar = jar(new)
    work = tempfile.mkdtemp(prefix="mcshaders-report-")
    env = dict(os.environ, MC_VERSION=new)
    regressions = []
    specs = sorted(glob.glob(os.path.join(ROOT, "experiments", "*", "experiment.json"))
                   + glob.glob(os.path.join(ROOT, "examples", "*", "example.json")))
    for path in specs:
        name = os.path.basename(os.path.dirname(path))
        with open(path) as f:
            spec = json.load(f)
        expect = spec.get("expect", "pass")
        try:
            _, pack = experiments.build(spec, name, new_jar, work, formats[1])
            verdict, message = experiments.run_check(pack, env)
        except SystemExit as e:
            verdict, message = "cannot build", str(e)
        if verdict != expect:
            regressions.append(f"| `{name}` | {expect} | {verdict} | {message[:160].replace('|', '/')} |")
    if regressions:
        out += [f"**{len(regressions)} of {len(specs)}** no longer get their expected verdict:", "",
                "| Experiment / example | Expected | Got | Message |", "|---|---|---|---|"] + regressions
    else:
        out.append(f"All {len(specs)} get their expected verdict.")
    print("\n".join(out))
    sys.exit(1 if regressions else 0)


if __name__ == "__main__":
    main()
