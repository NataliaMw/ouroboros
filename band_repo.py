"""Live Band room that runs the loop on YOUR repo — the hackathon's useful path.

This connects all six agents to Band as remote agents, but gives two of them real
tools bound to your project:
  * @QAEngineer gets run_tests() — runs your real test command.
  * @CodeAuthor gets read_target()/write_target() — reads and patches your real file.

So the multi-agent coordination happens THROUGH Band (the agents @mention each other
to design and drive the loop), and the work is real (your tests gate it, your file
gets patched). Start it, then in a Band room @mention @LoopArchitect with the goal.

    python band_repo.py --repo ../your-project --test "pytest -q" --file src/thing.py \
        --goal "fix the discount rounding bug"
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_here, "shared"))
sys.path.insert(0, _here)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_here, ".env"))
except ImportError:
    pass

from band_harness import run_band_room
from specialists import architect, critic, runner, author, qaagent, reviewer
from repo_tools import make_repo_tools


def build_mission(repo: str, test_cmd: str, target_file: str | None, goal: str) -> str:
    return (
        "Loop engineering on a REAL repo, as a room. The user has a goal on an actual "
        f"project.\n\nGOAL: {goal}\nREPO: {repo}\nTEST COMMAND: {test_cmd}\n"
        f"FILE UNDER REPAIR: {target_file or '(none)'}\n\n"
        "Coordinate through Band: @LoopArchitect designs the loop (the exit gate is the "
        "user's real test command), @LoopCritic hardens it, @LoopRunner starts it. Then "
        "@CodeAuthor reads the file with read_target, proposes a fix, and writes it with "
        "write_target; @QAEngineer runs the real suite with run_tests and reports PASS/FAIL; "
        "@RivalReviewer bounces failures back to @CodeAuthor or, on PASS, hands to "
        "@LoopRunner to finalize. Loop until the real tests pass or the budget is spent. "
        "Only ship when run_tests reports PASS."
    )


async def main() -> None:
    p = argparse.ArgumentParser(description="Live Band room running the loop on your repo.")
    p.add_argument("--repo", required=True)
    p.add_argument("--test", required=True)
    p.add_argument("--file")
    p.add_argument("--goal", default="make the failing tests pass")
    args = p.parse_args()

    repo = os.path.abspath(os.path.expanduser(args.repo))
    tools = make_repo_tools(repo, args.test, args.file)
    mission = build_mission(repo, args.test, args.file, args.goal)

    specialists = [
        architect.specialist(),
        critic.specialist(),
        runner.specialist(),
        author.specialist(tools=[tools["read_target"], tools["write_target"]]),
        qaagent.specialist(tools=[tools["run_tests"]]),
        reviewer.specialist(),
    ]
    print(f"Connecting 6 agents to Band. Goal: {args.goal}")
    print(f"  repo={repo}\n  test={args.test}\n  file={args.file}")
    print("In a Band room, add the agents and @mention @LoopArchitect to start.\n")
    await run_band_room(specialists, mission)


if __name__ == "__main__":
    asyncio.run(main())
