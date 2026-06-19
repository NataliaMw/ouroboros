"""Real tools the live Band agents use to act on a user's repo.

This is what makes the live room *useful* instead of chatty: the QAEngineer agent
gets a tool that actually runs the user's test command, and the CodeAuthor agent
gets tools that actually read and patch the target file. The agents still coordinate
through Band (@mention handoffs) — but now their turns have real side effects on
real code, gated by the user's real tests.

Tools are built bound to one repo + test command via make_repo_tools(), then handed
to the relevant adapters as additional_tools.
"""

from __future__ import annotations

import os

import qa

from pydantic_ai import RunContext


def make_repo_tools(repo: str, test_cmd: str, target_file: str | None):
    repo = os.path.abspath(os.path.expanduser(repo))
    target = os.path.join(repo, target_file) if target_file else None

    async def run_tests(ctx: RunContext) -> str:
        """Run the project's real test command and return the pass/fail result with
        the tail of the output. Use this to check whether the code is correct."""
        res = qa.run_command(test_cmd, cwd=repo)
        status = "PASS" if res.passed else "FAIL"
        return f"[{status}] `{test_cmd}`\n{res.detail}"

    async def read_target(ctx: RunContext) -> str:
        """Read the current contents of the file under repair."""
        if not target or not os.path.isfile(target):
            return "ERROR: no target file configured."
        return open(target, encoding="utf-8", errors="ignore").read()

    async def write_target(ctx: RunContext, contents: str) -> str:
        """Overwrite the target file with corrected contents. Returns confirmation.
        Only call this with the FULL new file contents."""
        if not target:
            return "ERROR: no target file configured."
        open(target, "w", encoding="utf-8").write(contents)
        return f"wrote {len(contents)} chars to {target_file}"

    return {"run_tests": run_tests, "read_target": read_target, "write_target": write_target}
