from langchain_community.document_loaders import PDFPlumberLoader
from io import BytesIO
from PIL import Image
import io
import base64

def process_image(uploaded_file):
     # Read uploaded file into base64
    image_bytes = uploaded_file.read()
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    image = Image.open(io.BytesIO(image_bytes))
    
    return base64_image, image

def process_pdf(uploaded_file):
    """
    Process an uploaded PDF file using PDFPlumberLoader.
    
    Args:
        uploaded_file: Streamlit uploaded file object
    
    Returns:
        str: Extracted text content from the PDF
    """
    try:
        import tempfile
        import pdfplumber
        
        # Create a temporary file to save the uploaded PDF
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp_file:
            # Write the uploaded file content to the temp file
            tmp_file.write(uploaded_file.getvalue())
            tmp_file_path = tmp_file.name
        
        # Use pdfplumber directly instead of PDFPlumberLoader
        text_content = ""
        with pdfplumber.open(tmp_file_path) as pdf:
            for page in pdf.pages:
                text_content += page.extract_text() or ""
                text_content += "\n\n"  # Add spacing between pages
        
        # Clean up the temporary file
        import os
        os.unlink(tmp_file_path)
        
        return text_content
        
    except Exception as e:
        raise Exception(f"Error processing PDF: {str(e)}")