# Design tasks2sp

Begriffe siehe [GLOSSARY.md](../GLOSSARY.md).

## Ziel

Offene Google-Tasks aus einer Quellliste werden einmalig als SP-Tasks in
Super Productivity angelegt. Google Tasks wird nie verändert. Nach dem Import
ist Super Productivity führend.

## Aufruf

```sh
gog tasks list <tasklist-id> --all --json --results-only | ./tasks2sp.py
./tasks2sp.py --dry-run < tasks.json
```

- Eingabe: JSON-Array von Google-Tasks auf stdin
- `--all` ist Pflicht in der Pipe, sonst liefert gog maximal 20 Tasks
- `--dry-run`: zeigt geplante Imports, schreibt weder nach Super Productivity
  noch ins Importregister (legt auch keine Datei an)
- `--env-file`: Pfad der `.env`, Vorgabe ist die `.env` neben dem Skript;
  Umgebungsvariablen haben Vorrang

## Konfiguration (`.env`)

| Schlüssel       | Pflicht | Vorgabe                                |
| --------------- | ------- | -------------------------------------- |
| `SP_TOKEN`      | ja      | –                                      |
| `SP_API`        | nein    | `http://127.0.0.1:3876`                |
| `SP_IMPORT_TAG` | nein    | `gtask`                                |
| `TASKS2SP_DB`   | nein    | `~/.local/share/tasks2sp/import.sqlite` |

## Ablauf

1. Vorprüfung, bei Fehler Abbruch vor dem ersten Task:
   - stdin ist gültiges JSON und ein Array
   - `GET /health` liefert `server == "up"` und `rendererReady == true`
   - Token wird akzeptiert (kein HTTP 401)
   - `GET /tags`: Import-Tag existiert genau einmal (Vergleich ohne
     Groß-/Kleinschreibung), und er ist nicht `Today`
2. Filter: nur Google-Tasks mit `status == "needsAction"`
3. Überspringen, wenn die Google-`id` bereits im Importregister steht
4. Pro verbleibendem Task:
   1. `POST /tasks` mit abgebildeten Feldern
   2. `GET /tasks/<id>` und prüfen, dass `title`, `dueDay`, `notes` und
      `tagIds` übernommen wurden
   3. Eintrag ins Importregister
5. Zusammenfassung auf stderr

## Feldabbildung

| Google-Task | SP-Task  | Regel                                       |
| ----------- | -------- | ------------------------------------------- |
| `title`     | `title`  | fehlend oder leer → `(ohne Titel)`          |
| `due`       | `dueDay` | Datumsteil `YYYY-MM-DD`, ohne Umrechnung    |
| `notes`     | `notes`  | siehe unten                                 |
| `links`     | `notes`  | siehe unten                                 |
| `parent`    | –        | ignoriert, Unteraufgaben werden flach       |
| –           | `tagIds` | `[<id des Import-Tags>]`                    |

Ein `due` in der Vergangenheit wird unverändert übernommen.

`notes` besteht aus bis zu drei Blöcken, getrennt durch eine Leerzeile.
Fehlende Blöcke entfallen; fehlen alle, wird kein `notes` gesendet:

1. die Notiz des Google-Tasks
2. je Eintrag in `links` eine Zeile `- [<description>](<link>)`; ist
   `description` leer oder fehlt, steht dort `type`
3. `webViewLink`

Die Uhrzeit eines Google-Tasks ist über die Tasks-API nicht lesbar und geht
deshalb verloren.

## Super-Productivity-API (beobachtet)

Echte Antworten liegen in `tests/fixtures/sp_*.json`.

- Jede Antwort hat die Form `{"ok": true, "data": …}` bzw.
  `{"ok": false, "error": {"code": …, "message": …}}`
- `POST /tasks` antwortet mit 201 und dem vollständigen Task; `title`,
  `notes`, `dueDay` und `tagIds` werden gespeichert, `projectId` ist
  `INBOX_PROJECT`
- Falsches Token: 401 mit `error.code == "UNAUTHORIZED"`
- Unbekannte ID: 404 mit `error.code == "TASK_NOT_FOUND"`

## Importregister

SQLite-Tabelle `imported`:

| Spalte           | Typ           | Inhalt                    |
| ---------------- | ------------- | ------------------------- |
| `google_task_id` | TEXT PK       | `id` des Google-Tasks     |
| `sp_task_id`     | TEXT NOT NULL | `id` des SP-Tasks         |
| `imported_at`    | TEXT NOT NULL | ISO-8601-Zeitstempel, UTC |

- Ein Google-Task im Importregister wird nie erneut importiert, auch wenn
  der SP-Task gelöscht oder archiviert wurde
- Eintrag erst nach verifiziertem Anlegen: Ein Abbruch zwischen `POST` und
  Eintrag führt beim nächsten Lauf zu einem Duplikat statt zu einem
  verlorenen Task

## Fehlerverhalten und Exit-Codes

| Code | Bedeutung                                             |
| ---- | ----------------------------------------------------- |
| 0    | alle offenen Tasks importiert oder bereits importiert |
| 1    | mindestens ein Task fehlgeschlagen, Rest verarbeitet  |
| 2    | Vorprüfung oder Konfiguration fehlgeschlagen          |

Bei Code 2 wurde nichts angelegt.

- Fehlgeschlagene Tasks werden nicht registriert, beim nächsten Lauf erneut
  versucht
- Fortschritt pro Task und Zusammenfassung auf stderr (englisch), z. B.
  `29 read, 27 open, 3 imported, 24 already imported, 0 failed`

## Technik

- Eine Datei `tasks2sp.py`, Shebang `#!/usr/bin/env -S uv run --script`,
  Abhängigkeiten per PEP-723
- Laufzeit: Standardbibliothek plus `python-dotenv` (feste Version)
- Gliederung in Funktionen: Eingabe, Abbildung, SP-Client, Importregister,
  `main`
- `pyproject.toml` nur für Entwicklung: `pytest`, `pytest-cov`, `ruff`,
  `pyright` (feste Versionen), `pythonpath = ["."]`
- Tests ohne echtes Super Productivity: Fake-HTTP-Server (`http.server`,
  zufälliger Port), SQLite in `tmp_path`, anonymisierte gog-Ausgabe als
  Fixture
- Definition of Done: 100 % Testabdeckung, `ruff format`, keine Befunde von
  `ruff check` und `pyright`, alle Tests grün

## Nicht im Umfang

- Rückschreiben nach Google Tasks
- Nachziehen von Änderungen an bereits importierten Google-Tasks
- Mehrere Quelllisten, Projekte, Unteraufgaben-Hierarchie, Uhrzeiten
- Aufruf von gog durch das Skript
