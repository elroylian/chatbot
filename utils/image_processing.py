import numpy as np
from PIL import Image
import io
import base64

def process_image(uploaded_file):
     # Read uploaded file into base64
    image_bytes = uploaded_file.read()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    image = Image.open(io.BytesIO(image_bytes))
    
    return base64_image, image