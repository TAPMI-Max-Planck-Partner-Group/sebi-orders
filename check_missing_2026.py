import os
from playwright.sync_api import sync_playwright
import time
import json

MD_FILE = "/Users/soveet/.gemini/antigravity-ide/brain/e050fa4b-37d3-4174-8636-bfd64ca0080a/live_verification.md"

def log_missing_to_md(date_str, title, expected_filename):
    title = title.replace('|', '-')
    expected = expected_filename if expected_filename else "Unknown/Could not fetch URL"
    row = f"| {date_str} | {title} | {expected} |\n"
    with open(MD_FILE, "a", encoding="utf-8") as f:
        f.write(row)

def check_missing():
    dest_dir = "2026, sebi orders"
    existing_files = set(os.listdir(dest_dir)) if os.path.exists(dest_dir) else set()
    
    missing_orders = []
    total_2026_count = 0
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        base_url = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=2&ssid=9&smid=2"
        page.goto(base_url, timeout=60000)
        time.sleep(3)
        
        page_num = 1
        reached_2025 = False
        
        while not reached_2025:
            print(f"Checking page {page_num}...")
            rows = page.query_selector_all("table tr")
            
            items = []
            for row in rows:
                date_elem = row.query_selector("td:nth-child(1)")
                title_elem = row.query_selector("td:nth-child(2) a")
                if date_elem and title_elem:
                    date_text = date_elem.inner_text().strip()
                    title_text = title_elem.inner_text().strip()
                    href = title_elem.get_attribute("href")
                    items.append((date_text, title_text, href))
            
            if not items:
                break
                
            for date_text, title, url in items:
                if "2026" not in date_text and "2025" in date_text:
                    reached_2025 = True
                    break
                
                if "2026" in date_text:
                    total_2026_count += 1
                    target_filename = None
                    if url.lower().endswith(".pdf"):
                        target_filename = url.split("/")[-1].split("?")[0]
                    else:
                        full_url = url if url.startswith("http") else "https://www.sebi.gov.in" + url
                        try:
                            page.goto(full_url, timeout=60000)
                            time.sleep(2)
                            iframe = page.query_selector("iframe")
                            if iframe:
                                pdf_src = iframe.get_attribute("src")
                                if pdf_src and ".pdf" in pdf_src.lower():
                                    if "?file=" in pdf_src:
                                        pdf_src = pdf_src.split("?file=")[1]
                                    target_filename = pdf_src.split("/")[-1].split("?")[0]
                            if not target_filename:
                                pdf_link = page.query_selector("a[href$='.pdf']")
                                if pdf_link:
                                    pdf_url = pdf_link.get_attribute("href")
                                    target_filename = pdf_url.split("/")[-1].split("?")[0]
                            page.go_back(timeout=60000)
                            time.sleep(2)
                        except Exception:
                            pass
                    
                    # If target_filename is None, or not in existing files, it's missing
                    is_missing = True
                    if target_filename:
                        # Check exact match
                        if target_filename in existing_files:
                            is_missing = False
                        else:
                            # Fuzzy check
                            for ef in existing_files:
                                if target_filename.replace(".pdf", "") in ef:
                                    is_missing = False
                                    break
                    
                    if is_missing:
                        print(f"Missing: {title} | {target_filename}")
                        log_missing_to_md(date_text, title, target_filename)
                        missing_orders.append({
                            "date": date_text,
                            "title": title,
                            "url": url,
                            "expected_filename": target_filename
                        })
            
            if reached_2025:
                break
                
            next_btn = page.query_selector("a:has-text('Next')")
            if next_btn:
                next_btn.click()
                page_num += 1
                time.sleep(3)
            else:
                break

        browser.close()
        
    with open("missing_orders.json", "w") as f:
        json.dump({"total_2026": total_2026_count, "missing": missing_orders}, f, indent=2)
        
    # Append summary to markdown
    with open(MD_FILE, "a", encoding="utf-8") as f:
        f.write(f"\n\n**Verification Complete.**\nTotal 2026 Orders Found on Website: {total_2026_count}\nTotal Missing: {len(missing_orders)}\n")

if __name__ == "__main__":
    check_missing()
