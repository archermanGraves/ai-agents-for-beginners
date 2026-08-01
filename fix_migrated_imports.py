#!/usr/bin/env python3
"""Restore useful imports that were commented with the Azure/Foundry client block."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKIP = {"translations", "translated_images", ".ipynb_checkpoints"}

KEEP_IMPORT_RE = re.compile(
    r"^#\s*((?:from\s+\S+\s+import\s+.+)|(?:import\s+.+))\s*$"
)
DROP_IMPORT_RE = re.compile(
    r"agent_framework\.foundry|FoundryChatClient|OpenAIChatClient|azure\.identity|"
    r"AzureCliCredential|DefaultAzureCredential|AzureAIAgentClient|"
    r"get_bearer_token_provider|ChatAzureOpenAI|foundry_local|FoundryLocalManager"
)

MARKER = "# restored imports for later cells"


def extract_imports(src: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for line in src.splitlines():
        m = KEEP_IMPORT_RE.match(line)
        if not m:
            continue
        stmt = m.group(1).strip()
        if DROP_IMPORT_RE.search(stmt):
            continue
        if stmt in seen:
            continue
        seen.add(stmt)
        out.append(stmt)
    # always ensure these exist for MAF lessons
    for must in (
        "from agent_framework import tool",
        "import os",
    ):
        if must not in seen:
            out.append(must)
            seen.add(must)
    return out


def patch_cell(src: str) -> str | None:
    if "本代码已经替换为本地api" not in src:
        return None
    imports = extract_imports(src)
    block_lines = [MARKER + " (auto)"]
    block_lines.extend(imports)
    block = "\n".join(block_lines) + "\n"

    if MARKER in src:
        # replace previous restore block
        src = re.sub(
            r"# restored imports for later cells[\s\S]*?\Z",
            block,
            src,
            count=1,
        )
        if not src.endswith(block) and MARKER not in src[-400:]:
            src = src.rstrip() + "\n\n" + block
        elif MARKER in src and block not in src:
            # fallback append
            src = re.sub(r"(# restored imports for later cells[\s\S]*)", block, src, count=1)
        return src

    return src.rstrip() + "\n\n" + block


def main() -> None:
    n = 0
    for path in sorted(ROOT.rglob("*.ipynb")):
        if any(p in SKIP for p in path.parts):
            continue
        nb = json.loads(path.read_text(encoding="utf-8"))
        changed = False
        for cell in nb.get("cells", []):
            if cell.get("cell_type") != "code":
                continue
            src = "".join(cell.get("source", []))
            new = patch_cell(src)
            if new is None or new == src:
                continue
            lines = new.splitlines(keepends=True)
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            cell["source"] = lines
            changed = True
        if changed:
            path.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            n += 1
            print("fixed", path.relative_to(ROOT))
    print("fixed_count", n)


if __name__ == "__main__":
    main()
