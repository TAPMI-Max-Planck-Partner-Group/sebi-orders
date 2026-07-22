"""
Script to extract social media posts from a PDF using Gemini Vision.
This version keeps page images in memory and only saves the cropped social media posts.
"""

import fitz  # PyMuPDF
from PIL import Image
import io
import json
import pandas as pd
import time
import os
import random

from google import genai
from google.genai import types

from dotenv import load_dotenv
load_dotenv()
PROJECT_ID = os.environ.get("VERTEX_PROJECT_ID", "YOUR_VERTEX_AI_PROJECT_ID")
REGIONS = ["us-central1", "us-east4", "us-east1", "europe-west4", "us-west1", "us-west4"]

# --- Configuration ---
PDF_DIR = "recent 50 orders final"
MAX_PAGES = None
OUTPUT_DIR = "crops"

os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL_REGIONS = {}

def call_gemini_with_fallback(model_name, contents, config=None, max_retries=18, base_sleep=1):
    if model_name not in MODEL_REGIONS:
        regions = list(REGIONS)
        random.shuffle(regions)
        MODEL_REGIONS[model_name] = regions
        
    regions = MODEL_REGIONS[model_name]
    
    for attempt in range(max_retries):
        if not regions:
            raise Exception(f"All regions permanently failed (404 Not Found) for {model_name}.")
            
        region = regions[0] # always try the front of the queue
        try:
            client = genai.Client(vertexai=True, project=PROJECT_ID, location=region)
            return client.models.generate_content(
                model=model_name,
                contents=contents,
                config=config
            )
        except Exception as e:
            error_str = str(e)
            if "404" in error_str or "NOT_FOUND" in error_str:
                print(f"[{model_name}] Not available in {region}. Removing permanently.")
                regions.pop(0)
            elif "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                print(f"[{model_name}] Quota issue in {region}. Rotating to next region...")
                regions.append(regions.pop(0)) # Move to back of queue
                
                # Sleep if we have cycled through all available regions once
                if attempt >= len(regions) and attempt > 0:
                    time.sleep(base_sleep)
            else:
                print(f"[{model_name}] Unexpected error in {region}: {e}")
                raise e
                
    raise Exception(f"Failed to generate content with {model_name} after {max_retries} retries.")

MODEL_NAME = "gemini-2.5-pro"


SYSTEM_PROMPT = """
You are an expert analyst extracting social media posts and internal communications from legal orders.
Analyze the provided page image. Look for any screenshots or text of social media posts (WhatsApp, Telegram, Twitter, Facebook, etc.) OR internal communications between operators discussing strategy, schemes, or wording.

If found, extract the details for each post/communication, including a bounding box for where it appears on the page.

Return the result as a JSON array of objects. 
If there are no relevant screenshots on the page, return an empty array [].
The JSON objects must have the following keys:
1. "extracted_text": The textual content of the post or communication.
2. "platform": The platform (e.g., WhatsApp, Telegram, X, Facebook, SMS).
3. "modus_operandi": The attack vector, strategy, or scheme being discussed/demonstrated.
4. "post_type": Categorize as either "Public Post" or "Internal Communication".
5. "date": The date and time visible in the screenshot (e.g. "Jul 14, 2025, 10:23 AM" or "Not visible").
6. "box_2d": The bounding box of the screenshot in the format [ymin, xmin, ymax, xmax], where coordinates are normalized from 0 to 1000.
"""

FILTER_PROMPT = """
Analyze the provided page image. Does this page contain any visual screenshots of social media posts, messaging apps (like WhatsApp/Telegram), or internal chat communications?
Answer ONLY with "true" if there are screenshots of posts/chats, or "false" if there are none.
"""

