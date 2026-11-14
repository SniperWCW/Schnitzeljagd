# Schnitzeljagd für Home Assistant

Eine generische, konfigurierbare **Schnitzeljagd-Steuerung** als HACS-Integration. Stationen, Aufgaben (Erfolgshaken), Videos, Audios und Lichteffekte konfigurierst du komplett in der Home-Assistant-Oberfläche (alternativ per YAML-Import). Die Integration liefert dafür Entities und Services, mit denen du die Jagd bequem vom Handy oder Tablet aus steuerst.

Entstanden für einen Kindergeburtstag: Drache **Funkel** und Einhorn **Luna** führen durch 6 Stationen im Haus. Die komplette Beispieljagd liegt als Vorlage bei.

## Was sie kann

- **Stationen** mit Einleitungsclip ("Szene starten") und optionalen Zusatz-Clips (z. B. "Finale Teil 1")
- **Aufgaben** mit Erfolgshaken: Einschalten löst die Erfolgsaktionen genau einmal aus (Video, Audio, Regenbogen-LEDs, ...)
- **Fortschritt** in Prozent, aktuelle Station, "Spiel läuft"
- **Schatz**: wird nach einer bestimmten Aufgabe freigegeben (oder manuell im Notfall)
- **Vorbereiten / Medien-Stopp / Zurücksetzen** als Buttons
- Alle Aktionen sind **normale HA-Skript-Aktionen** (`service`, `delay`, `choose`, `wait_for_trigger`, ...), also funktioniert alles, was Home Assistant steuern kann
- Zustand bleibt nach einem Neustart erhalten
- Events für eigene Automationen: `schnitzeljagd_task_completed`, `schnitzeljagd_station_changed`

## Installation

1. HACS → ⋮ → *Benutzerdefinierte Repositories* → `https://github.com/SniperWCW/Schnitzeljagd` als Typ *Integration*
2. "Schnitzeljagd" installieren, Home Assistant neu starten
3. *Einstellungen → Geräte & Dienste → Integration hinzufügen → Schnitzeljagd* und wählen:
   - **Neue, leere Jagd**: du baust alles selbst in der UI
   - **Beispieljagd „Funkel & Luna“**: 6 Stationen, 7 Aufgaben als Vorlage (Geräte und Medien sind Platzhalter)
   - **Aus YAML-Datei importieren**: für bestehende Jagd-Dateien

## Konfiguration in der UI

*Einstellungen → Geräte & Dienste → Schnitzeljagd → Konfigurieren* öffnet den Editor:

| Menüpunkt | Inhalt |
|---|---|
| Allgemein | Name, Untertitel, Icon |
| Stationen | hinzufügen, bearbeiten, löschen; je Station die **Aktionen beim Start** (Einleitungsclip) |
| Aufgaben | Erfolgshaken mit **Aktionen bei Erfolg**, zugehöriger Station und optionalem Wechsel zur nächsten Station |
| Zusatz-Clips | zusätzliche manuelle Buttons je Station (z. B. „Finale Teil 1“) |
| Vorbereiten, Stopp, Zurücksetzen | globale Aktionen (Rollos schließen, Medien stoppen, ...) |
| Schatz | durch welche Aufgabe er freigegeben wird und was dabei passiert |
| Aus YAML importieren | ersetzt die gesamte Konfiguration durch eine Datei |

Alle Aktionen bearbeitest du mit dem **normalen Home-Assistant-Aktionseditor** (wie bei Skripten): Medien abspielen, Licht, Wartezeiten, Bedingungen usw. Änderungen gelten erst nach **Speichern und beenden**; danach lädt die Integration neu. Entities gelöschter Stationen, Aufgaben und Clips werden automatisch entfernt. Der Spielstand (Haken, aktuelle Station) bleibt erhalten, soweit die Einträge noch existieren.

Hinweis: Stationen werden nummeriert in der Reihenfolge ihres Anlegens (1, 2, 3, ...), Aufgaben bekommen ihre ID aus dem Namen. Medien sprichst du über die HA-Medienquelle an, z. B. `media-source://media_source/local/schnitzeljagd/video/1A.mp4`.

## Referenz: YAML-Format

Das Format ist identisch mit dem, was die UI intern speichert, und dient zum Import oder als Referenz.

