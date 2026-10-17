# Phase 1: Projektgerüst und Fixtures

## ~~Task 1.1: Entwicklungsumgebung~~ [Completed]

- `pyproject.toml` mit Dev-Abhängigkeiten in festen Versionen: `pytest`,
  `pytest-cov`, `ruff`, `pyright`
- pytest: `pythonpath = ["."]`, Coverage für `tasks2sp`, `fail_under = 100`
- `.gitignore` mit `.env`, `*.sqlite`, `.venv/`, Caches
- `.env.example` mit allen Schlüsseln aus `design.md`, ohne Werte für
  `SP_TOKEN`

AI Prompt:

> Lies `plan/design.md`. Lege `pyproject.toml` (nur Dev-Tools, Versionen
> mit `uv add --dev` gepinnt), `.gitignore` und `.env.example` an. pytest
> soll mit `--cov=tasks2sp --cov-fail-under=100` laufen. Prüfe mit
> `uv run ruff check` und `uv run pyright`.

## ~~Task 1.2: Skript-Hülle~~ [Completed]

- `tasks2sp.py` mit Shebang `#!/usr/bin/env -S uv run --script`,
  PEP-723-Block (Python-Version, `python-dotenv` gepinnt), leerer `main()`
  und `if __name__ == "__main__"`
- ein Smoke-Test, der `main` importiert

AI Prompt:

> Schreibe zuerst `tests/test_smoke.py`, das `tasks2sp.main` importiert und
> aufruft. Lege dann `tasks2sp.py` gemäß `plan/design.md`, Abschnitt Technik,
> an und mache es ausführbar. Alle Prüfungen der Definition of Done müssen
> grün sein.

## ~~Task 1.3: gog-Fixture~~ [Completed]

- `tests/fixtures/gog_tasks.json`: echte Ausgabe von
  `gog tasks list <id> --all --json --results-only`, anonymisiert (Titel,
  Notizen, IDs ersetzt; Struktur und Feldnamen unverändert)
- enthält mindestens: Task ohne `due`, Task mit `due` in der Vergangenheit,
  Task mit `notes`, Unteraufgabe mit `parent`, Task mit `status ==
  "completed"`

AI Prompt:

> Erzeuge die Fixture aus echter gog-Ausgabe der Quellliste und anonymisiere
> sie. Fehlende Fälle aus der Liste oben ergänzt du durch Kopien
> vorhandener Einträge mit angepassten Feldern. Keine echten Inhalte im
> Repository.
