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

def process_pdf(uploaded_file, extract_metadata=False, max_pages=None):
    """
    Process an uploaded PDF file using pdfplumber.
    
    Args:
        uploaded_file: Streamlit uploaded file object
        extract_metadata: Whether to extract and return PDF metadata (default: False)
        max_pages: Maximum number of pages to process (default: None - process all)
    
    Returns:
        Union[str, Dict[str, Any]]: Extracted text content from the PDF or dict with text and metadata
    """
    import pdfplumber
    import io
    import logging
    
    # Configure logging
    logger = logging.getLogger(__name__)
    
    # Initialize result
    result = {
        "text": "",
        "metadata": {},
        "pages_processed": 0,
        "total_pages": 0
    }
    
    try:
        # Get binary content from the uploaded file
        pdf_bytes = uploaded_file.getvalue()
        
        # Use BytesIO to create a file-like object from the bytes
        with io.BytesIO(pdf_bytes) as pdf_file:
            # Use pdfplumber to open the file-like object directly
            with pdfplumber.open(pdf_file) as pdf:
                # Store total pages count
                result["total_pages"] = len(pdf.pages)
                
                # Extract metadata if requested
                if extract_metadata:
                    result["metadata"] = pdf.metadata
                
                # Determine pages to process
                pages_to_process = pdf.pages[:max_pages] if max_pages else pdf.pages
                
                # Process each page
                text_content = []
                for i, page in enumerate(pages_to_process):
                    try:
                        page_text = page.extract_text() or ""
                        text_content.append(page_text)
                        result["pages_processed"] += 1
                    except Exception as page_error:
                        logger.warning(f"Error extracting text from page {i+1}: {str(page_error)}")
                        text_content.append(f"[Error extracting text from page {i+1}]")
                
                # Join all text with double newlines between pages
                result["text"] = "\n\n".join(text_content)
        
        # Return the result
        return result["text"] if not extract_metadata else result
    
    except pdfplumber.PDFSyntaxError as e:
        logger.error(f"Invalid or corrupted PDF file: {str(e)}")
        raise Exception(f"The uploaded file is not a valid PDF: {str(e)}")
    except Exception as e:
        logger.error(f"Error processing PDF: {str(e)}", exc_info=True)
        raise Exception(f"Error processing PDF: {str(e)}")