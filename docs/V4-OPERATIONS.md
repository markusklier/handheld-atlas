# Handheld Atlas 0.4: Automatic discovery, optional AI and Vision

## Purpose

This is an experimental *source discovery system*, not a catalogue of proven compatibility. It does not install, execute, download APKs, or distribute game files. It separates:

- **Reviewed routes:** `data/catalog.json` and variant-specific credited photographs already in the catalogue.
- **Automatic discoveries:** `data/projects.json` built by `scripts/atlas_v4.py` from trusted-source API leads, source repo monitoring and optional OpenAI web search. Every new finding remains untested.
- **AI observations:** `data/ai_findings.json`, bound to URL evidence actually returned by the API's web-search tool; no hardware claims.
- **Image plausibility checks:** `data/vision_reviews.json`, not a licence, ownership or version check.

## Private use

GitHub Actions works for private repositories subject to your plan's Actions limits. A private GitHub Pages site may require paid plan access. For an offline test, run the **Checks** workflow and download the `handheld-atlas-preview` ZIP artifact. Extract it and serve it with `python3 -m http.server 8765 -d dist`, then open `http://localhost:8765`.

For Pages, configure Settings → Pages → Source → GitHub Actions, add Actions **repository variable** `ATLAS_ENABLE_PAGES` set to `true`, then run **Deploy PWA to GitHub Pages**. The deploy job is intentionally skipped until that variable is enabled, so private preview tests have no misleading red Pages runs. For a non-public test, do not switch your repository visibility to public just to use Pages.

## Scheduled runs / manually focusing on any game

Actions → **Automated Atlas discovery** → Run workflow. Leave `game_id` empty for rotating discovery, or set a known game ID (including items from the broad games index). Enable `run_ai` only after adding `OPENAI_API_KEY` to Settings → Secrets and variables → Actions → Repository secrets.

Daily: observe known sources. Weekly: discover new repositories, rotate four games, and run **one** optional web-search model call and **at most two** optional image model calls if you have provided the key. These are cost limits by request count, **not monetary spending caps**. Configure model access and budget controls separately in your API account. Search results are untrusted.

The workflow updates **data files only** on `main` without PR review. Code changes still require normal code review. If branch rules prohibit Actions from pushing to `main`, you must change those rules or use a separate data branch/pull-request workflow.

`GITHUB_TOKEN` is automatically provided. Optional: `CURSEFORGE_API_KEY` only if authorized by CurseForge. `ATLAS_RESEARCH_MODEL` and `ATLAS_VISION_MODEL` are optional GitHub Actions **variables**; defaults are set in workflow. Never place provider API keys in files, HTML, or commits.

After an automated data commit, GitHub's normal `push` triggers may not fire because commits created using `GITHUB_TOKEN` do not initiate downstream workflows. The Pages workflow additionally listens for `workflow_run` completion, so deployment can run after a successful discovery workflow **when Pages is enabled**.

## Limitations and safety

1. A web-search model may miss relevant projects; not finding a mod never proves it does not exist.
2. A project documentation excerpt is evidence that a project claims something, **not** evidence the game runs on a given device.
3. Screenshot candidates are sourced by URL, with `rights: not-cleared`; model plausibility does not grant redistribution rights. Existing approved Eden-Duo images remain associated with their routes.
4. No new route is silently promoted to a tested configuration, and no executable or install script from source content is ever run.
5. The custom watchlist lives in the user's browser. It is not transmitted to GitHub and does not yet trigger server-side personalized searches or push notifications.
6. The available provider adapters are GitHub/Modrinth; optional CurseForge requires authorization. Forum/Discord/Reddit coverage is not exhaustive and must use permitted interfaces.
7. Secrets are only available at Actions runtime. AI steps are optional; missing secrets cause a clearly logged skip.

## Technical checks

```sh
python3 scripts/atlas_v4.py
python3 scripts/ai_agents.py --research    # no key => skip
python3 scripts/ai_agents.py --vision      # no key => skip
python3 scripts/validate.py
python3 -m unittest discover -s tests -p 'test_*.py'
node --test tests/core.test.cjs
python3 scripts/build.py
```
