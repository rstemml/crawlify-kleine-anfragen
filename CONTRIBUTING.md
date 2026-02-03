# Contributing

Danke fuer dein Interesse an diesem Projekt! Beitraege sind herzlich willkommen.

## Wie kann ich beitragen?

### Bug Reports

- Oeffne ein [Issue](https://github.com/rstemml/crawlify-kleine-anfragen/issues) mit:
  - Beschreibung des Problems
  - Schritte zur Reproduktion
  - Erwartetes vs. tatsaechliches Verhalten
  - Python-Version und Betriebssystem

### Feature Requests

- Oeffne ein Issue mit dem Label `enhancement`
- Beschreibe den Use Case und den Nutzen

### Code Contributions

1. **Fork** das Repository
2. **Clone** deinen Fork:
   ```bash
   git clone https://github.com/DEIN-USERNAME/crawlify-kleine-anfragen.git
   cd crawlify-kleine-anfragen
   ```

3. **Branch** erstellen:
   ```bash
   git checkout -b feature/mein-feature
   # oder
   git checkout -b fix/mein-bugfix
   ```

4. **Entwicklungsumgebung** einrichten:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Linux/Mac
   pip install -e ".[dev]"
   ```

5. **Aenderungen** machen und testen:
   ```bash
   pytest
   ```

6. **Commit** mit aussagekraeftiger Nachricht:
   ```bash
   git add .
   git commit -m "feat: Beschreibung der Aenderung"
   ```

7. **Push** und Pull Request erstellen:
   ```bash
   git push origin feature/mein-feature
   ```

## Code Style

- Python: PEP 8
- Docstrings fuer oeffentliche Funktionen
- Type Hints wo sinnvoll
- Tests fuer neue Funktionalitaet

## Commit Messages

Wir folgen [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` Neue Funktion
- `fix:` Bugfix
- `docs:` Dokumentation
- `refactor:` Code-Refactoring
- `test:` Tests
- `chore:` Maintenance

## Fragen?

Oeffne ein Issue oder kontaktiere den Maintainer.

---

Vielen Dank fuer deinen Beitrag!
