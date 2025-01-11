import requests
from bs4 import BeautifulSoup
import time
import os
import random
from urllib.parse import urljoin

class GeeksForGeeksScraper:
    def __init__(self, delay_range=(1, 3)):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.delay_range = delay_range
        self.base_url = "https://www.geeksforgeeks.org"

    def _delay(self):
        """Add random delay between requests"""
        time.sleep(random.uniform(*self.delay_range))

    def fetch_page(self, url):
        """Fetch a page with error handling"""
        try:
            self._delay()
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {str(e)}")
            return None

    def find_topic_section(self, soup):
        """Find the main topic section containing organized links"""
        # Look for common patterns in topic pages
        patterns = [
            # Pattern 1: Headers followed by lists
            {'headers': ['h2', 'h3'], 'min_links': 3},
            # Pattern 2: Multiple lists with significant links
            {'lists': 'ul', 'min_links': 5},
            # Pattern 3: Specific div classes that often contain topic lists
            {'container': ['post-content', 'entry-content', 'article-content']}
        ]
        
        for pattern in patterns:
            if 'headers' in pattern:
                # Look for sections with headers followed by lists
                for header_tag in pattern['headers']:
                    headers = soup.find_all(header_tag)
                    for header in headers:
                        next_ul = header.find_next('ul')
                        if next_ul and len(next_ul.find_all('a')) >= pattern['min_links']:
                            return header.parent
            
            elif 'lists' in pattern:
                # Look for sections with multiple lists
                lists = soup.find_all('ul')
                for ul in lists:
                    if len(ul.find_all('a')) >= pattern['min_links']:
                        return ul.parent
            
            elif 'container' in pattern:
                # Look for specific container classes
                for class_name in pattern['container']:
                    container = soup.find('div', class_=class_name)
                    if container and container.find_all('a'):
                        return container
        
        return None

    def scrape_from_url(self, url):
        """Scrape content from a GeeksForGeeks URL"""
        print(f"Fetching main page: {url}")
        html_content = self.fetch_page(url)
        if not html_content:
            return None
        
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find the page title
        page_title = soup.find('h1')
        main_title = page_title.get_text(strip=True) if page_title else "GeeksForGeeks Guide"
        
        # Find the topic section
        topic_section = self.find_topic_section(soup)
        if not topic_section:
            print("Could not find topic section in the page")
            return None
        
        # Initialize markdown content
        markdown_content = [f"# {main_title}\n"]
        
        # Find all section headers
        for header in topic_section.find_all(['h2', 'h3']):
            section_title = header.get_text(strip=True)
            if not section_title or len(section_title) < 2:
                continue
                
            print(f"\nProcessing section: {section_title}")
            markdown_content.append(f"\n## {section_title}\n")
            
            # Find the next ul element after the header
            ul = header.find_next('ul')
            if ul:
                for li in ul.find_all('li'):
                    link = li.find('a')
                    if link and link.get('href'):
                        article_url = urljoin(self.base_url, link.get('href'))
                        text = link.get_text(strip=True)
                        print(f"Scraping: {text} - {article_url}")
                        
                        markdown_content.append(f"\n### {text}\n")
                        
                        # Fetch and parse the linked page
                        page_html = self.fetch_page(article_url)
                        if page_html:
                            article_content = self.extract_article_content(page_html)
                            if article_content:
                                markdown_content.append(article_content['content'])
                        
                        markdown_content.append("\n---\n")
        
        return markdown_content
    
    def extract_article_content(self, html):
        """Extract content from an article page with improved code block handling"""
        if not html:
            return None
            
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract title
        title = ""
        h1 = soup.find('h1')
        if h1:
            title = h1.get_text(strip=True)
        
        # Initialize markdown content
        markdown_content = []
        
        # Find the main article content
        main_content = soup.find('article') or soup.find('div', {'class': ['post-content', 'entry-content', 'article-content']})
        
        if main_content:
            # Track code block state
            in_code_block = False
            current_code_block = []
            current_language = None
            
            # Process each element
            elements = main_content.find_all(['p', 'h2', 'h3', 'h4', 'pre', 'code', 'ul', 'ol', 'div'])
            
            for element in elements:
                # Handle headers
                if element.name in ['h2', 'h3', 'h4']:
                    # Close any open code block
                    if in_code_block and current_code_block:
                        markdown_content.append(f"\n```{current_language or ''}\n{''.join(current_code_block)}\n```\n")
                        current_code_block = []
                        in_code_block = False
                    
                    level = int(element.name[1]) + 1
                    markdown_content.append(f"\n{'#' * level} {element.get_text(strip=True)}\n")
                
                # Handle paragraphs
                elif element.name == 'p':
                    # Close any open code block
                    if in_code_block and current_code_block:
                        markdown_content.append(f"\n```{current_language or ''}\n{''.join(current_code_block)}\n```\n")
                        current_code_block = []
                        in_code_block = False
                    
                    text = element.get_text(strip=True)
                    if text:
                        markdown_content.append(f"\n{text}\n")
                
                # Handle code blocks
                elif element.name in ['pre', 'code'] or (element.name == 'div' and 'code' in element.get('class', [])):
                    code_text = element.get_text()
                    
                    # Try to detect the programming language
                    language = None
                    if 'class' in element.attrs:
                        classes = element.get('class', [])
                        language_classes = [c for c in classes if 'language-' in c]
                        if language_classes:
                            language = language_classes[0].replace('language-', '')
                    
                    # If this is the start of a new code block
                    if not in_code_block:
                        in_code_block = True
                        current_language = language
                    
                    # Add to current code block
                    if code_text.strip():
                        current_code_block.append(code_text)
                
                # Handle lists
                elif element.name in ['ul', 'ol']:
                    # Close any open code block
                    if in_code_block and current_code_block:
                        markdown_content.append(f"\n```{current_language or ''}\n{''.join(current_code_block)}\n```\n")
                        current_code_block = []
                        in_code_block = False
                    
                    markdown_content.append("\n")
                    for li in element.find_all('li'):
                        markdown_content.append(f"- {li.get_text(strip=True)}\n")
            
            # Close any remaining open code block
            if in_code_block and current_code_block:
                markdown_content.append(f"\n```{current_language or ''}\n{''.join(current_code_block)}\n```\n")
        
        return {
            'title': title,
            'content': "\n".join(markdown_content)
        }

    def save_content(self, content, filename):
        """Save content to a markdown file"""
        os.makedirs('scraped_content', exist_ok=True)
        filepath = os.path.join('scraped_content', filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
        print(f"\nContent saved to {filepath}")

def main():
    # Initialize scraper
    scraper = GeeksForGeeksScraper()
    
    urls = ["https://www.geeksforgeeks.org/greedy-algorithms/","https://www.geeksforgeeks.org/dynamic-programming/","https://www.geeksforgeeks.org/graph-data-structure-and-algorithms/","https://www.geeksforgeeks.org/pattern-searching/","https://www.geeksforgeeks.org/branch-and-bound-algorithm/","https://www.geeksforgeeks.org/geometric-algorithms/","https://www.geeksforgeeks.org/randomized-algorithms/"]
    
    for url in urls:
        # Generate filename from URL
        filename = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
        filename = f"{filename}.md"
        
        # Scrape content
        content = scraper.scrape_from_url(url)
        
        if content:
            # Save to file
            scraper.save_content(content, filename)
        else:
            print("Failed to scrape content from the URL")
    # # Get URL from user
    # url = "https://www.geeksforgeeks.org/divide-and-conquer/"
    
    # # Generate filename from URL
    # filename = url.split('/')[-2] if url.endswith('/') else url.split('/')[-1]
    # filename = f"{filename}.md"
    
    # # Scrape content
    # content = scraper.scrape_from_url(url)
    
    # if content:
    #     # Save to file
    #     scraper.save_content(content, filename)
    # else:
    #     print("Failed to scrape content from the URL")

if __name__ == "__main__":
    main()