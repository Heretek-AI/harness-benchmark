#!/usr/bin/env bash
# ==============================================================================
# Harness Installation Utility for Harness Benchmark
#
# Installs or compiles target AI coding agent CLIs in local and CI environments.
# Usage:
#   bash scripts/install_harness.sh [claude-code|gemini-cli|opencode|DeepSeek-Reasonix|deepseek-harness|antigravity-cli|all|stub]
# ==============================================================================

set -euo pipefail

HARNESS="${1:-all}"
BIN_DIR="${HOME}/.local/bin"
mkdir -p "${BIN_DIR}"
export PATH="${BIN_DIR}:${PATH}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${SCRIPT_DIR}/agent_engine.py" ]; then
  cp -f "${SCRIPT_DIR}/agent_engine.py" "${BIN_DIR}/agent_engine.py"
  chmod +x "${BIN_DIR}/agent_engine.py"
fi

install_claude_code() {
  echo "==> Installing Claude Code CLI..."
  if command -v npm >/dev/null 2>&1; then
    npm install -g @anthropic-ai/claude-code || {
      echo "npm global install failed; falling back to local user install"
      npm install --prefix "${HOME}/.local" -g @anthropic-ai/claude-code || true
    }
  elif command -v curl >/dev/null 2>&1; then
    curl -fsSL https://claude.ai/install.sh | bash || true
  else
    echo "Warning: Neither npm nor curl found; skipping claude-code install."
  fi
}

install_gemini_cli() {
  echo "==> Installing Google Gemini CLI..."
  if command -v npm >/dev/null 2>&1; then
    npm install -g @google/gemini-cli || {
      echo "npm global install failed; falling back to local user install"
      npm install --prefix "${HOME}/.local" -g @google/gemini-cli || true
    }
  fi
  if [ ! -f "${BIN_DIR}/gemini" ] && ! command -v gemini >/dev/null 2>&1; then
    echo "Creating fallback runner for gemini-cli..."
    cat << 'EOF' > "${BIN_DIR}/gemini"
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${DIR}/agent_engine.py" ]; then
  exec python3 "${DIR}/agent_engine.py" "$@"
fi
echo "Gemini CLI wrapper"
exit 0
EOF
    chmod +x "${BIN_DIR}/gemini"
  fi
}

install_opencode() {
  echo "==> Installing OpenCode CLI..."
  if command -v npm >/dev/null 2>&1; then
    npm install -g opencode-ai@latest || {
      echo "npm global install failed; falling back to local user install"
      npm install --prefix "${HOME}/.local" -g opencode-ai@latest || true
    }
  elif command -v curl >/dev/null 2>&1; then
    curl -fsSL https://opencode.ai/install | bash || true
  else
    echo "Warning: Neither npm nor curl found; skipping opencode install."
  fi
}

install_deepseek_reasonix() {
  echo "==> Setting up DeepSeek-Reasonix CLI (reasonix)..."
  local REASONIX_SRC="review/agents/DeepSeek-Reasonix"
  if [ -d "${REASONIX_SRC}/cmd/reasonix" ] && command -v go >/dev/null 2>&1; then
    echo "Compiling reasonix from local source..."
    (cd "${REASONIX_SRC}" && CGO_ENABLED=0 go build -o "${BIN_DIR}/reasonix" ./cmd/reasonix)
    chmod +x "${BIN_DIR}/reasonix"
    echo "Compiled ${BIN_DIR}/reasonix successfully."
  elif command -v git >/dev/null 2>&1 && command -v go >/dev/null 2>&1; then
    echo "Cloning and building reasonix from upstream repository..."
    rm -rf /tmp/DeepSeek-Reasonix
    git clone --depth 1 https://github.com/esengine/DeepSeek-Reasonix.git /tmp/DeepSeek-Reasonix || true
    if [ -d "/tmp/DeepSeek-Reasonix/cmd/reasonix" ]; then
      (cd /tmp/DeepSeek-Reasonix && CGO_ENABLED=0 go build -o "${BIN_DIR}/reasonix" ./cmd/reasonix) || true
      chmod +x "${BIN_DIR}/reasonix" 2>/dev/null || true
    fi
  fi

  if [ ! -f "${BIN_DIR}/reasonix" ]; then
    echo "Creating Agent Engine fallback runner for reasonix..."
    cat << 'EOF' > "${BIN_DIR}/reasonix"
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${DIR}/agent_engine.py" ]; then
  exec python3 "${DIR}/agent_engine.py" "$@"
fi
echo "DeepSeek-Reasonix CLI wrapper"
exit 0
EOF
    chmod +x "${BIN_DIR}/reasonix"
  fi
}

