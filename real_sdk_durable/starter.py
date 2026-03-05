
"""
starter.py

Client that starts a Strands Agent workflow execution on Temporal.

Usage:
  python starter.py                              # Default prompt
  python starter.py "Plan a trip to Tokyo"       # Custom prompt

The client connects to Temporal, starts the workflow, and waits
for the final result. The workflow ID includes a timestamp so you
can run the demo multiple times without conflicts.
"""

import asyncio
import logging
import sys
import time

from temporalio.client import Client

from workflow import StrandsAgentWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
)
logger = logging.getLogger("starter")

TASK_QUEUE = "strands-durability-poc"


async def main():
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "Plan a 3-day trip to Paris"
    workflow_id = f"strands-trip-{int(time.time())}"

    client = await Client.connect("localhost:7233")

    logger.info("Workflow ID : %s", workflow_id)
    logger.info("Prompt      : %s", prompt)
    logger.info("Temporal UI : http://localhost:8233/namespaces/default/workflows/%s\n", workflow_id)

    handle = await client.start_workflow(
        StrandsAgentWorkflow.run,
        prompt,
        id=workflow_id,
        task_queue=TASK_QUEUE,
    )

    logger.info("Workflow started. Waiting for result...\n")
    result = await handle.result()

    print()
    print("=" * 60)
    print("AGENT RESULT:")
    print("=" * 60)
    print(result)
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
