UV ?= uv

.PHONY: help init convert clean

help:
	@echo "Available targets:"
	@echo "  init    : Sync dependencies from uv.lock"
	@echo "  convert : Convert between Markdown, DOCX, and PDF (auto-detects direction)"
	@echo "            MD to DOCX:  make convert INPUT=doc.md"
	@echo "            MD to PDF:   make convert INPUT=doc.md FORMAT=pdf"
	@echo "            DOCX to MD:  make convert INPUT=doc.docx"
	@echo "            With output: make convert INPUT=doc.md OUTPUT=out.docx"
	@echo "  clean   : Remove virtual environment folder (.venv)"

init:
	@$(UV) sync --native-tls

convert:
	@if [ -z "$(INPUT)" ]; then \
		echo "INPUT is required. Example: make convert INPUT=doc.md [FORMAT=pdf] [OUTPUT=out.pdf]"; \
		exit 1; \
	fi
	@$(UV) run --no-sync dfx -i "$(INPUT)" $(if $(OUTPUT),-o "$(OUTPUT)",) $(if $(FORMAT),-f $(FORMAT),)

clean:
	@$(UV) run --no-sync python -c "import shutil; shutil.rmtree('.venv', ignore_errors=True)"
