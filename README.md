# 🎟️ Eventus Publicus

**Eventus Publicus** is your personal local event curator. 

Event websites can be slow, cluttered, and frustrating to browse. This tool is a simple and personal assistant designed to help you find local events quickly. It gathers events, filters out what you don't like, sorts them neatly, and puts everything onto **one clean page** (in Markdown and HTML formats) saved directly to your Downloads folder.

🌍 *Note: Currently, Eventus Publicus supports **Eventbrite** as its primary event provider.*

> ⚠️ **A Friendly Note on Usage:** 
> Eventus Publicus is built for **personal, reasonable use only** (such as finding something fun to do in your city this weekend). Please do not use this tool for massive, automated, or commercial data scraping. Always respect event platforms and their servers!

---

## ✨ Features

- 📄 **Single-Page View:** No endless scrolling. See all events in a clean table.
- 🧹 **Smart Filtering:** Automatically hides events you don't care about using a customizable blacklist.
- 📊 **Sorted & Organized:** Events are automatically sorted by time, location, and title.
- 🔍 **Rich Details:** Scrapes individual event pages for prices, organizers, and full addresses.
- 📦 **Cached Results:** Saves results locally per date so you don't waste time re-fetching the same days. 
  > 💡 **Important Cache Note:** The cache stores results per date. If new events are added to Eventbrite *after* your initial search, the tool will still show your old saved results. If you want to check for newly added events, use the `--no-cache` flag to force a fresh rescan!

---

## 🛠️ 1. Install `uv` (Fast Python Package Manager)

This project uses `uv` to manage everything easily and quickly. If you don't have `uv` installed yet, open your terminal and run the command for your system:

* macOS / Linux:
    curl -LsSf https://astral.sh/uv/install.sh | sh

* Windows (PowerShell):
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

*(Remember to restart your terminal after installing).*

---

## 📥 2. Download and Setup the Project

1. Clone the project repository to your computer:
    git clone <your-repository-url>
    cd eventus-publicus
   *(Note: The `tests/` folder is included in the repository for developers, but regular users can safely ignore it!)*

2. Install the required browser automation tools for Playwright:
    uv run playwright install chromium

---

## ⚙️ 3. Configuration (Important!)

Before running the tool for the first time, you need to set up your configuration files:

1. **Environment Settings (.env):**
   Find the file named `.env.example` in the project root. Make a copy of it and rename the copy to `.env`. 

2. **Personal Filters (Blacklist):**
   Find the file named `config/eventbrite.jsonc.example`. Make a copy of it inside the `config/` folder and rename the copy to `config/eventbrite.jsonc`. 
   Open this new file and add any words or event titles/locations you want to filter out automatically.

---

## 🎛️ Command-Line Arguments & Defaults

| Argument | Description | Default Value |
| :--- | :--- | :--- |
| `--start` | Start date (YYYY-MM-DD) | Coming Monday |
| `--end` | End date (YYYY-MM-DD) | Following Sunday |
| `--country` | Country or state code (e.g., canada, co) | Value from .env (canada) |
| `--city` | City or town name (e.g., calgary, denver) | Value from .env (calgary) |
| `--cache / --no-cache` | Use cached JSON results if available | Enabled (--cache) |
| `--enrich / --no-enrich` | Scrape individual event links for details | Enabled (--enrich) |
| `--log-level` | Diagnostics logging level (DEBUG, INFO, WARNING, ERROR) | WARNING |

---

## 🚀 4. How to Use (Examples)

* **Basic Run** (grabs events for the upcoming week in your default city):
    uv run eventus-publicus

* **Custom Date Range**:
    uv run eventus-publicus --start 2026-08-10 --end 2026-08-16

* **Rescan Freshly Added Events (Bypass Cache)**:
    uv run eventus-publicus --no-cache

* **Custom Location**:
    uv run eventus-publicus --city vancouver --country canada

* **Fast Run (No Enrichment)**:
    uv run eventus-publicus --no-enrich

To see all available options anytime, run:
    uv run eventus-publicus --help

---

## 📂 Where are my reports?

Once the tool finishes running successfully, you will find two new files (.md and .html) waiting for you inside your computer's **Downloads** folder! 
* Open the HTML file in any web browser to enjoy a gorgeous, clickable table of your local events. 🖥️✨

---

## 🧪 Running Tests (For Developers)

If you are a developer or curious user who wants to run the tests, this project includes **unit tests** and **integration tests** (end-to-end tests are not included yet). 

You can run them easily using `pytest` via `uv`:
    uv run pytest