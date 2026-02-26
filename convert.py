# Import necessary tools (libraries) to help us do the work
import argparse  # Helps us read commands from the terminal
import sys       # Helps us interact with the computer system (like exiting the program)
import os        # Helps us work with files and folders
import re        # Helps us match text patterns
import subprocess
import base64    # Helps us encode data for URLs
import tempfile  # Helps us create temporary files
import shutil    # Helps us copy files
from urllib.parse import unquote, urlparse
import requests  # Helps us make web requests (for Mermaid rendering)
import urllib3   # Used to suppress SSL warnings in corporate environments
import pypandoc  # The main tool that converts files (like a translator)
from xhtml2pdf import pisa  # Pure-Python HTML -> PDF fallback for Windows

# Suppress SSL warnings when verify=False (common in corporate proxy environments)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class _Style:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    RED = '\033[31m'


USE_COLOR = sys.stdout.isatty() and os.getenv('NO_COLOR') is None


def _paint(text, *styles):
    if not USE_COLOR:
        return text
    return ''.join(styles) + text + _Style.RESET


def log_info(message):
    print(f"{_paint('[INFO]', _Style.CYAN, _Style.BOLD)} {message}")


def log_warn(message):
    print(f"{_paint('[WARN]', _Style.YELLOW, _Style.BOLD)} {message}")


def log_error(message):
    print(f"{_paint('[ERROR]', _Style.RED, _Style.BOLD)} {message}")


def log_success(message):
    print(f"{_paint('[OK]', _Style.GREEN, _Style.BOLD)} {message}")


def log_step(message):
    print(f"{_paint('>>', _Style.BLUE, _Style.BOLD)} {message}")


def _is_windows_drive_path(path_value):
    """Returns True for paths like C:/... or C:\\..."""
    return bool(re.match(r'^[a-zA-Z]:[\\/]', path_value or ''))


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
        if parsed.scheme in ('http', 'https'):
            return uri

        if parsed.scheme == 'file':
            candidate = unquote(parsed.path or '')
            # Windows file URI can be /C:/path -> strip first slash
            if candidate.startswith('/') and re.match(r'^/[a-zA-Z]:', candidate):
                candidate = candidate[1:]
            if os.path.exists(candidate):
                return candidate

        raw = unquote(uri).replace('\\', os.sep)
        if _is_windows_drive_path(raw) and os.path.exists(raw):
            return raw

        if os.path.isabs(raw) and os.path.exists(raw):
            return raw

        rel_hint = unquote(rel or '')
        for base in [rel_hint, *normalized_search_paths]:
            if not base:
                continue
            candidate = os.path.abspath(os.path.join(base, raw))
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
            [weasyprint_exe, '--info'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10
        )
        return probe.returncode == 0
    except Exception:
        return False


def _convert_pdf_with_xhtml2pdf(content, output_file, resource_paths, resource_path_arg):
    """
    Fallback PDF generation:
    Markdown -> HTML (Pandoc), then HTML -> PDF (xhtml2pdf).
    """
    html = pypandoc.convert_text(
        content,
        'html',
        format='markdown',
        extra_args=[f'--resource-path={resource_path_arg}']
    )
    css = (
        "<style>"
        "body { font-family: Helvetica, Arial, sans-serif; font-size: 10px; }"
        "table { border-collapse: collapse; max-width: 100%; margin: 8px 0; }"
        "th, td { border: 1px solid #999; padding: 3px 5px; text-align: left;"
        " overflow: hidden; word-wrap: break-word; }"
        "th { background-color: #e9ecef; font-weight: bold; }"
        "</style>"
    )
    html = f"<html><head><meta charset='utf-8'>{css}</head><body>{html}</body></html>"
    callback = _make_xhtml2pdf_link_callback(resource_paths)
    with open(output_file, 'wb') as f:
        result = pisa.CreatePDF(src=html, dest=f, encoding='utf-8', link_callback=callback)
    if result.err:
        raise RuntimeError("xhtml2pdf failed to render the generated HTML to PDF.")


