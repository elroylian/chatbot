# Description: This script converts a PDF file to a Markdown 
import pathlib
import os
import pymupdf4llm

def pdf_to_md():
    try:
        # Input PDF path from user
        path_of_file = input("Please enter the path to the PDF file you would like to convert to Markdown: ")
        
        # Extract Markdown from PDF
        md_text = pymupdf4llm.to_markdown(path_of_file)
        
        # Input output file name
        name_of_file = input("Please enter the name of the output file: ")
        
        # Ensure the filename ends with .md
        if not name_of_file.endswith(".md"):
            name_of_file += ".md"
        
        # Create directory if it does not exist
        output_directory = pathlib.Path("data/md/")
        output_directory.mkdir(parents=True, exist_ok=True)  # Create 'data/md/' directory if it doesn't exist
        
        # Save the markdown file
        output_file_path = output_directory / name_of_file
        output_file_path.write_bytes(md_text.encode())
        
        print(f"Markdown file successfully created as {output_file_path}")
    
    except Exception as e:
        print(f"Error: {e}")

def convert_all_pdfs_to_md():
    try:
        # Path to books directory
        books_dir = pathlib.Path("data/books/")
        md_output_dir = pathlib.Path("data/md/")
        md_output_dir.mkdir(parents=True, exist_ok=True)  # Ensure md directory exists

        # Loop through all PDF files in the books directory
        for pdf_file in books_dir.glob("*.pdf"):
            md_text = pymupdf4llm.to_markdown(str(pdf_file))
            name_of_file = pdf_file.stem  # Filename without extension

            # Ensure the markdown file ends with .md
            md_file_path = md_output_dir / f"{name_of_file}.md"
            md_file_path.write_bytes(md_text.encode())

            print(f"Markdown file created: {md_file_path}")
            # print(pdf_file)

    except Exception as e:
        print(f"Error: {e}")