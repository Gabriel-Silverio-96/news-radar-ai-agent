#!/bin/zsh
set -euo pipefail


PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
ADK_BIN="$PROJECT_DIR/.venv/bin/adk"
AGENT_DIR="$PROJECT_DIR"
REQUEST="Research the latest international headlines, prepare a Brazilian Portuguese report with 5 to 10 distinct news items, and save it as a new Google Doc using save_news_report. Return the document link."

print "
█░░ █▀█ ▄▀█ █▀▄ █ █▄░█ █▀▀ ░ ░ ░
█▄▄ █▄█ █▀█ █▄▀ █ █░▀█ █▄█ ▄ ▄ ▄"

if [[ ! -x "$ADK_BIN" ]]; then
  print -u2 "ADK was not found at $ADK_BIN. Create or activate the project's virtual environment and install google-adk."
  exit 1
fi

if "$ADK_BIN" run "$AGENT_DIR" "$REQUEST"; then
    print "
█▀▀ █ █▄░█ █ █▀ █░█
█▀░ █ █░▀█ █ ▄█ █▀█"
else
  exit_code=$?
  print -u2 "News report failed (exit code $exit_code)."
  exit "$exit_code"
fi
