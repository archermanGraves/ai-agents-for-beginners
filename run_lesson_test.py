#!/usr/bin/env python3
"""Run one local-capable lesson notebook and append a record to exe_log.txt on success."""

from __future__ import annotations

import argparse
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LOG = ROOT / "exe_log.txt"

# Disable proxies for localhost vLLM
for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "all_proxy"):
    os.environ.pop(k, None)
os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost")
os.environ.setdefault("no_proxy", "127.0.0.1,localhost")
os.environ.setdefault("LOCAL_VLLM_BASE_URL", "http://127.0.0.1:8030/v1")
os.environ.setdefault("LOCAL_VLLM_API_KEY", "EMPTY")
os.environ.setdefault("OPENAI_BASE_URL", "http://127.0.0.1:8030/v1")
os.environ.setdefault("OPENAI_API_KEY", "EMPTY")


def append_log(line: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def run_notebook(nb_path: Path, timeout: int) -> None:
    import nbformat
    from nbclient import NotebookClient

    # Ensure repo root importable for local_llm.py regardless of notebook cwd
    sys.path.insert(0, str(ROOT))

    nb = nbformat.read(nb_path, as_version=4)
    # Skip %pip / !pip install cells — deps already in agent_run
    for cell in nb.cells:
        if cell.get("cell_type") != "code":
            continue
        src = cell.get("source", "")
        if isinstance(src, list):
            src = "".join(src)
        lines = []
        for line in src.splitlines(keepends=True):
            s = line.lstrip()
            if s.startswith("%pip ") or s.startswith("!pip ") or s.startswith("%conda "):
                lines.append("# skipped install magic during automated test: " + line.lstrip("%!"))
            else:
                lines.append(line)
        cell["source"] = "".join(lines)

    client = NotebookClient(
        nb,
        timeout=timeout,
        kernel_name="agent_run",
        allow_errors=False,
        resources={"metadata": {"path": str(nb_path.parent)}},
    )
    # Execute with cwd = notebook dir so relative assets work; local_llm found via parents walk
    client.execute(cwd=str(nb_path.parent))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("notebook", type=str, help="Notebook path relative to repo root or absolute")
    parser.add_argument("--timeout", type=int, default=300, help="Per-cell timeout seconds")
    parser.add_argument("--skip-reason", type=str, default="", help="If set, record SKIP and exit 0")
    args = parser.parse_args()

    nb_path = Path(args.notebook)
    if not nb_path.is_absolute():
        nb_path = (ROOT / nb_path).resolve()
    rel = nb_path.relative_to(ROOT) if nb_path.is_relative_to(ROOT) else nb_path
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if args.skip_reason:
        append_log(f"[{ts}] SKIP  {rel}  reason={args.skip_reason}")
        print(f"SKIP {rel}: {args.skip_reason}")
        return 0

    if not nb_path.exists():
        append_log(f"[{ts}] FAIL  {rel}  error=file_not_found")
        print(f"FAIL {rel}: file not found", file=sys.stderr)
        return 2

    print(f"RUN  {rel} ...", flush=True)
    try:
        run_notebook(nb_path, timeout=args.timeout)
    except Exception as exc:
        err = f"{type(exc).__name__}: {exc}".replace("\n", " ")
        append_log(f"[{ts}] FAIL  {rel}  error={err}")
        print(f"FAIL {rel}: {err}", file=sys.stderr)
        traceback.print_exc()
        return 1

    append_log(f"[{ts}] PASS  {rel}")
    print(f"PASS {rel}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
/home/wanghao/desktop/envs/miniconda3/envs/agent_run/bin/python run_lesson_test.py 01-intro-to-ai-agents/code_samples/01-python-agent-framework.ipynb
"""
