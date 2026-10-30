#!/usr/bin/env python3
"""Pre-publish check for data/costs.csv.

A basic guard against common data-entry mistakes; it does not replace a manual
review. Exit 0 = pass, 1 = fail.

Requires a local deny list (one term per line), read from the file named in the
CHECK_DENY_FILE environment variable, or from scripts/deny.local.txt. That file
is gitignored and must never be committed. The check fails if it is missing or
empty.
"""
import csv, math, os, re, sys
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "costs.csv"
DEFAULT_DENY = Path(__file__).resolve().parent / "deny.local.txt"

COLUMNS = ["month", "category", "item", "list_price_usd", "billing", "source_url", "as_of", "note"]
ALLOWED_CATEGORIES = {"AI subscriptions", "Cloud", "Domains", "Tools"}
ALLOWED_BILLING = {"monthly", "annual", "free", "usage-based"}
# Vendor pricing pages this file may cite. Add a vendor's domain here when adding its row.
ALLOWED_SOURCE_HOSTS = {"x.ai", "docs.x.ai", "github.com", "docs.github.com", "claude.com", "chatgpt.com"}
PLACEHOLDER = "PLACEHOLDER"
# Usage-based lines with no fixed list price; shown as "Varies monthly" and left out of the total.
VARIES = "VARIES"
PLACEHOLDER_WORDS = re.compile(r"placeholder|to be confirmed|not yet confirmed|\btbc\b|\btbd\b", re.I)

# Generic patterns for things that belong on a bill, not on this page.
TEXT_PATTERNS = [
    (r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)", "card-number-like digit run"),
    (r"(?<!\d)\d{7,}(?!\d)", "long digit run (possible account or invoice id)"),
    (r"\b(?:acct|account)\b[\s_#:.-]*(?:id|no|number)?[\s#:.-]*\w*\d", "account id"),
    (r"\b[a-z]{2,6}[-_#]\d{3,}\b", "id-like code (e.g. INV-123)"),
    (r"#\s*\d{3,}", "numbered reference"),
    (r"\b(?:ending|last\s*4|last\s*four)\b\D{0,10}\d{4}\b", "card digits"),
    (r"[\w.+-]+@[\w-]+\.[\w.-]+", "email address"),
    (r"\b(?:charged|charge|bill|bills|billed|invoice|invoiced|receipt|statement)\b", "bill or charge wording"),
    (r"\b\d+(?:\.\d+)?\s*(?:gb|tb|mb|gib|tib|gb-hours?|hours?|hrs|requests|tokens|vcpu|instances?)\b", "usage amount"),
    (r"\b\d{4}-\d{2}-\d{2}\b", "full date outside as_of (possible charge date)"),
]


class Report:
    def __init__(self):
        self.items = []

    def add(self, msg):
        if msg not in self.items:
            self.items.append(msg)


def tokens(s):
    return re.findall(r"[a-z0-9]+", s.lower())


def load_deny(rep):
    path = Path(os.environ.get("CHECK_DENY_FILE") or DEFAULT_DENY)
    if not path.is_file():
        rep.add(f"deny list not found at {path} (set CHECK_DENY_FILE or create scripts/deny.local.txt)")
        return None
    terms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        anywhere = line.startswith("*")
        t = tokens(line.lstrip("*"))
        if t:
            terms.append((line.lstrip("*").lower(), t, anywhere))
    if not terms:
        rep.add(f"deny list at {path} is empty")
        return None
    return terms


def deny_hits(text, terms):
    """Whole-word match on the lowercased text, also across spaces/punctuation
    (consecutive word pieces joined), plus substring match for '*' terms."""
    toks = tokens(text)
    joined_all = "".join(toks)
    hits = []
    for label, ttoks, anywhere in terms:
        target = "".join(ttoks)
        found = False
        # plain form: term tokens appear as consecutive whole tokens
        n = len(ttoks)
        for i in range(len(toks) - n + 1):
            if toks[i:i + n] == ttoks:
                found = True
                break
        # de-spaced form: consecutive tokens that join to exactly the term
        if not found:
            for i in range(len(toks)):
                acc = ""
                for j in range(i, len(toks)):
                    acc += toks[j]
                    if acc == target:
                        found = True
                        break
                    if len(acc) >= len(target) or not target.startswith(acc):
                        break
                if found:
                    break
        if not found and anywhere and target in joined_all:
            found = True
        if found:
            hits.append(label)
    return hits


