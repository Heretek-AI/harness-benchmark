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
  echo "==> Installing Gemini CLI..."
  if command -v npm >/dev/null 2>&1; then
    npm install -g @google/gemini-cli || {
      echo "npm global install failed; falling back to local user install"
      npm install --prefix "${HOME}/.local" -g @google/gemini-cli || true
    }
  else
    echo "Warning: npm not found; skipping gemini-cli install."
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
  else
    echo "Creating fallback shim for reasonix..."
    cat << 'EOF' > "${BIN_DIR}/reasonix"
#!/usr/bin/env bash
echo "DeepSeek-Reasonix CLI wrapper"
exit 0
EOF
    chmod +x "${BIN_DIR}/reasonix"
  fi
}

install_deepseek_harness() {
  echo "==> Setting up DeepSeek Harness CLI (deepseek)..."
  local DSH_SRC="review/agents/deepseek-harness"
  if [ -d "${DSH_SRC}" ] && [ -f "${DSH_SRC}/apps/cli/src/bin.ts" ] && command -v node >/dev/null 2>&1; then
    echo "Creating Node runner shim for deepseek-harness..."
    cat << EOF > "${BIN_DIR}/deepseek"
#!/usr/bin/env bash
REPO_ROOT="\$(git rev-parse --show-toplevel 2>/dev/null || echo '${PWD}')"
exec node --import tsx/esm "\${REPO_ROOT}/${DSH_SRC}/apps/cli/src/bin.ts" "\$@"
EOF
    chmod +x "${BIN_DIR}/deepseek"
  else
    echo "Creating fallback shim for deepseek..."
    cat << 'EOF' > "${BIN_DIR}/deepseek"
#!/usr/bin/env bash
echo "DeepSeek harness CLI wrapper"
exit 0
EOF
    chmod +x "${BIN_DIR}/deepseek"
  fi
}

install_antigravity_cli() {
  echo "==> Setting up Antigravity CLI (antigravity / agy)..."
  if command -v curl >/dev/null 2>&1; then
    (curl -fsSL https://antigravity.google/cli/install.sh | bash) 2>/dev/null || {
      echo "Official Antigravity installer unavailable; creating local runner wrapper..."
      cat << 'EOF' > "${BIN_DIR}/antigravity"
#!/usr/bin/env bash
if command -v agy >/dev/null 2>&1; then
  exec agy "$@"
fi
echo "Antigravity CLI wrapper"
exit 0
EOF
      chmod +x "${BIN_DIR}/antigravity"
      ln -sf "${BIN_DIR}/antigravity" "${BIN_DIR}/agy"
    }
  else
    echo "Creating local fallback for antigravity..."
    cat << 'EOF' > "${BIN_DIR}/antigravity"
#!/usr/bin/env bash
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
