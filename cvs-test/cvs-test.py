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


try:
    COOKIE = get_cookie_from_node("get_cvs_cookie.js")
    # truncated preview for logs
    print(f"Using COOKIE from node script: {COOKIE[:100]}...")
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
