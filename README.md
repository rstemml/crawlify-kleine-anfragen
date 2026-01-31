# Crawlify Kleine Anfragen

Sammelt "Kleine Anfragen" aus dem Deutschen Bundestag und speichert sie in einer SQLite-Datenbank.

## Was sind Kleine Anfragen?

Kleine Anfragen sind Fragen von Bundestagsabgeordneten an die Bundesregierung. Die Regierung muss innerhalb von 14 Tagen antworten.

## Datenmodell

```
VORGANG (Parlamentarischer Vorgang)
│   ID, Titel, Datum, Status (beratungsstand)
│
└── DRUCKSACHE (Offizielle Dokumente)
    │   Typ: "Kleine Anfrage" (die Fragen)
    │   Typ: "Antwort" (die Antworten der Regierung)
    │
    └── DRUCKSACHE_TEXT (Volltext aus PDF)
```

**Beispiel:**
- Vorgang #330152: "Gefahren für Deutsche durch Tourismus in Risikogebiete"
  - Drucksache 21/3679: Die Fragen (Kleine Anfrage)
  - Drucksache 21/3819: Die Antwort der Bundesregierung

## Installation

```bash
pip install -e .
export DIP_API_KEY="dein-api-key"  # Von bundestag.de
```

## Schnellstart

```bash
# Alles auf einmal (neue Vorgänge + Dokumente für 50 davon)
python scripts/update_db.py

# Nur neue Vorgänge holen
python scripts/update_db.py --skip-drucksache --skip-text

# Mehr Dokumente nachladen
python scripts/update_db.py --skip-vorgang --limit 100
```

## Daten anschauen

**Option 1: Datasette (Web-UI)**
```bash
pip install datasette
datasette data/db/crawlify.sqlite
# Öffne http://127.0.0.1:8001
```

**Option 2: SQLite direkt**
```bash
sqlite3 data/db/crawlify.sqlite
```

## Nützliche SQL-Abfragen

```sql
-- Alle offenen Anfragen (noch keine Antwort)
SELECT vorgang_id, datum, titel
FROM vorgang
WHERE beratungsstand = 'Noch nicht beantwortet'
ORDER BY datum DESC;

-- Beantwortete Anfragen mit Volltext
SELECT v.titel, d.drucksachetyp, dt.volltext
FROM vorgang v
JOIN drucksache d ON d.vorgang_id = v.vorgang_id
JOIN drucksache_text dt ON dt.drucksache_id = d.drucksache_id
WHERE v.beratungsstand = 'Beantwortet'
LIMIT 10;

-- Statistik nach Status
SELECT beratungsstand, COUNT(*) as anzahl
FROM vorgang
GROUP BY beratungsstand;
```

## Status-Werte (beratungsstand)

| Status | Bedeutung |
|--------|-----------|
| `Beantwortet` | Antwort liegt vor |
| `Noch nicht beantwortet` | Wartet auf Antwort |
| `Zurückgezogen` | Anfrage zurückgezogen |
| `Erledigt durch Ablauf der Wahlperiode` | Legislaturperiode endete |

## Projektstruktur

```
├── data/
│   ├── raw/vorgang/       # Original JSON von API
│   └── db/crawlify.sqlite # Normalisierte Datenbank
├── logs/
│   └── update_db.log      # Logs vom Update-Script
├── state/
│   ├── vorgang_cursor.json # Für inkrementelle Updates
│   └── update_db.lock     # Lockfile (verhindert parallele Läufe)
├── scripts/
│   ├── update_db.py       # Update-Script
│   └── install-systemd.sh # Installiert systemd Timer
├── systemd/
│   ├── crawlify-update.service # Systemd Service
│   └── crawlify-update.timer   # Systemd Timer (täglich 3:00)
└── src/crawlify/          # Python-Module
    ├── cli.py             # CLI-Befehle
    ├── dip_client.py      # API-Client
    ├── db.py              # Datenbank-Schema
    └── normalize.py       # JSON → DB Mapping
```

## API-Infos

Die Daten kommen von der DIP-API (Dokumentations- und Informationssystem für Parlamentarische Vorgänge):
- Basis-URL: `https://search.dip.bundestag.de/api/v1`
- Max 100 Items pro Request (Cursor-Pagination)
- Bot-Schutz (Enodia) - siehe nächster Abschnitt

## Bot-Schutz (Captcha)

Die DIP-API verwendet Enodia-Challenges als Bot-Schutz. Um diese automatisch zu lösen:

```bash
# Playwright installieren
pip install -e ".[browser]"

# Chromium-Browser herunterladen
playwright install chromium
```

Bei Bedarf kann die Challenge manuell gelöst werden:

```bash
crawlify solve-challenge   # Öffnet Browser zur manuellen Lösung
crawlify clear-cookies     # Löscht gespeicherte Cookies
```

Die gelösten Cookies werden in `state/cookies.json` gecacht.

## Automatische Updates (CronJob)

Das Projekt enthält systemd-Dateien für tägliche automatische Updates.

### Installation

```bash
# 1. Initialen Full-Load durchführen (kann Stunden dauern)
python scripts/update_db.py --full

# 2. Systemd Timer installieren (als root)
sudo ./scripts/install-systemd.sh
```

### Timer verwalten

```bash
# Status prüfen
systemctl status crawlify-update.timer

# Logs ansehen
journalctl -u crawlify-update.service

# Manuell ausführen
sudo systemctl start crawlify-update.service

# Timer deaktivieren
sudo systemctl disable crawlify-update.timer
```

### Logs

Das Update-Script schreibt Logs nach `logs/update_db.log`.

## CLI-Befehle (Einzeln)

```bash
# Vorgänge
crawlify fetch-vorgang
crawlify normalize-vorgang

# Drucksachen
crawlify fetch-drucksache
crawlify normalize-drucksache

# Volltexte
crawlify fetch-drucksache-text
crawlify normalize-drucksache-text

# Suche (benötigt sentence-transformers)
crawlify embed-vorgang
crawlify search-vorgang "Klimaschutz"
```

