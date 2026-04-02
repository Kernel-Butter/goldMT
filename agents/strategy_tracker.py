"""
GoldBot Strategy Tracker Agent
=================================
Detects strategy changes in the codebase and updates strategy_info.json.

Usage:
  python agents/strategy_tracker.py              # auto-detect changes from git diff
  python agents/strategy_tracker.py --log        # same (explicit)
  python agents/strategy_tracker.py --manual     # interactive: describe change yourself
  python agents/strategy_tracker.py --plan "title" "description" [--priority high|medium|low]
  python agents/strategy_tracker.py --issue "description of a known problem"
  python agents/strategy_tracker.py --resolve-issue 0   # mark issue 0 as resolved (removes it)
  python agents/strategy_tracker.py --outcome "active|success|failed|superseded" "note"
  python agents/strategy_tracker.py --show       # print current state summary
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

# ── Paths ──────────────────────────────────────────────────
ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INFO_PATH  = os.path.join(ROOT, "strategy_info.json")
STRATEGY_FILES = [
    "main.py",
    "technical.py",
    "config.py",
    "groq_analyst.py",
    "risk_manager.py",
]

# ── Groq (optional — used for AI-assisted change summarisation) ──
try:
    sys.path.insert(0, ROOT)
    from config import GROQ_API_KEY, GROQ_URL
    import requests as _req
    GROQ_AVAILABLE = bool(GROQ_API_KEY)
except Exception:
    GROQ_AVAILABLE = False


# ── Helpers ────────────────────────────────────────────────

def load() -> dict:
    with open(INFO_PATH, encoding="utf-8") as f:
        return json.load(f)


def save(data: dict):
    with open(INFO_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  [saved] {INFO_PATH}")


def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def git(*args) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", ROOT, *args],
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
    except Exception:
        return ""


def latest_commit() -> dict:
    """Return info about the most recent commit."""
    line  = git("log", "--oneline", "-1")
    parts = line.split(" ", 1)
    return {
        "hash":  parts[0] if parts else "",
        "title": parts[1] if len(parts) > 1 else "",
    }


def diff_strategy_files() -> str:
    """Get git diff for strategy-relevant files vs last commit."""
    files = [f for f in STRATEGY_FILES if os.path.exists(os.path.join(ROOT, f))]
    diff  = git("diff", "HEAD~1", "HEAD", "--", *files)
    if not diff:
        # Try unstaged changes
        diff = git("diff", "--", *files)
    return diff


def ask_groq(prompt: str) -> str:
    """Send a prompt to Groq and return the response text."""
    if not GROQ_AVAILABLE:
        return ""
    try:
        resp = _req.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
            json={
                "model":      "llama-3.3-70b-versatile",
                "messages":   [{"role": "user", "content": prompt}],
                "max_tokens": 800,
                "temperature": 0.2,
            },
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [Groq error] {e}")
        return ""


def ai_summarise_diff(diff: str, commit_title: str) -> dict:
    """
    Ask Groq to extract structured change info from a git diff.
    Returns dict with: summary, changes (list of {type, item})
    """
    prompt = f"""You are analysing a git diff for a XAUUSD (Gold) trading bot codebase.
Commit: {commit_title}

Diff:
{diff[:6000]}