def strip_yaml_front_matter(text):
    """
    Removes YAML front matter (the block between --- markers at the top of a file)
    so that Pandoc doesn't choke on special YAML characters like * or &.
    Handles BOM, Windows line endings, and ... as closing delimiter.
    """
    # Remove BOM if present
    text = text.lstrip('\ufeff')
    # Match opening --- and closing --- or ... with flexible whitespace/line endings
    result = re.sub(r'\A---[ \t]*\r?\n.*?\r?\n(?:---|\.\.\.)[ \t]*\r?\n', '', text, count=1, flags=re.DOTALL)
    if result == text:
        log_warn("No YAML front matter detected to strip.")
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
    pattern = re.compile(r'```mermaid\s*\n(.*?)```', flags=re.DOTALL)
    matches = list(pattern.finditer(content))

    if not matches:
        return content

    # Use a local temp directory so Pandoc can always resolve the image paths
    diagrams_dir = os.path.join(temp_dir, 'mermaid_diagrams')
    os.makedirs(diagrams_dir, exist_ok=True)

    log_step(f"Found {len(matches)} Mermaid diagram(s), rendering to images...")

    for i, match in enumerate(reversed(matches), 1):
        diagram_code = match.group(1).strip()
        diagram_num = len(matches) - i + 1
        image_path = os.path.join(diagrams_dir, f'mermaid_{diagram_num}.png')

        try:
            # Encode the Mermaid code as base64 for the Mermaid Ink URL
            encoded = base64.urlsafe_b64encode(diagram_code.encode('utf-8')).decode('ascii')
            url = f'https://mermaid.ink/img/{encoded}'

            response = requests.get(url, timeout=30, verify=False)
            response.raise_for_status()

            with open(image_path, 'wb') as f:
                f.write(response.content)

            # Replace the code block with an image reference (use forward slashes for Pandoc)
            pandoc_path = image_path.replace('\\', '/')
            replacement = f'![Diagram {diagram_num}]({pandoc_path})'
            content = content[:match.start()] + replacement + content[match.end():]
            log_info(f"Rendered diagram {diagram_num} -> {image_path}")

        except Exception as e:
            log_warn(f"Failed to render diagram {diagram_num}: {e}")
            log_warn("The Mermaid code block will be kept as-is.")

    return content


