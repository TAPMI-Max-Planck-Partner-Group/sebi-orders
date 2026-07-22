import os
import requests
from playwright.sync_api import sync_playwright
import time
import argparse

def download_sebi_orders(max_orders=50, output_dir="orders"):
    os.makedirs(output_dir, exist_ok=True)
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        base_url = "https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=2&ssid=9&smid=2"
        print(f"Navigating to {base_url}...")
        page.goto(base_url, timeout=60000)
        time.sleep(3)
        
        downloaded_count = 0
        page_num = 1
        
        while downloaded_count < max_orders:
            print(f"--- Checking page {page_num} ---")
            rows = page.query_selector_all("table tr")
            
            # Skip the header row and iterate over order rows
            # Table structure usually has th or td. We just look for links.
            links = []
            for row in rows:
                title_elem = row.query_selector("td:nth-child(2) a")
                if title_elem:
                    title_text = title_elem.inner_text().strip()
                    href = title_elem.get_attribute("href")
                    links.append((title_text, href))
            
            if not links:
                print("No more links found on this page or reached end.")
                break
                
            for title, url in links:
                if downloaded_count >= max_orders:
                    break
                    
                print(f"[{downloaded_count+1}/{max_orders}] Processing: {title}")
                
                # Check if direct PDF link
                if url.lower().endswith(".pdf"):
                    if not url.startswith("http"):
                        url = "https://www.sebi.gov.in" + url
                    try:
                        res = requests.get(url, timeout=30)
                        filename = url.split("/")[-1].split("?")[0]
                        filepath = os.path.join(output_dir, filename)
                        with open(filepath, "wb") as f:
                            f.write(res.content)
                        print(f"  -> Saved direct PDF: {filename}")
                        downloaded_count += 1
                    except Exception as e:
                        print(f"  -> Failed to download direct PDF: {e}")
                    continue

                # Not a direct PDF link, navigate to it
                try:
                    page.goto(url, timeout=60000)
                    time.sleep(2)
                except Exception as e:
                    print(f"  -> Navigation error (might be unexpected direct download): {e}")
                    continue
                
                # Try to find iframe
                iframe = page.query_selector("iframe")
                pdf_found = False
                if iframe:
                    pdf_src = iframe.get_attribute("src")
                    if pdf_src and ".pdf" in pdf_src.lower():
                        if "?file=" in pdf_src:
                            pdf_src = pdf_src.split("?file=")[1]
                        try:
                            res = requests.get(pdf_src, timeout=30)
                            filename = pdf_src.split("/")[-1].split("?")[0]
                            filepath = os.path.join(output_dir, filename)
                            with open(filepath, "wb") as f:
                                f.write(res.content)
                            print(f"  -> Saved from iframe: {filename}")
                            downloaded_count += 1
                            pdf_found = True
                        except Exception as e:
                            print(f"  -> Failed to download from iframe: {e}")
                
                # Fallback to PDF link if iframe didn't work
                if not pdf_found:
                    pdf_link = page.query_selector("a[href$='.pdf']")
                    if pdf_link:
                        pdf_src = pdf_link.get_attribute("href")
                        if not pdf_src.startswith("http"):
                            pdf_src = "https://www.sebi.gov.in" + pdf_src
                        try:
                            res = requests.get(pdf_src, timeout=30)
                            filename = pdf_src.split("/")[-1].split("?")[0]
                            filepath = os.path.join(output_dir, filename)
                            with open(filepath, "wb") as f:
                                f.write(res.content)
                            print(f"  -> Saved from fallback link: {filename}")
                            downloaded_count += 1
                        except Exception as e:
                            print(f"  -> Failed to download from fallback link: {e}")
                    else:
                        print(f"  -> No PDF found on page for {title}")
                
                # Go back to the listing page
                page.go_back(timeout=60000)
                time.sleep(2)

            if downloaded_count >= max_orders:
                break
                
            # Click next page
            next_btn = page.query_selector("a:has-text('Next')")
            if next_btn:
                next_btn.click()
                page_num += 1
                time.sleep(3)
            else:
                print("No 'Next' button found. End of listings.")
                break

        browser.close()
        print(f"\nSuccessfully downloaded {downloaded_count} orders to '{output_dir}'.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Download SEBI orders robustly")
    parser.add_argument("--count", type=int, default=50, help="Number of orders to download")
    parser.add_argument("--dir", type=str, default="recent_sebi_orders", help="Output directory")
    args = parser.parse_args()
    
    download_sebi_orders(args.count, args.dir)
