# Stihi.ru / Proza.ru author archiver

Small Python utility to back up publicly accessible works from an author's pages on **stihi.ru** or **proza.ru**. Adapted from my [2021 Google Colab downloader](notebooks/legacy/) and kept alongside historical Markov-chain experiments.

> **Status:** tested against local HTML fixtures, **not yet verified against the live websites**. Both sites may have changed their HTML since 2021. If the output is empty or incomplete, inspect the index page and adjust the CSS/URL selectors. Please respect site rules, authors' copyrights, and `robots.txt`.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python archiver.py 'https://stihi.ru/avtor/USERNAME' --max-works 5
# or:
python archiver.py 'https://proza.ru/avtor/USERNAME'
```

To check discovered links without downloading the works:

```bash
python archiver.py 'https://stihi.ru/avtor/USERNAME' --dry-run --max-pages 2
```

Options: `--max-pages 100`, `--max-works N`, `--delay 1.2` (seconds between requests), `--timeout 20`, `-o archives`. It stops paging once an index page yields no new links, and checks the sites' `robots.txt` before fetching. It does **not** attempt to bypass site access restrictions.

## Results

By default, files appear under `archives/stihi.ru/USERNAME/` or `archives/proza.ru/USERNAME/`:

- `works/YYYY-MM-DD-ID.txt`: one plain-text file per work
- `manifest.json`: titles, source URLs, publication dates derived from URL, local filenames, and request errors
- `corpus.txt`: concatenated text suitable for text-analysis experiments

Archives are gitignored, so personal backups and copyrighted text aren't accidentally committed to a public repository.

## Background

The original downloader assumed the first 50 works were links 13 through 62 on each author index page and scraped 35 pages. The updated script selects only links matching the sites' work URL pattern, stops on repeats, validates the host, and records metadata. It still depends on the websites' HTML structure.

Historical Colab notebooks in [`notebooks/legacy/`](notebooks/legacy/) preserve the original explorations: author downloader, word-level and character-level Markov experiments, and generation from Pavlin's poetry/prose. Outputs and Google Colab session metadata were stripped for publishing. They are **historical experiments**, not supported current code.

## Development

```bash
python -m unittest discover -s tests -v
```

This is a personal archive/learning project, not an official API or an endorsed way to mirror either site.
