import pandas as pd
import xlsxwriter
import os
from PIL import Image

csv_file = "recent_50_extracted_posts.csv"
excel_file = "final_extracted_posts_with_images.xlsx"

df = pd.read_csv(csv_file)

# Clean up duplicate columns if they exist (due to append)
if 'pdf_name' in df.columns and 'PDF Name' in df.columns:
    df['PDF Name'] = df['PDF Name'].fillna(df['pdf_name'])
    df = df.drop(columns=['pdf_name'])
    
if 'image_file' in df.columns and 'Screenshot' in df.columns:
    df['Screenshot'] = df['Screenshot'].fillna(df['image_file'])
    df = df.drop(columns=['image_file'])

# Rename the first column to "Image"
cols = list(df.columns)
if 'Screenshot' in cols:
    idx = cols.index('Screenshot')
    cols[idx] = 'Screenshot (Image)'
    df.columns = cols

# Save the paths to a list before clearing the column
image_paths = df['Screenshot (Image)'].tolist()

# Clear the text in the image column so it's blank in Excel
df['Screenshot (Image)'] = ""

# Set up Excel writer
writer = pd.ExcelWriter(excel_file, engine='xlsxwriter')
df.to_excel(writer, sheet_name='Posts', index=False)

workbook  = writer.book
worksheet = writer.sheets['Posts']

# Set column widths
worksheet.set_column('A:A', 80) # Image column
worksheet.set_column('B:Z', 20)

row = 1 # Data starts at row 1 (0 is header)
for idx, img_path in enumerate(image_paths):
    worksheet.set_row(row, 400) # Set row height to fit image
    
    img_path = str(img_path)
    
    # Clean up the path
    if pd.notna(img_path) and img_path.strip() != "":
        # Some might be "crops/file.png" and some might just be "file.png"
        if not img_path.startswith("crops/"):
            img_path = os.path.join("crops", img_path)
            
        if os.path.exists(img_path):
            try:
                # Calculate scale to fit nicely in the cell (approx 560x530 pixels)
                with Image.open(img_path) as im:
                    w, h = im.size
                
                max_w = 540.0
                max_h = 510.0
                
                scale = min(max_w / w, max_h / h)
                
                # If image is smaller than max, don't scale it up too much, or maybe keep it at 1.0
                scale = min(scale, 1.0)
                
                worksheet.insert_image(row, 0, img_path, 
                                     {'x_scale': scale, 'y_scale': scale, 'positioning': 1})
            except Exception as e:
                print(f"Failed to insert {img_path}: {e}")
        else:
            print(f"Image not found: {img_path}")
            
    row += 1

writer.close()
print(f"Successfully generated {excel_file} with embedded images!")
