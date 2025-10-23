import os
import sys
import json
import typing as t
import requests
from dataclasses import dataclass
from dotenv import load_dotenv


# ===== Config =====
SEARCH_PATH = "/wday/cxs/kla/Search/jobs"
OUTPUT_PATH = "kla-auto.txt"
SEPARATOR = "#" * 91  # line of hashes between postings

DEFAULT_PAYLOAD = {
    "appliedFacets": {},
    "limit": 20,   # server page size; we still slice locally for --N
    "offset": 0,
    "searchText": ""
}

DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/137.0.0.0 Safari/537.36"
)

@dataclass
class WDConfig:
    base_url: str
    cookie: str
    csrf: str
    user_agent: str = DEFAULT_UA

def load_config() -> WDConfig:
    load_dotenv()
    base = os.getenv("WD_BASE_URL", "https://kla.wd1.myworkdayjobs.com").rstrip("/")
    cookie = os.getenv("WD_COOKIE", "").strip()
    csrf = os.getenv("WD_CSRF", "").strip()
    if not cookie or not csrf:
        sys.exit("Missing WD_COOKIE or WD_CSRF in environment/.env")
    return WDConfig(base_url=base, cookie=cookie, csrf=csrf)

def build_headers(cfg: WDConfig) -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": cfg.user_agent,
        "Origin": cfg.base_url,
        "Referer": f"{cfg.base_url}/Search",
        "X-Calypso-CSRF-Token": cfg.csrf,
        "Cookie": cfg.cookie,
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Site": "same-origin",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }

def post_search(cfg: WDConfig, payload: dict) -> requests.Response:
    url = f"{cfg.base_url}{SEARCH_PATH}"
    headers = build_headers(cfg)
    return requests.post(url, headers=headers, json=payload, timeout=30)

def extract_jobs(resp_json: dict) -> t.List[dict]:
    jp = resp_json.get("jobPostings")
    return jp if isinstance(jp, list) else []

def q(v) -> str:
    """JSON-quote a value (keeps quotes and escapes consistent)."""
    return json.dumps(v if v is not None else "", ensure_ascii=False)

def format_posting_for_text(post: dict) -> str:
    # Each field on its own line
    title = post.get("title", "")
    path  = post.get("externalPath", "")
    loc   = post.get("locationsText", "")
    posted = post.get("postedOn", "")
    return (
        f'"title": {q(title)}\n'
        f'"externalPath": {q(path)}\n'
        f'"locationsText": {q(loc)}\n'
        f'"postedOn": {q(posted)}'
    )

def write_postings_to_file(postings: t.List[dict], out_path: str) -> None:
    # Overwrite the file each run
    with open(out_path, "w", encoding="utf-8") as f:
        for idx, p in enumerate(postings):
            f.write(format_posting_for_text(p) + "\n")
            if idx != len(postings) - 1:
                f.write(SEPARATOR + "\n")

def main():
    cfg = load_config()

    # Two usages:
    # 1) no args     -> write ALL jobPostings to file + print count
    # 2) --N         -> write first N jobPostings to file + print count
    args = sys.argv[1:]
    limit_n = None
    if len(args) == 1 and args[0].startswith("--") and args[0][2:].isdigit():
        limit_n = int(args[0][2:])

    payload = dict(DEFAULT_PAYLOAD)
    resp = post_search(cfg, payload)
    if resp.status_code != 200:
        print(f"HTTP {resp.status_code}\n{resp.text[:1000]}")
        sys.exit(1)

    data = resp.json()
    postings = extract_jobs(data)

    if limit_n is not None:
        postings = postings[:limit_n]

    write_postings_to_file(postings, OUTPUT_PATH)

    # Console confirmation + length
    print(len(postings))
    print(f'Wrote {len(postings)} posting(s) to "{OUTPUT_PATH}".')

if __name__ == "__main__":
    main()
