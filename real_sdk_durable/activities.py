"""
activities.py

Temporal Activities that use the REAL Strands SDK:
  - call_model_activity: Creates a real BedrockModel, calls Claude via Bedrock
  - call_tool_activity: Calls real @tool decorated functions

Activities run on the Temporal Worker (outside the workflow sandbox).
I/O, network calls, and non-deterministic code are allowed here.

Temporal records each Activity's return value in Event History.
On replay after a crash, Activities that already completed return
their cached result WITHOUT re-executing.
"""

import asyncio
import logging
import os
from temporalio import activity

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("activities")


# ── Configuration ────────────────────────────────────────────────

MODEL_ID = os.environ.get(
    "STRANDS_MODEL_ID",
    "us.anthropic.claude-sonnet-4-20250514-v1:0",
)


# ── Crash simulation ────────────────────────────────────────────
# Set CRASH_AFTER_ACTIVITY=N to hard-crash the worker process after
# N completed activities. This simulates a real infrastructure crash.
# On restart, Temporal replays completed activities from Event History.

_activity_count = 0
_crash_after = int(os.environ.get("CRASH_AFTER_ACTIVITY", "0"))
_crash_event: asyncio.Event | None = None
_crash_loop: asyncio.AbstractEventLoop | None = None


def set_crash_event(event: asyncio.Event, loop: asyncio.AbstractEventLoop) -> None:
    global _crash_event, _crash_loop
    _crash_event = event
    _crash_loop = loop


def _maybe_crash(name: str) -> None:
    global _activity_count
    _activity_count += 1
    if _crash_after > 0 and _activity_count >= _crash_after:
        logger.error(
            "CRASH_AFTER_ACTIVITY=%d reached after [%s]. Killing worker process.",
            _crash_after,
            name,
        )
        if _crash_event and _crash_loop:
            _crash_loop.call_soon_threadsafe(_crash_event.set)


# ── Model Activity ───────────────────────────────────────────────

@activity.defn(name="strands-call-model")
async def call_model_activity(
    model_id: str,
    messages: list,
    system_prompt: str,
    tool_specs: list,
) -> dict:
    """Call Claude via real Strands BedrockModel.

    This Activity:
      1. Creates a BedrockModel (real boto3 client, real AWS credentials)
      2. Calls model.stream() which hits the Bedrock Converse API
      3. Processes the stream to get the final response
      4. Returns the stop_reason and message as a serializable dict

    Temporal checkpoints the return value. On replay this function
    is NOT called again; the cached result is returned instead.
    """
    # Import here so the worker (not workflow sandbox) loads these
    from strands.models.bedrock import BedrockModel

    activity.logger.info(
        ">>> call-model | messages=%d, tools=%d, model=%s",
        len(messages),
        len(tool_specs) if tool_specs else 0,
        model_id,
    )

    from strands.event_loop import streaming as strands_streaming

    model = BedrockModel(model_id=model_id)

    stop_reason = None
    message = None
    async for event in strands_streaming.process_stream(model.stream(
        messages=messages,
        tool_specs=tool_specs if tool_specs else None,
        system_prompt=system_prompt,
    )):
        if "stop" in event:
            stop_reason, message, *_ = event["stop"]

    activity.logger.info("    stop_reason=%s", stop_reason)

    _maybe_crash("call-model")

    return {
        "stop_reason": stop_reason,
        "message": message,
    }


# ── Tool Activity ────────────────────────────────────────────────

@activity.defn(name="strands-call-tool")
async def call_tool_activity(
    tool_name: str,
    tool_input: dict,
    tool_use_id: str,
) -> dict:
    """Call a real Strands @tool decorated function.

    This Activity:
      1. Looks up the tool from the registry
      2. Calls the real Python function
      3. Returns a ToolResult-shaped dict

    Temporal checkpoints the return value. On replay this function
    is NOT called again; the cached result is returned instead.
    """
    from tools import TOOLS

    activity.logger.info(">>> call-tool  | %s(%s)", tool_name, tool_input)

    tool_fn = TOOLS.get(tool_name)
    if not tool_fn:
        return {
            "toolUseId": tool_use_id,
            "content": [{"text": f"Unknown tool: {tool_name}"}],
            "status": "error",
        }

    try:
        result = tool_fn(**tool_input)

        activity.logger.info("    result: %s", str(result)[:80])

        _maybe_crash("call-tool")

        return {
            "toolUseId": tool_use_id,
            "content": [{"text": str(result)}],
            "status": "success",
        }
    except Exception as e:
        activity.logger.error("    error: %s", e)
        return {
            "toolUseId": tool_use_id,
            "content": [{"text": f"Error: {e}"}],
            "status": "error",
        }
