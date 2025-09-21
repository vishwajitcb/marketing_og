#!/usr/bin/env python3
"""
Test script for concurrent video generation
Tests 2 simultaneous video generations
"""

import requests
import asyncio
import aiohttp
import time
import json
from typing import List, Dict

SERVER_URL = "http://localhost:8000"

async def generate_video(session: aiohttp.ClientSession, test_id: str, name: str, birthday: str) -> Dict:
    """Generate a video and track the process"""
    start_time = time.time()

    try:
        # Start video generation
        async with session.post(f"{SERVER_URL}/generate", json={
            "name": name,
            "birthday": birthday
        }) as response:
            if response.status != 200:
                return {
                    "test_id": test_id,
                    "status": "failed",
                    "error": f"HTTP {response.status}",
                    "duration": time.time() - start_time
                }

            data = await response.json()
            job_id = data.get("job_id")

            if not job_id:
                return {
                    "test_id": test_id,
                    "status": "failed",
                    "error": "No job_id returned",
                    "duration": time.time() - start_time
                }

            print(f"🎬 {test_id}: Video generation started, job_id: {job_id}")

            # Poll for completion
            max_polls = 60  # 5 minutes max
            poll_count = 0

            while poll_count < max_polls:
                await asyncio.sleep(5)  # Wait 5 seconds between polls
                poll_count += 1

                async with session.get(f"{SERVER_URL}/status/{job_id}") as status_response:
                    if status_response.status == 200:
                        status_data = await status_response.json()
                        status = status_data.get("status")
                        message = status_data.get("message", "")

                        print(f"📊 {test_id}: Poll {poll_count}/60 - Status: {status}, Message: {message}")

                        if status == "completed":
                            return {
                                "test_id": test_id,
                                "status": "completed",
                                "job_id": job_id,
                                "download_url": status_data.get("download_url"),
                                "duration": time.time() - start_time,
                                "polls": poll_count
                            }
                        elif status == "failed":
                            return {
                                "test_id": test_id,
                                "status": "failed",
                                "job_id": job_id,
                                "error": status_data.get("error", "Unknown error"),
                                "duration": time.time() - start_time,
                                "polls": poll_count
                            }
                    else:
                        print(f"⚠️ {test_id}: Status check failed with HTTP {status_response.status}")

            return {
                "test_id": test_id,
                "status": "timeout",
                "job_id": job_id,
                "error": f"Timed out after {max_polls} polls",
                "duration": time.time() - start_time,
                "polls": poll_count
            }

    except Exception as e:
        return {
            "test_id": test_id,
            "status": "error",
            "error": str(e),
            "duration": time.time() - start_time
        }

async def check_system_status(session: aiohttp.ClientSession):
    """Check system status"""
    try:
        async with session.get(f"{SERVER_URL}/system/status") as response:
            if response.status == 200:
                data = await response.json()
                concurrent = data.get("concurrent_processing", {})
                memory = data.get("memory_optimization", {})

                print("🔧 System Status:")
                print(f"  Max concurrent slots: {concurrent.get('max_slots')}")
                print(f"  Available slots: {concurrent.get('available_slots')}")
                print(f"  Active jobs: {concurrent.get('active_jobs')}")
                print(f"  Memory per video: {memory.get('estimated_memory_per_video')}")
                print(f"  Processing resolution: {memory.get('processing_resolution')}")
                return data
    except Exception as e:
        print(f"❌ Failed to get system status: {e}")
        return None

async def main():
    """Run concurrent video generation test"""
    print("🚀 Starting concurrent video generation test...")
    print("=" * 60)

    async with aiohttp.ClientSession() as session:
        # Check initial system status
        await check_system_status(session)
        print()

        # Start 2 concurrent video generations
        tasks = [
            generate_video(session, "Video-1", "John Doe", "05/15/1990"),
            generate_video(session, "Video-2", "Jane Smith", "12/03/1985")
        ]

        print("🎬 Starting 2 concurrent video generations...")
        start_time = time.time()

        # Run both tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.time() - start_time

        print("\n" + "=" * 60)
        print("📊 RESULTS:")
        print("=" * 60)

        for result in results:
            if isinstance(result, Exception):
                print(f"❌ Exception: {result}")
            else:
                test_id = result.get("test_id")
                status = result.get("status")
                duration = result.get("duration", 0)

                if status == "completed":
                    print(f"✅ {test_id}: SUCCESS - Completed in {duration:.1f}s ({result.get('polls')} polls)")
                    print(f"   Download: {result.get('download_url')}")
                elif status == "failed":
                    print(f"❌ {test_id}: FAILED - {result.get('error')} (Duration: {duration:.1f}s)")
                else:
                    print(f"⚠️ {test_id}: {status.upper()} - {result.get('error', 'Unknown')} (Duration: {duration:.1f}s)")
                print()

        print(f"🕐 Total test duration: {total_time:.1f}s")

        # Final system status check
        print("\n🔧 Final system status:")
        await check_system_status(session)

if __name__ == "__main__":
    asyncio.run(main())