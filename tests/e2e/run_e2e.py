# -*- coding: utf-8 -*-
"""JALIY e2e — validates the /analysis + /comparison page split end to end."""
import json, sys, tempfile, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).parent))
import server as stub

PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"

# ---- CDN stubs (sandbox has no egress; real libs are untouched in prod) ----
CDN_STUBS = {
    "pdf.min.js": "window.pdfjsLib={GlobalWorkerOptions:{}};",
    "mammoth.browser.min.js": "window.mammoth={};",
    "tesseract.min.js": "window.Tesseract={};",
    "html2canvas.min.js": (
        "window.html2canvas=function(el){var c=document.createElement('canvas');"
        "c.width=Math.max(2,(el.offsetWidth||100)*2);c.height=Math.max(2,(el.offsetHeight||100)*2);"
        "var x=c.getContext('2d');x.fillStyle='#fff';x.fillRect(0,0,c.width,c.height);"
        "return Promise.resolve(c);};"
    ),
    "jspdf.umd.min.js": (
        "window.jspdf={jsPDF:function(){this.addPage=function(){return this};"
        "this.addImage=function(){return this};this.setFontSize=function(){return this};"
        "this.setTextColor=function(){return this};this.text=function(){return this};"
        "this.save=function(name){var b=new Blob(['%PDF-1.4 stub'],{type:'application/pdf'});"
        "var a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=name;"
        "document.body.appendChild(a);a.click();a.remove();};}};"
    ),
}

passed, failed = 0, 0
def check(name, cond):
    global passed, failed
    if cond: passed += 1
    else:
        failed += 1
        print("E2E FAIL:", name)

def counts():
    with urllib.request.urlopen(f"{BASE}/__counts") as r:
        return json.load(r)

def route_cdn(page):
    def handler(route):
        url = route.request.url
        for key, js in CDN_STUBS.items():
            if key in url:
                return route.fulfill(status=200, content_type="application/javascript", body=js)
        if "fonts.googleapis.com" in url:
            return route.fulfill(status=200, content_type="text/css", body="/* stub */")
        if "fonts.gstatic.com" in url:
            return route.fulfill(status=200, content_type="font/woff2", body=b"")
        return route.continue_()
    page.route("**/*", handler)

def visible(page, sel): return page.locator(sel).is_visible()

