import fitz  # PyMuPDF

# Load the PDF file
pdf_path = "data/books/cp1.pdf"
doc = fitz.open(pdf_path)

# Loop through the pages and extract text
for page_num in range(doc.page_count):
    page = doc.load_page(page_num)  # Load the page
    text = page.get_text("text")    # Extract text from the page
    print(f"--- Page {page_num + 1} ---\n{text}\n")

