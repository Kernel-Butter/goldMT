---
name: Terminal style preferences
description: User's preferences for terminal output formatting and color usage
type: feedback
---

Do not use blue color in terminal output or scripts.

**Why:** User finds it hard to read or simply dislikes it.

**How to apply:** When writing shell scripts, Python CLI output, or any colored terminal text, avoid blue (e.g., avoid `\033[34m`, `\033[94m`, `Fore.BLUE`, `chalk.blue`, etc.). Use white, green, yellow, red, or plain text instead.
