import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archiver import archive, index_links, normalize_work_url, page_url, parse_author_url, parse_work


INDEX = '''<html><body><a href="/">home</a>
<a href="/2021/02/11/102">First</a>
<a href="https://stihi.ru/2021/02/12/103">Second</a>
<a href="/2021/02/11/102">Duplicate</a>
<a href="https://evil.example/2021/02/12/104">Outside</a>
<a href="/avtor/other">Other author</a></body></html>'''
WORK = '<html><head><title>Poem | Стихи.ру</title></head><body><h1>Poem</h1><div class="text">Line 1<br>Line <em>two</em><br>Line 3</div></body></html>'


class FakeResponse:
    def __init__(self, text, status_code=200):
        self.text = text
        self.status_code = status_code
        self.encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def get(self, url, timeout):
        self.calls.append(url)
        if url.endswith('/robots.txt'):
            return FakeResponse('User-agent: *\nAllow: /')
        if '/avtor/' in url:
            return FakeResponse(INDEX)
        return FakeResponse(WORK)


class ArchiveTests(unittest.TestCase):
    def test_author_url_validation(self):
        self.assertEqual(parse_author_url('https://proza.ru/avtor/username'), ('proza.ru', 'username'))
        for invalid in ('http://stihi.ru/avtor/name', 'https://evil.example/avtor/name',
                        'https://stihi.ru.evil.example/avtor/name', 'https://stihi.ru/2021/02/11/2'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                parse_author_url(invalid)

    def test_index_filters_and_deduplicates(self):
        self.assertEqual(index_links(INDEX, 'stihi.ru'), [
            'https://stihi.ru/2021/02/11/102', 'https://stihi.ru/2021/02/12/103'])
        self.assertIsNone(normalize_work_url('//evil.example/2021/02/11/1', 'stihi.ru'))
        self.assertEqual(page_url('stihi.ru','user',50), 'https://stihi.ru/avtor/user&s=50')

    def test_extract_title_body_and_date(self):
        work, text = parse_work(WORK, 'https://stihi.ru/2021/02/11/102', 'works/a.txt')
        self.assertEqual((work.title, work.date), ('Poem', '2021-02-11'))
        self.assertEqual(text, 'Line 1\nLine two\nLine 3')

    def test_archives_files_and_stops_on_duplicate_page(self):
        session = FakeSession()
        with tempfile.TemporaryDirectory() as directory, patch('archiver.time.sleep'):
            works = archive('https://stihi.ru/avtor/user', Path(directory), session=session)
            self.assertEqual(len(works), 2)
            self.assertEqual((Path(directory)/'works/2021-02-11-102.txt').read_text(), 'Line 1\nLine two\nLine 3\n')
            self.assertIn('Line 1\nLine two', (Path(directory)/'corpus.txt').read_text())
            self.assertTrue((Path(directory)/'manifest.json').is_file())
            self.assertEqual(sum('/avtor/' in url for url in session.calls), 2)

    def test_proza_uses_same_work_structure(self):
        sample = '<a href="/2021/01/02/10">Prose</a>'
        self.assertEqual(index_links(sample, 'proza.ru'), ['https://proza.ru/2021/01/02/10'])
        item, text = parse_work(WORK, 'https://proza.ru/2021/01/02/10', 'works/x.txt')
        self.assertEqual(item.date, '2021-01-02')
        self.assertEqual(text.splitlines()[0], 'Line 1')

    def test_dry_run_leaves_no_files(self):
        session = FakeSession()
        with tempfile.TemporaryDirectory() as directory, patch('archiver.time.sleep'):
            output = Path(directory)/'archive'
            self.assertEqual(archive('https://stihi.ru/avtor/user', output, dry_run=True, session=session, max_pages=2), [])
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
