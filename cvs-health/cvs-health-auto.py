import os
import sys
import json
import typing as t
import requests
from dataclasses import dataclass
from dotenv import load_dotenv


# ===== Config =====
BASE_PATH = "/widgets"
OUTPUT_PATH = "cvs-health-auto.txt"
SEPARATOR = "#" * 91  # visual break between postings

# "Most recent" payload you shared (ddoKey eagerLoadRefineSearch)
RECENT_PAYLOAD = {"sortBy":"Most recent","subsearch":"","from":0,"jobs":True,"counts":True,"all_fields":["category","subCategory","country","state","city","type","remote","businessUnit","phLocSlider"],"pageName":"search-results","size":10,"clearAll":False,"jdsource":"facets","isSliderEnable":True,"pageId":"page10","siteType":"external","keywords":"","global":True,"selected_fields":{},"sort":{"order":"desc","field":"postedDate"},"locationData":{"sliderRadius":50,"aboveMaxRadius":True,"LocationUnit":"miles"},"s":"1","lang":"en_us","deviceType":"desktop","country":"us","refNum":"CVSCHLUS","ddoKey":"eagerLoadRefineSearch"}

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)

@dataclass
class CVSConfig:
    base_url: str
    cookie: str
    csrf: str
    user_agent: str = DEFAULT_UA
    referer_path: str = "/us/en/search-results?s=1"  # matches the page making the call

def load_config() -> CVSConfig:
    load_dotenv()
    base = os.getenv("CVS_BASE_URL", "https://jobs.cvshealth.com").rstrip("/")
    cookie = os.getenv("CVS_COOKIE", "").strip()
    csrf = os.getenv("CVS_CSRF", "").strip()
    if not cookie or not csrf:
        sys.exit("Missing CVS_COOKIE or CVS_CSRF in environment/.env")
    return CVSConfig(base_url=base, cookie=cookie, csrf=csrf)

def build_headers(cfg: CVSConfig) -> dict:
    return {
        "Accept": "*/*",
        "Content-Type": "application/json",
        "User-Agent": cfg.user_agent,
        "Origin": cfg.base_url,
        "Referer": f"{cfg.base_url}{cfg.referer_path}",
        "x-csrf-token": cfg.csrf,
        "Cookie": cfg.cookie,
        # helpful browser-ish headers
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Site": "same-origin",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

def post_widgets(cfg: CVSConfig, payload: dict) -> requests.Response:
    url = f"{cfg.base_url}{BASE_PATH}"
    headers = build_headers(cfg)
    return requests.post(url, headers=headers, json=payload, timeout=30)

# ---- Parsing helpers ----

def _find_first_list(obj) -> t.List[dict]:
    """Recursively find the first list of dicts (jobs) in an arbitrary JSON."""
    if isinstance(obj, list) and (not obj or isinstance(obj[0], dict)):
        return obj
    if isinstance(obj, dict):
        # prefer well-known keys
        for k in ("jobs", "items", "results", "data"):
            if k in obj:
                found = _find_first_list(obj[k])
                if found:
                    return found
        # otherwise scan all values
        for v in obj.values():
            found = _find_first_list(v)
            if found:
                return found
    return []

def extract_jobs(resp_json: dict) -> t.List[dict]:
    """Try to extract the job list from Phenom widgets response."""
    # Common shapes: {"data":{"jobs":[...]}} or {"refineSearch":{"data":{"jobs":[...]}}}
    for path in (
        ("data", "jobs"),
        ("refineSearch", "data", "jobs"),
        ("widgets", 0, "data", "jobs"),  # sometimes nested per-widget
    ):
        cur = resp_json
        ok = True
        for key in path:
            if isinstance(key, int):
                if isinstance(cur, list) and len(cur) > key:
                    cur = cur[key]
                else:
                    ok = False
                    break
            else:
                if isinstance(cur, dict) and key in cur:
                    cur = cur[key]
                else:
                    ok = False
                    break
        if ok and isinstance(cur, list):
            return cur
    # Fallback: search anywhere
    return _find_first_list(resp_json)

# ---- Output formatting ----

def q(v) -> str:
    return json.dumps(v if v is not None else "", ensure_ascii=False)

def coalesce(*vals):
    for v in vals:
        if v:
            return v
    return ""

def build_abs_url(base: str, maybe_path: str) -> str:
    if not maybe_path:
        return ""
    if maybe_path.startswith("http://") or maybe_path.startswith("https://"):
        return maybe_path
    if maybe_path.startswith("/"):
        return f"{base}{maybe_path}"
    return maybe_path

def format_posting_lines(p: dict, base_url: str) -> str:
    """
    Write four lines:
      "title": "..."\n
      "externalPath": "..."\n
      "locationsText": "..."\n
      "postedOn": "..."
    We map CVS fields defensively to these.
    """
    # Title-like
    title = coalesce(
        p.get("title"),
        p.get("name"),
        p.get("jobTitle"),
        p.get("displayTitle"),
    )

    # URL / path-like
    path = coalesce(
        p.get("jobUrl"),
        p.get("url"),
        p.get("jobDetailUrl"),
        p.get("canonicalUrl"),
        p.get("absolute_url"),
        p.get("externalPath"),
        p.get("applyUrl"),
    )
    path = build_abs_url(base_url, path)

    # Location-like
    location = coalesce(
        p.get("location"),
        p.get("formattedLocation"),
        p.get("cityState"),
        p.get("jobLocation"),
        p.get("locationsText"),
        # nested forms
        (isinstance(p.get("locations"), list) and ", ".join([str(x) for x in p["locations"]]) or None),
    )

    # Posted date-like
    posted = coalesce(
        p.get("postedOn"),
        p.get("postedDate"),
        p.get("displayPostedDate"),
        p.get("postedDateStr"),
    )

    return (
        f'"title": {q(title)}\n'
        f'"externalPath": {q(path)}\n'
        f'"locationsText": {q(location)}\n'
        f'"postedOn": {q(posted)}'
    )

def write_postings_to_file(postings: t.List[dict], base_url: str, out_path: str) -> None:
    with open(out_path, "w", encoding="utf-8") as f:
        for i, p in enumerate(postings):
            f.write(format_posting_lines(p, base_url) + "\n")
            if i != len(postings) - 1:
                f.write(SEPARATOR + "\n")

# ---- Main ----

def main():
    cfg = load_config()

    # Modes:
    #   1) no args        -> write ALL recent results returned by this call
    #   2) --N            -> write first N from recent results
    args = sys.argv[1:]
    limit_n = None
    if len(args) == 1 and args[0].startswith("--") and args[0][2:].isdigit():
        limit_n = int(args[0][2:])

    payload = dict(RECENT_PAYLOAD)
    resp = post_widgets(cfg, payload)
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}\n{resp.text[:1200]}")
        sys.exit(1)

    data = resp.json()
    postings = extract_jobs(data)

    if limit_n is not None:
        postings = postings[:limit_n]

    write_postings_to_file(postings, cfg.base_url, OUTPUT_PATH)

    # Console: print count and a confirmation
    print(len(postings))
    print(f'Wrote {len(postings)} posting(s) to "{OUTPUT_PATH}".')

if __name__ == "__main__":
    main()
