"""
workflow.py — real_sdk_durable

Demonstrates the proposed Level 2 native integration from durable-execution-integration.md.

User-facing API (exactly as the doc proposes):

    agent = Agent(tools=[...], durability=TemporalDurability())
    result = await agent.invoke_async(prompt)

At runtime, TemporalDurability intercepts the event loop's two I/O call sites
and dispatches them as Temporal Activities. On crash + replay, completed
Activities return cached results — the real Agent loop resumes mid-conversation.

SDK changes made (in sdk-python):
  1. strands/agent/durability.py       — Durability ABC (no-op base)
  2. Agent.__init__ durability= param  — stored as self.durability
  3. event_loop.py two call sites      — check agent.durability, delegate to wrap_model_call / wrap_tool_call
"""

import logging
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    import awscrt  # noqa: F401 — suppress late-import warning
    import strands
    import strands.types.streaming
    import strands.types.collections
    import strands.types.citations
    import strands.types.content
    import strands.types.media
    import strands.types.tools
    import strands.types.interrupt
    import strands.types.event_loop
    import strands.types.guardrails
    import strands.interrupt
    from strands.agent.durability import Durability
    from activities import call_model_activity, call_tool_activity
    from tools import search_flights, book_hotel

logger = logging.getLogger("workflow")

SYSTEM_PROMPT = (
    "You are a helpful travel assistant. "
    "Use the search_flights and book_hotel tools to help plan trips. "
    "Always search for flights first, then book a hotel."
)

RETRY = RetryPolicy(initial_interval=timedelta(seconds=1), backoff_coefficient=1.0)


# ── TemporalDurability (strands-temporal package) ────────────────
#
# wrap_model_call receives: fn(messages, system_prompt, tool_specs) -> (stop_reason, message)
# wrap_tool_call  receives: fn(tool_name, tool_input, tool_use_id)  -> ToolResult dict

class TemporalDurability(Durability):
    """Production-safe: model_id is passed to activities; no boto3 in the workflow."""

    def __init__(self, model_id: str):
        self.model_id = model_id

    def wrap_model_call(self, call_model_fn):
        model_id = self.model_id
        async def wrapped(messages, system_prompt, tool_specs):
            result = await workflow.execute_activity(
                call_model_activity,
                args=[model_id, messages, system_prompt, tool_specs],
                start_to_close_timeout=timedelta(minutes=2),
                retry_policy=RETRY,
            )
            return result["stop_reason"], result["message"]
        return wrapped

    def wrap_tool_call(self, call_tool_fn):
        async def wrapped(tool_name, tool_input, tool_use_id):
            return await workflow.execute_activity(
                call_tool_activity,
                args=[tool_name, tool_input, tool_use_id],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RETRY,
            )
        return wrapped


MODEL_ID = "us.anthropic.claude-sonnet-4-20250514-v1:0"


# ── User's Temporal Workflow ─────────────────────────────────────
# No sandbox_unrestricted needed — no boto3 constructed in the workflow.

@workflow.defn
class StrandsAgentWorkflow:

    @workflow.run
    async def run(self, prompt: str) -> str:
        workflow.logger.info("=== Workflow started: %s", prompt)

        with workflow.unsafe.imports_passed_through():
            from strands import Agent

        agent = Agent(
            tools=[search_flights, book_hotel],
            system_prompt=SYSTEM_PROMPT,
            durability=TemporalDurability(MODEL_ID),
            callback_handler=None,
        )

        result = await agent.invoke_async(prompt)

        workflow.logger.info("=== Workflow completed ===")
        return str(result.message)