def convert_md_to_output(input_file, output_file, output_format):
    """
    Converts a Markdown file to DOCX or PDF using pypandoc.
    output_format should be 'docx' or 'pdf'.
    """
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
        extra_args = [f'--resource-path={resource_path_arg}']

        # For PDF, try Pandoc + WeasyPrint first, then fall back to xhtml2pdf.
        use_weasyprint = False
        if output_format == 'pdf':
            venv_dir = os.path.dirname(os.path.abspath(sys.executable))
            weasyprint_exe = os.path.join(venv_dir, 'weasyprint.exe')
            if not os.path.exists(weasyprint_exe):
                weasyprint_exe = os.path.join(venv_dir, 'weasyprint')
            if _can_use_weasyprint(weasyprint_exe):
                extra_args.append(f'--pdf-engine={weasyprint_exe}')
                use_weasyprint = True
                log_info("PDF engine: WeasyPrint")
            else:
                log_info("PDF engine: xhtml2pdf fallback (WeasyPrint runtime unavailable)")
            extra_args.append('--metadata=title= ')

        # Read the file and replace standalone --- lines (horizontal rules)
        # with *** to prevent Pandoc from misinterpreting them as YAML blocks.
        with open(input_file, 'r', encoding='utf-8-sig') as f:
            content = f.read()
        content = strip_yaml_front_matter(content)
        content = re.sub(r'^---\s*$', '***', content, flags=re.MULTILINE)

        # Use a local temp directory for Mermaid images and Pandoc output
        # to avoid issues with UNC paths, spaces, and file locks.
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Render any Mermaid diagrams to PNG images in the temp directory
            content = render_mermaid_blocks(content, tmp_dir)

            # Write output to a local temp file first, then copy to final destination
            tmp_output = os.path.join(tmp_dir, f'output.{output_format}')
            if output_format != 'pdf':
                pypandoc.convert_text(content, output_format, format='markdown', outputfile=tmp_output, extra_args=extra_args)
            else:
                if use_weasyprint:
                    try:
                        pypandoc.convert_text(content, output_format, format='markdown', outputfile=tmp_output, extra_args=extra_args)
                    except Exception as pdf_error:
                        log_warn(f"Pandoc PDF engine failed ({pdf_error}).")
                        log_info("Falling back to xhtml2pdf (no native GTK dependencies required).")
                        fallback_paths = [tmp_dir, input_dir, cwd]
                        _convert_pdf_with_xhtml2pdf(content, tmp_output, fallback_paths, resource_path_arg)
                else:
                    fallback_paths = [tmp_dir, input_dir, cwd]
                    _convert_pdf_with_xhtml2pdf(content, tmp_output, fallback_paths, resource_path_arg)
            shutil.copy2(tmp_output, output_file)

        log_success(f"Converted '{input_file}' to '{output_file}'.")

    except OSError as e:
        log_error(f"Error during conversion: {e}")
        log_error("Make sure Pandoc is installed and available in your system path.")
        if output_format == 'pdf':
            log_info("PDF output uses WeasyPrint when available, otherwise xhtml2pdf fallback.")
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
        media_dir = os.path.join(output_dir, 'media')

        extra_args = [
            '--wrap=none',                          # Don't hard-wrap lines
            f'--extract-media={media_dir}',         # Save embedded images
        ]

        pypandoc.convert_file(input_file, 'markdown', outputfile=output_file, extra_args=extra_args)
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


def detect_direction(input_file, output_format='docx'):
    """
    Auto-detects the conversion direction based on the input file extension.
    For Markdown input, uses output_format to determine the output extension.
    Returns (direction, default_output).
    """
    ext = os.path.splitext(input_file)[1].lower()
    base = os.path.splitext(input_file)[0]
    if ext in ('.docx',):
        return 'docx2md', base + '.md'
    else:
        return 'md2out', base + '.' + output_format


def choose_output_format(default_format='docx'):
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
    if selected not in ('docx', 'pdf'):
        log_warn(f"Unknown format '{selected}', defaulting to '{default_format}'.")
        return default_format
    return selected


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert between Markdown, DOCX, and PDF (auto-detects direction).")
    parser.add_argument("input_file", nargs="?", help="Path to the input file (.md or .docx).")
    parser.add_argument("output_file", nargs="?", help="Path to the output file.")
    parser.add_argument("-f", "--format", choices=["docx", "pdf"], default=None,
                        help="Output format when converting from Markdown. If omitted, you will be prompted (default: docx).")

    args = parser.parse_args()

    input_file = args.input_file
    output_file = args.output_file
    output_format = args.format

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
        if ext not in ('.docx',):
            output_format = choose_output_format('docx')
        else:
            output_format = 'docx'

    # Auto-detect conversion direction
    direction, default_output = detect_direction(input_file, output_format)
    if direction == 'docx2md':
        direction_label = "DOCX -> Markdown"
    else:
        direction_label = f"Markdown -> {output_format.upper()}"
    log_step(f"Detected conversion: {direction_label}")

    # Ask for output file if not provided
    if not output_file:
        try:
            output_file = input(f"Enter output file path (default: {default_output}): ").strip()
            output_file = output_file.strip('"').strip("'")
        except KeyboardInterrupt:
            print()
            log_warn("Operation cancelled.")
            sys.exit(0)

        if not output_file:
            output_file = default_output

    # Run the appropriate conversion
    if direction == 'docx2md':
        convert_docx_to_md(input_file, output_file)
    else:
        convert_md_to_output(input_file, output_file, output_format)
