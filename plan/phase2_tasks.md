# Phase 2: Reine Logik

## ~~Task 2.1: Eingabe lesen und filtern~~ [Completed]

- `read_google_tasks(text) -> list[dict]`: JSON parsen, muss ein Array sein,
  sonst `InputError`
- `open_tasks(tasks) -> list[dict]`: nur `status == "needsAction"`

AI Prompt:

> Schreibe zuerst Tests für gültiges Array, kein JSON, JSON-Objekt statt
> Array, leeres Array und die Filterung mit `tests/fixtures/gog_tasks.json`.
> Implementiere dann beide Funktionen ohne Ein-/Ausgabe.

## ~~Task 2.2: Feldabbildung~~ [Completed]

- `to_sp_task(google_task, tag_id) -> dict` gemäß Abschnitt Feldabbildung
  in `design.md`
- `title` fehlend oder nur Leerzeichen → `(ohne Titel)`
- `due` → Datumsteil der ersten 10 Zeichen, keine Zeitzonenumrechnung
- `notes`: Blöcke Notiz, `links`, `webViewLink`, getrennt durch Leerzeile;
  fehlende Blöcke entfallen, ohne Blöcke kein `notes`-Feld
- `parent` wird ignoriert

AI Prompt:

> Schreibe zuerst Tests für jede Zeile der Feldabbildung, jede Kombination
> der `notes`-Blöcke, Links mit und ohne `description` sowie `due` in der
> Vergangenheit. Implementiere dann `to_sp_task` als reine Funktion.

## ~~Task 2.3: Importregister~~ [Completed]

- `ImportRegister(path)`: legt Verzeichnis und Tabelle `imported` an
- `contains(google_task_id) -> bool`
- `add(google_task_id, sp_task_id)`: speichert `imported_at` in UTC
- Kontextmanager, schließt die Verbindung

AI Prompt:

> Schreibe zuerst Tests mit einer Datenbank in `tmp_path`: neues
> Verzeichnis, leeres Register, Eintrag und Abfrage, Persistenz über zwei
> Instanzen, doppelter Eintrag wirft. Implementiere dann die Klasse mit
> `sqlite3`.
