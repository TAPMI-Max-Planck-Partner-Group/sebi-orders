# SEBI Orders: Misinformation & Strategy Extraction Methodology

## Objective
To extract and structure evidence of pump-and-dump schemes from official SEBI orders. These orders contain critical documentation of both the "stimuli" (public misinformation posted to WhatsApp/Telegram/X) and the internal strategy communications of the operators.

## Challenges
SEBI orders are incredibly long (often hundreds of pages) and densely packed with legal text. Processing the entire document through a Large Language Model for data extraction is both computationally expensive and highly inefficient, as the vast majority of pages do not contain relevant evidence.

## Two-Pass Extraction Pipeline
To efficiently arrive at the relevant subset of data, we engineered an automated, two-pass pipeline utilizing Vision-Language Models (VLMs):

### 1. Pre-Filtering (Pass 1)
We employ a lightweight, high-speed model (`gemini-2.5-flash`) to rapidly scan every individual page of the PDF. The model acts as a binary gatekeeper, answering a single question: *"Does this page contain visual screenshots of social media posts, messaging apps, or internal chat communications?"* 
Irrelevant text-heavy pages are instantly discarded, saving massive amounts of API quota and processing time.

### 2. Deep Extraction & Categorization (Pass 2)
Only the specific pages flagged by the pre-filter are forwarded to our advanced reasoning model (`gemini-2.5-pro`). This model performs a detailed extraction:
*   **Data Points:** Extracts the textual content, platform (e.g., WhatsApp, Telegram), and the specific modus operandi/attack vector.
*   **Categorization:** Distinguishes between "Public Posts" (the actual misinformation shown to retail investors) and "Internal Communications" (operators discussing strategy evasion tactics).
*   **Temporal Mapping:** Parses the exact date and time visible in the screenshots to allow for chronological modeling of the scheme's evolution.
*   **Cropping:** Calculates bounding boxes to crop the exact images out of the PDF.

### 3. Output Generation
The pipeline compiles the structured data and the cropped images into a clean dataset (CSV and Excel format), ready for mapping specific misinformation back to the overarching scheme.
