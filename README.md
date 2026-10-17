# tasks2sp

Imports open Google Tasks from one task list into
[Super Productivity](https://super-productivity.com/) via its local REST API.
Google Tasks is only read, never modified. Each Google Task is imported once;
afterwards Super Productivity owns the task.

Design and terminology: [plan/design.md](plan/design.md),
[GLOSSARY.md](GLOSSARY.md).

## Requirements

- [uv](https://docs.astral.sh/uv/)
- gog (Google CLI) with access to Google Tasks
- Super Productivity desktop with *Settings → Misc → Enable local REST API*
- An existing tag in Super Productivity that every imported task receives
  (default `gtask`); the API cannot create tags

## Configuration

Copy `.env.example` to `.env` next to the script and fill in `SP_TOKEN` from
*Settings → Misc → Access Token*. Environment variables override the file.

| Key             | Default                                |
| --------------- | -------------------------------------- |
| `SP_TOKEN`      | required                               |
| `SP_API`        | `http://127.0.0.1:3876`                |
| `SP_IMPORT_TAG` | `gtask`                                |
| `TASKS2SP_DB`   | `~/.local/share/tasks2sp/import.sqlite` |

The token grants full access to your tasks; keep `.env` out of version
control.

## Usage

Find the list id with `gog tasks lists list`, then:

```sh
gog tasks list <tasklist-id> --all --json --results-only \
  | ./tasks2sp.py --dry-run
gog tasks list <tasklist-id> --all --json --results-only | ./tasks2sp.py
```

`--all` is required, otherwise gog returns at most 20 tasks. Progress and a
summary go to stderr.

To try the import on a few tasks first, cut the list down with `jq`:

```sh
gog tasks list <tasklist-id> --all --json --results-only \
  | jq '[.[] | select(.status == "needsAction")][:2]' | ./tasks2sp.py
```

## What is imported

- Only tasks with status `needsAction`
- `title`; a missing title becomes `(ohne Titel)`
- `due` as `dueDay` (date only; the Tasks API does not expose the time)
- `notes`: the note, the task's links as a Markdown list and the link to the
  task in Google Tasks
- Subtasks are imported as independent tasks into the Inbox

A Google Task recorded in the import register is never imported again, even
after its Super Productivity task was deleted. Changes to an imported Google
Task are not carried over.

## Exit codes

| Code | Meaning                                                      |
| ---- | ------------------------------------------------------------ |
| 0    | all open tasks imported or already imported                  |
| 1    | at least one task failed; it is retried on the next run      |
| 2    | configuration, input or precheck failed; nothing was created |

## Development

```sh
uv run pytest
uv run ruff format && uv run ruff check
uv run pyright
```

Tests run against a fake API and never touch a real Super Productivity.
