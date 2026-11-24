"""Fetches fresh MBA-type jobs from the Adzuna API (India) and writes
jobs.json in the format My Job Agent imports.

Setup:  free keys at https://developer.adzuna.com  ->  set env vars
        ADZUNA_APP_ID and ADZUNA_APP_KEY
Run:    python fetch_jobs.py
"""
import os, re, json, time, urllib.parse, urllib.request

APP_ID, APP_KEY = os.environ["ADZUNA_APP_ID"], os.environ["ADZUNA_APP_KEY"]

# Search phrases, grouped by MBA domain (matches the domains in the agent).
ROLES = [
    # Consulting
    "associate consultant", "management consultant", "strategy consultant",
    # Strategy
    "strategy manager", "corporate strategy", "chief of staff",
    # B2B sales / business development
    "key account manager", "business development manager",
    "enterprise sales manager", "solution sales manager",
    # Sales & marketing
    "marketing manager", "brand manager", "product marketing manager",
    "growth manager", "category manager", "sales manager",
    # Finance
    "financial analyst", "corporate finance manager", "fp&a manager",
    "investment banking associate", "equity research analyst",
    "credit risk manager",
    # Business analytics
    "business analyst", "business analytics manager", "product analyst",
    # Product management
    "product manager", "associate product manager",
    # Operations
    "operations manager", "business operations manager", "program manager",
    # Supply chain & procurement
    "supply chain manager", "procurement manager", "demand planning manager",
    # HR
    "hr business partner", "talent acquisition manager",
]
CITIES = [""]      # "" = all India. Example: ["", "Hyderabad", "Bengaluru"]
MAX_DAYS = 7       # only jobs posted in the last N days
PAGES = 2          # 50 results per page per search

# Optional: put a config.json next to this script to personalise the search.
# Click "Download search config" in the agent to create one, or write it by hand:
#   {"extra_roles": ["risk analyst"], "cities": ["Hyderabad"], "max_days": 7, "pages": 2}
if os.path.exists("config.json"):
    with open("config.json", encoding="utf-8") as f:
        cfg = json.load(f)
    ROLES += [r.lower() for r in cfg.get("extra_roles", []) if r.lower() not in ROLES]
    CITIES = cfg.get("cities") or CITIES
    MAX_DAYS = int(cfg.get("max_days", MAX_DAYS))
    PAGES = int(cfg.get("pages", PAGES))
    print("Loaded config.json:", len(ROLES), "roles,", len(CITIES), "city searches")

UNIT = r"(?:months?|mos?|yrs?|years?)"

def exp_from(text):
    """Finds experience like '3-5 years', '6 months-2 years', '18 months', '2 years 6 months'."""
    for pat in (
        rf"\d+(?:\.\d+)?\s*{UNIT}?\s*(?:-|–|to)\s*\d+(?:\.\d+)?\s*{UNIT}",
        r"\d+\s*(?:years?|yrs?)\s*(?:and\s*)?\d+\s*(?:months?|mos?)",
        rf"\d+(?:\.\d+)?\s*\+?\s*{UNIT}(?=\s*(?:of\s*)?(?:relevant\s*)?(?:experience|exp))",
    ):
        m = re.search(pat, text, re.I)
        if m:
            return m.group(0).strip()
    return ""

def lpa(v):
    return round(v / 100000, 1) if v else 0

def fetch(what, where, page):
    q = {"app_id": APP_ID, "app_key": APP_KEY, "results_per_page": 50,
         "title_only": what, "max_days_old": MAX_DAYS, "sort_by": "date",
         "content-type": "application/json"}
    if where:
        q["where"] = where
    url = f"https://api.adzuna.com/v1/api/jobs/in/search/{page}?" + urllib.parse.urlencode(q)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r).get("results", [])

seen, out = set(), []
for role in ROLES:
    for city in CITIES:
        for page in range(1, PAGES + 1):
            try:
                rows = fetch(role, city, page)
            except Exception as e:
                print("skip", role, city, page, e)
                break
            for r in rows:
                url = r.get("redirect_url", "")
                if not url or url in seen:
                    continue
                seen.add(url)
                desc = r.get("description", "")
                out.append({
                    "title": r.get("title", ""),
                    "company": (r.get("company") or {}).get("display_name", ""),
                    "location": (r.get("location") or {}).get("display_name", ""),
                    "source": "Adzuna",
                    "posted": (r.get("created") or "")[:10],
                    "salary_min": lpa(r.get("salary_min")),
                    "salary_max": lpa(r.get("salary_max")),
                    "salary_predicted": str(r.get("salary_is_predicted")) == "1",
                    "notice_period": "",
                    "experience": exp_from(desc),
                    "skills": desc[:400],
                    "url": url,
                })
            if len(rows) < 50:
                break
            time.sleep(1)  # be polite to the API
    print("done:", role, "| total so far:", len(out))

with open("jobs.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"Wrote {len(out)} jobs to jobs.json")