def extract_posts_from_pdf(pdf_path, max_pages=None, start_page=0):
    doc = fitz.open(pdf_path)
    results = []
    
    num_pages = len(doc) if max_pages is None else min(max_pages, len(doc))
    print(f"Processing first {num_pages} pages out of {len(doc)} (starting at page {start_page+1})...")
    
    for page_num in range(start_page, num_pages):
        print(f"Processing page {page_num + 1} / {num_pages}...")
        page = doc[page_num]
        
        # Render page to image in memory
        pix = page.get_pixmap(dpi=150) 
        img_bytes = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_bytes))
        width, height = img.size
        
        # --- FLASH FILTER PASS ---
        is_relevant = True
        try:
            flash_response = call_gemini_with_fallback(
                model_name="gemini-2.5-flash",
                contents=[img, FILTER_PROMPT],
                config=types.GenerateContentConfig(temperature=0.0),
                max_retries=18,
                base_sleep=1
            )
            is_relevant = flash_response.text.strip().lower() == "true"
        except Exception as e:
            print(f"Failed Flash filter for page {page_num + 1} across all regions. Proceeding to Pro anyway...")
            
        if not is_relevant:
            print(f"Skipping page {page_num + 1} (No relevant screenshots detected by Flash filter)")
            continue
        else:
            print(f"Page {page_num + 1} flagged by Flash. Sending to Pro...")
            
        # --- PRO EXTRACTION PASS ---
        try:
            response = call_gemini_with_fallback(
                model_name=MODEL_NAME,
                contents=[img, SYSTEM_PROMPT],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
                max_retries=18,
                base_sleep=1
            )
            
            response_text = response.text.strip()
            
            # Clean up markdown block if present
            if response_text.startswith("```json"):
                response_text = response_text[7:-3]
            elif response_text.startswith("```"):
                response_text = response_text[3:-3]
                
            posts = json.loads(response_text)
            
            for idx, post in enumerate(posts):
                # Process bounding box and crop
                box_2d = post.get("box_2d")
                crop_path = ""
                if box_2d and len(box_2d) == 4:
                    ymin, xmin, ymax, xmax = box_2d
                    # Convert normalized (0-1000) coords to actual pixels
                    left = (xmin / 1000.0) * width
                    top = (ymin / 1000.0) * height
                    right = (xmax / 1000.0) * width
                    bottom = (ymax / 1000.0) * height
                    
                    cropped_img = img.crop((left, top, right, bottom))
                    pdf_base = os.path.splitext(os.path.basename(pdf_path))[0]
                    crop_filename = f"{pdf_base}_page_{page_num + 1}_post_{idx + 1}.png"
                    crop_path = os.path.join(OUTPUT_DIR, crop_filename)
                    cropped_img.save(crop_path)
                else:
                    print(f"Warning: No valid box_2d found for post on page {page_num + 1}")

                results.append({
                    "Screenshot": crop_path,
                    "Extracted Text": post.get("extracted_text", ""),
                    "Platform": post.get("platform", ""),
                    "Modus Operandi": post.get("modus_operandi", ""),
                    "Post Type": post.get("post_type", ""),
                    "Date": post.get("date", ""),
                    "Page Number": page_num + 1,
                    "PDF Name": os.path.basename(pdf_path)
                })
            
        except Exception as e:
            print(f"Failed to process page {page_num + 1} with Pro model after retries. Skipping. Error: {e}")
            
        time.sleep(1)
        
    return results

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract social media posts from SEBI orders PDFs")
    parser.add_argument("--input-dir", type=str, default="recent 50 orders final", help="Directory containing PDFs")
    parser.add_argument("--output-prefix", type=str, default="", help="Prefix for output files (e.g. 2025_)")
    parser.add_argument("--md-log", type=str, default="", help="Markdown file for live progress tracking")
    args = parser.parse_args()

    PDF_DIR = args.input_dir
    OUTPUT_DIR = f"{args.output_prefix}crops" if args.output_prefix and not args.output_prefix.endswith('_') else f"{args.output_prefix}_crops" if args.output_prefix else "crops"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    csv_file = f"{args.output_prefix}extracted_posts.csv" if args.output_prefix and not args.output_prefix.endswith('_') else f"{args.output_prefix}_extracted_posts.csv" if args.output_prefix else "extracted_posts.csv"
    html_file = f"{args.output_prefix}extracted_posts.html" if args.output_prefix and not args.output_prefix.endswith('_') else f"{args.output_prefix}_extracted_posts.html" if args.output_prefix else "extracted_posts.html"
    
    md_file = args.md_log

    if md_file:
        with open(md_file, "w", encoding="utf-8") as f:
            f.write(f"# Live Extraction Logs\n\n| PDF File | Status | Found Posts |\n| :--- | :---: | :---: |\n")

    all_extracted_data = []

    if os.path.exists(PDF_DIR):
        pdfs_to_process = []
        if os.path.isdir(PDF_DIR):
            for filename in os.listdir(PDF_DIR):
                if filename.lower().endswith(".pdf"):
                    pdfs_to_process.append(os.path.join(PDF_DIR, filename))
        elif os.path.isfile(PDF_DIR) and PDF_DIR.lower().endswith(".pdf"):
            pdfs_to_process.append(PDF_DIR)
            
        for pdf_path in pdfs_to_process:
            filename = os.path.basename(pdf_path)
            print(f"\n--- Processing {filename} ---")
            
            try:
                data = extract_posts_from_pdf(pdf_path, MAX_PAGES)
                all_extracted_data.extend(data)
                
                if md_file:
                    with open(md_file, "a", encoding="utf-8") as f:
                        f.write(f"| {filename} | ✅ Done | {len(data)} |\n")
            except Exception as e:
                print(f"Error processing {filename}: {e}")
                if md_file:
                    with open(md_file, "a", encoding="utf-8") as f:
                        f.write(f"| {filename} | ❌ Error | 0 |\n")
                        
    else:
        print(f"Directory {PDF_DIR} not found.")

    if all_extracted_data:
        df = pd.DataFrame(all_extracted_data)
        
        print(f"\nFound {len(all_extracted_data)} posts/communications total.")
        html_content = f"<html><body><h1>Extracted Social Media Posts & Internal Comms</h1>"
        html_content += "<table border='1'><tr><th>PDF Name</th><th>Screenshot</th><th>Date</th><th>Post Type</th><th>Text</th><th>Platform</th><th>Modus Operandi</th></tr>"
        for item in all_extracted_data:
            img_tag = f"<img src='{item['Screenshot']}' width='300'/>" if item['Screenshot'] else "No Image"
            html_content += f"<tr><td>{item['PDF Name']}</td><td>{img_tag}</td><td>{item['Date']}</td><td>{item['Post Type']}</td><td>{item['Extracted Text']}</td><td>{item['Platform']}</td><td>{item['Modus Operandi']}</td></tr>"
        html_content += "</table></body></html>"
        
        with open(html_file, "w") as f:
            f.write(html_content)
        
        df.to_csv(csv_file, index=False)
        print(f"Saved clean results to {csv_file}")
    else:
        print("No social media posts found in any of the PDFs.")
