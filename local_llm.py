"""Local vLLM OpenAI-compatible client helper for this course fork.

Default endpoint matches tool.sh CLI 2:
  BASE_URL=http://127.0.0.1:8030/v1
  POST /chat/completions

本模块用于把课程样本从 Azure Foundry / Azure OpenAI 切换到本地 vLLM。
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "http://127.0.0.1:8030/v1"
DEFAULT_API_KEY = "EMPTY"
REMARK = "本代码已经替换为本地api"


def _repo_root() -> Path:
    here = Path(__file__).resolve().parent
    return here


def load_course_dotenv() -> None:
    """Load repo-root .env if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_path = _repo_root() / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=False)
    else:
        load_dotenv(override=False)


def get_local_base_url() -> str:
    load_course_dotenv()
    return (
        os.getenv("LOCAL_VLLM_BASE_URL")
        or os.getenv("OPENAI_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")


def get_local_api_key() -> str:
    load_course_dotenv()
    return os.getenv("LOCAL_VLLM_API_KEY") or os.getenv("OPENAI_API_KEY") or DEFAULT_API_KEY


def fetch_first_model_id(base_url: str | None = None, timeout: float = 10.0) -> str:
    """GET /models and return the first model id (vLLM OpenAI-compatible)."""
    base = (base_url or get_local_base_url()).rstrip("/")
    url = f"{base}/models"
    req = urllib.request.Request(url, headers={"User-Agent": "ai-agents-local-llm/1.0"})
    # Avoid corporate HTTP proxies for localhost.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"Cannot reach local vLLM at {url}. "
            "Start it with: bash /home/wanghao/desktop/code/qwen3.5_4B/run_qwen35_4B.sh "
            f"({exc})"
        ) from exc

    data = payload.get("data") if isinstance(payload, dict) else None
    if not data:
        raise RuntimeError(f"/models returned empty list from {url}: {payload!r}")
    model_id = data[0].get("id") if isinstance(data[0], dict) else None
    if not model_id:
        raise RuntimeError(f"/models first entry missing id: {data[0]!r}")
    return str(model_id)


def resolve_local_model(base_url: str | None = None) -> str:
    load_course_dotenv()
    explicit = (
        os.getenv("LOCAL_VLLM_MODEL")
        or os.getenv("OPENAI_MODEL")
        or os.getenv("OPENAI_CHAT_COMPLETION_MODEL")
        or ""
    ).strip()
    if explicit:
        return explicit
    return fetch_first_model_id(base_url=base_url)


def _no_proxy_httpx_client(*, timeout: float = 120.0):
    """httpx client that ignores HTTP(S)_PROXY for local vLLM."""
    import httpx

    # trust_env=False: do not pick up corporate proxies that break localhost.
    return httpx.Client(trust_env=False, timeout=timeout)


def _no_proxy_async_httpx_client(*, timeout: float = 120.0):
    import httpx

    return httpx.AsyncClient(trust_env=False, timeout=timeout)


def make_local_openai_sdk_client(**kwargs: Any):
    """Return openai.OpenAI pointed at local vLLM (Chat Completions)."""
    from openai import OpenAI

    base_url = kwargs.pop("base_url", None) or get_local_base_url()
    api_key = kwargs.pop("api_key", None) or get_local_api_key()
    http_client = kwargs.pop("http_client", None) or _no_proxy_httpx_client()
    return OpenAI(base_url=base_url, api_key=api_key, http_client=http_client, **kwargs)


def make_local_chat_client(**kwargs: Any):
    """Return MAF OpenAIChatCompletionClient for local vLLM.

    Prefer Chat Completions client because vLLM exposes /v1/chat/completions,
    not the Responses API used by OpenAIChatClient / FoundryChatClient.
    """
    from openai import AsyncOpenAI
    from agent_framework.openai import OpenAIChatCompletionClient

    base_url = kwargs.pop("base_url", None) or get_local_base_url()
    api_key = kwargs.pop("api_key", None) or get_local_api_key()
    model = kwargs.pop("model", None) or resolve_local_model(base_url=base_url)
    # Inject a no-proxy AsyncOpenAI so MAF does not route localhost via SOCKS/HTTP proxy.
    async_client = kwargs.pop("async_client", None)
    if async_client is None:
        async_client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=_no_proxy_async_httpx_client(),
        )
    client = OpenAIChatCompletionClient(
        model=model,
        base_url=base_url,
        api_key=api_key,
        async_client=async_client,
        **kwargs,
    )
    # 本代码已经替换为本地api
    return client


def local_client_bootstrap_snippet(var_name: str = "provider") -> str:
    """Notebook/source snippet that builds a local MAF chat client."""
    return f'''# --- local vLLM (Chat Completions) ---
# Original Azure Foundry / Azure OpenAI client code is kept above (commented) for teaching.
import sys
from pathlib import Path

_ROOT = Path.cwd().resolve()
for _candidate in [_ROOT, *_ROOT.parents]:
    if (_candidate / "local_llm.py").exists():
        if str(_candidate) not in sys.path:
            sys.path.insert(0, str(_candidate))
        break

from local_llm import make_local_chat_client, REMARK

{var_name} = make_local_chat_client()
print(REMARK)  # 本代码已经替换为本地api
print(f"Local chat client ready: {{{var_name}!r}}")
'''


"""
# smoke check (agents_local env + vLLM on :8030)
# /ssd1/envs/conda/envs/agents_local/bin/python -c "from local_llm import make_local_chat_client, resolve_local_model; print(resolve_local_model()); c=make_local_chat_client(); print(c)"
"""