Extract ONLY what changed in terms of trading strategy, indicators, filters, and risk rules.
Respond with valid JSON only, no markdown:
{{
  "summary": "one sentence describing the overall change",
  "changes": [
    {{"type": "added|removed|changed", "item": "plain English description of specific change"}}
  ]
}}
Focus on: filters added/removed, indicator thresholds changed, new logic, removed logic.
Ignore: formatting, comments, imports, dashboard/UI changes."""

    raw = ask_groq(prompt)
    if not raw:
        return {"summary": commit_title, "changes": []}

    # Strip markdown fences if present
    raw = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"summary": commit_title, "changes": []}


# ── Commands ───────────────────────────────────────────────

def cmd_log(manual: bool = False):
    """Detect changes and append a history entry."""
    data   = load()
    commit = latest_commit()

    # Check if this commit is already in history
    existing_commits = [h.get("commit", "") for h in data.get("history", [])]
    if commit["hash"] and commit["hash"] in existing_commits:
        print(f"  [skip] commit {commit['hash']} already in history.")
        return

    if manual:
        # Interactive mode
        print("\n── Manual strategy log ─────────────────────────────")
        title   = input("  Title (short description): ").strip()
        summary = input("  Summary (1-2 sentences): ").strip()
        print("  Changes (one per line, format: added|removed|changed: description)")
        print("  Press Enter on empty line to finish:")
        changes = []
        while True:
            line = input("  > ").strip()
            if not line:
                break
            if ":" in line:
                ctype, item = line.split(":", 1)
                changes.append({"type": ctype.strip().lower(), "item": item.strip()})
            else:
                changes.append({"type": "changed", "item": line})
    else:
        diff = diff_strategy_files()
        if not diff:
            print("  [info] No strategy file changes detected in last commit.")
            title   = commit["title"] or "Strategy update"
            summary = title
            changes = []
        else:
            print(f"  [detected] diff in strategy files — commit: {commit['hash']} {commit['title']}")
            if GROQ_AVAILABLE:
                print("  [groq] Summarising changes...")
                parsed  = ai_summarise_diff(diff, commit["title"])
                summary = parsed.get("summary", commit["title"])
                changes = parsed.get("changes", [])
                print(f"  Summary: {summary}")
                for c in changes:
                    print(f"    [{c['type']}] {c['item']}")
            else:
                print("  [warn] Groq not available — using commit title only.")
                summary = commit["title"]
                changes = []
            title = commit["title"]

    # Get current version and bump it
    current_ver = data.get("current", {}).get("version", "1.0")
    try:
        major, minor = current_ver.split(".")
        new_ver = f"{int(major)}.{int(minor) + 1}"
    except Exception:
        new_ver = current_ver

    entry = {
        "date":         today(),
        "version":      new_ver,
        "commit":       commit["hash"],
        "title":        title,
        "summary":      summary,
        "changes":      changes,
        "outcome":      "active",
        "outcome_note": "Recently applied — outcome pending evaluation",
    }

    # Insert at front of history (newest first)
    data.setdefault("history", []).insert(0, entry)

    # Update current version and last_updated
    data.setdefault("current", {})["version"]      = new_ver
    data["current"]["last_updated"] = today()

    save(data)
    print(f"\n  [logged] History entry added: {title}")


def cmd_plan(title: str, description: str, priority: str = "medium"):
    """Add a future plan entry."""
    data = load()
    plan = {
        "priority":    priority,
        "title":       title,
        "description": description,
        "status":      "not_started",
        "added":       today(),
    }
    data.setdefault("future_plans", []).insert(0, plan)
    save(data)
    print(f"  [added] Future plan: {title}")


def cmd_issue(description: str):
    """Add a known issue."""
    data = load()
    data.setdefault("current", {}).setdefault("known_issues", []).append(description)
    save(data)
    print(f"  [added] Known issue: {description}")


def cmd_resolve_issue(index: int):
    """Remove a known issue by index."""
    data   = load()
    issues = data.get("current", {}).get("known_issues", [])
    if 0 <= index < len(issues):
        removed = issues.pop(index)
        save(data)
        print(f"  [resolved] Removed issue: {removed}")
    else:
        print(f"  [error] No issue at index {index}. There are {len(issues)} issues (0–{len(issues)-1}).")


def cmd_outcome(outcome: str, note: str):
    """Update the outcome of the most recent history entry."""
    valid = {"active", "success", "failed", "superseded", "pending"}
    if outcome not in valid:
        print(f"  [error] outcome must be one of: {', '.join(sorted(valid))}")
        return
    data    = load()
    history = data.get("history", [])
    if not history:
        print("  [error] No history entries yet.")
        return
    history[0]["outcome"]      = outcome
    history[0]["outcome_note"] = note
    save(data)
    print(f"  [updated] Latest entry outcome → {outcome}: {note}")


def cmd_show():
    """Print a readable summary to the terminal."""
    data    = load()
    current = data.get("current", {})
    plans   = data.get("future_plans", [])
    history = data.get("history", [])

    print(f"\n{'═'*60}")
    print(f"  {current.get('name', 'GoldBot')}  v{current.get('version', '?')}  [{current.get('last_updated', '?')}]")
    print(f"  {current.get('phase_summary', '')}")
    print(f"{'─'*60}")

    print(f"\n  THIS WEEK: {current.get('this_week', {}).get('focus', '—')}")

    print(f"\n  ACTIVE FILTERS ({len(current.get('filters', []))}):")
    for f in current.get("filters", []):
        badge = "✓" if f["status"] == "active" else "~" if f["status"] == "testing" else "✗"
        print(f"    {badge} {f['name']} — {f['threshold']}")

    print(f"\n  KNOWN ISSUES ({len(current.get('known_issues', []))}):")
    for i, issue in enumerate(current.get("known_issues", [])):
        print(f"    [{i}] {issue}")

    print(f"\n  FUTURE PLANS ({len(plans)}):")
    for p in plans:
        pri_sym = {"high": "!!!", "medium": "!", "low": "·"}.get(p.get("priority", "low"), "·")
        print(f"    {pri_sym} [{p.get('priority','?').upper()}] {p['title']}")
        print(f"       {p['description'][:80]}...")

    print(f"\n  HISTORY ({len(history)} entries):")
    for h in history:
        outcome_sym = {"active": "▶", "success": "✓", "failed": "✗", "superseded": "→", "pending": "?"}.get(h.get("outcome", "?"), "?")
        print(f"    {outcome_sym} [{h['date']}] v{h.get('version','?')} — {h['title']}")
        if h.get("changes"):
            for c in h["changes"][:3]:
                print(f"         [{c['type']}] {c['item']}")
    print(f"\n{'═'*60}\n")


# ── CLI ────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="GoldBot Strategy Tracker — keeps strategy_info.json up to date"
    )
    parser.add_argument("--log",           action="store_true", help="Auto-detect changes from git diff and log them")
    parser.add_argument("--manual",        action="store_true", help="Manually describe a strategy change")
    parser.add_argument("--plan",          nargs=2, metavar=("TITLE", "DESC"), help="Add a future plan")
    parser.add_argument("--priority",      default="medium", choices=["high", "medium", "low"])
    parser.add_argument("--issue",         metavar="DESC", help="Add a known issue")
    parser.add_argument("--resolve-issue", metavar="INDEX", type=int, help="Remove a known issue by index")
    parser.add_argument("--outcome",       nargs=2, metavar=("STATUS", "NOTE"), help="Set outcome of latest history entry")
    parser.add_argument("--show",          action="store_true", help="Print current strategy summary")
    args = parser.parse_args()

    if args.show:
        cmd_show()
    elif args.plan:
        cmd_plan(args.plan[0], args.plan[1], args.priority)
    elif args.issue:
        cmd_issue(args.issue)
    elif args.resolve_issue is not None:
        cmd_resolve_issue(args.resolve_issue)
    elif args.outcome:
        cmd_outcome(args.outcome[0], args.outcome[1])
    elif args.manual:
        cmd_log(manual=True)
    else:
        # Default: auto-detect from git
        cmd_log(manual=False)


if __name__ == "__main__":
    main()
