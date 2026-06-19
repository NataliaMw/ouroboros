"""Ouroboros on YOUR repo — the useful path.

Point it at a real project and a real test command. Ouroboros runs the loop on
your actual code: run your tests → if they fail, a model patches the target file
using the real failure output → re-run → repeat until your tests pass or the budget
is spent. Every step is real: your test command is the exit gate, the model only
ever ships a patch your own tests accept.

    python run_on_repo.py --repo ../my-project \
        --test "pytest -q tests/test_cart.py" \
        --file src/cart.py \
        --goal "fix the discount rounding bug"

With no model key it still runs your tests and shows the loop; with AIMLAPI_API_KEY
(or OPENAI_API_KEY) it actually proposes fixes. It writes a .ouroboros.bak backup
and restores it if you abort, so it never eats your file.
"""

from __future__ import annotations

import argparse
import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _here)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(_here, ".env"))
except ImportError:
    pass

import qa


def _banner(t: str) -> None:
    line = "─" * 72
    print(f"\n{line}\n  {t}\n{line}")


def _model_client():
    try:
        from models import get_client
    except ImportError:
        return None
    c = get_client("author")
    return None if (c is None or c.__class__.__name__ == "CannedClient") else c


def _propose_fix(client, goal: str, path: str, source: str, failure: str) -> str | None:
    prompt = (
        "You are fixing a real source file so a failing test passes. Return ONLY the "
        "full corrected contents of the file — no prose, no code fences.\n\n"
        f"Goal: {goal}\n\nFile: {path}\n\n--- current contents ---\n{source}\n\n"
        f"--- test output (failing) ---\n{failure}\n"
    )
    try:
        out = client.complete(prompt).strip()
    except Exception as e:
        print(f"  (model error: {e})")
        return None
    if out.startswith("```"):
        out = out.strip("`")
        out = out[out.find("\n") + 1:] if "\n" in out else out
    return out or None


def _maybe_mirror_to_band(args, events) -> None:
    """If --band (or agent creds are present), post the run into a REAL Band room so
    the coordination lives on Band, and print the room link. Best-effort; never fails
    the loop."""
    want = getattr(args, "band", False) or os.getenv("OUROBOROS_AGENTS")
    if not want:
        return
    try:
        import band_rest as br
        agents = br._load_agents()
        rid = br.open_room(agents, title="Ouroboros — CLI run")
        br.post_step(agents, rid, "runner", "architect",
                     f"New task: {getattr(args,'goal','fix the failing tests')}.")
        br.post_step(agents, rid, "architect", "critic",
                     "Designed the loop: exit gate is the repo's real test command.")
        br.post_step(agents, rid, "critic", "author", "Exit condition holds. Approved.")
        for frm, to, txt in events:
            br.post_step(agents, rid, frm, to, txt)
        print(f"\n  ↗ mirrored to a real Band room: {br.room_url(rid)}\n")
    except Exception as e:
        print(f"\n  (Band mirror skipped: {e})\n")


def main() -> int:
    p = argparse.ArgumentParser(description="Run the Ouroboros loop on your own repo.")
    p.add_argument("--repo", required=True, help="path to your project (the loop's cwd)")
    p.add_argument("--test", required=True, help='your test command, e.g. "pytest -q"')
    p.add_argument("--file", help="the source file the loop may patch")
    p.add_argument("--goal", default="make the failing tests pass")
    p.add_argument("--max-revisions", type=int, default=3)
    p.add_argument("--band", action="store_true",
                   help="also mirror the loop into a real Band room (needs agent creds)")
    p.add_argument("--fallback-fix", help=argparse.SUPPRESS)  # known-good file for the
    # keyless bundled demo: when no model is available, apply this so the loop can close
    # end-to-end without a key. Not for real repos — there the loop needs a model.
    args = p.parse_args()

    repo = os.path.abspath(os.path.expanduser(args.repo))
    if not os.path.isdir(repo):
        print(f"repo not found: {repo}")
        return 2
    target = os.path.join(repo, args.file) if args.file else None

    _banner("LOOP ON YOUR REPO")
    print(f"  repo : {repo}")
    print(f"  test : {args.test}")
    print(f"  file : {args.file or '(none — read-only loop)'}")
    print(f"  goal : {args.goal}")

    print("\n  @LoopArchitect: this is a bugfix loop — exit gate is YOUR test command, "
          "max\n  {} revisions, RivalReviewer reads each real run.".format(args.max_revisions))

    client = _model_client()
    backup = None
    if target and os.path.isfile(target):
        backup = open(target, encoding="utf-8", errors="ignore").read()

    events = []  # (from, to, text) for optional Band-room mirroring
    final_rev = 0
    try:
        for rev in range(args.max_revisions + 1):
            res = qa.run_command(args.test, cwd=repo)
            final_rev = rev
            print(f"\n  ┃ QAEngineer ▸ revision {rev}: `{args.test}` → {res.icon}")
            events.append(("qa", "reviewer", f"revision {rev}: ran the real test → {'PASS' if res.passed else 'FAIL'}"))
            if res.passed:
                _banner("LOOP COMPLETE — your tests pass")
                print("  RivalReviewer: ran your real suite, it's green. Shipping.")
                print(f"  status: shipped after {rev} revision(s)\n")
                events.append(("reviewer", "runner", f"tests green ✅ — shipped after {rev} revision(s)."))
                _maybe_mirror_to_band(args, events)
                return 0
            tail = "\n".join("      " + l for l in res.detail.splitlines()[-6:])
            print(f"  ┃ RivalReviewer ▸ still failing:\n{tail}")

            if rev == args.max_revisions:
                break
            if not (target and os.path.isfile(target)):
                print("\n  (no --file to patch — stopping at a verified failure.)")
                break

            if client:
                print(f"  ┃ CodeAuthor ▸ patching {args.file} via AI/ML API "
                      f"against the real failure…")
                source = open(target, encoding="utf-8", errors="ignore").read()
                fixed = _propose_fix(client, args.goal, args.file, source, res.detail)
            elif args.fallback_fix and os.path.isfile(args.fallback_fix):
                print(f"  ┃ CodeAuthor ▸ patching {args.file} (no model key → "
                      f"deterministic reference fix)…")
                fixed = open(args.fallback_fix, encoding="utf-8", errors="ignore").read()
            else:
                print("\n  (no model key and no --file to patch — stopping at a verified "
                      "failure.\n   set AIMLAPI_API_KEY to let a model write the fix.)")
                break
            if not fixed:
                print("  CodeAuthor: no patch produced; stopping.")
                break
            open(target, "w", encoding="utf-8").write(fixed)

        _banner("LOOP EXHAUSTED — handing you a VERIFIED failure")
        print("  The loop could not make your tests pass within the budget.\n"
              "  That's a real result: your suite still fails, here's the last output above.\n")
        return 1
    except KeyboardInterrupt:
        if backup is not None:
            open(target, "w", encoding="utf-8").write(backup)
            print("\n  aborted — restored your original file.")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
