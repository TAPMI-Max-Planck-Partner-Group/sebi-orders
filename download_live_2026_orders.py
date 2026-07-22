import os
import requests
from playwright.sync_api import sync_playwright
import time
import shutil

MD_FILE = "/Users/soveet/.gemini/antigravity-ide/brain/e050fa4b-37d3-4174-8636-bfd64ca0080a/live_downloads.md"

def log_to_md(status, date_str, title, file_name):
    # Ensure no pipes in text break the table
    title = title.replace('|', '-')
    status_emoji = "✅" if status == "success" else "❌" if status == "error" else "⏭️" if status == "skipped" else "⏳"
    row = f"| {status_emoji} | {date_str} | {title} | {file_name} |\n"
    with open(MD_FILE, "a", encoding="utf-8") as f:
        f.write(row)

def download_sebi_orders(max_orders=50, dest_dir="2026, sebi orders"):
    # Clear dest_dir
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        base_url = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=2&ssid=9&smid=2"
        print(f"Navigating to {base_url}...")
        page.goto(base_url, timeout=60000)
        time.sleep(3)
        
        processed_count = 0
        page_num = 1
        
        while processed_count < max_orders:
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
                print("No more items found on this page or reached end.")
                break
                
            for date_text, title, url in items:
                if processed_count >= max_orders:
                    break
                    
                processed_count += 1
                is_2026 = "2026" in date_text
                print(f"[{processed_count}/{max_orders}] Date: {date_text} | 2026?: {is_2026}")
                
                if not is_2026:
                    continue
                
                pdf_url = None
                target_filename = None
                
                # Check if direct PDF link
                if url.lower().endswith(".pdf"):
                    pdf_url = url
                    target_filename = url.split("/")[-1].split("?")[0]
                else:
                    # Navigate to find the PDF link
                    if not url.startswith("http"):
                        url = "https://www.sebi.gov.in" + url
                    try:
                        page.goto(url, timeout=60000)
                        time.sleep(2)
                        
                        iframe = page.query_selector("iframe")
                        if iframe:
                            pdf_src = iframe.get_attribute("src")
                            if pdf_src and ".pdf" in pdf_src.lower():
                                if "?file=" in pdf_src:
                                    pdf_src = pdf_src.split("?file=")[1]
                                pdf_url = pdf_src
                                target_filename = pdf_url.split("/")[-1].split("?")[0]
                        
                        if not pdf_url:
                            pdf_link = page.query_selector("a[href$='.pdf']")
                            if pdf_link:
                                pdf_url = pdf_link.get_attribute("href")
                                target_filename = pdf_url.split("/")[-1].split("?")[0]
                        
                        # Go back
                        page.go_back(timeout=60000)
                        time.sleep(2)
                        
                    except Exception as e:
                        print(f"  -> Navigation error: {e}")
                
                if pdf_url and target_filename:
                    if not pdf_url.startswith("http"):
                        pdf_url = "https://www.sebi.gov.in" + pdf_url
                    try:
                        print(f"  -> Downloading {target_filename} from {pdf_url}")
                        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                        res = requests.get(pdf_url, timeout=30, headers=headers)
                        if res.status_code == 200:
                            dest_path = os.path.join(dest_dir, target_filename)
                            with open(dest_path, "wb") as f:
                                f.write(res.content)
                            print(f"  -> Successfully downloaded {target_filename}")
                            log_to_md("success", date_text, title, target_filename)
                        else:
                            print(f"  -> Failed to download. Status code: {res.status_code}")
                            log_to_md("error", date_text, title, f"Error {res.status_code}")
                    except Exception as e:
                        print(f"  -> Failed to download {target_filename}: {e}")
                        log_to_md("error", date_text, title, f"Download failed")
                else:
                    print(f"  -> Could not find PDF URL for {title}")
                    log_to_md("error", date_text, title, "No PDF URL found")

            if processed_count >= max_orders:
                break
                
            next_btn = page.query_selector("a:has-text('Next')")
            if next_btn:
                next_btn.click()
                page_num += 1
                time.sleep(3)
            else:
                break

        browser.close()
        print("\nDone.")

if __name__ == "__main__":
    download_sebi_orders()
