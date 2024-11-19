import numpy as np
from PIL import Image
import io
import base64

# def process_image_ocr(uploaded_file):
#     """
#     Process uploaded image files using EasyOCR
#     Returns extracted text and image array
#     """
#     # Initialize reader
#     reader = easyocr.Reader(['en'])
    
#     # Read image file
#     image_bytes = uploaded_file.read()
#     image = Image.open(io.BytesIO(image_bytes))
    
#     # Convert to numpy array
#     image_np = np.array(image)
    
#     # Perform OCR
#     try:
#         results = reader.readtext(image_np)
#         extracted_text = ' '.join([text[1] for text in results])
#         return extracted_text.strip(), image
#     except Exception as e:
#         raise Exception(f"OCR processing failed: {str(e)}")

# Function to encode the image
def encode_image(image_path):
  with open(image_path, "rb") as image_file:
    return base64.b64encode(image_file.read()).decode('utf-8')

def process_image(uploaded_file):
     # Read uploaded file into base64
    image_bytes = uploaded_file.read()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    image = Image.open(io.BytesIO(image_bytes))
    
    return base64_image, image