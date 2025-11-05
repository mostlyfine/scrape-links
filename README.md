# Web Scraper to Markdown

A Python script that recursively crawls pages under a specified URL and saves the main content in Markdown format.

## Features

- **Recursive Link Collection**: Automatically explores pages under the specified URL
- **Depth Control**: Specify page hierarchy depth (0 to unlimited)
- **High-Quality Content Extraction**: 5-stage fallback (trafilatura → readability → newspaper3k → CSS selectors → body)
- **Configurable Extractors**: Customize extraction order with `-e` option
- **JavaScript Support**: Use `--selenium` to fetch rendered HTML after JavaScript execution
- **Markdown Conversion**: Converts HTML to GitHub Flavored Markdown
- **Domain-Based Organization**: Output is organized by domain directory
- **Flexible File Handling**: Overwrite by default; use `--skip-existing` to skip existing files
- **Rate Limiting**: Random delay (1-3 seconds) between requests to reduce server load

## Installation

### Prerequisites

- Python 3.11 or higher

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Using a Virtual Environment (Recommended)

It is strongly recommended to isolate dependencies using a virtual environment to avoid polluting your global Python installation and to ensure reproducible runs.

Create and activate a virtual environment:

```bash
# Create virtual environment in project root
python -m venv .venv

# Activate (macOS/Linux)
source .venv/bin/activate

# (Optional) Upgrade pip
pip install -U pip

# Install dependencies into the venv
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
.venv\\Scripts\\Activate.ps1
```

On Windows CMD:

```cmd
.venv\\Scripts\\activate.bat
```

Deactivate when finished:

```bash
deactivate
```

Run the script explicitly with the virtual environment interpreter (optional but explicit):

```bash
./.venv/bin/python scrape_links.py -d 1 -o saved_docs https://example.com/docs/
```

## Usage

### Using uvx (Recommended)

You can run this tool without installing it locally using `uvx`:

#### From Local Directory

```bash
# Fetch only the specified page (default: depth 0)
uvx --from . scrape-links https://example.com/docs/

# Depth 1 (immediate child pages)
uvx --from . scrape-links -d 1 https://example.com/docs/

# Save as Markdown to a custom directory
uvx --from . scrape-links -d 1 -o saved_docs https://example.com/docs/

# Fetch all child pages with verbose logging
uvx --from . scrape-links -d -1 -o -v https://example.com/docs/
```

#### From GitHub Repository

Run directly from GitHub without cloning:

```bash
# Run from GitHub repository (default: depth 0)
uvx --from git+https://github.com/mostlyfine/scrape-links scrape-links https://example.com/docs/

# With depth 1 and markdown output saved under "docs_dump"
uvx --from git+https://github.com/mostlyfine/scrape-links scrape-links -d 1 -o docs_dump https://example.com/docs/

# Verbose logging and unlimited depth
uvx --from git+https://github.com/mostlyfine/scrape-links scrape-links -d -1 -o -v https://example.com/docs/

# From specific branch (e.g., develop)
uvx --from git+https://github.com/mostlyfine/scrape-links@develop scrape-links https://example.com/docs/

# From specific commit
uvx --from git+https://github.com/mostlyfine/scrape-links@abc1234 scrape-links https://example.com/docs/
```

**Note**: `uvx` will automatically handle dependencies in an isolated environment. If you don't have `uvx` installed, you can install it via:

```bash
# Install uv (which includes uvx)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or via pip
pip install uv
```

### Basic Usage

```bash
# Fetch only the specified page (default: depth 0)
python scrape_links.py https://example.com/docs/

# Depth 1 (immediate child pages)
python scrape_links.py -d 1 https://example.com/docs/

# Fetch all child pages (unlimited)
python scrape_links.py -d -1 https://example.com/docs/
```

### Save as Markdown

```bash
# Save extracted pages as markdown into "saved_docs"
python scrape_links.py -d 1 -o saved_docs https://example.com/docs/

# Save with verbose logging (default output directory)
python scrape_links.py -d -1 -o -v https://example.com/docs/

# Skip existing files (default: overwrite)
python scrape_links.py -d 1 -o saved_docs -s https://example.com/docs/
```

`-o` オプションの引数を省略すると、既定の `output/` ディレクトリに保存されます。

### Customize Extractor Order

```bash
# Use newspaper3k first, then xpath
python scrape_links.py -d 1 -o saved_docs -e newspaper,xpath https://example.com/docs/

# Use only trafilatura and readability
python scrape_links.py -d 1 -o saved_docs -e trafilatura,readability https://example.com/docs/
```

Valid extractors: `trafilatura`, `newspaper`, `xpath`, `readability`
Default order: `trafilatura,readability,newspaper`

### Use Selenium for JavaScript-Rendered Pages

