"""
worker.py

Temporal Worker that hosts the workflow and activities.

Usage:
  python worker.py                         # Normal run
  CRASH_AFTER_ACTIVITY=2 python worker.py  # Crash after 2 activities

The worker connects to the local Temporal server, registers the
workflow and activities, and polls the task queue for work.
"""

import asyncio
import logging
import os

from temporalio.client import Client
from temporalio.worker import Worker

from activities import call_model_activity, call_tool_activity, set_crash_event
from workflow import StrandsAgentWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("worker")

TASK_QUEUE = "strands-durability-poc"


async def main():
    client = await Client.connect("localhost:7233")

    crash_after = os.environ.get("CRASH_AFTER_ACTIVITY", "0")
    if crash_after != "0":
        logger.warning(
            "*** CRASH MODE: worker will die after %s completed activities ***",
            crash_after,
        )

    logger.info("Task queue : %s", TASK_QUEUE)
    logger.info("Workflow   : StrandsAgentWorkflow")
    logger.info("Activities : strands-call-model, strands-call-tool")
    logger.info("Worker running. Ctrl+C to stop.\n")

    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[StrandsAgentWorkflow],
        activities=[call_model_activity, call_tool_activity],
    )

    crash_event = asyncio.Event()
    set_crash_event(crash_event, asyncio.get_event_loop())

    worker_task = asyncio.create_task(worker.run())
    await crash_event.wait()
    logger.error("Crash event received. Killing worker process.")
    os._exit(1)


if __name__ == "__main__":
    asyncio.run(main())
