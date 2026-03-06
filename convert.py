__version__ = "1.0.0"
import argparse  # Helps us read commands from the terminal
import sys  # Helps us interact with the computer system (like exiting the program)
import os  # Helps us work with files and folders
import re  # Helps us match text patterns
import subprocess
import base64  # Helps us encode data for URLs
import tempfile  # Helps us create temporary files
import shutil  # Helps us copy files
from urllib.parse import unquote, urlparse
import requests  # Helps us make web requests (for Mermaid rendering)
import urllib3  # Used to suppress SSL warnings in corporate environments
import pypandoc  # The main tool that converts files (like a translator)

try:
    from PIL import Image
except Exception:
    Image = None
try:
    from xhtml2pdf import pisa  # Optional PDF fallback
except Exception:
    pisa = None

# Set MDY_INSECURE_TLS=1 to opt in to disabling SSL verification (e.g. corporate proxy).
# Default is secure (verify=True). Warnings are suppressed only when explicitly opted in.
_INSECURE_TLS = os.getenv("MDY_INSECURE_TLS") == "1"
if _INSECURE_TLS:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_MAX_MERMAID_DIAGRAM_BYTES = (
    4096  # 4 KB — generous for diagram syntax, safe for URL encoding
)


class _Style:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"


def _init_color():
    """Determine whether to emit ANSI colours and, on Windows, enable VT100 mode."""
    if os.getenv("NO_COLOR") is not None or not sys.stdout.isatty():
        return False
    if sys.platform == "win32":
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32
            # STD_OUTPUT_HANDLE = -11, ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            return False
    return True


USE_COLOR = _init_color()
VERBOSE = False


def _paint(text, *styles):
    if not USE_COLOR:
        return text
    return "".join(styles) + text + _Style.RESET


def log_info(message):
    if not USE_COLOR:
        print(message)
    else:
        print(f"{_paint('[INFO]', _Style.CYAN, _Style.BOLD)} {message}")


def log_warn(message):
    if not USE_COLOR:
        print(f"WARNING: {message}")
    else:
        print(f"{_paint('[WARN]', _Style.YELLOW, _Style.BOLD)} {message}")


def log_error(message):
    if not USE_COLOR:
        print(f"ERROR: {message}")
    else:
        print(f"{_paint('[ERROR]', _Style.RED, _Style.BOLD)} {message}")


def log_success(message):
    if VERBOSE:
        if not USE_COLOR:
            print(message)
        else:
            print(f"{_paint('[OK]', _Style.GREEN, _Style.BOLD)} {message}")
    else:
        print(f"{_paint('✓', _Style.GREEN, _Style.BOLD)} {message}")


def log_step(message):
    if VERBOSE:
        if not USE_COLOR:
            print(f">> {message}")
        else:
            print(f"{_paint('>>', _Style.BLUE, _Style.BOLD)} {message}")
    else:
        print(f"{_paint('>', _Style.CYAN, _Style.BOLD)} {message}")


def _is_windows_drive_path(path_value):
    """Returns True for paths like C:/... or C:\\..."""
    return bool(re.match(r"^[a-zA-Z]:[\\/]", path_value or ""))


def _make_xhtml2pdf_link_callback(search_paths):
    """
    Resolves local image/file references for xhtml2pdf.
    Keeps HTTP(S) URIs untouched and maps local/relative paths to filesystem paths.
    """
    normalized_search_paths = [os.path.abspath(p) for p in search_paths if p]

    def link_callback(uri, rel):
        if not uri:
            return uri

        parsed = urlparse(uri)
        if parsed.scheme in ("http", "https"):
            return uri

        if parsed.scheme == "file":
            candidate = unquote(parsed.path or "")
            # Windows file URI can be /C:/path -> strip first slash
            if candidate.startswith("/") and re.match(r"^/[a-zA-Z]:", candidate):
                candidate = candidate[1:]
            if os.path.exists(candidate):
                return candidate

        raw = unquote(uri).replace("\\", os.sep)
        if _is_windows_drive_path(raw) and os.path.exists(raw):
            return raw

        if os.path.isabs(raw) and os.path.exists(raw):
            return raw

        rel_hint = unquote(rel or "")
        for base in [rel_hint, *normalized_search_paths]:
            if not base:
                continue
            base_abs = os.path.abspath(base)
            base_dir = (
                base_abs if os.path.isdir(base_abs) else os.path.dirname(base_abs)
            )
            if not base_dir:
                continue
            candidate = os.path.abspath(os.path.join(base_dir, raw))
            # Prevent path traversal: resolved path must stay within the base directory.
            try:
                common = os.path.commonpath([candidate, base_dir])
            except ValueError:
                continue  # Different drives on Windows — skip.
            if common != base_dir:
                continue
            if os.path.exists(candidate):
                return candidate

        # Let xhtml2pdf handle unknown URIs as-is.
        return uri

    return link_callback


