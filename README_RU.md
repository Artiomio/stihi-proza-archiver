# Архиватор «Стихи.ру» и «Проза.ру»

Восстановленный проект на основе Colab-ноутбука февраля 2021 года. Основной скрипт позволяет скачать доступные произведения автора на локальный компьютер. Рядом лежат пять исторических Colab-ноутбуков с парсером и марковскими экспериментами.

## Быстрая проверка на Mac / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python archiver.py 'https://stihi.ru/avtor/ИМЯ_АВТОРА' --max-works 5
```

Или для прозы:

```bash
python archiver.py 'https://proza.ru/avtor/ИМЯ_АВТОРА' --max-works 5
```

Режим `--dry-run` выводит ссылки, не скачивая тексты:

```bash
python archiver.py 'https://stihi.ru/avtor/ИМЯ_АВТОРА' --dry-run --max-pages 2
```

Результаты появятся в `archives/<сайт>/<имя автора>/`:

- `works/*.txt`: произведения по отдельности;
- `corpus.txt`: все тексты в одном файле, для экспериментов;
- `manifest.json`: названия, URL, даты из адресов страниц и ошибки загрузки.

Выполнение ограничено `--max-pages 100` и паузами между запросами (`--delay 1.2`). Скрипт проверяет `robots.txt`. Папка `archives/` исключена из Git, чтобы не выкладывать чужие тексты в открытый репозиторий.

**Важно:** скрипт проверен только на локальных HTML-примерах, не на работающих сайтах. Сайты могли изменить разметку, поэтому первая проверка должна быть с `--dry-run` и `--max-works 5`. Текущая версия не обходит ограничения доступа.

## Тесты

```bash
python -m unittest discover -s tests -v
```

## Клонирование репозитория

```bash
git clone https://github.com/Artiomio/stihi-proza-archiver.git
cd stihi-proza-archiver
```