```yaml
name: Meine Jagd
subtitle: Untertitel

on_prepare: [...]   # "Spiel vorbereiten" (z. B. Rollos schließen)
on_stop: [...]      # "Medien-Stopp"
on_reset: [...]     # "Zurücksetzen"

treasure:
  released_by: schatz     # ID der Aufgabe, die den Schatz freigibt
  release: [...]          # Aktionen bei Freigabe

stations:
  - id: "1"
    name: Esszimmer
    icon: mdi:silverware-fork-knife
    description: Freitext für dich als Spielleitung
    intro: [...]          # Aktionen bei "Station starten"
    clips:                # optionale Zusatz-Buttons
      - id: finale_1
        name: Finale Teil 1 starten
        actions: [...]

tasks:
  - id: schatz
    name: Schatz gefunden
    station: "6"
    on_complete: [...]    # läuft genau einmal beim Haken
    next_station: "2"     # optional: danach automatisch weiterschalten
```

Alle Aktionslisten sind Standard-HA-Aktionen. Zusätzlich stehen dir in Aktionen die Variablen `station`, `progress` und `hunt` zur Verfügung. Ein vollständiges Beispiel steht in [`examples/funkel_luna.yaml`](custom_components/schnitzeljagd/examples/funkel_luna.yaml).

### Automatische Übergänge

Weil Aktionen normale Skripte sind, lassen sich Abläufe wie "Nach Video 2B: 10 Sekunden warten, dann Audio 3A in Station 3" direkt in `on_complete` schreiben:

```yaml
on_complete:
  - service: media_player.play_media
    target: { entity_id: media_player.gaestezimmer_tv }
    data: { media_content_id: media-source://media_source/local/video/2B.mp4, media_content_type: video/mp4 }
  - delay: "00:00:10"
  - service: schnitzeljagd.start_station
    data: { station: "3" }
```

## Entities

Pro Jagd entsteht ein Gerät mit:

| Entity | Zweck |
|---|---|
| `sensor` Aktuelle Station / Fortschritt | Anzeige für die Spielleitung |
| `binary_sensor` Spiel läuft / Schatz freigegeben | Status |
| `select` Station | Station manuell wählen |
| `switch` je Aufgabe | Erfolgshaken (an = Aktionen laufen einmal; aus = Haken ohne Aktion zurücknehmen) |
| `button` Spiel vorbereiten, Medien-Stopp, Spiel zurücksetzen, Schatz manuell freigeben | Steuerung |
| `button` je Station / je Clip | Einleitung bzw. Zusatzaktion starten |

## Lovelace-Karte (mitgeliefert)

Die Integration bringt eine eigene Spielleitungs-Karte mit. Sie wird automatisch als Frontend-Ressource registriert, du musst nichts unter *Ressourcen* eintragen (nach der Installation ggf. Browser-Cache leeren bzw. App neu laden).

```yaml
type: custom:schnitzeljagd-card
entity: sensor.funkel_luna_fortschritt   # irgendeine Entity der Jagd genügt
title: Spielleitung                      # optional
show_stations: true                      # optional: Stationen mit Aufgaben anzeigen
```

Die Karte zeigt Fortschrittsring, aktuelle Station, Spielstatus und Schatz, Buttons für Vorbereiten, Medien-Stopp, Zurücksetzen und Schatz-Freigabe, eine Stationsauswahl sowie je Station den Start-Button, Zusatz-Clips und die Erfolgshaken. Alle weiteren Entities findet sie selbst über das Gerät der Jagd. Sie ist über den visuellen Editor konfigurierbar und läuft mobil wie am Desktop.

Alternativ liegt ein Beispiel aus Standardkarten in [`dashboard/example_dashboard.yaml`](dashboard/example_dashboard.yaml).

## Services

`schnitzeljagd.prepare`, `stop`, `reset`, `set_station`, `start_station`, `complete_task`, `release_treasure`, `reload_hunt`. Bei mehreren Jagden gibst du zusätzlich `config_entry` an.

## Entwicklung

```bash
pip install pytest pyyaml
pytest tests
node tests/card.test.js
```

Die Spiellogik (`model.py`, `engine.py`) kommt ohne Home Assistant aus und ist getestet, ebenso die Entity-Erkennung und das Rendering der Karte (mit Browser-Stubs). Die HA-Anbindung (`manager.py`, Plattformen, Config-Flow, Karten-Registrierung) wurde bisher nur geschrieben und syntaktisch geprüft, aber noch nicht in einer echten HA-Instanz ausgeführt.

## Roadmap

- Stationen per Klick umsortieren
- Export der Jagd als YAML
- Übersetzung der Entity-Namen für weitere Sprachen

Lizenz: MIT
