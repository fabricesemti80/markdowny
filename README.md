# Markdown, DOCX, and PDF Converter

This project provides a Python script to convert:

- Markdown -> DOCX
- Markdown -> PDF
- DOCX -> Markdown

The script auto-detects the direction from the input file extension.

## Requirements

### Required tools

- Python 3.10+ (tested with Python 3.13)
- Pandoc (must be installed and available in `PATH`)
- `uv` (required for `uv sync`, `uv run`, and `make init`)

### Optional tools

- GNU Make (if you want to use the `Makefile` convenience targets)
- WeasyPrint runtime libraries (optional): if unavailable, PDF generation automatically falls back to `xhtml2pdf`

### Python dependencies

- Declared in `pyproject.toml` and locked in `uv.lock`:
  - `pypandoc`
  - `requests`
  - `xhtml2pdf`

### Network requirement

- Mermaid diagrams are rendered through `https://mermaid.ink`; internet access is required when converting Markdown files containing Mermaid blocks.

## What the script does

- Auto-detects conversion direction:
  - `.md` -> `.docx` or `.pdf`
  - `.docx` -> `.md`
- Supports command-line and interactive modes.
- If format is not provided for Markdown input, prompts for output format (`docx` default, `pdf` optional).
- Markdown -> DOCX:
  - Strips YAML front matter before conversion.
  - Replaces standalone `---` lines with `***` to avoid YAML misinterpretation.
  - Resolves image resources from both the input file directory and current working directory.
  - Renders fenced Mermaid blocks (```mermaid ... ```) to PNG images via `https://mermaid.ink`.
- DOCX -> Markdown:
  - Extracts embedded media into a `media` folder next to the output Markdown file.
  - Uses unwrapped lines (`--wrap=none`).

## Using Make

### 1. Initialize environment

```bash
make init
```

This syncs dependencies using `uv sync`.

### 2. Convert files

Markdown -> DOCX:

```bash
make convert INPUT=doc.md
make convert INPUT=doc.md OUTPUT=out.docx
```

Markdown -> PDF:

```bash
make convert INPUT=doc.md FORMAT=pdf
```

Prompt for format (defaults to DOCX):

```bash
make convert INPUT=doc.md
```

DOCX -> Markdown:

```bash
make convert INPUT=doc.docx
make convert INPUT=doc.docx OUTPUT=out.md
```

If `OUTPUT` is omitted, the script uses a default based on input filename.
If `FORMAT` is omitted for Markdown input, the script prompts for `docx`/`pdf` (default: `docx`).

### 3. Clean up

```bash
make clean
```

## Manual usage (without Make)

1. Sync project environment from lockfile:
   `uv sync --native-tls`
2. Run the script:
   - With arguments:
     `uv run --no-sync mdy input_file [output_file] -f [docx|pdf]`
   - Interactive mode:
     `uv run --no-sync mdy`
   - Shortcut flags:
     `--pdf` (same as `-f pdf`) and `--docx` (same as `-f docx`)
   - If `output_file` is omitted, a default path is used automatically.

Examples:

```bash
uv run --no-sync mdy test.md
uv run --no-sync mdy test.md test.docx
uv run --no-sync mdy test.md --pdf
uv run --no-sync mdy test.md test.pdf --pdf
uv run --no-sync mdy document.docx
uv run --no-sync mdy document.docx document.md
```

Install as a global command:

```bash
uv tool install --native-tls .
mdy --help
mdy /path/to/file.md --pdf
```

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
uv tool run mdy /path/to/file.md --pdf
```
