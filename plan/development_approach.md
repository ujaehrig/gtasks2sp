# Development Approach

Grundlage ist [design.md](design.md). Jede Phase wird test-first umgesetzt:
erst die Tests, dann der Code. Eine Phase ist fertig, wenn die Definition of
Done aus `design.md` erfüllt ist.

## Phasen

1. [Projektgerüst und Fixtures](phase1_tasks.md): Werkzeuge, Skript-Hülle,
   anonymisierte gog-Ausgabe
2. [Reine Logik](phase2_tasks.md): Eingabe lesen, filtern, abbilden,
   Importregister
3. [Super Productivity und Ablauf](phase3_tasks.md): HTTP-Client,
   Vorprüfung, Import-Schleife, `--dry-run`, Exit-Codes, README
