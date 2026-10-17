# tasks2sp

Übernimmt offene Aufgaben aus Google Tasks nach Super Productivity, ohne
Google Tasks zu verändern.

## Language

**Google-Task**:
Eine Aufgabe in einer Google-Tasks-Liste; die Quelle eines Imports.
_Avoid_: Quell-Task, Remote-Task

**SP-Task**:
Eine Aufgabe in Super Productivity, die durch einen Import entstanden ist.
_Avoid_: Ziel-Task, lokaler Task

**Offener Google-Task**:
Ein Google-Task mit Status `needsAction`; nur solche werden importiert.
_Avoid_: aktiver Task, unerledigter Task

**Quellliste**:
Die eine Google-Tasks-Liste, aus der importiert wird.
_Avoid_: Taskliste, Liste

**Import-Tag**:
Ein bereits in Super Productivity existierender Tag, den jeder SP-Task beim
Import erhält.
_Avoid_: Label, Kategorie

**Import**:
Einmaliges Anlegen eines SP-Tasks zu einem offenen Google-Task. Danach ist
Super Productivity führend; spätere Änderungen am Google-Task werden ignoriert.
_Avoid_: Sync, Abgleich

**Importregister**:
Das Verzeichnis, welcher Google-Task bereits zu welchem SP-Task importiert
wurde.
_Avoid_: Cache, Mapping-Tabelle
