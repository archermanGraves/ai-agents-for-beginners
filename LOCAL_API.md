# local_api fork — local vLLM migration notes

> 本代码已经替换为本地api

## What changed

Python course samples on branch `local_api` now prefer a **local vLLM** OpenAI-compatible endpoint:

- `LOCAL_VLLM_BASE_URL=http://127.0.0.1:8030/v1` (see `tool.sh` CLI 2)
- Shared helper: [`local_llm.py`](./local_llm.py)
- Migration script (notebooks): [`migrate_to_local_vllm.py`](./migrate_to_local_vllm.py)

Original Azure Foundry / Azure OpenAI teaching code is **kept** (commented) in notebooks; local replacement is **appended** after it.

## Start VLM

```bash
bash /home/wanghao/desktop/code/qwen3.5_4B/run_qwen35_4B.sh
curl --noproxy '*' -sS http://127.0.0.1:8030/v1/models | python3 -m json.tool
```

## Conda env

Use the prepared env (do **not** use the abandoned `agents_local` clone):

```bash
conda activate agent_run
# python: /home/wanghao/desktop/envs/miniconda3/envs/agent_run/bin/python
# MAF already installed: agent-framework-core/openai/foundry == 1.10.0
```

Smoke check:

```bash
/home/wanghao/desktop/envs/miniconda3/envs/agent_run/bin/python -c "from local_llm import make_local_chat_client, resolve_local_model; print(resolve_local_model()); print(make_local_chat_client())"
```

## Feasibility layers (as executed)

| Layer | Action |
|-------|--------|
| High: 01–04, 06–07, 09–12, 14 notebooks, 17 | Replaced with `OpenAIChatCompletionClient` via `local_llm` |
| Medium: tool/multi-agent/planning samples | Same replacement |
| Partial: 05 RAG | LLM replaced; Azure AI Search still required |
| Skip/hard: 08-04 Bing condition workflow | Note only |
| Partial: 15 browser-use | Azure client commented; local OpenAI SDK appended |
| Partial: 16 routing | LLM client replaced; dual-model routing demoted |
| Skip: 14-langchain hosted | Foundry hosted runtime |
| Skip: .NET, translations | Not migrated |

## Remark string

Every replacement site includes:

`本代码已经替换为本地api`