def check_url(url, where, rep):
    if not url.startswith("https://"):
        rep.add(f"{where}: source_url must start with https://")
        return
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
    except ValueError:
        rep.add(f"{where}: source_url is not a valid URL")
        return
    if not host or "." not in host:
        rep.add(f"{where}: source_url has no real host")
        return
    if host not in ALLOWED_SOURCE_HOSTS:
        rep.add(f"{where}: source_url host '{host}' is not on the vendor allowlist in check.py")
    if parts.query or parts.fragment or parts.username or parts.password or parts.port:
        rep.add(f"{where}: source_url must not carry query strings, fragments, ports or credentials")
    if re.search(r"\d{4,}", parts.path):
        rep.add(f"{where}: source_url path contains a long digit run")
    if re.search(r"(?:utm_|[?&/]ref[=/_-]|referral|affiliate|aff_id)", url, re.I):
        rep.add(f"{where}: source_url looks like a tracking or referral link")


def main():
    rep = Report()
    terms = load_deny(rep)

    header, rows = None, []
    try:
        with CSV_PATH.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f, strict=True)
            header = next(reader, None)
            for rec in reader:
                rows.append((reader.line_num, rec))
    except csv.Error as e:
        rep.add(f"costs.csv could not be parsed (unterminated quote or bad quoting): {e}")
        rows = []
    except (OSError, UnicodeDecodeError) as e:
        rep.add(f"costs.csv could not be read: {e}")

    if header != COLUMNS:
        rep.add(f"header must be exactly {','.join(COLUMNS)}")
    if not rows and not rep.items:
        rep.add("no data rows")

    for line, rec in rows:
        where = f"line {line}"
        if rec == [] or rec == [""]:
            continue
        if len(rec) != len(COLUMNS):
            rep.add(f"{where}: expected {len(COLUMNS)} columns, found {len(rec)}")
            continue
        r = dict(zip(COLUMNS, (v.strip() for v in rec)))
        text = " ".join(r.values())

        if terms:
            for label in deny_hits(text, terms):
                rep.add(f"{where}: matches a term on the local deny list ('{label}')")

        non_url = " ".join(r[k] for k in COLUMNS if k not in ("source_url", "as_of", "month"))
        for pat, label in TEXT_PATTERNS:
            if re.search(pat, non_url, re.I):
                rep.add(f"{where}: {label}")
        # digit runs / ids hidden in the URL
        for pat, label in TEXT_PATTERNS[:3]:
            if re.search(pat, r["source_url"], re.I):
                rep.add(f"{where}: {label} in source_url")

        m = re.fullmatch(r"(\d{4})-(\d{2})", r["month"])
        if not m or not 1 <= int(m.group(2)) <= 12:
            rep.add(f"{where}: month must be YYYY-MM with month 01-12")
        if r["category"] not in ALLOWED_CATEGORIES:
            rep.add(f"{where}: category '{r['category']}' is not on the allowlist")
        if r["billing"] not in ALLOWED_BILLING:
            rep.add(f"{where}: billing '{r['billing']}' must be one of {sorted(ALLOWED_BILLING)}")
        if not r["item"]:
            rep.add(f"{where}: item is empty")

        price = r["list_price_usd"]
        if price == VARIES:
            if r["billing"] != "usage-based":
                rep.add(f"{where}: list_price_usd {VARIES} is only allowed with billing usage-based")
            if r["source_url"]:
                check_url(r["source_url"], where, rep)
            continue
        if price.upper() == VARIES:
            rep.add(f"{where}: use exactly {VARIES} (uppercase) for a usage-based line")
            continue
        if price == PLACEHOLDER:
            if r["source_url"]:
                check_url(r["source_url"], where, rep)
            continue
        if price.upper() == PLACEHOLDER or PLACEHOLDER_WORDS.search(r["item"] + " " + r["note"]):
            rep.add(f"{where}: row is labelled as a placeholder but list_price_usd is not exactly {PLACEHOLDER}")
            continue
        if not re.fullmatch(r"\d+(?:\.\d{1,2})?", price):
            rep.add(f"{where}: list_price_usd must be a plain non-negative number like 20.00, {PLACEHOLDER} or {VARIES}")
        else:
            v = float(price)
            if math.isnan(v) or math.isinf(v) or v < 0:
                rep.add(f"{where}: list_price_usd must be a finite number >= 0")
        if not r["source_url"]:
            rep.add(f"{where}: confirmed row needs a source_url")
        else:
            check_url(r["source_url"], where, rep)
        try:
            d = date.fromisoformat(r["as_of"]) if re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["as_of"]) else None
        except ValueError:
            d = None
        if d is None:
            rep.add(f"{where}: confirmed row needs as_of as a real date (YYYY-MM-DD)")
        elif d > date.today():
            rep.add(f"{where}: as_of is in the future")

    if rep.items:
        print("CHECK FAILED")
        for e in rep.items:
            print(" -", e)
        return 1
    print(f"CHECK PASSED: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
