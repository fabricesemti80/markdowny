# Changelog

All notable changes to this project will be documented in this file.

## [0.2.1] - 2025-03-12

### Added
- Docker support for Linux users (avoids dependency management)
- `--verbose` flag for detailed logging output
- Output path prompt in interactive mode with default suggestion
- Clean progress indicators for non‑verbose mode (docker‑compose style)

### Changed
- Improved non‑verbose output with visually appealing progress indicators
- README updated with visual decorations and Docker section

### Fixed
- Python version requirement corrected to 3.10+ in documentation

## [0.2.0] - 2025-03-05

### Added
- Tag trigger for CI workflow (runs on `v*` tags)
- CLI options: `-i`/`--in` for input, `-o`/`--out` for output, `-v`/`--version` for version
- Windows support in CI workflow
- Sample image to demo directory
- Uninstall script and documentation

### Fixed
- Release workflow now uses `--force` when fetching tags to avoid conflicts

## [0.1.0] - 2024

### Added
- Bidirectional conversion: Markdown ↔ DOCX, Markdown → PDF
- Mermaid diagram rendering to PNG images
- Support for tall Mermaid diagrams (split across pages in PDF)
- Multiple PDF engines: WeasyPrint (preferred), wkhtmltopdf (fallback), xhtml2pdf (last resort)
- Colored terminal output
- GitHub Actions workflows: CI, release, and version bumping
- Ruff linting integration
- Interactive mode with format selection

### Fixed
- YAML front matter handling
- Horizontal rule rendering
- Resource path resolution for images
- CI/CD workflow dependencies
