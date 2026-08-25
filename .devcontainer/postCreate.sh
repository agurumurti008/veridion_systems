#!/usr/bin/env bash
# .devcontainer/postCreate.sh
# Runs once per Codespace creation. Keep this fast — dependency installation
# already happened in updateContentCommand (and was baked in by prebuilds).
set -uo pipefail  # no -e: a failed sync here should not kill the whole script

git config --global --add safe.directory "$(pwd)"

echo "=== Checking workspace members declared in pyproject.toml ==="
python3 - <<'PY'
import re, os
try:
    text = open("pyproject.toml").read()
except FileNotFoundError:
    raise SystemExit(0)
m = re.search(r"members\s*=\s*\[(.*?)\]", text, re.S)
if m:
    members = re.findall(r'"([^"]+)"', m.group(1))
    for member in members:
        status = "OK" if os.path.isfile(os.path.join(member, "pyproject.toml")) else "MISSING pyproject.toml"
        print(f"  {member}: {status}")
PY

echo "=== Running uv sync (no --locked yet; no uv.lock committed) ==="
if uv sync --all-groups; then
  echo "uv sync succeeded."
else
  echo "uv sync FAILED — see output above. Common causes:"
  echo "  1. A folder listed in [tool.uv.workspace] members has no pyproject.toml yet."
  echo "  2. A dependency version constraint across members conflicts."
  echo "  Fix the cause, then run 'uv sync --all-groups' manually in the terminal."
fi

# Optional: install pre-commit hooks if the workspace uses them.
if uv run python -c "import pre_commit" >/dev/null 2>&1; then
  uv run pre-commit install || true
fi

echo "Devcontainer ready."
echo "Python: $(uv run python --version 2>/dev/null || echo 'venv not ready yet')"
echo "uv:     $(uv --version)"
echo "venv:   $UV_PROJECT_ENVIRONMENT"