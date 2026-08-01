#!/usr/bin/env python3
"""Migrate course Python samples to local vLLM while preserving original teaching code.

Rules:
- Do not delete original textbook/code content; comment it out and append local replacement.
- Add remark: 本代码已经替换为本地api
- Skip translations/, translated_images/, .NET (.cs), checkpoints
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REMARK = "本代码已经替换为本地api"
MARKER = "local_llm import make_local_chat_client"

SKIP_PARTS = {"translations", "translated_images", ".ipynb_checkpoints", ".git"}

LOCAL_BOOTSTRAP = '''
# --- local vLLM replacement (appended; original Azure/Foundry code kept above as comments) ---
import sys
from pathlib import Path as _Path

_ROOT = _Path.cwd().resolve()
for _candidate in [_ROOT, *_ROOT.parents]:
    if (_candidate / "local_llm.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from local_llm import make_local_chat_client, make_local_openai_sdk_client, resolve_local_model, REMARK as _LOCAL_REMARK
print(_LOCAL_REMARK)  # 本代码已经替换为本地api
'''.lstrip()


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def comment_block(src: str) -> str:
    lines = src.splitlines()
    out = ["# --- original teaching code (kept, not deleted) ---"]
    for line in lines:
        if line.strip() == "":
            out.append("#")
        else:
            out.append("# " + line if not line.startswith("#") else line)
    return "\n".join(out)


def detect_var_name(src: str) -> str:
    for name in ("provider", "chat_client", "client", "llm"):
        if re.search(rf"\b{name}\s*=\s*(FoundryChatClient|OpenAIChatClient|OpenAI|ChatAzureOpenAI)\s*\(", src):
            return name
    m = re.search(
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(FoundryChatClient|OpenAIChatClient|OpenAI|ChatAzureOpenAI)\s*\(",
        src,
    )
    return m.group(1) if m else "provider"


def needs_maf_local(src: str) -> bool:
    return ("FoundryChatClient(" in src) or ("OpenAIChatClient(" in src)


def needs_openai_sdk_local(src: str) -> bool:
    if "ChatAzureOpenAI(" in src:
        return True
    if re.search(r"\bOpenAI\s*\(", src) and (
        "AZURE_OPENAI" in src
        or "azure_endpoint" in src
        or "get_bearer_token_provider" in src
        or "FoundryLocalManager" in src
        or "openai/v1" in src
    ):
        return True
    return False


def already_migrated(src: str) -> bool:
    return MARKER in src or "本代码已经替换为本地api" in src


def maf_replacement(var_name: str) -> str:
    return (
        LOCAL_BOOTSTRAP
        + f"\n{var_name} = make_local_chat_client()  # 本代码已经替换为本地api\n"
        + f'print(f"Using local vLLM client as `{var_name}`")\n'
    )


def openai_sdk_replacement(var_name: str) -> str:
    return (
        LOCAL_BOOTSTRAP
        + f"\n{var_name} = make_local_openai_sdk_client()  # 本代码已经替换为本地api\n"
        + f"_LOCAL_MODEL = resolve_local_model()\n"
        + f'print(f"Using local vLLM OpenAI SDK client as `{var_name}`, model={{_LOCAL_MODEL}}")\n'
    )


def transform_code_cell(src: str) -> tuple[str, bool]:
    if already_migrated(src):
        return src, False
    if needs_maf_local(src):
        var = detect_var_name(src)
        new_src = comment_block(src.rstrip()) + "\n\n" + maf_replacement(var)
        return new_src, True
    if needs_openai_sdk_local(src):
        var = detect_var_name(src)
        # special-case browser-use ChatAzureOpenAI -> keep commented, use OpenAI SDK + note
        if "ChatAzureOpenAI(" in src:
            extra = (
                "\n# NOTE: Browser-Use ChatAzureOpenAI still needs Azure for full demo.\n"
                "# Local path below builds an OpenAI-compatible client for experimentation.\n"
                "# If Browser-Use requires ChatOpenAI, wire base_url to LOCAL_VLLM_BASE_URL manually.\n"
            )
            new_src = comment_block(src.rstrip()) + extra + "\n" + openai_sdk_replacement(var)
            return new_src, True
        new_src = comment_block(src.rstrip()) + "\n\n" + openai_sdk_replacement(var)
        return new_src, True
    return src, False


def migrate_notebook(path: Path) -> bool:
    nb = json.loads(path.read_text(encoding="utf-8"))
    changed = False
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        src = "".join(cell.get("source", []))
        new_src, did = transform_code_cell(src)
        if did:
            # notebook source as line array ending with \n except possibly last
            lines = new_src.splitlines(keepends=True)
            if lines and not lines[-1].endswith("\n"):
                lines[-1] = lines[-1] + "\n"
            cell["source"] = lines
            # clear stale outputs so notebooks look fresh
            cell["outputs"] = []
            cell["execution_count"] = None
            changed = True
    if changed:
        path.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return changed


def migrate_py(path: Path) -> bool:
    """Only surgically handled .py files; do NOT whole-file comment scripts."""
    # Notebooks are the main target. Standalone .py samples are patched manually
    # (hotel_booking_workflow_sample.py, github-mcp/app.py) to avoid commenting
    # the entire teaching module.
    return False
    src = path.read_text(encoding="utf-8")
    if already_migrated(src):
        return False
    if not (needs_maf_local(src) or needs_openai_sdk_local(src)):
        return False

    # Comment original client construction regions heuristically by whole-file comment+append
    # Prefer targeted: if file has clear create functions, append at end of client factory.
    var = detect_var_name(src)
    if needs_maf_local(src):
        appendix = (
            "\n\n# ===== local vLLM override (original code above preserved) =====\n"
            "import sys as _sys\n"
            "from pathlib import Path as _Path\n"
            "_ROOT = _Path(__file__).resolve().parents\n"
            "for _c in [_Path(__file__).resolve().parent, *_ROOT]:\n"
            "    if (_c / 'local_llm.py').exists():\n"
            "        if str(_c) not in _sys.path:\n"
            "            _sys.path.insert(0, str(_c))\n"
            "        break\n"
            "from local_llm import make_local_chat_client\n"
            f"# 本代码已经替换为本地api — callers should prefer make_local_chat_client()\n"
            f"def _local_api_{var}():\n"
            f"    print('本代码已经替换为本地api')\n"
            f"    return make_local_chat_client()\n"
        )
        # Also try to replace assignments in-place while commenting originals line-by-line for matching blocks
        new_src, did = transform_code_cell(src)
        if did:
            path.write_text(new_src + "\n", encoding="utf-8")
            return True
        path.write_text(src.rstrip() + append + "\n", encoding="utf-8")
        return True

    new_src, did = transform_code_cell(src)
    if did:
        path.write_text(new_src + "\n", encoding="utf-8")
        return True
    return False


def append_setup_note() -> None:
    setup = ROOT / "00-course-setup" / "README.md"
    if not setup.exists():
        return
    text = setup.read_text(encoding="utf-8")
    banner = "## Local vLLM (this fork: `local_api` branch)"
    if banner in text:
        return
    note = f"""

