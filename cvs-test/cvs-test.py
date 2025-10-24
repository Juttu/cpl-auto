#!/usr/bin/env python3
"""
Fetch the first 100 CVS jobs and save them (overwriting) to cvs-test.json.

What it does
- Requests the HTML for /search-results?from=0,25,50,75&s=1
- Extracts the embedded eagerLoadRefineSearch JSON from each page
- Collects up to 100 jobs and writes a normalized list to cvs-test.json
- Output schema per item:
    {
      "job_id": <1..N>,                # just a running index
      "job_title": <string>,
      "job_link": <string>,            # job/apply/detail url (best-effort)
      "job_location": <string>,        # single-line location
      "job_posted_date": <string>      # best-effort posted date field
    }
"""

import html
import json
import requests

# ======== CONFIG (edit this only) ========
COOKIE= r'''VISITED_LANG=en; VISITED_COUNTRY=us; in_ref=https%3A%2F%2Fwww.google.com%2F; _ga=GA1.1.1320764963.1761270501; SNS=1; PHPPPE_GCC=d; _gcl_au=1.1.706138294.1761270502; _sn_m={"r":{"n":1,"r":"google"},"gi":{"lt":"42.29040","lg":"-71.07120","latitude":"42.29040","longitude":"-71.07120","country":"United States","countryCode":"US","regionCode":"MA","regionName":"Massachusetts"}}; _RCRTX03=860907bab07b11f0bb750b69f81ed5afd04ae830011449068d56914ff82bd272; _RCRTX03-samesite=860907bab07b11f0bb750b69f81ed5afd04ae830011449068d56914ff82bd272; _tt_enable_cookie=1; _ttp=01K89YE507V5PPCGT5KEJSBHB2_.tt.1; OptanonAlertBoxClosed=2025-10-24T01:48:25.640Z; PLAY_SESSION=eyJhbGciOiJIUzI1NiJ9.eyJkYXRhIjp7IkpTRVNTSU9OSUQiOiJlOTUwNjU3OC05NDliLTQ5NTctYjJmNy0zNjc3ZDAyZjkxMWEiLCJjc3JmVG9rZW4iOiI4YjU2MmE4NzIwYmE0YTkxYWY0MDA0ZWMxODQ2ZjYwMSJ9LCJuYmYiOjE3NjEyODc1NzksImlhdCI6MTc2MTI4NzU3OX0.5o9yyKbzYI73Z_snjw5CGYnIGqG5bY1whLkk7zVuC2U; PHPPPE_ACT=e9506578-949b-4957-b2f7-3677d02f911a; ext_trk=pjid%3De9506578-949b-4957-b2f7-3677d02f911a&p_in_ref%3Dhttps://www.google.com/&p_lang%3Den_us&refNum%3DCVSCHLUS; _sn_n={"cs":{"b06b":{"i":[1792806506236,1],"c":1}},"ssc":1,"a":{"i":"e78eb88a-972c-418b-b71e-0e7b8eb3019d"}}; _ga_K585E9E3MR=GS2.1.s1761287579$o3$g1$t1761292873$j59$l0$h0; _sn_a={"a":{"s":1761287199490,"l":"https://cvshealth.com/us/en/search-results","e":1761291846878},"v":"dc22fa24-f319-4c97-ae43-a552aa9e79bb","g":{"sc":{"b06bf6c0-a2ac-44b3-ace6-50de59dd886f":1}}}; OptanonConsent=isGpcEnabled=0&datestamp=Fri+Oct+24+2025+04%3A01%3A14+GMT-0400+(Eastern+Daylight+Time)&version=202411.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&landingPath=NotLandingPage&groups=C0001%3A1%2CC0011%3A1&geolocation=US%3BNY&AwaitingReconsent=false; ttcsid=1761287454186::YABn2bKhrOcK1IevvaUK.3.1761292945384.0; ttcsid_C355C0FG09FC36CGKOGG=1761287454186::rXEDZZxacz92OhQGA7iK.3.1761292945385.0'''
# ========================================

BASE = "https://jobs.cvshealth.com/us/en/search-results?s=1&from="
OFFSETS = [0, 25, 50, 75]        # 4 pages × 25 = 100
OUT_FILE = "cvs-test.json"

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                   "Chrome/141.0.0.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8,ml;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Upgrade-Insecure-Requests": "1",
    # We'll set Referer dynamically per request to the previous page
    # and inject the Cookie header below.
}

