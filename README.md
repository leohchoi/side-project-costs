# Side-project costs

A small static page showing what my side projects cost each month, using vendors' public list prices (not actual bills). Plain HTML, CSS and JS; no libraries, CDNs, fonts, trackers or analytics. Works as-is on GitHub Pages.

## Files

- `index.html`, `style.css`, `app.js`: the page. `app.js` reads `data/costs.csv` and draws the table and a bar chart (inline SVG).
- `data/costs.csv`: the data. One row per line item per month.
- `scripts/check.py`: a basic pre-publish check for common data-entry mistakes in `costs.csv`. Run it before every publish. It does not replace reading the rows yourself.
- `scripts/deny.local.txt`: a local list of terms that must never appear in the data. **Gitignored and required**: `check.py` fails if it is missing or empty. Keep it on your own machine only; never commit it. You can point to a different file with the `CHECK_DENY_FILE` environment variable.

## CSV columns

`month,category,item,list_price_usd,billing,source_url,as_of,note`

- `month`: `YYYY-MM`. The page shows the latest month in the file.
- `category`: one of `AI subscriptions`, `Cloud`, `Domains`, `Tools`.
- `item`: plan name as shown on the vendor's public pricing page. Usage-based services go in a generic line (for example "Cloud hosting & compute"), not by vendor name.
- `list_price_usd`: monthly list price as a plain number (`200.00`, `0.00`); exactly `VARIES` for a usage-based line with no fixed list price (billing must be `usage-based`; shows as "Varies monthly"); or exactly `PLACEHOLDER` if not confirmed yet (shows as "To be confirmed"). `VARIES` and `PLACEHOLDER` rows are left out of the total.
- `billing`: `monthly`, `annual`, `free` or `usage-based`.
- `source_url`: the vendor's public pricing page, https, with no query string or tracking parameters. Its domain must be on the allowlist in `check.py`; add a new vendor's domain there when you add its row.
- `as_of`: `YYYY-MM-DD` date the price was checked on that page. Required unless the row is a placeholder.
- `note`: short and factual. Only include claims that the cited page shows.

## Monthly update

1. Copy last month's rows and change `month` to the new month.
2. Re-open each `source_url` and check the list price. Update `list_price_usd` and `as_of`. If a price can't be confirmed, use `PLACEHOLDER` with the note "Placeholder, not yet confirmed".
3. Add or remove rows only for things actually used that month. Usage-based lines stay `VARIES` with the note "Varies monthly (usage-based), not counted."
4. Run `python3 scripts/check.py`. It must print `CHECK PASSED`.
5. Preview locally: `python3 -m http.server 8000` in this folder, then open `http://127.0.0.1:8000/`. (Opening `index.html` directly from disk won't load the CSV in most browsers.)
6. Commit and push. Older months stay in the CSV as history.

## Never put in this repo

- Bills, receipts or screenshots of them, even briefly (git history keeps them).
- Account IDs, reference numbers, card digits, email addresses or other personal details.
- Negotiated or private pricing. Public list prices only.
- Affiliate or referral links. If that ever changes, the footer must disclose it.
- `scripts/deny.local.txt`.
