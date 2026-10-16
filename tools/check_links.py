"""Check that every relative link and image in the repository's Markdown files points to something that exists.

    python3 tools/check_links.py

Also checks #anchors against the headings of the target file (GitHub's slug rules, simplified).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINK = re.compile(r"!?\[[^\]]*\]\(([^)\s]+)\)")


def slug(heading):
    s = heading.strip().lower()
    s = re.sub(r"[^\w\- ]", "", s)
    return s.replace(" ", "-")


def anchors(path):
    with open(path) as f:
        return {slug(m.group(1)) for m in re.finditer(r"^#+\s+(.*)$", f.read(), re.M)}


def main():
    problems = 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "build")]
        for name in filenames:
            if not name.endswith(".md"):
                continue
            path = os.path.join(dirpath, name)
            with open(path) as f:
                text = f.read()
            text = re.sub(r"```.*?```", "", text, flags=re.S)
            for target in LINK.findall(text):
                if re.match(r"[a-z]+:", target):
                    continue
                file_part, _, anchor = target.partition("#")
                resolved = os.path.normpath(os.path.join(dirpath, file_part)) if file_part else path
                rel = os.path.relpath(path, ROOT)
                if not os.path.exists(resolved):
                    print(f"{rel}: missing {target}")
                    problems += 1
                elif anchor and os.path.isfile(resolved) and resolved.endswith(".md") and anchor not in anchors(resolved):
                    print(f"{rel}: no heading for #{anchor} in {os.path.relpath(resolved, ROOT)}")
                    problems += 1
    print(f"{problems} broken link(s)")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