def _best(obj, *keys, default=None):
    """Pick the first present/non-empty key from obj."""
    for k in keys:
        if isinstance(k, (list, tuple)):
            cur = obj
            ok = True
            for kk in k:
                if isinstance(cur, dict) and kk in cur:
                    cur = cur[kk]
                else:
                    ok = False
                    break
            if ok and cur not in (None, "", []):
                return cur
        else:
            if isinstance(obj, dict) and k in obj and obj[k] not in (None, "", []):
                return obj[k]
    return default

def _stringify_location(job):
    # Try simple string fields first
    loc = _best(job, "primaryLocation", "location", "formattedLocation", "jobLocation")
    if isinstance(loc, str) and loc.strip():
        return loc.strip()

    # Sometimes locations is an array of strings/objects
    locs = _best(job, "locations")
    if isinstance(locs, list) and locs:
        first = locs[0]
        if isinstance(first, str):
            return first
        if isinstance(first, dict):
            s = _best(first, "name", "displayName", "formatted", "location")
            if s:
                return s

    # Compose from city/state/country if present
    city = _best(job, "city")
    state = _best(job, "state", "stateCode", "regionCode")
    country = _best(job, "country", "countryCode")
    parts = [p for p in (city, state, country) if p]
    if parts:
        return ", ".join(parts)

    return ""

def _stringify_posted_date(job):
    # Common fields seen across Phenom career sites
    return (
        _best(job, "postedDate", "postedDateStr", "displayPostedDate", "postedOn")
        or _best(job, ["metadata", "postedDate"])
        or ""
    )

def _stringify_link(job):
    # Prefer a concrete apply/deeplink/detail URL
    return (
        _best(job, "applyUrl", "applyUrlDeeplink", "jobDetailUrl",
              "jobUrl", "canonicalPositionUrl", "canonicalUrl",
              "canonicalExternalUrl", "externalUrl")
        or ""
    )

def extract_json_block(doc: str, key: str) -> str:
    """
    Extract the JSON object immediately following `"key":` in the document.
    Returns the raw JSON text with balanced braces.
    """
    anchor = f'"{key}"'
    i = doc.find(anchor)
    if i == -1:
        raise ValueError(f'Anchor "{anchor}" not found')
    i = doc.find(":", i)
    if i == -1:
        raise ValueError(f'Colon after "{anchor}" not found')
    i = doc.find("{", i)
    if i == -1:
        raise ValueError(f'Opening brace after "{anchor}" not found')

    depth = 0
    in_str = False
    str_quote = None
    esc = False
    start = i
    for j in range(i, len(doc)):
        ch = doc[j]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == str_quote:
                in_str = False
        else:
            if ch in ("'", '"'):
                in_str = True
                str_quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return doc[start:j+1]
    raise ValueError(f'Unbalanced braces while extracting "{key}"')

def fetch_jobs_page(session: requests.Session, from_offset: int, last_referer: str | None):
    url = f"{BASE}{from_offset}"
    headers = DEFAULT_HEADERS.copy()
    if last_referer:
        headers["Referer"] = last_referer
    headers["Cookie"] = COOKIE

    resp = session.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    html_text = html.unescape(resp.text)
    raw_json = extract_json_block(html_text, "eagerLoadRefineSearch")
    data = json.loads(raw_json)
    jobs = data.get("data", {}).get("jobs", []) or []
    return url, jobs

def main():
    sess = requests.Session()
    all_jobs = []
    referer = "https://jobs.cvshealth.com/us/en/search-results?from=0&s=1"

    for idx, off in enumerate(OFFSETS):
        url, jobs = fetch_jobs_page(sess, off, referer if idx > 0 else referer)
        referer = url  # next request's referer
        all_jobs.extend(jobs)
        if len(all_jobs) >= 100:
            break

    # Normalize and cap to 100
    all_jobs = all_jobs[:100]

    normalized = []
    for i, job in enumerate(all_jobs, start=1):
        title = _best(job, "title", "jobTitle", "name") or ""
        link = _stringify_link(job)
        loc = _stringify_location(job)
        posted = _stringify_posted_date(job)

        normalized.append({
            "job_id": i,                 # running index (i++)
            "job_title": title,
            "job_link": link,
            "job_location": loc,
            "job_posted_date": posted,
        })

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(normalized, f, ensure_ascii=False, indent=2)

    print(f"Wrote {len(normalized)} jobs → {OUT_FILE}")

if __name__ == "__main__":
    # Only acceptable invocation: python cvs_jobs_extract.py
    main()
