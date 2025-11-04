# Web Scraper to Markdown

A Python script that recursively crawls pages under a specified URL and saves the main content in Markdown format.

## Features

- **Recursive Link Collection**: Automatically explores pages under the specified URL
- **Depth Control**: Specify page hierarchy depth (0 to unlimited)
- **High-Quality Content Extraction**: 3-stage fallback using XPath, readability, and body
- **Markdown Conversion**: Converts HTML to GitHub Flavored Markdown
- **Domain-Based Organization**: Output is organized by domain directory
- **Incremental Execution**: Existing files are automatically skipped

## Installation

### Prerequisites

- Python 3.7 or higher

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
./.venv/bin/python scrape_links.py -d 1 -o https://example.com/docs/
```

## Usage

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
# Save extracted pages as markdown
python scrape_links.py -d 1 -o https://example.com/docs/

# Save with verbose logging
python scrape_links.py -d -1 -o -v https://example.com/docs/
```

## Options

| Option | Description |
|--------|-------------|
| `url` | Base URL to scrape (required) |
| `-d, --depth N` | Maximum depth (default: 0, -1 for unlimited) |
| `-o, --output` | Save extracted pages as markdown |
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

Content is extracted using a 3-stage fallback approach:

1. **XPath Extraction**: Extract using common selectors (`main`, `article`, `#content`, etc.)
2. **readability**: Automatic extraction using readability-lxml
3. **body Element**: Use entire body element as final fallback

## Examples

### Fetching Claude Code Documentation

```bash
# Overview page only
python scrape_links.py https://docs.claude.com/en/docs/claude-code/overview

# All sections
python scrape_links.py -d 1 -o https://docs.claude.com/en/docs/claude-code/overview

# With verbose logging
python scrape_links.py -d 1 -o -v https://docs.claude.com/en/docs/claude-code/overview
```

## Troubleshooting

### Unable to Fetch Pages

- Verify the URL is correct
- Check network connection
- Use `-v` option to view detailed logs

### Poor Markdown Quality

Content extraction is attempted in 3 stages. If XPath extraction fails, it falls back to readability.

### Overwrite Existing Files

The current implementation automatically skips existing files. To overwrite, delete them first:

```bash
rm -rf output/
```

## License

MIT

## Contributing

Pull requests are welcome.
