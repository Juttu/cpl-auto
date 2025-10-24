import requests
import json
import os
import tempfile


def save_json(data, path="cvs-test.json"):
    import tempfile
    dir_name = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp_path = tempfile.mkstemp(
        dir=dir_name, prefix=".tmp_cvs_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp_path, path)
        print(f"Wrote {path}")
    except Exception:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        raise


def build_payload(page_index=0, size=10):
    """
    page_index: 0 => first page (items 1–size)
                1 => second page (items size+1–2*size), etc.
    size: number of results per page (default 10 to match your final payload)
    """
    return {"sortBy": "Most recent", "subsearch": "", "from": 0, "jobs": True, "counts": True, "all_fields": ["category", "subCategory", "country", "state", "city", "type", "remote", "businessUnit", "phLocSlider"], "pageName": "search-results", "size": 10, "clearAll": False, "jdsource": "facets", "isSliderEnable": True, "pageId": "page10", "siteType": "external", "keywords": "", "global": True, "selected_fields": {"country": ["United States"], "subCategory": ["Information Technology", "Data and Analytics", "Digital Engineering & Architecture"], "category": ["Innovation and Technology", "Students"], "type": ["Full time"]}, "sort": {"order": "desc", "field": "postedDate"}, "locationData": {"sliderRadius": 50, "aboveMaxRadius": True, "LocationUnit": "miles"}, "s": "1", "lang": "en_us", "deviceType": "desktop", "country": "us", "refNum": "CVSCHLUS", "ddoKey": "refineSearch"}


def fetch_page(page_index=0, size=25):
    url = "https://jobs.cvshealth.com/widgets"

    headers = {
        # Normal request headers (safe/meaningful to send)
        "Accept": "*/*",
        # requests sets this by default; keeping it explicit is fine
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "en-GB,en-US;q=0.9,en;q=0.8,ml;q=0.7",
        "Cache-Control": "no-cache",
        "Content-Type": "application/json",
        "Origin": "https://jobs.cvshealth.com",
        "Pragma": "no-cache",
        "Referer": "https://jobs.cvshealth.com/us/en/search-results",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        "X-CSRF-Token": "b13fbf1f28c34122b63fa299479d35f6",

        # Chrome client-hint / fetch metadata headers (server may ignore; harmless to include)
        "Sec-CH-UA": "\"Google Chrome\";v=\"141\", \"Not?A_Brand\";v=\"8\", \"Chromium\";v=\"141\"",
        "Sec-CH-UA-Mobile": "?0",
        "Sec-CH-UA-Platform": "\"macOS\"",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",

        # Priority (some servers ignore; included to match capture)
        "Priority": "u=1, i",

        # Cookies (copied verbatim from your capture)
        "Cookie": (
            'PLAY_SESSION=eyJhbGciOiJIUzI1NiJ9.eyJkYXRhIjp7IkpTRVNTSU9OSUQiOiI3MDI0ODc2Mi00MGRlLTQxZTAtYWI0OC1kY2Q2MDc5OWI5NGUiLCJjc3JmVG9rZW4iOiJiMTNmYmYxZjI4YzM0MTIyYjYzZmEyOTk0NzlkMzVmNiJ9LCJuYmYiOjE3NjEyNzA0OTksImlhdCI6MTc2MTI3MDQ5OX0.zBZCQXFvp38FWMW7ZFkuS8aTOQDMl6kzQP0AmCyajoE; '
            'PHPPPE_ACT=70248762-40de-41e0-ab48-dcd60799b94e; '
            'VISITED_LANG=en; VISITED_COUNTRY=us; in_ref=https%3A%2F%2Fwww.google.com%2F; '
            '_ga=GA1.1.1320764963.1761270501; SNS=1; PHPPPE_GCC=d; '
            'ext_trk=pjid%3D70248762-40de-41e0-ab48-dcd60799b94e&p_in_ref%3Dhttps://www.google.com/&p_lang%3Den_us&refNum%3DCVSCHLUS; '
            '_gcl_au=1.1.706138294.1761270502; '
            '_sn_m={"r":{"n":1,"r":"google"},"gi":{"lt":"42.29040","lg":"-71.07120","latitude":"42.29040","longitude":"-71.07120","country":"United States","countryCode":"US","regionCode":"MA","regionName":"Massachusetts"}}; '
            '_RCRTX03=860907bab07b11f0bb750b69f81ed5afd04ae830011449068d56914ff82bd272; '
            '_RCRTX03-samesite=860907bab07b11f0bb750b69f81ed5afd04ae830011449068d56914ff82bd272; '
            '_tt_enable_cookie=1; _ttp=01K89YE507V5PPCGT5KEJSBHB2_.tt.1; '
            'OptanonAlertBoxClosed=2025-10-24T01:48:25.640Z; '
            '_sn_n={"cs":{"b06b":{"i":[1792806506236,1],"c":1}},"a":{"i":"62d85d3b-a0bc-461b-8306-115e3b62aad4"},"ssc":1}; '
            '_sn_a={"a":{"s":1761270502208,"l":"https://cvshealth.com/us/en/search-results"},"v":"dc22fa24-f319-4c97-ae43-a552aa9e79bb","g":{"sc":{"b06bf6c0-a2ac-44b3-ace6-50de59dd886f":1}}}; '
            '_ga_K585E9E3MR=GS2.1.s1761273181$o2$g1$t1761276697$j59$l0$h0; '
            'OptanonConsent=isGpcEnabled=0&datestamp=Thu+Oct+23+2025+23%3A31%3A38+GMT-0400+(Eastern+Daylight+Time)&version=202411.1.0&browserGpcFlag=0&isIABGlobal=false&hosts=&landingPath=NotLandingPage&groups=C0001%3A1%2CC0011%3A1&geolocation=US%3BNY&AwaitingReconsent=false; '
            'ttcsid=1761273184095::JTFZV2Kf4Ko_b3Ozc6Pv.2.1761276699001.0; '
            'ttcsid_C355C0FG09FC36CGKOGG=1761273184093::0kPgMULM2wR_e7KP1iCp.2.1761276699001.0'
        ),

        # Optional: mimic Host header if you want to reflect ":authority" ̰
        "Host": "jobs.cvshealth.com",
    }

    payload = build_payload(page_index=page_index, size=size)
    r = requests.post(url, headers=headers, json=payload)
    if r.status_code != 200:
        print(f"Request failed: {r.status_code}\n{r.text}")
        return None
    try:
        data = r.json()
    except json.JSONDecodeError:
        print("Received non-JSON response:")
        print(r.text)
        return None
    return data


# === Example: fetch page 2 (jobs 26–50) and save ===
data = fetch_page(page_index=0, size=25)
if data:
    print(json.dumps(data, indent=2))
    save_json(data, "cvs-test.json")
