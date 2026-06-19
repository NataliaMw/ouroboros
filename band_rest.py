"""Drive a REAL Band room over the Agent REST API.

This is how the hosted demo and the CLI make the loop's coordination genuinely live
on Band: we create a real chat room, add the six registered agents as participants,
and post each step of the loop as a message FROM the agent that produced it, @mentioning
the next agent — exactly the handoff chain, as real Band messages on a real transcript.

Auth is the per-agent X-API-Key (the Agent API). A browser User-Agent is required or
Band's edge returns 403. Agent ids/keys come from agent_config.yaml (or env in prod).

Returns the room id so the result links straight to the Band room the judges can open.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

BASE = "https://app.band.ai"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124 Safari/537.36")

HANDLES = {
    "architect": "natalia/looparchitect",
    "critic": "natalia/loopcritic",
    "runner": "natalia/looprunner",
    "author": "natalia/codeauthor",
    "qa": "natalia/qaengineer",
    "reviewer": "natalia/rivalreviewer",
}


def _load_agents() -> dict:
    """agent_config.yaml in dev; OUROBOROS_AGENTS (json) env var in prod (Vercel)."""
    env = os.getenv("OUROBOROS_AGENTS")
    if env:
        return json.loads(env)
    here = os.path.dirname(os.path.abspath(__file__))
    for cand in (os.path.join(here, "agent_config.yaml"),):
        if os.path.isfile(cand):
            import yaml
            return yaml.safe_load(open(cand))
    raise RuntimeError("no agent credentials (set OUROBOROS_AGENTS or agent_config.yaml)")


def _call(method: str, path: str, key: str, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    h = {"User-Agent": UA, "Accept": "application/json", "X-API-Key": key}
    if data:
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:200]


def open_room(agents: dict, title: str = "Ouroboros — live loop") -> str:
    """Create a room owned by the runner and add the other five agents."""
    owner = agents["runner"]["api_key"]
    s, room = _call("POST", "/api/v1/agent/chats", owner, {"chat": {"title": title}})
    if s != 201:
        raise RuntimeError(f"create room failed: {s} {room}")
    rid = room["data"]["id"]
    for k in ("architect", "critic", "author", "qa", "reviewer"):
        _call("POST", f"/api/v1/agent/chats/{rid}/participants", owner,
              {"participant": {"participant_id": agents[k]["agent_id"]}})
    return rid


def post_step(agents: dict, rid: str, frm: str, to: str, text: str) -> bool:
    """Post `text` as agent `frm`, @mentioning agent `to` (the handoff)."""
    body = {"message": {"content": f"{text} @{HANDLES[to]}",
                        "mentions": [{"id": agents[to]["agent_id"],
                                      "handle": HANDLES[to], "kind": "mention"}]}}
    s, _ = _call("POST", f"/api/v1/agent/chats/{rid}/messages", agents[frm]["api_key"], body)
    return s == 201


def room_url(rid: str) -> str:
    return f"{BASE}/chat/{rid}"
