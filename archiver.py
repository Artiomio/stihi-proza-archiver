#!/usr/bin/env python3
"""Download an author's publicly accessible works from stihi.ru or proza.ru.

This script is adapted from a 2021 Google Colab notebook. It deliberately keeps
archives local and is conservative about request rate and URL scope.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

ALLOWED_HOSTS = {"stihi.ru", "proza.ru"}
# Both sites use /YYYY/MM/DD/ID for individual works; /editor/... occurs too.
WORK_PATH = re.compile(r"^/(?:editor/)?(\d{4})/(\d{1,2})/(\d{1,2})/(\d+)/?$", re.I)
USER_AGENT = "PersonalLiteraryArchiver/0.1 (+local backup; 1 request per second)"


@dataclass(frozen=True)
class Work:
    url: str
    title: str
    date: str | None
    file: str


def parse_author_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in ALLOWED_HOSTS or parsed.port is not None:
        raise ValueError("Use an HTTPS author URL on stihi.ru or proza.ru")
    match = re.fullmatch(r"/avtor/([\w.-]+)", parsed.path, re.UNICODE)
    if not match:
        raise ValueError("Expected https://stihi.ru/avtor/NAME (or proza.ru)")
    return host, match.group(1)


def page_url(host: str, author: str, offset: int) -> str:
    # Legacy sites use an ampersand in the path itself, not '?s='.
    return f"https://{host}/avtor/{author}&s={offset}"


def normalize_work_url(href: str | None, host: str) -> str | None:
    if not href:
        return None
    absolute = urljoin(f"https://{host}/", href)
    parsed = urlparse(absolute)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() != host:
        return None
    if not WORK_PATH.fullmatch(parsed.path):
        return None
    return f"https://{host}{parsed.path.rstrip('/')}"


def index_links(html: str, host: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[str] = []
    seen: set[str] = set()
    for link in soup.select("a[href]"):
        url = normalize_work_url(link.get("href"), host)
        if url and url not in seen:
            seen.add(url)
            results.append(url)
    return results


def clean_text(div) -> str:
    # .get_text('\n') inserts artificial breaks around inline tags. Replacing
    # only <br> preserves deliberate line breaks without splitting <em> words.
    from bs4 import NavigableString

    for unwanted in div.select("script, style"):
        unwanted.decompose()
    for br in div.find_all("br"):
        br.replace_with(NavigableString("\n"))
    text = div.get_text()
    text = text.replace("\xa0", " ").replace("\r\n", "\n").replace("\r", "\n")
    return "\n".join(line.rstrip() for line in text.split("\n")).strip()


def parse_work(html: str, url: str, output_name: str) -> tuple[Work, str]:
    soup = BeautifulSoup(html, "html.parser")
    body = soup.select_one("div.text")
    if body is None:
        raise ValueError(f"Work page has no div.text: {url}")
    content = clean_text(body)
    if not content:
        raise ValueError(f"Work page has an empty text block: {url}")
    heading = soup.select_one("h1")
    title = heading.get_text(" ", strip=True) if heading else ""
    if not title and soup.title:
        title = soup.title.get_text(" ", strip=True).split(" | ")[0].strip()
    match = WORK_PATH.fullmatch(urlparse(url).path)
    if match is None:
        raise ValueError(f"Unexpected work URL: {url}")
    year, month, day, _ = match.groups()
    try:
        published = date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        published = None
    return Work(url=url, title=title or output_name, date=published, file=output_name), content


def robots_rules(session: requests.Session, host: str, timeout: float) -> RobotFileParser:
    robots_url = f"https://{host}/robots.txt"
    response = session.get(robots_url, timeout=timeout)
    if response.status_code in (404, 410):
        lines = []
    else:
        response.raise_for_status()
        lines = response.text.splitlines()
    parser = RobotFileParser()
    parser.parse(lines)
    return parser


def get_page(session: requests.Session, url: str, timeout: float, delay: float) -> str:
    if delay:
        time.sleep(delay)
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    # requests normally uses HTTP encoding and apparent_encoding fallback.
    if response.encoding is None or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


def archive(
    author_url: str,
    output_dir: Path,
    *,
    max_pages: int = 100,
    max_works: int | None = None,
    delay: float = 1.2,
    timeout: float = 20,
    dry_run: bool = False,
    session: requests.Session | None = None,
) -> list[Work]:
    host, author = parse_author_url(author_url)
    if max_pages < 1 or (max_works is not None and max_works < 1) or delay < 0:
        raise ValueError("max-pages and max-works must be positive; delay cannot be negative")
    session = session or requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    robot = robots_rules(session, host, timeout)
    urls: list[str] = []
    visited: set[str] = set()

    for page in range(max_pages):
        url = page_url(host, author, page * 50)
        if not robot.can_fetch(USER_AGENT, url):
            raise PermissionError(f"robots.txt disallows: {url}")
        links = index_links(get_page(session, url, timeout, delay), host)
        new_links = [link for link in links if link not in visited]
        if not new_links:
            break
        for link in new_links:
            visited.add(link)
            urls.append(link)
        print(f"Index page {page+1}: +{len(new_links)} works", file=sys.stderr)
        if max_works is not None and len(urls) >= max_works:
            urls = urls[:max_works]
            break

    if dry_run:
        for url in urls:
            print(url)
        return []

    output_dir.mkdir(parents=True, exist_ok=True)
    works_dir = output_dir / "works"
    works_dir.mkdir(parents=True, exist_ok=True)
    works: list[Work] = []
    errors: list[dict[str, str]] = []
    for index, url in enumerate(urls, start=1):
        if not robot.can_fetch(USER_AGENT, url):
            errors.append({"url": url, "error": "Disallowed by robots.txt"})
            continue
        match = WORK_PATH.fullmatch(urlparse(url).path)
        assert match
        work_file = f"{'-'.join(match.groups())}.txt"
        try:
            html = get_page(session, url, timeout, delay)
            work, content = parse_work(html, url, f"works/{work_file}")
            (works_dir / work_file).write_text(content + "\n", encoding="utf-8")
            works.append(work)
            print(f"[{index}/{len(urls)}] {work.title}", file=sys.stderr)
        except (requests.RequestException, ValueError) as exc:
            errors.append({"url": url, "error": str(exc)})
            print(f"Failed: {url}: {exc}", file=sys.stderr)

    combined = "\n\n".join((output_dir / item.file).read_text(encoding="utf-8").rstrip() for item in works)
    (output_dir / "corpus.txt").write_text(combined + ("\n" if combined else ""), encoding="utf-8")
    manifest = {"site": host, "author": author, "source": author_url,
                "works": [asdict(x) for x in works], "errors": errors}
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return works


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("author_url", help="e.g. https://stihi.ru/avtor/yourname")
    parser.add_argument("-o", "--output", type=Path, default=Path("archives"))
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--max-works", type=int)
    parser.add_argument("--delay", type=float, default=1.2, help="seconds between requests")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--dry-run", action="store_true", help="list found URLs without downloading works")
    args = parser.parse_args(argv)
    try:
        host, author = parse_author_url(args.author_url)
        target = args.output / host / author
        works = archive(args.author_url, target, max_pages=args.max_pages,
                        max_works=args.max_works, delay=args.delay, timeout=args.timeout,
                        dry_run=args.dry_run)
    except (ValueError, requests.RequestException, PermissionError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    if not args.dry_run:
        print(f"Saved {len(works)} works to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
