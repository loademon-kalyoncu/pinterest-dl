# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**pinterest-dl** is a Python CLI tool and library for scraping and downloading media (images and video streams) from Pinterest. It uses a reverse-engineered Pinterest API as the default scraping backend, with Selenium WebDriver as a fallback option for more reliability.

- **Language**: Python 3.10+
- **Main entry point**: `pinterest_dl/cli.py` via `pinterest-dl` or `pin-dl` command
- **Current version**: Defined in `pinterest_dl/__init__.py`

## Common Commands

### Development Setup
```bash
pip install .
```

### Run CLI
```bash
# Login to save cookies for private boards
pinterest-dl login -o cookies.json

# Scrape and download from a URL
pinterest-dl scrape "https://www.pinterest.com/pin/123456/" -o output -n 30

# Search by query
pinterest-dl search "art" -o output -n 30

# Download from cached JSON
pinterest-dl download cache.json -o output
```

### Testing
- **Note**: Testing is not yet implemented (see Known Issues in README)

## Architecture

### Client Modes

The tool supports two scraping backends:

1. **API Mode** (default, `--client api`): Uses reverse-engineered Pinterest API endpoints
   - Faster and more efficient
   - Implemented in `low_level/api/pinterest_api.py` with `_ScraperAPI` wrapper
   - Supports search functionality

2. **WebDriver Mode** (`--client chrome|firefox`): Uses Selenium automation
   - Slower but more reliable for edge cases
   - Implemented in `low_level/webdriver/` with `_ScraperWebDriver` wrapper
   - Requires Chrome or Firefox browser

### Core Components

- **`pinterest_dl/__init__.py`**: Main `PinterestDL` class that provides static factory methods:
  - `PinterestDL.with_api()` → returns `_ScraperAPI`
  - `PinterestDL.with_browser()` → returns `_ScraperWebdriver`

- **`pinterest_dl/cli.py`**: Command-line interface with four main commands:
  - `login`: Authenticate and save cookies
  - `scrape`: Scrape from Pinterest URLs
  - `search`: Search Pinterest by query
  - `download`: Download from cached JSON

- **`pinterest_dl/scrapers/`**: Scraper implementations
  - `scraper_base.py`: Base class with shared download, caption, and pruning utilities
  - `scraper_api.py`: API-based scraper (`_ScraperAPI`)
  - `scraper_webdriver.py`: WebDriver-based scraper (`_ScraperWebdriver`)

- **`pinterest_dl/low_level/api/`**: Pinterest API interaction
  - `pinterest_api.py`: Core API client (`PinterestAPI` class)
  - `endpoints.py`: API endpoint definitions
  - `pinterest_response.py`: Response parsing (`PinResponse` class)
  - `bookmark_manager.py`: Manages pagination bookmarks

- **`pinterest_dl/low_level/http/`**: HTTP and media downloading
  - `downloader.py`: Concurrent media downloader
  - `http_client.py`: HTTP utilities
  - `request_builder.py`: URL/request construction

- **`pinterest_dl/low_level/hls/`**: Video stream processing
  - `hls_processor.py`: HLS video stream downloader (requires ffmpeg)

- **`pinterest_dl/low_level/webdriver/`**: Selenium automation
  - `browser.py`: WebDriver initialization
  - `pinterest_driver.py`: Pinterest-specific automation
  - `driver_installer.py`: Auto-install WebDriver binaries

- **`pinterest_dl/data_model/`**: Data structures
  - `pinterest_media.py`: `PinterestMedia` class representing scraped media
  - `cookie.py`: Cookie handling (`PinterestCookieJar`)

### Data Flow

1. **Scraping**: URL → API/WebDriver → `PinterestMedia` objects
2. **Download**: `PinterestMedia` list → concurrent downloads → local files
3. **Post-processing**: Prune by resolution, add captions (txt/json/metadata)

### Key Features

- **Caption support**: Alt text can be saved as separate files (`.txt`, `.json`) or embedded as EXIF metadata
- **Cookie support**: Use `--cookies` flag to access private boards/pins
- **Video streams**: Download HLS streams with `--video` flag (requires ffmpeg in PATH)
- **Pagination**: Uses Pinterest's bookmark system for batch scraping
- **Resolution filtering**: `--resolution WxH` to filter images by minimum dimensions

## Important Notes

- **Private content**: Requires cookies obtained via `pinterest-dl login` command
- **Rate limiting**: Use `--delay` to control request timing (default 0.2s)
- **Batch size**: API requests limited to 50 items per request internally
- **Video downloads**: Require `ffmpeg` in PATH, only available in API mode
- **Caption from title**: Use `--cap-from-title` to use image title as caption instead of alt text
