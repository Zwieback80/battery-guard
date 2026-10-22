# Battery Guard

🇩🇪 Deutsch · [🇬🇧 English](README.en.md)

Battery Guard ist eine Integration für Home Assistant, die **alle Batterien in deinem Smart Home automatisch findet**, ihren Zustand bewertet, den Verbrauch prognostiziert und dir sagt, **welche Batterie wann gewechselt werden muss**. Es gibt nichts zu konfigurieren: Installieren, hinzufügen, fertig.

- Getestet mit Home Assistant 2026.9.x
- Installation über HACS (Custom Repository) oder manuell
- Lizenz: [PolyForm Noncommercial 1.0.0](LICENSE) – **kommerzielle Nutzung ist nicht gestattet**

## Funktionen im Überblick

### Automatische Erkennung
Battery Guard durchsucht alle Entitäten und findet Batterien selbst:
- `sensor` mit Geräteklasse *battery* (oder Einheit `%` und „battery“ im Namen) → Batterie mit Prozentwert
- `binary_sensor` mit Geräteklasse *battery* → nur „Batterie schwach“ ja/nein (z. B. viele Rauchmelder)
- Hilfssensoren wie `…_battery_state` (Laden/Entladen) und Battery Guards eigene Sensoren werden nicht mitgezählt.

Neue Geräte werden beim nächsten Durchlauf (standardmäßig alle 5 Minuten) automatisch angelegt.

### Status
Jedes Gerät bekommt einen Status:

| Status | Bedeutung (Standardwerte) |
|---|---|
| `ok` | ab 40 % |
| `watch` (Beobachten) | 25 – 40 % |
| `low` (Niedrig) | 15 – 25 % |
| `critical` (Kritisch) | unter 15 % – bei Batterien ohne Prozentwert: „Batterie schwach“ ist aktiv |
| `offline` | seit mehr als 48 Stunden keine Meldung des Geräts |
| `unknown` | Wert nicht lesbar |

Alle Schwellen und die Offline-Zeit lassen sich in den Optionen anpassen.

### Prognose: „Tage bis leer“
Aus dem Verlauf der letzten Tage (Standard: 14) berechnet Battery Guard den Verbrauch in %/Tag mit einer Ausgleichsgeraden und schätzt, wie viele Tage bis zur kritischen Schwelle bleiben. Fällt der Wert nicht, steht der Trend auf *stabil* bzw. *steigend*. Die Prognose wird alle 6 Stunden neu berechnet. Mindestens 3 Datenpunkte sind nötig; bis dahin steht der Trend auf *unbekannt*.

### Health Score (0–100)
Eine einzige Zahl pro Gerät, bewusst nachvollziehbar aus drei Teilwerten:
- **Füllstand (50 %)** – wo liegt der Wert zwischen kritischer Schwelle und voll
- **Trend (30 %)** – wie viele Tage Reserve bleiben im Verhältnis zu 60 Tagen (ohne Trenddaten neutral 70)
- **Zuverlässigkeit (20 %)** – 0, wenn das Gerät offline ist, sonst 100

Die Teilwerte stehen als Attribute am Sensor, ein auffälliger Wert lässt sich so erklären.

### Batteriewechsel und Batterietyp
- **Automatische Erkennung:** Springt der Wert um mindestens 40 Prozentpunkte nach oben, trägt Battery Guard automatisch einen Wechsel ein. Geräte, die auch einen Ladezustands-Sensor haben (Handy, Tablet), sind ausgenommen, dort ist ein Sprung normales Laden.
- **Manuell:** Dienst `battery_guard.log_change` (siehe unten).
- Pro Gerät werden bis zu 20 Wechsel gespeichert (inkl. Typ, Anzahl, Notiz). Die Daten liegen in Home Assistants `.storage` und werden nicht vom Recorder gelöscht.

### Einkaufsliste
Der Übersichts-Sensor zählt für alle Geräte mit Status *niedrig* oder *kritisch* zusammen, welche Batterien du brauchst (Typ × Anzahl), z. B. `AAA: 3`. Den Typ hinterlegst du mit `battery_guard.set_battery_info` oder beim Eintragen eines Wechsels.

### Räume – vollautomatisch
Jedes Battery-Guard-Gerät wird automatisch in den **Raum der Quelle** gelegt. Hat die Quelle keinen Raum, landet es im Bereich **„Sonstiges“** (bei englischer Systemsprache „Other“; wird bei Bedarf selbst angelegt). Von Hand gesetzte Räume am Battery-Guard-Gerät werden bewusst überschrieben: Möchtest du ein Gerät verschieben, ändere den Raum am Quellgerät.

### Automatisches Aufräumen
Wird ein Gerät ersetzt oder eine Quell-Entität umbenannt, bleibt sonst ein „Geisterkind“ zurück. Battery Guard entfernt Geräte, deren Quelle länger als **72 Stunden** nicht mehr gefunden wurde, und meldet das per Benachrichtigung. Geräte ganz ohne Entitäten werden sofort entfernt. Die Karenzzeit überlebt Neustarts und lässt sich in den Optionen ändern (0 = Aufräumen aus).

