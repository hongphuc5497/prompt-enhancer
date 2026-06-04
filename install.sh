#!/bin/sh
# Prompt Enhancer — quick install script
# Usage: curl -fsSL https://raw.githubusercontent.com/hongphuc5497/prompt-enhancer/main/install.sh | sh

set -e

BIN_DIR="${HOME}/.local/bin"
REPO="https://github.com/hongphuc5497/prompt-enhancer.git"
INSTALL_DIR="${HOME}/.prompt-enhancer/repo"

echo "📦 Installing Prompt Enhancer..."

# Create bin directory
mkdir -p "${BIN_DIR}"

# Clone/update repo
if [ -d "${INSTALL_DIR}" ]; then
    echo "  Updating existing install..."
    git -C "${INSTALL_DIR}" pull --rebase origin main 2>/dev/null || true
else
    echo "  Cloning repo..."
    git clone "${REPO}" "${INSTALL_DIR}" 2>/dev/null
fi

# Install via pip (user install, no venv needed)
PYTHON="${PYTHON3:-$(which python3.11 2>/dev/null || which python3)}"
echo "  Using Python: ${PYTHON}"
"${PYTHON}" -m pip install --user --quiet "${INSTALL_DIR}" 2>/dev/null || {
    echo "  pip install failed, falling back to symlink..."
    # Fallback: symlink the CLI directly (stdlib only, pip not strictly needed)
    ln -sf "${INSTALL_DIR}/src/prompt_enhancer/cli.py" "${BIN_DIR}/prompt-enhancer"
    chmod +x "${BIN_DIR}/prompt-enhancer"
}

# Add to PATH if needed
case ":${PATH}:" in
    *:"${BIN_DIR}":*) ;;
    *)
        SHELL_RC="${HOME}/.zshrc"
        if [ -f "${HOME}/.bashrc" ]; then SHELL_RC="${HOME}/.bashrc"; fi
        echo "export PATH=\"${BIN_DIR}:\$PATH\"" >> "${SHELL_RC}"
        echo "  Added ${BIN_DIR} to PATH in ${SHELL_RC}"
        ;;
esac

echo ""
echo "✅ Prompt Enhancer installed!"
echo "   Run: prompt-enhancer enhance \"a Rust dev who likes functional style\""
echo ""
echo "   Set up your API key:"
echo "   echo 'LLM_API_KEY=*** > ~/.prompt-enhancer.env"
