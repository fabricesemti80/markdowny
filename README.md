# Markdowny CLI

`mdy` converts:

- Markdown -> DOCX
- Markdown -> PDF
- DOCX -> Markdown

## Requirements

- `uv`
- **Pandoc** – the CLI will auto‑download a copy via `pypandoc` if a system
  binary isn't found, but for best performance and file size you can install
  Pandoc yourself and put it on your `PATH`.
- For PDF output: `libcairo2-dev` and `pkg-config` (Linux) or equivalent
- Optional for better long Mermaid handling in DOCX: `pillow`

## Quick Install (all prerequisites)

### Linux / macOS

```bash
curl -sSL https://raw.githubusercontent.com/fabricesemti80/markdowny/main/install.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/fabricesemti80/markdowny/main/install.ps1 | iex
```

## Uninstall

To remove `mdy` (leaves pandoc, uv, and system libs intact):

### Linux / macOS

```bash
curl -sSL https://raw.githubusercontent.com/fabricesemti80/markdowny/main/uninstall.sh | bash
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/fabricesemti80/markdowny/main/uninstall.ps1 | iex
```

## Install

From this repository root:

```bash
uv tool install --native-tls --python 3.12 .
```

Note: Python 3.12 is required for PDF support (xhtml2pdf dependency).

If `mdy` is not found after install, your tools bin directory is not on `PATH`.

PowerShell (current session):

```powershell
$env:PATH = "C:\Users\<your-user>\.local\bin;$env:PATH"
mdy --help
```

Permanent shell setup:

```powershell
uv tool update-shell
```

Then restart your terminal.

No-PATH fallback:

```bash
uv tool run mdy --help
```

## Usage

Show help:

```bash
mdy --help
```

Markdown -> PDF:

```bash
mdy path/to/file.md --pdf
```

Markdown -> DOCX:

```bash
mdy path/to/file.md --docx
```

DOCX -> Markdown:

```bash
mdy path/to/file.docx
```

Optional output path:

```bash
mdy path/to/file.md out.pdf --pdf
```

If output path is omitted, `mdy` auto-generates one based on the input filename.

## Developer Notes

Development workflows (`make`, `uv sync`, `uv run`, local testing) are in `DEVNOTES.md`.
