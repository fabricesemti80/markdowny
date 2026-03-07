#!/bin/bash

set -e

echo "Uninstalling docflux (dfx)..."

if ! command -v uv &> /dev/null; then
    echo "uv not found – nothing to uninstall."
    exit 0
fi

if uv tool list 2>/dev/null | grep -q "md-converter"; then
    uv tool uninstall md-converter
    echo "Removed dfx tool."
else
    echo "dfx is not currently installed via uv."
fi

echo ""
echo "Done! The following were NOT removed (they may be used by other tools):"
echo "  - uv"
echo "  - pandoc"
echo "  - libcairo2-dev / pkg-config"
echo "To remove those manually:"
echo "  sudo apt-get remove --purge pandoc libcairo2-dev pkg-config"
echo "  rm -rf ~/.local/bin/uv ~/.cargo/bin/uv"
