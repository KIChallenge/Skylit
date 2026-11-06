# Antwortangaben und Transparenz

`AnswerFooter` und `TransparencyDrawer` stehen unter `@/features/transparency` bereit.
Die Exporte verwenden die Domain-Typen aus `@/lib/api`.

| Export | Props | Verhalten |
| --- | --- | --- |
| `AnswerFooter` | `messageId`, `client?`, `initialSources?` | Lädt Angaben zur gespeicherten KI-Antwort und enthält den Drawer. |
| `TransparencyDrawer` | `messageId`, `client?`, `resource?` | Lädt ohne gemeinsame Ressource erst beim Öffnen. |

`AnswerFooterProps` und `TransparencyDrawerProps` stehen als Typ-Exporte bereit.
`client` akzeptiert einen vollständigen `ApiClient`. Ohne `client` verwenden beide Komponenten `api`.
`initialSources` enthält bereits empfangene Quellen aus dem Stream.
`resource` enthält `state` und `retry`. Der Footer übergibt diese Ressource intern.

Übergeben Sie während des Streams `messageId={null}`.
Übergeben Sie die gespeicherte Assistant-ID nach `message.completed`.
Übergeben Sie nach einem Stream-Fehler nur die ID einer bereits gespeicherten Teilantwort.
Die Komponenten prüfen die Speicherung nicht selbst.

## Technische Entscheidung

Der Hook speichert erfolgreiche Angaben und 404-Ergebnisse je Client und Nachrichten-ID.
Der Footer teilt seine Ressource mit dem Drawer. Das Öffnen löst keine zweite Anfrage aus.
Ein ID-Wechsel bricht die Anfrage ab. Der Hook verwirft verspätete Antworten.
Netzwerkfehler bleiben wiederholbar. Der Transport begrenzt die Laufzeit der Anfrage.

Eine gemeinsame globale Ressource könnte parallele Komponenten verbinden.
Der lokale Hook vermeidet zusätzliche Abhängigkeiten und hält injizierte Clients getrennt.
Der Speicher bleibt bis zum Neuladen erhalten. Die Angaben gehören zu gespeicherten Antworten.

Das Backend bestimmt die Sicherheit. Die Komponenten übernehmen Stufe und Begründung unverändert.
Der Drawer liest die Wissenssuche aus `entries`. Das Backend liefert `retrieval` derzeit leer.
Ein fehlender Anbieter erzeugt keinen Betreiberhinweis.

## Vorschau und Prüfung

Die Route `/styleguide/transparency` verwendet ein synthetisches `MessageTransparency`-Objekt mit injiziertem Client.
Die Vorschau benötigt weder Backend noch KI-Modell.

Führen Sie diese Befehle im Projektverzeichnis aus:

```sh
make frontend-setup
make frontend-unit ARGS=src/features/transparency
make frontend-typecheck
make frontend-dev
```

Öffnen Sie die Vorschau am konfigurierten `PORT`.
Prüfen Sie 1440×900 und 1920×1080. Speichern Sie Screenshots außerhalb des Repositorys.

Die Tests prüfen Erfolg, Nullwerte, 404, Netzwerkfehler, Zeitüberschreitung, Wiederholung und Abbruch.
Die Tests prüfen außerdem Quellenlinks, Fokusbindung, Escape und Fokus-Rückkehr mit dem gemeinsamen Sheet.