def run():
    srv = stub.start(PORT)
    console_errors, page_errors = [], []
    tmp = Path(tempfile.mkdtemp())
    fileA = tmp / "contract-a.txt"; fileA.write_text(stub.CONTRACT_A, encoding="utf-8")
    fileB = tmp / "contract-b-with-a-very-long-file-name-to-stress-the-chip-layout.txt"
    fileB.write_text(stub.CONTRACT_B, encoding="utf-8")

    with sync_playwright() as p:
        browser = p.chromium.launch()
        ctx = browser.new_context(viewport={"width": 1366, "height": 900}, accept_downloads=True)
        page = ctx.new_page()
        route_cdn(page)
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: page_errors.append(str(e)))

        # ---------- 1. direct open /analysis ----------
        page.goto(f"{BASE}/analysis"); page.wait_for_load_state("networkidle")
        check("1. /analysis direct: analysis view shown", visible(page, "#viewAnalyze"))
        check("1. /analysis direct: home & compare hidden",
              not visible(page, "#viewHome") and not visible(page, "#viewCompare"))
        check("1. /analysis: page title rendered", "تحليل العقد" in page.locator("#uploadTitle").inner_text())
        check("1. nav highlights Analyze", "is-current" in (page.locator('.topbar [data-nav="analysis"]').get_attribute("class") or "")
              and page.locator('.topbar [data-nav="analysis"]').get_attribute("aria-current") == "page")
        check("1. analyze button disabled when empty", page.locator("#analyzeBtn").is_disabled())

        # ---------- 2. direct open /comparison ----------
        page.goto(f"{BASE}/comparison"); page.wait_for_load_state("networkidle")
        check("2. /comparison direct: compare view shown", visible(page, "#viewCompare"))
        check("2. /comparison direct: analysis view hidden", not visible(page, "#viewAnalyze"))
        check("2. comparison page title rendered", "مقارنة العقدين" in page.locator("#cmpPageTitle").inner_text())
        check("2. nav highlights Compare", "is-current" in (page.locator('.topbar [data-nav="comparison"]').get_attribute("class") or ""))
        check("2. compare button disabled with no contracts", page.locator("#compareBtn").is_disabled())

        # ---------- 3. header navigation + homepage buttons ----------
        page.locator('.topbar [data-nav="analysis"]').click()
        check("3. header nav -> /analysis view", visible(page, "#viewAnalyze") and not visible(page, "#viewCompare"))
        page.locator('.topbar .brand').click()
        check("3. brand -> home", visible(page, "#viewHome"))
        page.locator('.topbar [data-nav="comparison"]').click()
        page.locator('.topbar-actions [data-nav="home"]').click()
        check("3. Home button returns to main page", visible(page, "#viewHome")
              and not visible(page, "#viewCompare") and not visible(page, "#viewAnalyze"))
        check("3. Home button highlighted on homepage",
              "is-current" in (page.locator('.topbar-actions [data-nav="home"]').get_attribute("class") or ""))
        page.locator('#viewHome [data-nav="comparison"]').first.click()
        check("3. hero compare CTA -> comparison page", visible(page, "#viewCompare"))
        page.locator('.topbar .brand').click()
        page.locator('#viewHome [data-nav="analysis"]').first.click()
        check("3. hero analyze CTA -> analysis page", visible(page, "#viewAnalyze"))
        check("3. legacy #analyze alias resolves", (page.evaluate("location.hash") in ("#analysis", "#analyze")))

        # ---------- 4. upload a file for analysis & run ----------
        page.set_input_files("#fileInput", str(fileA))
        page.wait_for_selector("#fileRow:not([hidden])")
        check("4. file chip shows name", "contract-a.txt" in page.locator("#fileName").inner_text())
        check("4. analyze button enabled with file", page.locator("#analyzeBtn").is_enabled())
        page.locator("#analyzeBtn").click()
        page.wait_for_selector("#results:not([hidden])", timeout=20000)
        check("4. results render after file analysis", visible(page, "#results"))
        check("4. overall risk badge populated", len(page.locator("#overallLevel").inner_text().strip()) > 0)
        check("4. executive summary populated", len(page.locator("#panelSummary").inner_text().strip()) > 40)
        check("4. risks tab count > 0", page.locator("#countRisks").inner_text().strip() not in ("", "0", "٠"))

        # evidence expandable section
        page.locator(".tab[data-tab='risks']").click()
        ev_btn = page.locator("#panelRisks .evidence-toggle").first
        ev_btn.click()
        check("4. evidence expands with verbatim quote",
              "غرامة إنهاء مبكر" in page.locator("#panelRisks .evidence").first.inner_text())

        # ---------- 13a. duplicate clicks -> single request ----------
        before = counts()["analyze"]
        page.locator("#resetSingleBtn").click()
        page.locator("#pasteInput").fill(stub.CONTRACT_A)
        btn = page.locator("#analyzeBtn")
        btn.click()
        try: btn.click(timeout=500, force=True)
        except Exception: pass
        page.wait_for_selector("#results:not([hidden])", timeout=20000)
        check("5. paste-text analysis renders results", visible(page, "#results"))
        check("13. double-click produced exactly one /api/analyze call", counts()["analyze"] - before == 1)

        # ---------- 7. export analysis PDF ----------
        with page.expect_download(timeout=20000) as dl:
            page.locator("#downloadPdfBtn").click()
        check("7. analysis PDF downloads", dl.value.suggested_filename.startswith("JALIY-summary") and dl.value.suggested_filename.endswith(".pdf"))

        # ---------- 8-11. comparison workflow ----------
        page.locator('.topbar [data-nav="comparison"]').click()
        check("8. analysis inputs do not leak into comparison",
              page.locator("#cmpPasteA").input_value() == "" and page.locator("#cmpFileRowA").get_attribute("hidden") is not None)
        page.locator("#cmpPasteA").fill(stub.CONTRACT_A)          # paste one
        check("8. compare still disabled with one contract", page.locator("#compareBtn").is_disabled())
        page.set_input_files("#cmpFileInputB", str(fileB))        # upload the other
        page.wait_for_selector("#cmpFileRowB:not([hidden])")
        check("9. contract B file name displayed", "contract-b" in page.locator("#cmpFileNameB").inner_text())
        check("9. long file name does not widen page",
              page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
        page.wait_for_function("!document.getElementById('compareBtn').disabled")
        check("8. compare enabled once both provided", True)

        # 10. remove & replace
        page.locator("#cmpRemoveB").click()
        check("10. removing contract B disables compare", page.locator("#compareBtn").is_disabled())
        page.set_input_files("#cmpFileInputB", str(fileB))
        page.wait_for_function("!document.getElementById('compareBtn').disabled")

        # 11. run comparison (with duplicate-click guard)
        before = counts()["compare"]
        page.locator("#compareBtn").click()
        try: page.locator("#compareBtn").click(timeout=500, force=True)
        except Exception: pass
        page.wait_for_selector("#cmpResults:not([hidden])", timeout=20000)
        body = page.locator("#cmpResultsBody").inner_text()
        check("11. comparison results render", len(body) > 200)
        check("11. more-favorable verdict present", "أخف كلفة" in body or "الثاني" in body)
        check("11. key differences present", "غرامة الإنهاء المبكر" in body)
        check("11. only-in-one-contract clauses present", "القانون الواجب التطبيق" in body)
        check("13. double-click produced exactly one /api/compare call", counts()["compare"] - before == 1)
        ev = page.locator("#cmpResultsBody .evidence-toggle").first
        ev.click()
        check("11. comparison evidence expands", page.locator("#cmpResultsBody .evidence").first.is_visible())

        # ---------- 12. export comparison PDF ----------
        with page.expect_download(timeout=20000) as dl2:
            page.locator("#downloadCmpPdfBtn").click()
        check("12. comparison PDF downloads", dl2.value.suggested_filename.startswith("JALIY-comparison"))

        # ---------- state isolation both directions ----------
        page.locator('.topbar [data-nav="analysis"]').click()
        check("iso. analysis results survived the comparison run", visible(page, "#results"))
        page.locator('.topbar [data-nav="comparison"]').click()
        check("iso. comparison results survived navigating away", visible(page, "#cmpResults"))
        # per-page reset only clears its own page
        page.locator("#resetCompareBtn").click()
        check("iso. reset comparison clears its results", not visible(page, "#cmpResults"))
        check("iso. reset comparison clears its inputs", page.locator("#cmpPasteA").input_value() == "")
        page.locator('.topbar [data-nav="analysis"]').click()
        check("iso. resetting comparison did NOT reset analysis", visible(page, "#results"))

        # ---------- 13. language switch (EN + LTR / AR + RTL) ----------
        page.locator("#langBtn").click()
        page.wait_for_function("document.documentElement.dir === 'ltr'")
        check("13. EN layout is LTR", page.evaluate("document.documentElement.dir") == "ltr")
        check("13. EN Home label applied", page.locator('.topbar-actions [data-nav="home"]').inner_text().strip() == "Home")
        check("13. EN nav labels applied", page.locator('.topbar [data-nav="analysis"]').inner_text().strip() == "Analyze Contract"
              and page.locator('.topbar [data-nav="comparison"]').inner_text().strip() == "Compare Contracts")
        check("13. EN page title applied", page.locator("#uploadTitle").inner_text().strip() == "Contract Analysis")
        page.locator('.topbar [data-nav="comparison"]').click()
        check("13. EN comparison title applied", page.locator("#cmpPageTitle").inner_text().strip() == "Contract Comparison")
        page.locator("#langBtn").click()
        page.wait_for_function("document.documentElement.dir === 'rtl'")
        check("13. AR layout back to RTL", page.evaluate("document.documentElement.dir") == "rtl")

        # ---------- 15. refresh each route directly ----------
        page.goto(f"{BASE}/comparison"); page.wait_for_load_state("networkidle")
        check("15. refresh /comparison lands on comparison", visible(page, "#viewCompare"))
        page.goto(f"{BASE}/analysis"); page.wait_for_load_state("networkidle")
        check("15. refresh /analysis lands on analysis", visible(page, "#viewAnalyze"))
        page.goto(f"{BASE}/analyze"); page.wait_for_load_state("networkidle")
        check("15. legacy /analyze path still resolves", visible(page, "#viewAnalyze"))
        page.goto(f"{BASE}/compare"); page.wait_for_load_state("networkidle")
        check("15. legacy /compare path still resolves", visible(page, "#viewCompare"))

        # ---------- 14. mobile layout ----------
        mpage = ctx.new_page(); route_cdn(mpage)
        mpage.set_viewport_size({"width": 390, "height": 844})
        mpage.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)
        mpage.on("pageerror", lambda e: page_errors.append(str(e)))
        mpage.goto(f"{BASE}/comparison"); mpage.wait_for_load_state("networkidle")
        cols = mpage.evaluate("getComputedStyle(document.querySelector('.cmp-slots')).gridTemplateColumns")
        check("14. mobile: contract boxes stack vertically", len(cols.split(" ")) == 1)
        check("14. mobile: no horizontal scrolling",
              mpage.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth"))
        boxA = mpage.locator('.cmp-slot[data-slot="A"]').bounding_box()
        boxB = mpage.locator('.cmp-slot[data-slot="B"]').bounding_box()
        check("14. mobile: boxes equal width & aligned", abs(boxA["width"] - boxB["width"]) < 2 and abs(boxA["x"] - boxB["x"]) < 2)
        mpage.goto(f"{BASE}/analysis"); mpage.wait_for_load_state("networkidle")
        check("14. mobile: analysis page renders", mpage.locator("#viewAnalyze").is_visible())
        mpage.close()

        # ---------- 16. console health ----------
        benign = [e for e in console_errors if "net::" in e or "Failed to load resource" in e]
        real = [e for e in console_errors if e not in benign]
        check("16. no console errors", len(real) == 0)
        check("16. no uncaught page errors", len(page_errors) == 0)
        if real: print("console:", real[:5])
        if page_errors: print("pageerrors:", page_errors[:5])

        browser.close()
    srv.shutdown()
    print(f"E2E PASS: {passed} FAIL: {failed}")
    sys.exit(1 if failed else 0)

if __name__ == "__main__":
    run()