## Entitäten

Pro überwachter Batterie (alle in der Kategorie *Diagnose*):

| Entität | Inhalt |
|---|---|
| Batteriestatus | Status, Füllstand, Quelle, Raum, zuletzt gesehen, Verbrauch/Tag, Tage bis leer, Trend |
| Health Score | 0–100 mit Teilwerten |
| Tage bis leer | nur bei Batterien mit Prozentwert |
| Letzter Batteriewechsel | Zeitstempel; Attribute: Batterietyp, Anzahl, Anzahl Wechsel, letzte Notiz, letzte Wechsel |

Dazu ein Gerät **Battery Guard** mit dem Sensor **Übersicht**: Zustand = schlechtester Status im Haushalt; Attribute: `monitored_devices`, `counts`, `needs_attention`, `average_health_score`, `shopping_list`.

## Dienste

| Dienst | Zweck |
|---|---|
| `battery_guard.log_change` | Batteriewechsel eintragen (Gerät, optional Typ, Anzahl, Notiz, Datum) |
| `battery_guard.set_battery_info` | Batterietyp und Anzahl hinterlegen, ohne einen Wechsel einzutragen |
| `battery_guard.clear_history` | Wechsel-Historie eines Geräts löschen (z. B. Testeinträge) |

## Optionen

Einstellungen → Geräte & Dienste → Battery Guard → Konfigurieren:

| Option | Standard |
|---|---|
| Beobachten ab / Niedrig ab / Kritisch ab | 40 / 25 / 15 % |
| Offline nach | 48 Stunden |
| Aktualisierungsintervall | 5 Minuten |
| Verlaufsfenster für die Prognose | 14 Tage |
| Prognose neu berechnen alle | 6 Stunden |
| Batteriewechsel automatisch erkennen | an |
| Sprung-Schwelle dafür | 40 Prozentpunkte |
| Karenzzeit für verwaiste Geräte | 72 Stunden (0 = aus) |

## Dashboard-Karte

Battery Guard bringt eine **eigene Karte** mit. Sie braucht keine weiteren Karten oder Erweiterungen und lädt sich mit der Integration selbst – es muss keine Ressource eingerichtet werden.

Hinzufügen: Dashboard bearbeiten → *Karte hinzufügen* → **Battery Guard**, oder per YAML:

```yaml
type: custom:battery-guard-card
```

Die Karte zeigt:
- Zähler je Status (kritisch, niedrig, beobachten, offline, ok) und den durchschnittlichen Health Score
- alle Batterien **nach Raum gruppiert** (der Bereich „Sonstiges“ zuletzt), kritische Geräte zuerst
- pro Gerät Füllstand, Tage bis leer und Health Score; ein Tipp klappt die Details auf (Trend, Verbrauch, letzter Wechsel, Batterietyp)
- in den Details: **„Batterie gewechselt“** und **„Typ speichern“** direkt aus dem Dashboard
- die Einkaufsliste

Optionen (alle optional):

| Option | Standard | Bedeutung |
|---|---|---|
| `title` | „Battery Guard“ | Titel der Karte |
| `show_overview` | `true` | Zähler je Status anzeigen |
| `show_shopping_list` | `true` | Einkaufsliste anzeigen |
| `hide_ok` | `false` | Geräte mit Status *ok* ausblenden, nur Handlungsbedarf zeigen |

Die Karte findet neue Geräte selbst und folgt der Sprache von Home Assistant (Deutsch oder Englisch). Nach einem Update der Integration den Browser-Cache leeren, falls die Karte noch alt aussieht.

## Installation

**HACS (empfohlen)**
1. HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/Zwieback80/battery-guard` als *Integration* hinzufügen.
2. *Battery Guard* installieren und Home Assistant neu starten.
3. Einstellungen → Geräte & Dienste → *Integration hinzufügen* → **Battery Guard**.

**Manuell:** Den Ordner `custom_components/battery_guard` nach `config/custom_components/` kopieren, neu starten, Integration hinzufügen.

Battery Guard erlaubt nur eine Instanz.

## Sprachen
Integration und Karte gibt es auf **Deutsch und Englisch** und folgen der Sprache von Home Assistant; andere Sprachen fallen auf Englisch zurück.

## Lizenz und Nutzungsbedingungen
Battery Guard steht unter der [PolyForm Noncommercial License 1.0.0](LICENSE). Du darfst es privat und für andere nicht-kommerzielle Zwecke nutzen, ändern und weitergeben. **Kommerzielle Nutzung ist nicht gestattet.** Maßgeblich ist der vollständige Lizenztext in der Datei `LICENSE`, siehe auch `NOTICE`.

Copyright (c) 2026 Christian Brandt · christianbrandt@mailbox.org
