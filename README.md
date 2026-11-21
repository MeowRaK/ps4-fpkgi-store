# PS4 FPKGi+ Catalog — GitHub-ready builder

This is the **PS4** equivalent of your PS3 catalog project. It does not modify `MeowRaK/ps3-rpcs3-store`.

Two distinct outputs prevent the problem encountered with disc-only PS3 games:

- `PS4_LIBRARY.json`: a broad searchable *title-ID metadata library*, using the `ps4_titles.csv` published by [Axekinn/ps4-scraper](https://github.com/Axekinn/ps4-scraper). The upstream CSV currently has ~49,057 title records. This does **not** mean ~49,057 unique games or downloads.
- `GAMES.json`: an FPKGi-compatible download catalog, initially sourced from [Dinos17/FPKGi-Catalog-Hub](https://github.com/Dinos17/FPKGi-Catalog-Hub) with roughly 873 current index entries, filtered/deduplicated by the builder. Those entries point to third-party package sources; a listing does **not** verify the file is downloadable, safe, correctly packaged, or legally licensed. Only obtain content you have the rights to use.

The project does not include or host commercial game files, keys, decryptors, or licenses. The public source could contain dead links or incorrect entries. PSN update packages aren't the same thing as installable fake PS4 game packages.

## One-time setup

1. Create a **new public GitHub repository** named `ps4-fpkgi-store` at https://github.com/new. Leave your existing PS3 repo untouched.
2. Extract this ZIP. Upload **everything**, including `.github/workflows/update-ps4-catalog.yml`, at the repo root. Preserve the folder paths. Do not upload the ZIP itself as the only file.
3. Open **Actions → Build PS4 catalog**. Check the run; use **Run workflow** if it did not start automatically.
4. When GitHub Actions succeeds, it commits four generated JSON files: `GAMES.json`, `PS4_LIBRARY.json`, `PS4_LANGUAGE_EXCLUDED.json`, and `catalog_report.json`.
5. The direct FPKGi catalog URL will be:

   `https://raw.githubusercontent.com/MeowRaK/ps4-fpkgi-store/main/GAMES.json`

   This URL won't work until you create the repository and the workflow completes.

6. On the GoldHEN PS4, use **FPKGi+ → Settings → Content sources → Games** and paste the URL, then ensure **Populate via web** is on and reload the lists.
7. If the online source doesn't load (as happened with PS3), download `GAMES.json` from GitHub and transfer through FTP to:

   `/data/FPKGiPlus/ContentJSONs/GAMES.json`

   Then set **Games → Local files**, **Populate via web → OFF**, and **Reload content lists**.

**PS3 stays in Demos**, if that is how you configured it. **PS4 goes in Games**. Download/installation is handled by FPKGi+; do not try to install PS3 packages as PS4 apps.

## View the full PS4 library

Upload the included `index.html` as well. In the new repository go to **Settings → Pages → Deploy from a branch → main → /(root)**. Once published, browse:

`https://meowrak.github.io/ps4-fpkgi-store/`

The website's search includes metadata-only titles, marked `Metadata only` so they do not look like fake download buttons. It is independent of FPKGi+.

## English language filtering

The builder excludes packages with explicit non-English edition labels, such as `(German)`, `(Italy/Spain)` or `[GER]`, **unless English is explicitly marked**. It keeps region variants with unknown language. Region alone (EU, USA, Japan) isn't enough to prove language support. This filter is deliberately conservative and is not a complete audio/subtitle language verifier.

- `PS4_LANGUAGE_EXCLUDED.json` shows excluded entries.
- `catalog_report.json` shows source, skips, counts, and metadata-only records.
- To manually block a confirmed non-English CUSA ID, add it to `excluded_title_ids` in `sources.json`.
- If you own/host authorized PKGs, add entries using the same FPKGi `DATA` format to `GAMES_CUSTOM.json` and commit. The workflow merges them.
- Additional FPKGi JSON feeds can be added as objects under `catalog_sources` in `sources.json`. Do not assume third-party feed links are functional or authorized.

Example of adding your own authorized download entry:

```json
{
  "DATA": {
    "https://your-server.example/your-game.pkg": {
      "title_id": "CUSA12345",
      "name": "Your game title",
      "size": 123456789,
      "region": "USA",
      "version": "01.00",
      "release": null,
      "min_fw": null,
      "cover_url": null
    }
  }
}
```

This example is intentionally NOT a real game or a real URL.

## Run locally (optional)

Python 3.10+; no extra dependencies:

```
python -m unittest discover -s tests -v
python build_ps4_catalog.py --config sources.json --output .
```

The Github workflow uses Node 24-compatible `actions/checkout@v7` and `actions/setup-python@v7`, and runs weekly plus when builder/config files change. Source updates don't necessarily mean download-link availability has been verified. On a network error or empty catalog, the builder exits instead of overwriting a previously working `GAMES.json`.

## Important limitations

- The 49k title-ID records are broader than the 873 package listings; a PS4 game without a PKG source remains visible **only in the metadata website**, not the FPKGi+ Games tab.
- A PKG reference alone does not establish authorization, correct firmware support, download health, or GoldHEN compatibility.
- No retail game files, purchase entitlements, or decrypted content are included in this project.
- Output is *not pre-built* in this ZIP because this execution environment cannot fetch large live source files. GitHub Actions is designed to perform that live build on the repository you create.