```bash
# Enable Selenium to fetch pages after JavaScript execution
python scrape_links.py --selenium -d 1 -o saved_docs https://example.com/docs/

# Combine with custom extractors
python scrape_links.py --selenium -d 1 -o saved_docs -e trafilatura,readability https://example.com/docs/
```

**Note**: Selenium requires Chrome/Chromium to be installed on your system. The script runs Chrome in headless mode.

## Options

| Option | Description |
|--------|-------------|
| `url` | Base URL to scrape (required) |
| `-d, --depth N` | Maximum depth (default: 0, -1 for unlimited) |
| `-o [DIR], --output [DIR]` | Save extracted pages as markdown under `DIR`; omit `DIR` to use the default `output/` |
| `-e EXTRACTORS, --extractors EXTRACTORS` | Comma-separated list of extractors (e.g., `newspaper,xpath`). Valid: `trafilatura`, `newspaper`, `xpath`, `readability`. Default: `trafilatura,readability,newspaper` |
| `-s, --skip-existing` | Skip saving files that already exist (default: overwrite existing files) |
| `--selenium` | Enable Selenium to fetch rendered HTML after JavaScript execution (requires Chrome/Chromium) |
| `-v, --verbose` | Show verbose logs |
| `-h, --help` | Show help message |

## Depth Specification

- **0** (default): Only the specified page
- **1**: Immediate child pages (e.g., `/docs/page1.html`)
- **2**: One more level down (e.g., `/docs/section/page2.html`)
- **-1**: Unlimited (all descendant pages)

## Output Format

### Directory Structure

```
output/
└── {domain}/
    └── {path}/
        └── {filename}.md
```

Example:
```
output/
└── docs.claude.com/
    └── ja/
        └── docs/
            └── claude-code/
                ├── overview.md
                ├── quickstart.md
                └── ...
```

### Markdown Files

Each file starts with a title and URL in this format:

```markdown
# [Page Title](URL)

Content...
```

## Content Extraction Algorithm

Content is extracted using a 5-stage fallback approach (prioritizing accuracy):

1. **trafilatura**: Fast and accurate text extraction with support for images and tables
2. **readability-lxml**: Heuristic-based extraction using machine learning
3. **newspaper3k**: Article parsing with NLP-enhanced text extraction
4. **CSS Selectors (xpath)**: Extract using common selectors (`main`, `article`, `#content`, etc.)
5. **body Element**: Use entire body element as final fallback

You can customize the extraction order using the `-e` option. The `body` fallback is always used when all other extractors fail and cannot be disabled.

### Rate Limiting

To reduce server load, the script automatically waits 1-3 seconds (random) between each request. This behavior is:
- **Always enabled**: No option to disable
- **Configurable**: Can be customized via `wait_before_request(max_delay)` function
- **Logged**: Use `-v` to see actual wait times

## Examples

### Running from GitHub (No Installation Required)

```bash
# Fetch a blog post
uvx --from git+https://github.com/mostlyfine/scrape-links scrape-links \
  -o blog_posts https://syu-m-5151.hatenablog.com/entry/2025/11/03/020316

# Fetch documentation site (depth 1)
uvx --from git+https://github.com/mostlyfine/scrape-links scrape-links \
  -d 1 -o docs_dump https://docs.example.com/
```

### Fetching Claude Code Documentation

```bash
# Overview page only
uvx --from git+https://github.com/mostlyfine/scrape-links scrape-links \
  https://docs.claude.com/en/docs/claude-code/overview

# All sections
uvx --from git+https://github.com/mostlyfine/scrape-links scrape-links \
  -d 1 -o claude_docs https://docs.claude.com/en/docs/claude-code/overview

# With verbose logging
uvx --from git+https://github.com/mostlyfine/scrape-links scrape-links \
  -d 1 -o -v https://docs.claude.com/en/docs/claude-code/overview
```

### Local Development

```bash
# Overview page only
python scrape_links.py https://docs.claude.com/en/docs/claude-code/overview

# All sections
python scrape_links.py -d 1 -o claude_docs https://docs.claude.com/en/docs/claude-code/overview

# With verbose logging
python scrape_links.py -d 1 -o -v https://docs.claude.com/en/docs/claude-code/overview
```

## Troubleshooting

### Unable to Fetch Pages

- Verify the URL is correct
- Check network connection
- Use `-v` option to view detailed logs

### Poor Markdown Quality

Content extraction is attempted in 5 stages (trafilatura → readability → newspaper3k → xpath → body). You can customize the extraction order using the `-e` option.

### File Handling

By default, the script overwrites existing files. To skip existing files, use the `--skip-existing` option:

```bash
python scrape_links.py -d 1 -o saved_docs --skip-existing https://example.com/docs/
```

To force overwrite all files, delete them first:

```bash
rm -rf output/
```

## License

MIT

## Contributing

Pull requests are welcome.
