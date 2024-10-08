import asyncio
from langchain_community.document_loaders import PyPDFLoader

async def load_pages():
    file_path = r"C:/Users/elroy/OneDrive/Desktop/Personal/Elroy/chatbot/introduction-to-algorithms.pdf"
    loader = PyPDFLoader(file_path)
    pages = []
    async for page in loader.alazy_load():
        pages.append(page)
    return pages

# Running the async function
if __name__ == "__main__":
    pages = asyncio.run(load_pages())
    print(f"{pages[24].metadata}\n")
    print(pages[24].page_content)