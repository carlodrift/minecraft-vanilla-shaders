"""Generate the reference pages from the game itself.

    python3 tools/reference.py [--version 26.3]

Reads the render pipelines (tools/mcshaders pipelines) and the vanilla shader sources (from the
installed game jar), and writes:
    reference/<version>/pipelines.json   raw pipeline data
    docs/reference/core-shaders.md       per shader program: pipelines, defines, uniforms, vertex inputs
    docs/reference/uniforms.md           every uniform block / sampler and where it is available
    docs/reference/pipelines.md          every pipeline
"""
import argparse
import collections
import json
import os
import re
import subprocess
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MC = os.path.expanduser("~/Library/Application Support/minecraft")
OIT_BOOKKEEPING = {"OIT_WAVELET_RANK", "OIT_COEFF_COUNT", "OIT_COEFF_ATTACHMENT_COUNT"}


def short(identifier):
    return identifier.removeprefix("minecraft:")


def defines_of(p):
    return set(p["flags"]) | set(p["defines"])


def guard(pipelines, uniform):
    """Find the simplest define condition under which `uniform` is provided."""
    with_u = [p for p in pipelines if uniform in {u["name"] for u in p["uniforms"]}]
    without = [p for p in pipelines if p not in with_u]
    names = sorted(set().union(*(defines_of(p) for p in pipelines)) - OIT_BOOKKEEPING)
    # A literal is (define, wanted): defined(define) == wanted.
    literals = [(d, w) for d in names for w in (True, False)]
    text = lambda d, w: f"defined({d})" if w else f"!defined({d})"
    holds = lambda lit, p: (lit[0] in defines_of(p)) == lit[1]

    def exact(test):
        return all(test(p) for p in with_u) and not any(test(p) for p in without)

    for lit in literals:
        if exact(lambda p: holds(lit, p)):
            return f"`#ifdef {lit[0]}`" if lit[1] else f"`#ifndef {lit[0]}`"
    for i, a in enumerate(literals):
        for b in literals[i + 1:]:
            if a[0] == b[0]:
                continue
            if exact(lambda p: holds(a, p) and holds(b, p)):
                return f"`#if {text(*a)} && {text(*b)}`"
            if exact(lambda p: holds(a, p) or holds(b, p)):
                return f"`#if {text(*a)} \\|\\| {text(*b)}`"
    # No exact condition: find the widest one under which the uniform is always provided.
    best, best_count = None, 0
    candidates = [(f"`#ifdef {l[0]}`" if l[1] else f"`#ifndef {l[0]}`", (lambda l: lambda p: holds(l, p))(l)) for l in literals]
    for i, a in enumerate(literals):
        for b in literals[i + 1:]:
            if a[0] != b[0]:
                candidates.append((f"`#if {text(*a)} && {text(*b)}`", (lambda a, b: lambda p: holds(a, p) and holds(b, p))(a, b)))
                candidates.append((f"`#if {text(*a)} \\|\\| {text(*b)}`", (lambda a, b: lambda p: holds(a, p) or holds(b, p))(a, b)))
    for label, test in candidates:
        count = sum(test(p) for p in with_u)
        if not any(test(p) for p in without) and count > best_count:
            best, best_count = label, count
    if best and best_count > len(with_u) // 2:
        return f"safe under {best} (provided in {len(with_u)} of {len(pipelines)} pipelines)"
    return f"{len(with_u)} of {len(pipelines)} pipelines, not tied to a define: see the pipeline list"