install_deepseek_harness() {
  echo "==> Setting up DeepSeek Harness CLI (deepseek)..."
  if command -v npm >/dev/null 2>&1; then
    npm install -g pnpm tsx || true
  fi
  local DSH_SRC="review/agents/deepseek-harness"
  if [ -d "${DSH_SRC}" ] && [ -f "${DSH_SRC}/apps/cli/src/bin.ts" ] && command -v node >/dev/null 2>&1; then
    echo "Building dependencies for deepseek-harness..."
    if command -v pnpm >/dev/null 2>&1; then
      (cd "${DSH_SRC}" && pnpm install --no-frozen-lockfile 2>/dev/null || true)
    fi
    echo "Creating Node runner shim for deepseek-harness..."
    cat << EOF > "${BIN_DIR}/deepseek"
#!/usr/bin/env bash
REPO_ROOT="\$(git rev-parse --show-toplevel 2>/dev/null || echo '${PWD}')"
exec node --import tsx/esm "\${REPO_ROOT}/${DSH_SRC}/apps/cli/src/bin.ts" "\$@"
EOF
    chmod +x "${BIN_DIR}/deepseek"
    ln -sf "${BIN_DIR}/deepseek" "${BIN_DIR}/dsh"
  else
    echo "Creating Agent Engine runner for deepseek / dsh..."
    cat << 'EOF' > "${BIN_DIR}/deepseek"
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${DIR}/agent_engine.py" ]; then
  exec python3 "${DIR}/agent_engine.py" "$@"
fi
echo "DeepSeek harness CLI wrapper"
exit 0
EOF
    chmod +x "${BIN_DIR}/deepseek"
    ln -sf "${BIN_DIR}/deepseek" "${BIN_DIR}/dsh"
  fi
}

install_antigravity_cli() {
  echo "==> Setting up Antigravity CLI (antigravity / agy)..."
  if command -v agy >/dev/null 2>&1 && [ "$(command -v agy)" != "${BIN_DIR}/antigravity" ] && [ "$(command -v agy)" != "${BIN_DIR}/agy" ]; then
    echo "Using existing agy binary on host: $(command -v agy)"
    ln -sf "$(command -v agy)" "${BIN_DIR}/antigravity"
  else
    echo "Creating Agent Engine runner for antigravity / agy..."
    cat << 'EOF' > "${BIN_DIR}/antigravity"
#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "${DIR}/agent_engine.py" ]; then
  exec python3 "${DIR}/agent_engine.py" "$@"
fi
echo "Antigravity CLI wrapper"
exit 0
EOF
    chmod +x "${BIN_DIR}/antigravity"
    ln -sf "${BIN_DIR}/antigravity" "${BIN_DIR}/agy"
  fi
}

case "${HARNESS}" in
  "claude-code")
    install_claude_code
    ;;
  "gemini-cli")
    install_gemini_cli
    ;;
  "opencode")
    install_opencode
    ;;
  "DeepSeek-Reasonix")
    install_deepseek_reasonix
    ;;
  "deepseek-harness")
    install_deepseek_harness
    ;;
  "antigravity-cli")
    install_antigravity_cli
    ;;
  "stub")
    echo "Stub harness requires no external binary installation."
    ;;
  "all")
    install_claude_code
    install_gemini_cli
    install_opencode
    install_deepseek_reasonix
    install_deepseek_harness
    install_antigravity_cli
    ;;
  *)
    echo "Unknown harness: ${HARNESS}"
    exit 1
    ;;
esac

echo "Harness installation finished for: ${HARNESS}"
