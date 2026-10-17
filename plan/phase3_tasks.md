# Phase 3: Super Productivity und Ablauf

## Task 3.1: Fake-Server für Tests

- pytest-Fixture mit `http.server` auf zufälligem Port in einem Thread
- antwortet mit den Fixtures `tests/fixtures/sp_*.json`, zeichnet Requests
  auf, Verhalten pro Test steuerbar (401, 404, falsche Felder, Ausfall)

AI Prompt:

> Baue in `tests/conftest.py` einen Fake-Server für `/health`, `/tags`,
> `POST /tasks` und `GET /tasks/<id>`. Antworten basieren auf den echten
> Fixtures. Er muss Authorization-Header und Request-Bodies aufzeichnen.

## Task 3.2: SP-Client

- `SpClient(base_url, token)` mit `health()`, `tags()`, `create_task(body)`,
  `get_task(id)` über `urllib.request`
- wertet `ok`/`error` aus; 401 → `AuthError`, Verbindungsfehler →
  `ConnectionError`, sonst `ApiError` mit `code` und `message`

AI Prompt:

> Schreibe zuerst Tests gegen den Fake-Server für jede Methode und jeden
> Fehlerfall. Implementiere dann den Client. Das Token darf in keiner
> Fehlermeldung erscheinen.

## Task 3.3: Vorprüfung

- `precheck(client, tag_name) -> tag_id` gemäß `design.md`, Ablauf Schritt 1
- Fehler: nicht erreichbar, `rendererReady` false, 401, Tag fehlt, Tag
  mehrdeutig, Tag ist `Today`

AI Prompt:

> Schreibe zuerst je einen Test pro Fehlerfall und einen für den Erfolg
> (Vergleich ohne Groß-/Kleinschreibung). Implementiere dann `precheck`.

## Task 3.4: Import-Schleife und `main`

- Konfiguration aus `.env` und Umgebung, Vorgaben aus `design.md`
- pro Task: überspringen wenn registriert, sonst `POST`, `GET`,
  Feldvergleich, Eintrag ins Register; Fehler eines Tasks melden und
  weitermachen
- `--dry-run`: keine Writes nach Super Productivity und ins Register
- Fortschritt und Zusammenfassung auf stderr, Exit-Codes 0/1/2

AI Prompt:

> Schreibe zuerst End-to-End-Tests von `main` mit Fake-Server, `tmp_path`
> und gog-Fixture auf stdin: Erstlauf, zweiter Lauf ohne neue Imports,
> Fehler bei einem Task (Exit 1, nicht registriert), Vorprüfung schlägt fehl
> (Exit 2, kein POST), `--dry-run` (kein POST, Register leer), fehlendes
> `SP_TOKEN`. Implementiere dann die Schleife und `main`.

## Task 3.5: Dokumentation und Abnahme

- `README.md`: Zweck, Voraussetzungen (Tag `gtask`, REST-API aktiv,
  Token), Konfiguration, Aufruf mit Pipe, Exit-Codes, Grenzen
- einmaliger echter Lauf mit `--dry-run` gegen die Quellliste

AI Prompt:

> Schreibe die README nach den Markdown-Regeln. Führe danach
> `gog tasks list <id> --all --json --results-only | ./tasks2sp.py
> --dry-run` aus und vergleiche die Ausgabe mit der Quellliste. Einen
> echten Import nur nach Rückfrage.