def parse_blocks(jar):
    """uniform block name -> (file, members) from the vanilla sources."""
    blocks = {}
    for name in sorted(jar.namelist()):
        if not name.startswith("assets/minecraft/shaders/") or not name.endswith((".glsl", ".vsh", ".fsh")):
            continue
        text = jar.read(name).decode()
        for m in re.finditer(r"layout\s*\(\s*std140\s*\)\s*uniform\s+(\w+)\s*\{(.*?)\}", text, re.S):
            members = [" ".join(l.split()) for l in m.group(2).split(";") if l.strip()]
            if m.group(1) not in blocks or name.endswith(".glsl"):
                blocks[m.group(1)] = (name.removeprefix("assets/minecraft/shaders/"), members)
        for m in re.finditer(r"uniform\s+(\w+)\s+(\w+)\s*;", text):
            if m.group(1).startswith(("sampler", "isampler", "usampler")) and m.group(2) not in blocks:
                blocks[m.group(2)] = (name.removeprefix("assets/minecraft/shaders/"), [m.group(1)])
    return blocks


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--version", default="26.3")
    args = p.parse_args()

    out = subprocess.run([os.path.join(ROOT, "tools", "mcshaders"), "pipelines"], capture_output=True, text=True,
                         check=True, env=dict(os.environ, MC_VERSION=args.version)).stdout
    pipelines = [json.loads(l) for l in out.splitlines() if l.startswith("{")]
    jar = zipfile.ZipFile(os.path.join(MC, "versions", args.version, args.version + ".jar"))
    blocks = parse_blocks(jar)

    os.makedirs(os.path.join(ROOT, "reference", args.version), exist_ok=True)
    with open(os.path.join(ROOT, "reference", args.version, "pipelines.json"), "w") as f:
        json.dump(pipelines, f, indent=1)
        f.write("\n")

    programs = collections.defaultdict(list)
    for pl in pipelines:
        for stage in ("vertex", "fragment"):
            if stage in pl:
                programs[(pl[stage], stage)].append(pl)

    docs = os.path.join(ROOT, "docs", "reference")
    os.makedirs(docs, exist_ok=True)
    header = (f"<!-- Generated by tools/reference.py from Minecraft {args.version}. Do not edit by hand. -->\n\n")

    # core-shaders.md
    lines = [header + f"# Core shader programs ({args.version})", "",
             "Every core shader program the game compiles, with what each one can use.", "",
             "- **Pipelines**: a program is compiled once per pipeline that uses it, with that pipeline's defines.",
             "  A pack that replaces the file must compile and link for every one of them.",
             "- **Always available**: uniforms every pipeline of this program provides.",
             "- **Conditional**: uniforms only some pipelines provide. Declare them only under the given guard,",
             "  otherwise the pipelines that don't provide them fail to load (see experiment 42).",
             "- OIT bookkeeping defines (`OIT_WAVELET_RANK`, `OIT_COEFF_COUNT`, `OIT_COEFF_ATTACHMENT_COUNT`) are omitted.",
             ""]
    names = sorted({short(s) for s, _ in programs})
    lines.append("Programs: " + ", ".join(f"[`{n}`](#{n.replace('/', '').replace('_', '_')})" for n in names))
    lines.append("")
    for name in names:
        lines += [f"## {name}", ""]
        for stage in ("vertex", "fragment"):
            pls = programs.get(("minecraft:" + name, stage))
            if not pls:
                continue
            ext = ".vsh" if stage == "vertex" else ".fsh"
            other = "fragment" if stage == "vertex" else "vertex"
            partners = sorted({short(p[other]) for p in pls if other in p})
            lines.append(f"### `{name}{ext}`: {len(pls)} pipeline{'s' if len(pls) > 1 else ''}")
            lines.append("")
            if partners != [name]:
                lines.append(f"Linked with {other} program{'s' if len(partners) > 1 else ''}: "
                             + ", ".join(f"`{x}`" for x in partners) + ". Its interface must match every one of them.")
                lines.append("")
            uni = [{u["name"]: u["type"] for u in p["uniforms"]} for p in pls]
            always = sorted(set.intersection(*(set(u) for u in uni)))
            sometimes = sorted(set.union(*(set(u) for u in uni)) - set(always))
            kinds = {k: v for u in uni for k, v in u.items()}
            lines.append("| Uniform | Kind | Availability |")
            lines.append("|---|---|---|")
            for u in always:
                lines.append(f"| [`{u}`](uniforms.md#{u.lower()}) | {kinds[u]} | always |")
            for u in sometimes:
                lines.append(f"| [`{u}`](uniforms.md#{u.lower()}) | {kinds[u]} | {guard(pls, u)} |")
            lines.append("")
            defs = collections.Counter()
            values = collections.defaultdict(set)
            for p in pls:
                for f in p["flags"]:
                    defs[f] += 1
                for k, v in p["defines"].items():
                    if k not in OIT_BOOKKEEPING:
                        defs[k] += 1
                        values[k].add(v)
            if defs:
                lines.append("Defines: " + ", ".join(
                    f"`{d}`" + (f" = {', '.join(sorted(values[d]))}" if values[d] else "") + f" ({n}/{len(pls)})"
                    for d, n in sorted(defs.items())))
                lines.append("")
            if stage == "vertex":
                formats = collections.Counter(
                    " ".join(f"`{a['name']}` {a['format']}" for b in p["vertex_formats"] for a in b["attributes"]) or "none"
                    for p in pls)
                lines.append("Vertex inputs (declare `in` variables with exactly these names):")
                lines.append("")
                for fmt, n in formats.most_common():
                    lines.append(f"- {fmt} ({n} pipeline{'s' if n > 1 else ''})")
                lines.append("")
            lines.append("<details><summary>Pipelines</summary>")
            lines.append("")
            for p in sorted(pls, key=lambda p: p["location"]):
                d = sorted(set(p["flags"]) | {f"{k}={v}" for k, v in p["defines"].items() if k not in OIT_BOOKKEEPING})
                lines.append(f"- `{short(p['location'])}`" + (": " + " ".join(f"`{x}`" for x in d) if d else ""))
            lines += ["", "</details>", ""]
    with open(os.path.join(docs, "core-shaders.md"), "w") as f:
        f.write("\n".join(lines))

    # uniforms.md
    users = collections.defaultdict(set)
    kinds = {}
    for (prog, stage), pls in programs.items():
        for p in pls:
            for u in p["uniforms"]:
                users[u["name"]].add(short(prog))
                kinds[u["name"]] = u["type"]
    lines = [header + f"# Uniforms ({args.version})", "",
             "Every uniform block and sampler a vanilla pipeline provides. A core shader may only declare uniforms",
             "its pipelines provide, by exactly this name (see [core-shaders.md](core-shaders.md)). Blocks use the",
             "std140 layout: if you declare one by hand instead of including the vanilla file, keep every member,",
             "in this order.", ""]
    for name in sorted(users):
        lines += [f"## {name}", ""]
        src = blocks.get(name)
        lines.append(f"Kind: {kinds[name]}" + (f". Declared in `{src[0]}`." if src else "."))
        lines.append("")
        if src and kinds[name] == "UNIFORM_BUFFER":
            lines.append("```glsl")
            lines.append(f"layout(std140) uniform {name} {{")
            lines += [f"    {m};" for m in src[1]]
            lines.append("};")
            lines.append("```")
            lines.append("")
        lines.append("Available to: " + ", ".join(f"`{u}`" for u in sorted(users[name])))
        lines.append("")
    with open(os.path.join(docs, "uniforms.md"), "w") as f:
        f.write("\n".join(lines))

    # pipelines.md
    lines = [header + f"# Render pipelines ({args.version})", "",
             f"{len(pipelines)} pipelines. Raw data: [reference/{args.version}/pipelines.json](../../reference/{args.version}/pipelines.json).", "",
             "| Pipeline | Vertex | Fragment | Defines |", "|---|---|---|---|"]
    for p in pipelines:
        d = sorted(set(p["flags"]) | {f"{k}={v}" for k, v in p["defines"].items() if k not in OIT_BOOKKEEPING})
        lines.append(f"| `{short(p['location'])}` | `{short(p.get('vertex', ''))}` | `{short(p.get('fragment', ''))}` | "
                     + " ".join(f"`{x}`" for x in d) + " |")
    with open(os.path.join(docs, "pipelines.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(pipelines)} pipelines, {len(programs)} programs, {len(users)} uniforms")


if __name__ == "__main__":
    main()
