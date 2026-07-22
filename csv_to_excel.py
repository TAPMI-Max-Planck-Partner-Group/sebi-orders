import pandas as pd
import xlsxwriter
from PIL import Image
import os

csv_file = "extracted_posts.csv"
excel_file = "extracted_posts_final.xlsx"

df = pd.read_csv(csv_file)
workbook = xlsxwriter.Workbook(excel_file)
worksheet = workbook.add_worksheet()

header_format = workbook.add_format({'bold': True, 'bg_color': '#D7E4BC'})
text_format = workbook.add_format({'text_wrap': True, 'valign': 'top', 'valign': 'vcenter'})

headers = df.columns.tolist()
for col_num, header in enumerate(headers):
    worksheet.write(0, col_num, header, header_format)

COL_A_WIDTH_CHARS = 70 # Approx 490 pixels wide for larger readability
worksheet.set_column('A:A', COL_A_WIDTH_CHARS) 
worksheet.set_column('B:B', 50) # Extracted Text
worksheet.set_column('C:C', 15) # Platform
worksheet.set_column('D:D', 40) # Modus Operandi
worksheet.set_column('E:E', 20) # Post Type
worksheet.set_column('F:F', 20) # Date
worksheet.set_column('G:G', 15) # Page Number 
worksheet.set_column('H:H', 30) # PDF Name

# Approximate pixels per character width in Excel
PIXELS_PER_CHAR = 7
COL_A_WIDTH_PIXELS = COL_A_WIDTH_CHARS * PIXELS_PER_CHAR

for row_num, row_data in df.iterrows():
    excel_row = row_num + 1
    img_path = str(row_data['Screenshot'])
    
    row_height_points = 60 # default fallback height
    
    if pd.notna(img_path) and os.path.exists(img_path):
        try:
            with Image.open(img_path) as img:
                width, height = img.size
            
            # We want the image to fit the column width exactly.
            if width > 0:
                scale = COL_A_WIDTH_PIXELS / width
            else:
                scale = 1.0
                
            # If the image is naturally smaller, don't upscale it to blurriness
            if scale > 1.0:
                scale = 1.0
                
            # Calculate what the visual height will be in pixels
            scaled_height = height * scale
            
            # Convert pixels to points for Excel row height (1 pixel ~ 0.75 points)
            # Add 15 points of padding
            row_height_points = max(60, (scaled_height * 0.75) + 15) 
            
            worksheet.set_row(excel_row, row_height_points)
            
            # Insert original high-res image, but scaled visually in Excel
            worksheet.insert_image(excel_row, 0, img_path, 
                                   {'x_scale': scale, 'y_scale': scale, 'x_offset': 5, 'y_offset': 5, 'object_position': 1})
        except Exception as e:
            worksheet.set_row(excel_row, row_height_points)
            worksheet.write(excel_row, 0, f"Error: {e}", text_format)
    else:
        worksheet.set_row(excel_row, row_height_points)
        worksheet.write(excel_row, 0, "No image", text_format)
        
    worksheet.write(excel_row, 1, str(row_data['Extracted Text']) if pd.notna(row_data.get('Extracted Text')) else "", text_format)
    worksheet.write(excel_row, 2, str(row_data['Platform']) if pd.notna(row_data.get('Platform')) else "", text_format)
    worksheet.write(excel_row, 3, str(row_data['Modus Operandi']) if pd.notna(row_data.get('Modus Operandi')) else "", text_format)
    worksheet.write(excel_row, 4, str(row_data['Post Type']) if pd.notna(row_data.get('Post Type')) else "", text_format)
    worksheet.write(excel_row, 5, str(row_data['Date']) if pd.notna(row_data.get('Date')) else "", text_format)
    worksheet.write(excel_row, 6, str(row_data['Page Number']) if pd.notna(row_data.get('Page Number')) else "", text_format)
    worksheet.write(excel_row, 7, str(row_data['PDF Name']) if pd.notna(row_data.get('PDF Name')) else "", text_format)

workbook.close()
print("Successfully created extracted_posts_final.xlsx with dynamic row heights and high-res images!")
