import os
import argparse
import requests
import time
import shutil
from playwright.sync_api import sync_playwright

def log_to_md(md_file, status, date_str, title, file_name):
    title = title.replace('|', '-')
    status_emoji = "✅" if status == "success" else "❌" if status == "error" else "⏭️" if status == "skipped" else "⏳"
    row = f"| {status_emoji} | {date_str} | {title} | {file_name} |\n"
    with open(md_file, "a", encoding="utf-8") as f:
        f.write(row)

def download_sebi_orders(target_year=None, max_count=50):
    if target_year:
        dest_dir = f"sebi order {target_year}"
        md_file = f"live_downloads_{target_year}.md"
        print(f"Mode: Downloading all orders for year {target_year}")
    else:
        dest_dir = f"recent {max_count} orders"
        md_file = "live_downloads_recent.md"
        print(f"Mode: Downloading most recent {max_count} orders")

    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    # Initialize markdown log
    with open(md_file, "w", encoding="utf-8") as f:
        f.write(f"# Live Download Logs: SEBI Orders\n\n| Status | Date | Title | File |\n| :---: | :--- | :--- | :--- |\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        base_url = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=2&ssid=9&smid=2"
        page.goto(base_url, timeout=60000)
        time.sleep(3)
        
        processed_count = 0
        page_num = 1
        stop_crawling = False
        
        while not stop_crawling:
            print(f"--- Checking page {page_num} ---")
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
                if target_year:
                    # If looking for a specific year
                    if str(int(target_year) - 1) in date_text:
                        stop_crawling = True
                        break
                    if target_year not in date_text:
                        continue
                else:
                    # If just looking for recent N
                    if processed_count >= max_count:
                        stop_crawling = True
                        break
                
                processed_count += 1
                print(f"[{processed_count}] Date: {date_text}")
                
                pdf_url = None
                target_filename = None
                
                if url.lower().endswith(".pdf"):
                    pdf_url = url
                    target_filename = url.split("/")[-1].split("?")[0]
                else:
                    if not url.startswith("http"):
                        url = "https://www.sebi.gov.in" + url
                    try:
                        page2 = browser.new_page()
                        page2.goto(url, timeout=60000)
                        time.sleep(2)
                        
                        iframe = page2.query_selector("iframe")
                        if iframe:
                            pdf_src = iframe.get_attribute("src")
                            if pdf_src and ".pdf" in pdf_src.lower():
                                if "?file=" in pdf_src:
                                    pdf_src = pdf_src.split("?file=")[1]
                                pdf_url = pdf_src
                                target_filename = pdf_url.split("/")[-1].split("?")[0]
                        
                        if not pdf_url:
                            pdf_link = page2.query_selector("a[href$='.pdf']")
                            if pdf_link:
                                pdf_url = pdf_link.get_attribute("href")
                                target_filename = pdf_url.split("/")[-1].split("?")[0]
                        
                        page2.close()
                    except Exception as e:
                        print(f"  -> Navigation error: {e}")
                
                if pdf_url and target_filename:
                    if not pdf_url.startswith("http"):
                        pdf_url = "https://www.sebi.gov.in" + pdf_url
                    try:
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                        res = requests.get(pdf_url, timeout=30, headers=headers)
                        if res.status_code == 200:
                            dest_path = os.path.join(dest_dir, target_filename)
                            with open(dest_path, "wb") as f:
                                f.write(res.content)
                            log_to_md(md_file, "success", date_text, title, target_filename)
                        else:
                            log_to_md(md_file, "error", date_text, title, f"Error {res.status_code}")
                    except Exception:
                        log_to_md(md_file, "error", date_text, title, "Download failed")
                else:
                    log_to_md(md_file, "error", date_text, title, "No PDF URL found")

            if stop_crawling:
                break
                
            next_btn = page.query_selector("a:has-text('Next')")
            if next_btn:
                next_btn.evaluate("element => element.click()")
                page_num += 1
                time.sleep(3)
            else:
                break

        browser.close()
        print(f"\nDone. Processed {processed_count} orders.")
        with open(md_file, "a", encoding="utf-8") as f:
            f.write(f"\n\n**Finished Downloading {processed_count} SEBI orders.**\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download SEBI orders.")
    parser.add_argument("--year", type=str, help="Target year to download (e.g., 2026, 2025).")
    parser.add_argument("--recent", type=int, default=50, help="Number of recent orders to download (default 50). Ignored if --year is set.")
    args = parser.parse_args()
    
    download_sebi_orders(target_year=args.year, max_count=args.recent)
