# Developer Notes

This file contains development workflows that are intentionally kept out of `README.md`.

## Local Setup

1. Sync project environment from lockfile:

```bash
uv sync --native-tls
```

2. Run CLI from project environment:

```bash
uv run --no-sync mdy --help
uv run --no-sync mdy test.md --pdf
```

## Make Targets

Show targets:

```bash
make help
```

Initialize dependencies:

```bash
make init
```

Convert examples:

```bash
make convert INPUT=doc.md
make convert INPUT=doc.md FORMAT=pdf
make convert INPUT=doc.docx
make convert INPUT=doc.md OUTPUT=out.docx
```

Clean virtual environment directory:

```bash
make clean
```

## Notes

- `FORMAT` is used by the Make target for Markdown input (`docx` or `pdf`).
- If `OUTPUT` is omitted, `mdy` infers a default output path.
- The CLI will attempt to download a bundled pandoc on first use if it's not
  already installed; running `uv tool install` today therefore no longer
  requires you to separately install pandoc for basic functionality.