def _can_use_weasyprint(weasyprint_exe):
    """
    Returns True if the configured WeasyPrint executable is callable.
    This avoids noisy Pandoc failures when GTK runtime libs are missing.
    """
    if not weasyprint_exe or not os.path.exists(weasyprint_exe):
        return False
    try:
        probe = subprocess.run(
            [weasyprint_exe, "--info"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
        )
        return probe.returncode == 0
    except Exception:
        return False


def _can_use_wkhtmltopdf():
    """Returns True if wkhtmltopdf is available in PATH."""
    return shutil.which("wkhtmltopdf") is not None


def _normalize_markdown_tables_for_xhtml2pdf(md_text):
    """
    xhtml2pdf handles inline code in Markdown tables poorly.
    Strip backticks in table rows so content can wrap inside cells.
    """
    normalized_lines = []
    for line in md_text.splitlines():
        stripped = line.strip()
        is_table_row = stripped.startswith("|") and stripped.endswith("|")
        is_table_sep = bool(re.match(r"^\|[\s:\-|\t]+\|$", stripped))
        if is_table_row and not is_table_sep:
            line = re.sub(r"`([^`]+)`", r"\1", line)
        normalized_lines.append(line)
    return "\n".join(normalized_lines)


def _convert_pdf_with_wkhtmltopdf(content, output_file, resource_path_arg):
    """
    Fallback PDF generation:
    Markdown -> HTML (Pandoc), then HTML -> PDF (wkhtmltopdf).
    """
    html = pypandoc.convert_text(
        content,
        "html",
        format="markdown",
        extra_args=[f"--resource-path={resource_path_arg}"],
    )
    css = (
        "<style>"
        "body { font-family: Arial, Helvetica, sans-serif; font-size: 11px; }"
        "table { border-collapse: collapse; width: 100%; table-layout: fixed; }"
        "th, td { border: 1px solid #999; padding: 4px 6px; vertical-align: top;"
        " white-space: normal; word-wrap: break-word; overflow-wrap: anywhere; }"
        "img { max-width: 100%; height: auto; page-break-inside: avoid; }"
        "code { white-space: normal; word-break: break-word; overflow-wrap: anywhere; }"
        "th { background-color: #e9ecef; font-weight: bold; }"
        "</style>"
    )
    html = f"<html><head><meta charset='utf-8'>{css}</head><body>{html}</body></html>"
    with tempfile.NamedTemporaryFile(
        "w", suffix=".html", delete=False, encoding="utf-8"
    ) as tmp_html:
        tmp_html.write(html)
        tmp_html_path = tmp_html.name

    try:
        result = subprocess.run(
            ["wkhtmltopdf", "--enable-local-file-access", tmp_html_path, output_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=90,
        )
        if result.returncode != 0:
            details = (result.stderr or result.stdout or "").strip()
            raise RuntimeError(details or "wkhtmltopdf failed")
    finally:
        try:
            os.remove(tmp_html_path)
        except OSError:
            pass


def _convert_pdf_with_xhtml2pdf(
    content, output_file, resource_paths, resource_path_arg
):
    """
    Fallback PDF generation:
    Markdown -> HTML (Pandoc), then HTML -> PDF (xhtml2pdf).
    """
    if pisa is None:
        raise RuntimeError(
            "xhtml2pdf fallback is not installed. Install with: uv tool install --native-tls '.[pdf-fallback]'"
        )
    safe_content = _normalize_markdown_tables_for_xhtml2pdf(content)
    html = pypandoc.convert_text(
        safe_content,
        "html",
        format="markdown",
        extra_args=[f"--resource-path={resource_path_arg}"],
    )
    css = (
        "<style>"
        "body { font-family: Helvetica, Arial, sans-serif; font-size: 10px; }"
        "table { border-collapse: collapse; width: 100%; table-layout: fixed; margin: 8px 0; }"
        "th, td { border: 1px solid #999; padding: 3px 5px; text-align: left;"
        " vertical-align: top; white-space: normal; overflow: hidden;"
        " word-wrap: break-word; overflow-wrap: anywhere; word-break: break-word; }"
        "img { max-width: 100%; height: auto; }"
        "code { white-space: normal; overflow-wrap: anywhere; word-break: break-word; }"
        "tr { page-break-inside: avoid; }"
        "th { background-color: #e9ecef; font-weight: bold; }"
        "</style>"
    )
    html = f"<html><head><meta charset='utf-8'>{css}</head><body>{html}</body></html>"
    callback = _make_xhtml2pdf_link_callback(resource_paths)
    with open(output_file, "wb") as f:
        result = pisa.CreatePDF(
            src=html, dest=f, encoding="utf-8", link_callback=callback
        )
    if result.err:
        raise RuntimeError("xhtml2pdf failed to render the generated HTML to PDF.")


def strip_yaml_front_matter(text):
    """
    Removes YAML front matter (the block between --- markers at the top of a file)
    so that Pandoc doesn't choke on special YAML characters like * or &.
    Handles BOM, Windows line endings, and ... as closing delimiter.
    """
    # Remove BOM if present
    text = text.lstrip("\ufeff")
    # Match opening --- and closing --- or ... with flexible whitespace/line endings
    result = re.sub(
        r"\A---[ \t]*\r?\n.*?\r?\n(?:---|\.\.\.)[ \t]*\r?\n",
        "",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if result == text:
        if VERBOSE:
            log_step("No YAML front matter detected; nothing to strip.")
    else:
        log_info("YAML front matter was stripped before conversion.")
    return result


def render_mermaid_blocks(content, temp_dir):
    """
    Finds all ```mermaid code blocks in the Markdown content,
    renders each one to a PNG image using the Mermaid Ink service,
    and replaces the code block with a Markdown image reference.
    Images are saved to a local temp directory to avoid UNC path issues with Pandoc.
    """
    # Pattern to match ```mermaid ... ``` blocks
    pattern = re.compile(r"```mermaid\s*\n(.*?)```", flags=re.DOTALL)
    matches = list(pattern.finditer(content))

    if not matches:
        return content

    # Use a local temp directory so Pandoc can always resolve the image paths
    diagrams_dir = os.path.join(temp_dir, "mermaid_diagrams")
    os.makedirs(diagrams_dir, exist_ok=True)

    log_step(f"Found {len(matches)} Mermaid diagram(s), rendering to images...")

    def split_tall_image_if_needed(source_path, base_name, max_chunk_height=1400):
        """
        Word cannot split a single oversized image across pages reliably.
        If Mermaid output is very tall, split into stacked PNG chunks.
        """
        if Image is None:
            log_warn(
                "Pillow is not installed; skipping Mermaid image splitting for long diagrams."
            )
            return [source_path]
        with Image.open(source_path) as img:
            width, height = img.size
            if height <= max_chunk_height:
                return [source_path]

            chunk_paths = []
            top = 0
            part = 1
            while top < height:
                bottom = min(top + max_chunk_height, height)
                chunk = img.crop((0, top, width, bottom))
                chunk_path = os.path.join(diagrams_dir, f"{base_name}_part{part}.png")
                chunk.save(chunk_path)
                chunk_paths.append(chunk_path)
                top = bottom
                part += 1
            return chunk_paths

    for i, match in enumerate(reversed(matches), 1):
        diagram_code = match.group(1).strip()
        diagram_num = len(matches) - i + 1
        image_path = os.path.join(diagrams_dir, f"mermaid_{diagram_num}.png")

        if len(diagram_code.encode("utf-8")) > _MAX_MERMAID_DIAGRAM_BYTES:
            log_warn(
                f"Diagram {diagram_num} exceeds {_MAX_MERMAID_DIAGRAM_BYTES} bytes; "
                "skipping mermaid.ink render (block kept as-is)."
            )
            continue

        try:
            # Encode the Mermaid code as base64 for the Mermaid Ink URL
            encoded = base64.urlsafe_b64encode(diagram_code.encode("utf-8")).decode(
                "ascii"
            )
            url = f"https://mermaid.ink/img/{encoded}"

            response = requests.get(url, timeout=30, verify=not _INSECURE_TLS)
            response.raise_for_status()

            with open(image_path, "wb") as f:
                f.write(response.content)

            chunk_paths = split_tall_image_if_needed(
                image_path, f"mermaid_{diagram_num}"
            )
            refs = []
            for idx, chunk_path in enumerate(chunk_paths, 1):
                pandoc_path = chunk_path.replace("\\", "/")
                if len(chunk_paths) == 1:
                    refs.append(
                        f"![Diagram {diagram_num}]({pandoc_path}){{ width=95% }}"
                    )
                else:
                    refs.append(
                        f"![Diagram {diagram_num} ({idx}/{len(chunk_paths)})]({pandoc_path}){{ width=95% }}"
                    )
            replacement = "\n\n".join(refs)
            content = content[: match.start()] + replacement + content[match.end() :]
            log_info(f"Rendered diagram {diagram_num} -> {image_path}")

        except Exception as e:
            log_warn(f"Failed to render diagram {diagram_num}: {e}")
            log_warn("The Mermaid code block will be kept as-is.")

    return content


def _ensure_pandoc_available():
    """Ensure that a pandoc binary is accessible.

    pypandoc normally requires an external pandoc installation. When the
    converter runs inside a fresh environment (such as via ``uv tool install``)
    the binary may not yet be present. If pandoc cannot be found we trigger
    ``pypandoc.download_pandoc()`` which grabs a self-contained copy into
    ``~/.pypandoc`` and updates the internal path so subsequent calls work.

    This makes ``uv tool install`` effectively boot‑strap pandoc for the user
    without requiring a separate system package. The feature is opt‑out when a
    real pandoc already exists in ``PATH`` (preferred for production workloads).
    """
    try:
        # ``get_pandoc_version`` will raise ``OSError`` if no binary is found.
        pypandoc.get_pandoc_version()
    except OSError:
        log_warn("Pandoc not found in PATH; attempting to download via pypandoc...")
        try:
            pypandoc.download_pandoc()
            # After downloading, pypandoc will update its internal path; verify.
            version = pypandoc.get_pandoc_version()
            log_info(f"Successfully downloaded pandoc {version}.")
        except Exception:
            log_error(
                "Automatic pandoc download failed. "
                "Please install pandoc manually and ensure it is on your PATH."
            )
            # re‑raise to keep original behaviour (exit with failure)
            raise


def convert_md_to_output(input_file, output_file, output_format):
    """
    Converts a Markdown file to DOCX or PDF using pypandoc.
    output_format should be 'docx' or 'pdf'.
    """
    # make sure pandoc exists or download a bundled copy; see _ensure_pandoc_available
    _ensure_pandoc_available()

    if not os.path.exists(input_file):
        log_error(f"Input file '{input_file}' not found.")
        sys.exit(1)

    try:
        log_step(f"Starting conversion: Markdown -> {output_format.upper()}")
        log_info(f"Input: {input_file}")
        log_info(f"Output: {output_file}")
        input_dir = os.path.dirname(os.path.abspath(input_file))
        cwd = os.getcwd()
        resource_path_arg = os.pathsep.join([input_dir, cwd])
        extra_args = [f"--resource-path={resource_path_arg}"]

        # For PDF, prefer WeasyPrint, then wkhtmltopdf, then Pandoc default, then xhtml2pdf.
        use_weasyprint = False
        use_wkhtmltopdf = False
        use_pandoc_default_pdf = False
        if output_format == "pdf":
            venv_dir = os.path.dirname(os.path.abspath(sys.executable))
            weasyprint_exe = os.path.join(venv_dir, "weasyprint.exe")
            if not os.path.exists(weasyprint_exe):
                weasyprint_exe = os.path.join(venv_dir, "weasyprint")
            if _can_use_weasyprint(weasyprint_exe):
                extra_args.append(f"--pdf-engine={weasyprint_exe}")
                use_weasyprint = True
                log_info("PDF engine: WeasyPrint")
            elif _can_use_wkhtmltopdf():
                use_wkhtmltopdf = True
                log_info(
                    "PDF engine: wkhtmltopdf fallback (WeasyPrint runtime unavailable)"
                )
            else:
                use_pandoc_default_pdf = True
                log_info(
                    "PDF engine: Pandoc default fallback (WeasyPrint runtime unavailable)"
                )
            extra_args.append("--metadata=title= ")

        # Read the file and replace standalone --- lines (horizontal rules)
        # with *** to prevent Pandoc from misinterpreting them as YAML blocks.
        with open(input_file, "r", encoding="utf-8-sig") as f:
            content = f.read()
        content = strip_yaml_front_matter(content)
        content = re.sub(r"^---\s*$", "***", content, flags=re.MULTILINE)
        content = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"![](\2)", content)

        # Use a local temp directory for Mermaid images and Pandoc output
        # to avoid issues with UNC paths, spaces, and file locks.
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Render any Mermaid diagrams to PNG images in the temp directory
            content = render_mermaid_blocks(content, tmp_dir)

            # Write output to a local temp file first, then copy to final destination
            tmp_output = os.path.join(tmp_dir, f"output.{output_format}")
            if output_format != "pdf":
                pypandoc.convert_text(
                    content,
                    output_format,
                    format="markdown",
                    outputfile=tmp_output,
                    extra_args=extra_args,
                )
            else:
                if use_weasyprint:
                    try:
                        pypandoc.convert_text(
                            content,
                            output_format,
                            format="markdown",
                            outputfile=tmp_output,
                            extra_args=extra_args,
                        )
                    except Exception as pdf_error:
                        log_warn(f"Pandoc PDF engine failed ({pdf_error}).")
                        if _can_use_wkhtmltopdf():
                            log_info("Falling back to wkhtmltopdf.")
                            _convert_pdf_with_wkhtmltopdf(
                                content, tmp_output, resource_path_arg
                            )
                        else:
                            log_warn(
                                "Falling back to xhtml2pdf. Complex tables may render poorly."
                            )
                            fallback_paths = [tmp_dir, input_dir, cwd]
                            _convert_pdf_with_xhtml2pdf(
                                content, tmp_output, fallback_paths, resource_path_arg
                            )
                elif use_wkhtmltopdf:
                    _convert_pdf_with_wkhtmltopdf(
                        content, tmp_output, resource_path_arg
                    )
                elif use_pandoc_default_pdf:
                    try:
                        pandoc_default_args = [
                            f"--resource-path={resource_path_arg}",
                            "--metadata=title= ",
                        ]
                        pypandoc.convert_text(
                            content,
                            output_format,
                            format="markdown",
                            outputfile=tmp_output,
                            extra_args=pandoc_default_args,
                        )
                    except Exception as pdf_error:
                        log_warn(f"Pandoc default PDF engine failed ({pdf_error}).")
                        log_warn(
                            "Falling back to xhtml2pdf. Complex tables may render poorly."
                        )
                        fallback_paths = [tmp_dir, input_dir, cwd]
                        _convert_pdf_with_xhtml2pdf(
                            content, tmp_output, fallback_paths, resource_path_arg
                        )
                else:
                    log_warn(
                        "Using xhtml2pdf fallback. Complex tables may render poorly."
                    )
                    fallback_paths = [tmp_dir, input_dir, cwd]
                    _convert_pdf_with_xhtml2pdf(
                        content, tmp_output, fallback_paths, resource_path_arg
                    )
            shutil.copy2(tmp_output, output_file)

        log_success(f"Converted '{input_file}' to '{output_file}'.")

    except OSError as e:
        log_error(f"Error during conversion: {e}")
        log_error("Make sure Pandoc is installed and available in your system path.")
        if output_format == "pdf":
            log_info(
                "PDF output prefers WeasyPrint/wkhtmltopdf, then falls back to xhtml2pdf."
            )
        sys.exit(1)
    except Exception as e:
        log_error(f"An unexpected error occurred: {e}")
        sys.exit(1)


def convert_docx_to_md(input_file, output_file):
    """
    Converts a DOCX file to a Markdown file using pypandoc.
    """
    if not os.path.exists(input_file):
        log_error(f"Input file '{input_file}' not found.")
        sys.exit(1)

    try:
        log_step("Starting conversion: DOCX -> Markdown")
        log_info(f"Input: {input_file}")
        log_info(f"Output: {output_file}")
        # Extract images into a subfolder next to the output file
        output_dir = os.path.dirname(os.path.abspath(output_file))
        media_dir = os.path.join(output_dir, "media")

        extra_args = [
            "--wrap=none",  # Don't hard-wrap lines
            f"--extract-media={media_dir}",  # Save embedded images
        ]

        pypandoc.convert_file(
            input_file, "markdown", outputfile=output_file, extra_args=extra_args
        )
        log_success(f"Converted '{input_file}' to '{output_file}'.")
        if os.path.isdir(media_dir):
            log_info(f"Extracted images saved to '{media_dir}'.")

    except OSError as e:
        log_error(f"Error during conversion: {e}")
        log_error("Make sure Pandoc is installed and available in your system path.")
        sys.exit(1)
    except Exception as e:
        log_error(f"An unexpected error occurred: {e}")
        sys.exit(1)


def detect_direction(input_file, output_format="docx"):
    """
    Auto-detects the conversion direction based on the input file extension.
    For Markdown input, uses output_format to determine the output extension.
    Returns (direction, default_output).
    """
    ext = os.path.splitext(input_file)[1].lower()
    base = os.path.splitext(input_file)[0]
    if ext in (".docx",):
        return "docx2md", base + ".md"
    else:
        return "md2out", base + "." + output_format


def choose_output_format(default_format="docx"):
    """
    Prompts for output format when Markdown is the input and no format was provided.
    Falls back to default_format on empty input, Ctrl+C, or EOF.
    """
    prompt = f"Choose output format [docx/pdf] (default: {default_format}): "
    try:
        selected = input(prompt).strip().lower()
    except KeyboardInterrupt:
        print()
        log_warn("Operation cancelled.")
        sys.exit(0)
    except EOFError:
        log_warn(f"No interactive input available; defaulting to '{default_format}'.")
        return default_format

    if not selected:
        return default_format
    if selected not in ("docx", "pdf"):
        log_warn(f"Unknown format '{selected}', defaulting to '{default_format}'.")
        return default_format
    return selected


def choose_output_path(default_output):
    """
    Prompts for output path confirmation when in interactive mode.
    Returns the output path (either default or user-provided).
    Falls back to default_output on empty input, Ctrl+C, or EOF.
    """
    prompt = f"Output file (default: {default_output}): "
    try:
        selected = input(prompt).strip()
    except KeyboardInterrupt:
        print()
        log_warn("Operation cancelled.")
        sys.exit(0)
    except EOFError:
        log_warn(f"No interactive input available; using default '{default_output}'.")
        return default_output

    if not selected:
        return default_output
    return selected


def main():
    parser = argparse.ArgumentParser(
        description="Convert between Markdown, DOCX, and PDF (auto-detects direction)."
    )
    parser.add_argument(
        "-i",
        "--in",
        dest="input_file",
        help="Path to the input file (.md or .docx).",
    )
    parser.add_argument(
        "-o",
        "--out",
        dest="output_file",
        help="Path to the output file.",
    )
    parser.add_argument(
        "-f",
        "--format",
        choices=["docx", "pdf"],
        default=None,
        help="Output format when converting from Markdown. If omitted, you will be prompted (default: docx).",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Shortcut for '--format pdf' when converting from Markdown.",
    )
    parser.add_argument(
        "--docx",
        action="store_true",
        help="Shortcut for '--format docx' when converting from Markdown.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output with detailed logs.",
    )

    args = parser.parse_args()

    global VERBOSE
    VERBOSE = args.verbose

    input_file = args.input_file
    output_file = args.output_file
    output_format = args.format

    if args.pdf and args.docx:
        parser.error("Use only one of '--pdf' or '--docx'.")
    if output_format and (args.pdf or args.docx):
        parser.error("Use either '--format' or '--pdf/--docx', not both.")
    if args.pdf:
        output_format = "pdf"
    elif args.docx:
        output_format = "docx"

    # Interactive mode: ask for input file if not provided
    if not input_file:
        try:
            input_file = input("Enter input file path (.md or .docx): ").strip()
            input_file = input_file.strip('"').strip("'")
        except KeyboardInterrupt:
            print()
            log_warn("Operation cancelled.")
            sys.exit(0)

    if not input_file:
        log_error("Input file is required.")
        sys.exit(1)

    # If no format is provided for Markdown input, ask the user (default docx).
    if output_format is None:
        ext = os.path.splitext(input_file)[1].lower()
        if ext not in (".docx",):
            output_format = choose_output_format("docx")
        else:
            output_format = "docx"

    # Auto-detect conversion direction
    direction, default_output = detect_direction(input_file, output_format)
    if direction == "docx2md":
        direction_label = "DOCX -> Markdown"
    else:
        direction_label = f"Markdown -> {output_format.upper()}"
    log_step(f"Detected conversion: {direction_label}")

    # Prompt for output path if not provided via CLI
    if not output_file:
        output_file = choose_output_path(default_output)
        if output_file != default_output:
            log_info(f"Using output path: {output_file}")

    # Run the appropriate conversion
    if direction == "docx2md":
        convert_docx_to_md(input_file, output_file)
    else:
        convert_md_to_output(input_file, output_file, output_format)
    return 0


if __name__ == "__main__":
    sys.exit(main())