{banner}

> {REMARK}

This fork can run many Python notebooks against a **local vLLM** OpenAI-compatible server instead of Azure Foundry / Azure OpenAI.

### Start local VLM (from host `tool.sh` CLI 2)

```bash
bash /home/wanghao/desktop/code/qwen3.5_4B/run_qwen35_4B.sh
curl --noproxy '*' -sS http://127.0.0.1:8030/v1/models | python3 -m json.tool
```

### Env vars (see `.env.example`)

```bash
LOCAL_VLLM_BASE_URL=http://127.0.0.1:8030/v1
LOCAL_VLLM_API_KEY=EMPTY
# LOCAL_VLLM_MODEL=   # optional; auto-detected from /v1/models if empty
```

### Shared helper

Use repo-root [`local_llm.py`](../local_llm.py):

- `make_local_chat_client()` → Microsoft Agent Framework `OpenAIChatCompletionClient` (Chat Completions)
- `make_local_openai_sdk_client()` → `openai.OpenAI` for raw SDK notebooks

Original Azure / Foundry teaching code is **kept** in notebooks (commented), with local replacement **appended** after it.

### Not fully local

These lessons still need cloud services beyond the LLM, or are skipped in this pass:

- Lesson 05 Azure AI Search index
- Lesson 08 Bing grounding / some Foundry-only workflows
- Lesson 15 Browser-Use Azure-specific LLM class (partial)
- .NET samples (not migrated)
- `translations/` (not migrated)
"""
    setup.write_text(text.rstrip() + note + "\n", encoding="utf-8")


def patch_env_example() -> None:
    env = ROOT / ".env.example"
    text = env.read_text(encoding="utf-8") if env.exists() else ""
    if "LOCAL_VLLM_BASE_URL" in text:
        return
    block = """

# -----------------------------------------------------------------------------
# Local vLLM (this fork / local_api branch) — 本代码已经替换为本地api
# Matches tool.sh CLI 2: http://127.0.0.1:8030/v1  (OpenAI-compatible chat/completions)
# -----------------------------------------------------------------------------
LOCAL_VLLM_BASE_URL=http://127.0.0.1:8030/v1
LOCAL_VLLM_API_KEY=EMPTY
# LOCAL_VLLM_MODEL=
OPENAI_BASE_URL=http://127.0.0.1:8030/v1
OPENAI_API_KEY=EMPTY
# OPENAI_MODEL=
"""
    env.write_text(text.rstrip() + block + "\n", encoding="utf-8")


def main() -> None:
    changed_files: list[str] = []
    for path in sorted(ROOT.rglob("*.ipynb")):
        if should_skip(path):
            continue
        if migrate_notebook(path):
            changed_files.append(str(path.relative_to(ROOT)))

    for path in sorted(ROOT.rglob("*.py")):
        if should_skip(path):
            continue
        if path.name in {"local_llm.py", "migrate_to_local_vllm.py"}:
            continue
        if migrate_py(path):
            changed_files.append(str(path.relative_to(ROOT)))

    append_setup_note()
    patch_env_example()
    print(f"migrated {len(changed_files)} files")
    for f in changed_files:
        print(" -", f)


if __name__ == "__main__":
    main()

"""
/ssd1/envs/conda/envs/agents_local/bin/python migrate_to_local_vllm.py
"""
