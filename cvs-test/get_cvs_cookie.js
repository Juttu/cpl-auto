const puppeteer = require("puppeteer");


const MANUAL_SN_A = `_sn_a={"a":{"s":1762252024992,"l":"https://cvshealth.com/us/en/search-results?s=1","e":1762251120297},"v":"dc22fa24-f319-4c97-ae43-a552aa9e79bb","g":{"sc":{"b06bf6c0-a2ac-44b3-ace6-50de59dd886f":1}}}`;
// --- Helper function to replace _sn_a ---
async function replaceSnACookie(page, newValue) {
  const cookies = await page.cookies();
  const updatedCookies = cookies.map((c) => {
    if (c.name === "_sn_a") {
      return { ...c, value: newValue };
    }
    return c;
  });

  // Add _sn_a if missing
  if (!cookies.some((c) => c.name === "_sn_a")) {
    updatedCookies.push({
      name: "_sn_a",
      value: newValue,
      domain: ".cvshealth.com",
      path: "/",
      httpOnly: false,
      secure: true,
    });
  }

  await page.setCookie(...updatedCookies);
}


// Sleep utility
const sleep = (ms) => new Promise((res) => setTimeout(res, ms));

(async () => {
  try {
    const browser = await puppeteer.launch({ headless: true });
    const page = await browser.newPage();

    await page.goto("https://jobs.cvshealth.com/us/en/search-results?s=1", {
      waitUntil: "networkidle2",
    });

    


    // Select "Most recent"
    await setSortFilter(page);
    await sleep(1000);
    // await waitForServerUpdate(page);



    // Click the filter button (opens filter panel)
    await clickFacetCheckbox(page, "Innovation and Technology");
    await sleep(1000); // wait for panel to open
    // await waitForServerUpdate(page);




    await clickFacetCheckbox(page, "Students");
    await sleep(1000);
    // await waitForServerUpdate(page);

    await clickFacetCheckbox(page, "Data and Analytics");
    await sleep(1000);
    // await waitForServerUpdate(page);



    await clickFacetCheckbox(page, "Digital Engineering & Architecture");
    await sleep(1000);
    // await waitForServerUpdate(page);


    await sleep(1000); // wait for panel to open

    await clickFacetCheckbox(page, "Information Technology");
    await sleep(1000);
    // await waitForServerUpdate(page);



    await clickFacetCheckbox(page, "United States");
    await sleep(1000);
    // await waitForServerUpdate(page);



    await clickFacetCheckbox(page, "Full time");
    await sleep(1000); // wait for panel to open
    // await waitForServerUpdate(page);


    await sleep(1500); // 1.5 seconds

    // await replaceSnACookie(page, MANUAL_SN_A);

    // Grab cookies as a single string
    const cookies = await page.cookies();
    const cookieHeader = cookies.map((c) => `${c.name}=${c.value}`).join("; ");
    console.log(cookieHeader);

    await browser.close();
  } catch (err) {
    console.error("Error:", err.message);
    process.exit(1);
  }

  async function setSortFilter(page) {
    await page.evaluate(() => {
      const sortSelect = document.getElementById("sortselect");
      if (!sortSelect) throw new Error("Sort dropdown (#sortselect) not found");

      let found = false;
      for (const option of sortSelect.options) {
        if (option.value.toLowerCase() === "most recent" || option.text.toLowerCase().includes("recent")) {
          sortSelect.value = option.value;
          found = true;
          break;
        }
      }

      if (!found) throw new Error("Most recent option not found in dropdown");
      sortSelect.dispatchEvent(new Event("change", { bubbles: true }));
    });
  }
  async function clickFacetCheckbox(page, facetText) {
    // run DOM work and return a simple result
    const res = await page.evaluate((text) => {
      const result = { found: false, clicked: false };

      try {
        // 1) direct input with attribute
        let input = document.querySelector(`input[data-ph-at-text="${text}"]`);
        if (input && input.type === "checkbox") {
          result.found = true;
          if (!input.checked) {
            input.click();
            result.clicked = true;
          }
          return result;
        }

        // 2) parent container with attribute
        let parent = document.querySelector(`[data-ph-at-text="${text}"]`);
        if (parent) {
          let insideInput = parent.querySelector('input[type="checkbox"]');
          if (insideInput) {
            result.found = true;
            if (!insideInput.checked) {
              insideInput.click();
              result.clicked = true;
            }
            return result;
          }
          if (parent.tagName && parent.tagName.toLowerCase() === "label") {
            const forId = parent.getAttribute("for");
            if (forId) {
              const forInput = document.getElementById(forId);
              if (forInput && forInput.type === "checkbox") {
                result.found = true;
                if (!forInput.checked) {
                  forInput.click();
                  result.clicked = true;
                }
                return result;
              }
            }
          }
        }

        // 3) label fallback (loose match)
        const labels = Array.from(document.querySelectorAll("label"));
        const label = labels.find((l) => (l.innerText || "").trim().includes(text));
        if (label) {
          result.found = true;
          const forId = label.getAttribute("for");
          if (forId) {
            const linked = document.getElementById(forId);
            if (linked && linked.type === "checkbox") {
              if (!linked.checked) {
                linked.click();
                result.clicked = true;
              }
              return result;
            }
          }
          // click the label itself
          label.click();
          result.clicked = true;
          return result;
        }

        // nothing found
        return result;
      } catch (e) {
        return result;
      }
    }, facetText);

    // Minimal one-line output with facet name and ticks
    const ok = "✓",
      no = "✗";
    const foundMark = res.found ? ok : no;
    const clickedMark = res.clicked ? ok : no;
    console.log(`${facetText} — FOUND ${foundMark}  CLICKED ${clickedMark}`);

    // small wait to let UI react
    await new Promise((r) => setTimeout(r, 600));
  }
  /**
   * Wait for the page to finish updating after a user action (sort/facet click).
   * Returns true if it detected a successful update within timeouts, false otherwise.
   *
   * Usage:
   *   await clickFacetCheckbox(...);
   *   await sleep(500);
   *   await waitForServerUpdate(page);   // <- call this after your sleeps
   */
  async function waitForServerUpdate(page, opts = {}) {
    const {
      xhrTimeout = 10000, // wait up to this for the search-results XHR
      ariaTimeout = 4000, // wait up to this for aria-live confirmation
      stableTimeout = 7000, // total timeout for DOM stabilization
      stablePeriod = 700, // required stable period (ms)
      checkInterval = 300, // polling interval for stability check
    } = opts;

    // 1) wait for a GET /search-results?from=* 200 response (non-fatal)
    try {
      await page.waitForResponse(
        (resp) => {
          try {
            return (
              resp.request().method() === "GET" && resp.url().includes("/search-results") && resp.status() === 200
            );
          } catch (e) {
            return false;
          }
        },
        { timeout: xhrTimeout }
      );
    } catch (e) {
      // timed out waiting for XHR — continue to other checks (non-fatal)
    }

    // 2) wait for aria-live text to reflect "most recent" (non-fatal)
    try {
      await page.waitForFunction(
        () => {
          const el =
            document.querySelector(".ph-a11y-sortBy-filter") ||
            document.querySelector('[data-ph-at-id="sortby-text"]');
          return el && (el.innerText || "").toLowerCase().includes("recent");
        },
        { timeout: ariaTimeout }
      );
    } catch (e) {
      // ignore — site might not update aria in some runs
    }

    // 3) wait for DOM stability of the job-list (fingerprint method)
    const stableOk = await page.evaluate(
      async (stablePeriod, checkInterval, stableTimeout) => {
        const getFingerprint = () => {
          const items = Array.from(document.querySelectorAll("a[href*='/job'], a[href*='/jobs/'], [data-job-id]"));
          const top = items
            .slice(0, 6)
            .map((el) => (el.href || el.innerText || "").trim())
            .join("|");
          return `${items.length}-${top}`;
        };

        const deadline = Date.now() + stableTimeout;
        let lastFp = getFingerprint();
        let stableSince = Date.now();

        while (Date.now() < deadline) {
          await new Promise((r) => setTimeout(r, checkInterval));
          const fp = getFingerprint();
          if (fp === lastFp) {
            if (Date.now() - stableSince >= stablePeriod) return true;
          } else {
            lastFp = fp;
            stableSince = Date.now();
          }
        }
        return false;
      },
      stablePeriod,
      checkInterval,
      stableTimeout
    );

    // small final delay for safety
    await new Promise((r) => setTimeout(r, 150));

    return stableOk;
  }
})();
