#!/usr/bin/env python3
"""
Fusion 360 API Documentation Content Extractor

Fast HTML-to-markdown converter for Fusion API documentation.
Replaces slow claude CLI calls with sub-second response times.
"""

import sys
import requests
import html2text
from pathlib import Path
from bs4 import BeautifulSoup
import re

def extract_content(url, language='python'):
    """Fetch HTML documentation and convert to clean markdown."""
    
    try:
        # Handle local file URLs for testing
        if url.startswith('file://'):
            file_path = url[7:]  # Remove 'file://' prefix
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
        else:
            # Fetch HTML content from web
            headers = {
                'User-Agent': 'Fusion API Documentation Tool/1.0'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            html_content = response.text
        
        # Clean and process HTML before conversion
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Remove copy code buttons and copyCode scripts
        for button in soup.find_all('button'):
            button.decompose()
        
        # Remove copyCode JavaScript functions
        for script in soup.find_all('script'):
            if script.string and 'copyCode' in script.string:
                script.decompose()
        
        # Clean up copyright notice div - keep only the essential copyright text
        copyright_div = soup.find('div', {'id': 'CopyrightNotice'})
        if copyright_div:
            # Keep just the simple copyright line, remove the table structure
            copyright_text = copyright_div.get_text().strip()
            if '© Copyright' in copyright_text:
                # Extract just the copyright line
                import re
                copyright_match = re.search(r'© Copyright \d{4} Autodesk, Inc\.', copyright_text)
                if copyright_match:
                    simple_copyright = soup.new_tag('p')
                    simple_copyright.string = copyright_match.group()
                    copyright_div.replace_with(simple_copyright)
                else:
                    copyright_div.decompose()
            else:
                copyright_div.decompose()
        
        # Process language-specific code blocks for tabbed samples
        if language == 'cpp':
            # Remove Python tabs and content
            for tab_div in soup.find_all('div', {'id': 'Python'}):
                tab_div.decompose()
            for li in soup.find_all('li'):
                if li.find('a') and li.find('a').get('href') == '#Python':
                    li.decompose()
        else:  # default to python
            # Remove C++ tabs and content  
            for tab_div in soup.find_all('div', {'id': 'C++'}):
                tab_div.decompose()
            for li in soup.find_all('li'):
                if li.find('a') and li.find('a').get('href') == '#C++':
                    li.decompose()
        
        # Also handle simple sequential Python/C++ headers (like BasicConcepts)
        if language == 'cpp':
            # Remove Python sections: find h4 with "Python" and remove until next h4 or h3
            current = None
            for elem in soup.find_all(['h4', 'h3', 'h2']):
                if elem.name == 'h4' and 'Python' in elem.get_text():
                    current = elem
                    break
            if current:
                # Remove this h4 and following pre until we hit another heading
                next_elem = current.next_sibling
                current.decompose()
                while next_elem and next_elem.name not in ['h4', 'h3', 'h2']:
                    if hasattr(next_elem, 'decompose'):
                        temp = next_elem.next_sibling
                        if next_elem.name == 'pre':
                            next_elem.decompose()
                        next_elem = temp
                    else:
                        next_elem = next_elem.next_sibling
        else:  # python
            # Remove C++ sections
            current = None
            for elem in soup.find_all(['h4', 'h3', 'h2']):
                if elem.name == 'h4' and 'C++' in elem.get_text():
                    current = elem
                    break
            if current:
                # Remove this h4 and following pre until we hit another heading
                next_elem = current.next_sibling
                current.decompose()
                while next_elem and next_elem.name not in ['h4', 'h3', 'h2']:
                    if hasattr(next_elem, 'decompose'):
                        temp = next_elem.next_sibling
                        if next_elem.name == 'pre':
                            next_elem.decompose()
                        next_elem = temp
                    else:
                        next_elem = next_elem.next_sibling
        
        # Convert <pre> tags to proper markdown code blocks
        # We need to do this BEFORE the html2text conversion to preserve formatting
        pre_blocks = []
        for i, pre in enumerate(soup.find_all('pre')):
            # Extract content while preserving whitespace using get_text() but with separator to maintain structure
            pre_content = pre.get_text(separator='', strip=False)
            
            if not pre_content.strip():
                continue
                
            # Determine language from content
            lang_hint = ""
            if 'adsk::' in pre_content or 'Ptr<' in pre_content or '#include' in pre_content:
                lang_hint = "cpp"
            elif 'import adsk' in pre_content or 'def ' in pre_content:
                lang_hint = "python"
            
            # Store the formatted code block
            placeholder = f"___CODEBLOCK_{i}___"
            pre_blocks.append((placeholder, lang_hint, pre_content))
            
            # Replace pre with placeholder
            pre.replace_with(soup.new_string(placeholder))
        
        # Configure html2text converter
        h = html2text.HTML2Text()
        h.ignore_links = False      # Preserve links to other documentation
        h.body_width = 0            # Don't wrap lines 
        h.ignore_images = False     # Keep image references
        h.ignore_emphasis = False   # Keep bold/italic formatting
        h.skip_internal_links = True # Skip javascript: links
        
        # Convert HTML to markdown
        markdown_content = h.handle(str(soup))
        
        # Replace placeholders with properly formatted code blocks
        for placeholder, lang_hint, pre_content in pre_blocks:
            code_block = f"\n```{lang_hint}\n{pre_content}\n```\n"
            markdown_content = markdown_content.replace(placeholder, code_block)
        
        # Clean up the output
        markdown_content = clean_markdown(markdown_content)
        
        return markdown_content.strip()
        
    except requests.RequestException as e:
        return f"Error fetching documentation: {e}\nURL: {url}"
    except Exception as e:
        return f"Error processing documentation: {e}\nURL: {url}"

def clean_markdown(content):
    """Clean up common markdown conversion artifacts."""
    
    # Remove excessive blank lines (more than 2 consecutive)
    lines = content.split('\n')
    cleaned_lines = []
    blank_count = 0
    
    for line in lines:
        if line.strip() == '':
            blank_count += 1
            if blank_count <= 2:
                cleaned_lines.append(line)
        else:
            blank_count = 0
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)

def main():
    """Command line interface."""
    
    if len(sys.argv) < 2:
        print("Usage: api_content_extractor.py <url> [language]", file=sys.stderr)
        print("  url: Documentation URL to fetch", file=sys.stderr) 
        print("  language: python|cpp (default: python)", file=sys.stderr)
        sys.exit(1)
    
    url = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else 'python'
    
    if language not in ['python', 'cpp']:
        print(f"Error: Invalid language '{language}'. Use 'python' or 'cpp'", file=sys.stderr)
        sys.exit(1)
    
    # Extract and print content
    content = extract_content(url, language)
    print(content)

if __name__ == '__main__':
    main()