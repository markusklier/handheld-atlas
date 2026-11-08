# Quality assurance / 0.1

Automated checks available:

- 10 Node unit tests: filtering, platform separation, exact evidence semantics,
  watchlist conditions, import sanitation, and URL/HTML escaping.
- 10 Python tests: catalog validation, candidate extraction and deduplication,
  baseline-vs-news behavior, rate limit handling, network failure preservation,
  partial-run freshness, and mocked end-to-end sync.
- Browser interaction smoke test and desktop/mobile layout inspection.

The browser runtime and external GitHub HTTP path are separate systems.
No real Thor, physical controller, external GitHub Actions runner, APK installation,
store publication, or device performance benchmark has been tested here.
The sandbox blocks outbound Python HTTP and browser HTTP navigation. Browser tests
therefore load the built HTML directly via Playwright set_content. Live API sync,
HTTPS service-worker lifecycle, offline reload and OS-level PWA installation need
an additional test after deployment. Do not describe those as already deployed.

There are no imported compatibility reports or fabricated FPS measurements.
Missing measurements remain null, and the 60-FPS-measured filter is empty.

Result: 20 unit/integration checks passed (10 Node, 10 Python). The browser
smoke run passed 8 interaction groups, including responsive layout and exports.
Storage was supplied by an in-memory fixture because about:blank has no origin.
