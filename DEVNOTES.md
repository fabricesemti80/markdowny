# Developer Notes

This file contains development workflows intentionally kept out of `README.md`.

## Local Setup

1. Sync the project environment from lockfile:

```bash
uv sync --native-tls
```

2. Run the CLI from the project environment:

```bash
uv run --no-sync dfx --help
uv run --no-sync dfx -i test.md --pdf
```

## Lint

Run Ruff locally:

```bash
uv sync --extra lint
uv run --no-sync ruff check .
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

Clean virtual environment directory:

```bash
make clean
```

Note on `make convert`:

- The current `make convert` target still uses legacy positional CLI arguments.
- The current CLI expects `-i/--in` and `-o/--out` flags.
- Prefer direct `uv run` commands until the target is updated.

## Useful Conversion Commands

Markdown -> DOCX:

```bash
uv run --no-sync dfx -i doc.md --docx
```

Markdown -> PDF:

```bash
uv run --no-sync dfx -i doc.md --pdf
```

DOCX -> Markdown:

```bash
uv run --no-sync dfx -i doc.docx
```

Custom output path:

```bash
uv run --no-sync dfx -i doc.md -o out.pdf --pdf
```

## Notes

- `dfx` attempts to download a bundled Pandoc on first use if Pandoc is not in `PATH`.
- Mermaid rendering requires outbound HTTPS access to `https://mermaid.ink`.
- CI currently runs on Ubuntu and Windows, and linting is performed with Ruff.
