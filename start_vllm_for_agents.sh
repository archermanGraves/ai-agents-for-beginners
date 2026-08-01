#!/usr/bin/env bash
# Start local Qwen3.5-4B vLLM with OpenAI tool-calling enabled (for MAF agent lessons).
# Based on tool.sh CLI 2 / run_qwen35_4B.sh, plus:
#   --enable-auto-tool-choice --tool-call-parser qwen3xml
set -euo pipefail

MODEL_PATH="${MODEL_PATH:-/ssd1/models/modelscope/models/Qwen/Qwen3___5-4B}"
PORT="${PORT:-8030}"
CUDA_DEVICE="${CUDA_DEVICE:-0}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.35}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-32768}"
TOOL_CALL_PARSER="${TOOL_CALL_PARSER:-qwen3_xml}"
PYTHON="${PYTHON:-/ssd1/envs/conda/envs/gemma4/bin/python3}"
VLLM_BIN="${VLLM_BIN:-/ssd1/envs/conda/envs/gemma4/bin/vllm}"

export VLLM_USE_FLASHINFER_SAMPLER=0
export VLLM_USE_MODELSCOPE=true
export CUDA_VISIBLE_DEVICES="${CUDA_DEVICE}"

echo "=== Qwen3.5-4B vLLM (tool-calling) ==="
echo "  port=${PORT} parser=${TOOL_CALL_PARSER}"

exec "${VLLM_BIN}" serve "${MODEL_PATH}" \
  --port "${PORT}" \
  --tensor-parallel-size 1 \
  --max-model-len "${MAX_MODEL_LEN}" \
  --gpu-memory-utilization "${GPU_MEMORY_UTILIZATION}" \
  --dtype bfloat16 \
  --trust-remote-code \
  --max-num-seqs 32 \
  --max-num-batched-tokens "${MAX_MODEL_LEN}" \
  --enable-prefix-caching \
  --async-scheduling \
  --enable-auto-tool-choice \
  --tool-call-parser "${TOOL_CALL_PARSER}" \
  --limit-mm-per-prompt "{\"image\":16}"
