.PHONY: help init convert docker docker-build clean

help:
	@echo "Available targets:"
	@echo "  init        : Sync dependencies from uv.lock"
	@echo "  convert     : Convert between Markdown, DOCX, and PDF (auto-detects direction)"
	@echo "                MD to DOCX:  make convert INPUT=doc.md"
	@echo "                MD to PDF:   make convert INPUT=doc.md FORMAT=pdf"
	@echo "                DOCX to MD:  make convert INPUT=doc.docx"
	@echo "                With output: make convert INPUT=doc.md OUTPUT=out.docx"
	@echo "  docker      : Run via Docker (must run from dir containing files)"
	@echo "                make docker ARGS='-i doc.md -o out.docx'"
	@echo "  docker-build: Build the Docker image"
	@echo "  clean       : Remove virtual environment folder (.venv)"

init:
	@$(UV) sync --native-tls

convert:
	@if [ -z "$(INPUT)" ]; then \
		echo "INPUT is required. Example: make convert INPUT=doc.md [FORMAT=pdf] [OUTPUT=out.pdf]"; \
		exit 1; \
	fi
	@$(UV) run --no-sync mdy -i "$(INPUT)" $(if $(OUTPUT),-o "$(OUTPUT)",) $(if $(FORMAT),-f $(FORMAT),)

docker:
	@./docker-run.sh $(ARGS)

docker-build:
	@docker build -t mdy .

clean:
	@$(UV) run --no-sync python -c "import shutil; shutil.rmtree('.venv', ignore_errors=True)"
