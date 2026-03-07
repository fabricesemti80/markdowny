#!/bin/bash

set -e

echo "Installing prerequisites for docflux..."

if ! command -v pandoc &> /dev/null; then
    echo "Installing pandoc..."
    if command -v apt-get &> /dev/null; then
        sudo rm -f /etc/apt/sources.list.d/yarn.list 2>/dev/null || true
        sudo apt-get update && sudo apt-get install -y pandoc
    elif command -v brew &> /dev/null; then
        brew install pandoc
    else
        echo "Please install pandoc manually: https://pandoc.org/installing.html"
        exit 1
    fi
fi

if ! command -v uv &> /dev/null; then
    echo "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "Installing system dependencies for PDF..."
if command -v apt-get &> /dev/null; then
    sudo apt-get install -y libcairo2-dev pkg-config
fi

if [[ -z "${BASH_SOURCE[0]}" || "${BASH_SOURCE[0]}" == "bash" ]]; then
    echo "Downloading latest docflux..."
    INSTALL_DIR=$(mktemp -d)
    curl -sSL https://github.com/fabricesemti80/docflux/archive/refs/heads/main.tar.gz | tar xz -C "$INSTALL_DIR"
    cd "$INSTALL_DIR/docflux-main"
elif [[ -f "pyproject.toml" ]]; then
    echo "Installing from local directory..."
else
    cd "$(dirname "${BASH_SOURCE[0]}")"
fi

echo "Installing Python 3.12 (required for PDF support)..."
uv python install 3.12

echo "Installing docflux with PDF support..."
uv tool install --native-tls --python 3.12 .

echo "Done! You can now run: dfx <input.md> [output]"
