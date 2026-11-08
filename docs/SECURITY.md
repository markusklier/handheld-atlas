# Sicherheitsgrenzen des MVP

- Keine Kommandos aus Quellen ausfuehren. Keine APKs, ROMs oder Bibliotheken laden.
- Keine Credentials im Frontend. GITHUB_TOKEN nur in der Prozessumgebung/CI.
- GitHub-Client laesst Redirects nur zur HTTPS-api.github.com-Domain zu.
- Maximal 6 MB pro API-Antwort, Timeout, ETag, serielle Requests, Stop bei Rate Limit.
- Datenimport trennt Kandidaten und freigegebene Katalogeintraege.
- Browser-Links nur HTTPS ohne Benutzername/Passwort; HTML wird escaped.
- Inline-JavaScript mit CSP-Hashes, keine externen Laufzeit-CDNs, kein eval.
- Merkliste importiert nur bekannte IDs, begrenzt die Dateigroesse und verwirft
  unbekannte Features. Importdaten sind keine Anweisungen.
- Der lokale Preview-Server bindet standardmaessig nur 127.0.0.1.
- ReadOnly-Setup-Export erzeugt KEIN Backup und veraendert KEIN Android-Geraet.

Vor oeffentlichem Betrieb: Actions auf gepruefte SHAs pinnen, Branch-Schutz,
Maintainer-Review, Abhaengigkeitspruefung, TLS, Datenschutz-/Kontaktseite und
Ablauf fuer Rechtebeschwerden einrichten. Vor automatischer APK-Installation
ist eine separate Sicherheitsanalyse erforderlich.

Vertrauensgrenze: Wer deinen gehosteten HTML/JS-Build veraendern kann, kann auch
den Client veraendern. CSP-Hashes ersetzen keine sichere Build-/Deploy-Kette.
Service Worker werden automatisch aktualisiert; ein Rollout-/Rollback-Test ist
vor breiter Nutzung notwendig. Dieses Paket ist kein zertifiziertes Produkt.
