import asyncio
import json
import os
import sqlite3

from fastmcp import Client

SERVER_URL = "https://localhost:8089/mcp"
DB_PATH = "flux-mcp-server-state.db"

import flux.job


def get_job_events(job_id):
    """
    Directly query the SQLite DB to see what the server recorded.
    """
    if not os.path.exists(DB_PATH):
        return []

    # Connect in read-only mode just to be safe, but not required. It's sqlite we can delete it.
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute(
                "SELECT event_type, payload FROM events WHERE job_id = ? ORDER BY timestamp ASC",
                (job_id,),
            )
            return [dict(row) for row in cur.fetchall()]
        except sqlite3.OperationalError:
            # Table might not exist yet if no events have occurred
            return []


async def run_test():
    print(f"🔌 Connecting to MCP Server at {SERVER_URL}...")

    try:
        async with Client(SERVER_URL) as client:

            # Submit a job "sleep 2"
            print("🚀 Submitting 'sleep 2' job...")
            jobspec = flux.job.JobspecV1.from_command(["sleep", "2"]).dumps()

            # Call the tool!
            result = await client.call_tool("flux_submit_job", {"jobspec": jobspec})
            print(result)

            # Parse the tool response (which is a JSON string inside the result object)
            response_text = result.content[0].text
            response = json.loads(response_text)

            if not response.get("success"):
                print(f"❌ Submit failed: {response}")
                return

            job_id = response["job_id"]
            print(f"   ✅ Job ID: {job_id}")

            # Poll database for events...
            # We wait up to 10 seconds for the job to finish and events to appear
            print("⏳ Waiting for events to propagate to DB...")

            found_types = set()
            for _ in range(10):
                events = get_job_events(job_id)
                found_types = {e["event_type"] for e in events}

                # Print progress
                if events:
                    print(f"   found {len(events)} events: {found_types}")

                # Did we see submission AND completion (clean or finish)?
                if "submit" in found_types and ("clean" in found_types or "finish" in found_types):
                    break

                await asyncio.sleep(1.0)

            # Captain, final report.
            print("\n📊 Event Log Analysis:")
            events = get_job_events(job_id)
            if not events:
                print("❌ No events found in database! Is the Scribe/EventEngine running?")
            else:
                print(f"✅ Success! Recorded {len(events)} events for Job {job_id}.")
                for e in events:
                    # Payload is stored as JSON string in DB, usually
                    try:
                        payload_str = e["payload"]
                        data = (
                            json.loads(payload_str) if isinstance(payload_str, str) else payload_str
                        )
                    except:
                        data = e["payload"]

                    # Pretty print specific state changes
                    etype = e["event_type"]
                    if etype == "state":
                        print(f"   - [STATE]  {data.get('state_name')}")
                    else:
                        print(f"   - [{etype.upper()}]")

    except Exception as e:
        print(f"\n❌ Client Error: {e}")
        print(
            "   Make sure the server is running with: python -m flux_mcp_server.server or flux-mcp-server"
        )


# 278783281 jan 13 2026 feb 11 26

if __name__ == "__main__":
    asyncio.run(run_test())
