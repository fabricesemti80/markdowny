# Markdowny CLI

`mdy` converts:

- Markdown -> DOCX
- Markdown -> PDF
- DOCX -> Markdown

## Requirements

- `uv`
- Pandoc available in `PATH`

## Install

From this repository root:

```bash
uv tool install --native-tls .
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
