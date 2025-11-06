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
import asyncio

# ======== CONFIG (edit this only) ========
import subprocess
import shlex
import sys
from pathlib import Path
import re

# ====== Replace your static COOKIE assignment with a dynamic call ======


def get_cookie_from_node(node_script_path="get_cvs_cookie.js", node_bin="node", timeout=30):
    """
    Run the Node script, stream stdout/stderr live to Python stdout,
    and return the cookie header string printed by the script.
    Raises RuntimeError on failure.
    """
    script = Path(node_script_path)
    if not script.exists():
        raise RuntimeError(f"Node script not found: {script.resolve()}")

    cmd = [node_bin, str(script)]
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Node binary not found ('{node_bin}'). Install Node.js or adjust node_bin.") from e
    except Exception as e:
        raise RuntimeError(f"Failed to start node process: {e}") from e

    lines = []
    try:
        # Stream output live, line by line
        for raw in proc.stdout:
            line = raw.rstrip("\n")
            if "FOUND" in line or "CLICKED" in line: 
                print(line)           # live log output
            lines.append(line)
        # Wait for process to exit (with timeout)
        try:
            proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            raise RuntimeError(f"Node script timed out after {timeout}s")
    finally:
        # ensure pipes are closed
        if proc.stdout:
            proc.stdout.close()

    if proc.returncode != 0:
        # include last few lines to help debug
        tail = "\n".join(lines[-20:])
        raise RuntimeError(
            f"Node script failed (exit {proc.returncode}). Last output:\n{tail}")

    # Extract the last non-empty line that looks like a cookie (contains '=')
    cookie_candidate = None
    for ln in reversed([ln for ln in lines if ln.strip()]):
        if "=" in ln:
            cookie_candidate = ln
            break

    if not cookie_candidate:
        tail = "\n".join(lines[-40:])
        raise RuntimeError(
            f"No cookie-like output found from node script. Last output:\n{tail}")

    return cookie_candidate

def extract_cookie_value(cookie_header: str, name: str) -> str | None:
    """Extract cookie value by name from a 'Cookie:' header string."""
    m = re.search(rf'(?:^|;\s*){re.escape(name)}\s*=\s*([^;]+)', cookie_header)
    if not m:
        return None
    val = m.group(1).strip()
    # strip quotes or trailing semicolons if any
    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
        val = val[1:-1]
    return val.rstrip(';')

def replace_cookie_value(cookie_header: str, name: str, new_value: str) -> str:
    """Replace/add a single cookie name=value inside a cookie header string."""
    pattern = re.compile(rf'(^|;\s*){re.escape(name)}\s*=\s*[^;]+')
    replacement = rf'\1{name}={new_value}'
    if pattern.search(cookie_header):
        return pattern.sub(replacement, cookie_header, count=1)
    # not present → append
    sep = "" if cookie_header.endswith(";") else ";"
    return f"{cookie_header}{sep} {name}={new_value}"

try:
    COOKIE = '''VISITED_LANG=en; VISITED_COUNTRY=us; _ga=GA1.1.1320764963.1761270501; PHPPPE_GCC=d; _gcl_au=1.1.706138294.1761270502; _RCRTX03=860907bab07b11f0bb750b69f81ed5afd04ae830011449068d56914ff82bd272; _RCRTX03-samesite=860907bab07b11f0bb750b69f81ed5afd04ae830011449068d56914ff82bd272; _tt_enable_cookie=1; _ttp=01K89YE507V5PPCGT5KEJSBHB2_.tt.1; OptanonAlertBoxClosed=2025-10-24T01:48:25.640Z; in_ref=https%3A%2F%2Fwww.google.com%2F; SNS=1; _sn_m={"r":{"n":0,"r":"google"},"gi":{"lt":"42.29040","lg":"-71.07120","latitude":"42.29040","longitude":"-71.07120","country":"United States","countryCode":"US","regionCode":"MA","regionName":"Massachusetts"}}; rx_jobid_b252f2ea-d743-11e6-bd44-e18ad9435508=R0563320; ttcsid=1762240913131::ZVfdVBWV71uv_2n2H203.5.1762240913358.0; ttcsid_C355C0FG09FC36CGKOGG=1762240913130::7rxpsifjAY5wmNhQKpYY.5.1762240913358.0; _sn_n={"cs":{"b06b":{"i":[1793752808855,2],"c":1,"h":1}},"ssc":1,"a":{"i":"dc2fc0bd-f4b7-4436-b2e7-fe06e86d9346"}}; PLAY_SESSION=eyJhbGciOiJIUzI1NiJ9.eyJkYXRhIjp7IkpTRVNTSU9OSUQiOiJkMjlhZTZkZi03MWM1LTQwNGQtYTdiNC01OTY0Nzg3YTZkYTIiLCJjc3JmVG9rZW4iOiI0YTgyY2U2MjUwMGU0OTNjODllMDliN2E2ODBiMjhjNSJ9LCJuYmYiOjE3NjIzOTkwMTksImlhdCI6MTc2MjM5OTAxOX0.s0m8KMfZtVsx4x6ugYukJw7MexEeqnaUTyLH-vU3qM8; OptanonConsent=isGpcEnabled=0&datestamp=Tue+Nov+04+2025+06%3A07%3A51+GMT-0500+(Eastern+Standard+Time)&version=202411.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&landingPath=NotLandingPage&groups=C0001%3A1%2CC0011%3A1%2CC0004%3A1%2CC0003%3A1&geolocation=US%3BNY&AwaitingReconsent=false; _ga_K585E9E3MR=GS2.1.s1762252034$o10$g1$t1762254471$j58$l0$h0; _sn_a={"a":{"s":1762252024992,"l":"https://cvshealth.com/us/en/search-results?from=10&s=1","e":1762251120297},"v":"dc22fa24-f319-4c97-ae43-a552aa9e79bb","g":{"sc":{"b06bf6c0-a2ac-44b3-ace6-50de59dd886f":1}}}'''
    node_cookie = get_cookie_from_node()
    fresh_play = extract_cookie_value(node_cookie, "PLAY_SESSION")
    COOKIE = replace_cookie_value(COOKIE, "PLAY_SESSION", fresh_play)
    # truncated preview for logs
    print(f"Using COOKIE from node script: {COOKIE}...")
except Exception as e:
    print("Failed to obtain cookie from Node script:", e, file=sys.stderr)
    # fall back to hard-coded COOKIE or re-raise to fail fast:
    # raise
    COOKIE = ""  # or set to a sensible default / previously saved cookie
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
    loc = _best(job, "primaryLocation", "location",
                "formattedLocation", "jobLocation")
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
        _best(job, "postedDate", "postedDateStr",
              "displayPostedDate", "postedOn")
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
