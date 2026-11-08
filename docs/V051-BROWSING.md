# Handheld Atlas 0.5.1 – Karten, Galerien und Handheld-Navigation

## Lokal ausprobieren

Das neu gebaute `Handheld-Atlas.html` enthält den Katalog zum **Zeitpunkt des Builds** und kann über `file://` ohne Konto geöffnet werden. Browser und Android-WebView benötigen eine Internetverbindung, um externe Bilder der Originalquellen abzurufen. Die Datei aktualisiert sich **nicht selbst**. Der Workflow `Update downloadable HTML snapshot` erzeugt nach Datenänderungen eine neue Datei.

## Medien pro Spiel

- **Suche:** horizontale Karte mit Originalspiel-Screenshots; Cover wird mit Quelle als kleines Inset angezeigt, wenn vorhanden. Manuell über kleine Pfeile; bei Maus-Hover/Focus rotiert die Vorschau automatisch.
- **Dual-Screen-Bilder priorisieren:** Nutzer-Schalter in der Suche. Bevorzugt echte, dem Spielweg zugeordnete Dual-Screen-Bilder. Wenn keine vorhanden sind, bleiben Originalspielbilder bzw. Cover sichtbar. Der Schalter ist nur eine **Ansichtspräferenz**, keine Gerätedetektion.
- **Details oben:** ausschließlich allgemeine Originalspiel-Screenshots. Ohne solche Bilder wird ein ehrlicher Hinweis angezeigt. Keine willkürliche Mod-Galerie als Originalbild.
- **Spielwege:** jeder bereits bebilderte Spielweg hat eine **eigene Bildergalerie**; Pfeile, direkte Vorschau-Auswahl, Pfeiltasten und Touch-Swipe blättern. Die Quelle ist verlinkt.
- **Zusätzliche Kandidaten:** unbestätigte Projektbilder bleiben als solche gekennzeichnet.

## Bedienung

- Desktop: links/rechts im Dialog auf dem Galerie-Element, PageUp/PageDown, `[` / `]`; Vorschaubild anklicken.
- Touch: Pfeiltasten innerhalb der Galerie oder horizontal wischen.
- Gamepad: Standard-Gampepads können über die Browser-Gamepad-API **L1/R1 (Buttons 4/5)** zur Galerie-Navigation auslösen. Existierende D-Pad-Navigation bleibt erhalten. **Die tatsächliche AYN-Thor-Tastenbelegung ist noch nicht auf Hardware getestet.**
- Ein späterer nativer Android-Wrapper kann `window.HandheldAtlasBridge.getCapabilities()` bereitstellen. Nur ein ausdrücklich bestätigtes `dualScreen: true` aktiviert automatisch die entsprechende Bilderpräferenz; eine manuelle Nutzerauswahl hat Vorrang. Ein gewöhnlicher Webbrowser erkennt die physischen Thor-Displays nicht zuverlässig.

## Index und Vertrauensstatus

Der allgemeine Spieleindex enthält jetzt zusätzliche GameCube-, Wii-, PSP-, Dreamcast-, PS-Vita-, Mega-Drive-, PS2- und 3DS-Titel. Neue Index-Einträge tragen `indexSource: editorial-name-only-v051` und sind **keine** geprüften Editionen, Spielwege, Downloads oder Leistungsdaten. Der Import ist in `scripts/expand_index.py` wiederholbar und idempotent. Franchise-Gruppen beruhen auf einfachen Titelregeln und müssen für knifflige Reihen noch manuell verifiziert werden.

Für Morrowind sind zusätzliche, quellenverlinkte Performance- und Content-Mods hinterlegt, ohne daraus pauschale Android-Kompatibilität zu folgern. OpenMW unterscheidet sich von Morrowind.exe; MWSE-, MCP- und MGE-XE-Abhängigkeiten sind deshalb nicht automatisch kompatibel.

## Offene Aufgaben

Die Cover- und Originalscreenshots-Pipeline deckt noch nicht alle Titel ab. Für Nintendo-exklusive Spiele benötigen wir eine autorisierte Medienquelle, bevor die passenden Bilder eingeblendet werden können. Eine echte Android-APK, aktive Dual-Screen-Gerätedetektion, reale Thor-Tests und verifizierte Schulterbelegung bleiben getrennte Entwicklungsaufgaben.
