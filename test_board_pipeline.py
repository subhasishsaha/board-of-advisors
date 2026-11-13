import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from board.orchestrator import BoardOrchestrator
from board.config import MEMORY_DIR, SESSIONS_DIR

async def run_pipeline_test():
    print("=" * 60)
    print("🧪 Running Board of Advisors Pipeline Smoke Test")
    print("=" * 60)

    # 1. Initialize orchestrator with 1 round for quick test
    orchestrator = BoardOrchestrator(discussion_rounds=1)
    print(f"Loaded {len(orchestrator.advisors)} advisors:")
    for a in orchestrator.advisors:
        print(f"  - {a.avatar} {a.name} ({a.tag}): {a.role}")

    assert len(orchestrator.advisors) >= 4, "Expected at least 4 advisors"

    # 2. Test problem
    test_problem = (
        "We are a 5-person team with 9 months of runway. Our core product is an AI-powered code review tool. "
        "An enterprise customer offered us a $200k contract to build a custom on-premise security scanner for them. "
        "Should we take the contract or stay 100% focused on our core SaaS tool?"
    )

    print(f"\n[Problem]: {test_problem}\n")
    print("Beginning deliberation (Opening Perspectives -> Discussion -> Plan Synthesis)...")

    # 3. Deliberation
    plan = await orchestrator.run_deliberation(problem=test_problem)

    print("\n" + "=" * 60)
    print("📋 SYNTHESIZED PLAN OF ACTION (PREVIEW):")
    print("=" * 60)
    print(plan[:600] + "...\n")

    # 4. Assertions on messages
    assert len(orchestrator.messages) >= 5, f"Expected at least 5 messages, got {len(orchestrator.messages)}"
    print(f"✅ Generated {len(orchestrator.messages)} board messages across deliberation stages.")

    # 5. Check memory persistence
    for a in orchestrator.advisors:
        mem_file = MEMORY_DIR / f"{a.id}.json"
        assert mem_file.exists(), f"Memory file for {a.name} not found at {mem_file}"
        print(f"✅ Advisor memory file confirmed: {mem_file.name}")

    # 6. Check session transcripts
    session_files = list(SESSIONS_DIR.glob("session_*.json"))
    assert len(session_files) > 0, "No session transcript saved in storage/sessions/"
    print(f"✅ Session transcript confirmed: {session_files[-1].name}")

    print("\n🎉 ALL SMOKE TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_pipeline_test())
