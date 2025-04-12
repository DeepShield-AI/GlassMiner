import time
from bs4 import BeautifulSoup
import warnings
import random
import requests
import ssl
import regex as re
from math import log2
import html2text
from difflib import SequenceMatcher
import zstandard as zstd
import io

from configs import *

requests.packages.urllib3.disable_warnings()
context = ssl.create_default_context()
context.set_ciphers('HIGH:!DH:!aNULL')

class CustomHTMLParser(html2text.HTML2Text):
    """
    Custom HTML parser to handle specific cases.
    """
    def __init__(self):
        super().__init__()

        self.ignore_emphasis = True
        self.ignore_links = True
        self.single_line_break = True
        self.body_width = 0

# For structure similarity computation.
class StructuralComparator(SequenceMatcher):
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            super().__init__()
            self._initialized = True
    
    def ratio(self) -> float:
        matches = sum(triple[-1] for triple in self.get_matching_blocks())
        modified_len = min(len(self.a), len(self.b)) + log2(max(len(self.a), len(self.b)))
        if modified_len == 0:
            return 0
        return 1.0 * matches / modified_len

def fetch_one_page(url, session: requests.Session, retry_count=0) -> dict:
    header = BASE_HEADER
    header["User-Agent"] = random.choice(USER_AGENT_LIST)
    try:
        # First send a HEAD request to check content size, discard if > 10 MB
        head_response = session.head(url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True)
        content_size = head_response.headers.get('Content-Length', 0)
        if content_size and int(content_size) > 10 * 1024 * 1024:
            return {
                "original_url": url,
                "error": "Content size too large",
                "success": False
            }
        else:
            response = session.get(url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True, stream=True)
            # check if the content encoding is zstandard
            if response.headers.get('Content-Encoding') == 'zstd':
                # decompress the content
                dctx = zstd.ZstdDecompressor()
                with dctx.stream_reader(io.BytesIO(response.raw.read())) as reader:
                    decompressed = reader.read()
                    response_text = decompressed.decode("utf-8")
            else:
                response_text = response.text
            final_url = response.url.rstrip('/')         
    except Exception as e:
        if retry_count < MAX_RETRY:
            return fetch_one_page(url, session, retry_count + 1)
        return {
            "original_url": url,
            "error": str(e),
            "success": False
        }
    soup = parse_webpages(response_text)
    filename = url_to_filename(final_url)
    filepath = os.path.join(SAVE_DIR, filename)
    with open(filepath, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(str(soup))
    return {
        "original_url": url,
        "final_url": final_url,
        "success": True
    }

def url_to_filename(url: str) -> str:
    """
    Convert the URL to a filename by replacing the special characters.
    """
    filename = url.split('://')[1]    
    # remove the tailing slash, and only keep the first 40 characters
    if filename.endswith('/'):
        filename = filename[:-1]
    filename = filename.replace('/', '_')
    if len(filename) > FILE_NAME_MAX_LENGTH:
        filename = filename[:FILE_NAME_MAX_LENGTH]
    return filename

def contain_filter_words(contents: str) -> bool:
    """
    Check if the webpage contains any filter words.
    """
    text_lower = contents.lower()
    for word in SIMPLE_FILETER_WORDS:
        if word.lower() in text_lower:
            return True
    return False

def parse_webpages(webpage) -> BeautifulSoup:
    """
    Adaptive parsing of the webpage content by html parser or lxml parser.
    """
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            soup = BeautifulSoup(webpage, "html.parser")
            # Check for XML parsed as HTML warnings
            if any("XMLParsedAsHTMLWarning" in str(warning.message) for warning in w):
                soup = BeautifulSoup(webpage, "xml")
    except Exception as e:
        print(f"Error parsing webpage: {e}")
        return None
    return soup
    
def is_symbols(token):
    if re.match(PTN_CHAR, token):
        return True
    return False

def collect_text_in_order(html_str):
    if len(html_str) > 500000:
        return None
    # Part one: Extract text in input / meta, change them into direct text
    soup = parse_webpages(html_str)
    if soup is None:
        return None
    # Find all input with "placeholder" or "value" attributes
    input_tags = soup.find_all("input")
    for input_tag in input_tags:
        text = ""
        # Check if the input tag has a placeholder or value attribute
        if "placeholder" in input_tag.attrs:
            text = input_tag["placeholder"]    
        elif "value" in input_tag.attrs:
            text = input_tag["value"]
        # replace input tags by [Input]:{text}
        if text:
            input_tag.replace_with(f"[Input]:{text}")
    # fing the meta tags with "content" and "name" attributes
    meta_tags = soup.find_all("meta", attrs={"name": True, "content": True})
    # repalce meta tags with [Meta]{name}:{content}
    meta_text = []
    for meta_tag in meta_tags:
        # Check if the meta tag has a name attribute
        name = meta_tag["name"]
        if "hyperglass" in name or "title" in name or "description" in name:            
            content = meta_tag["content"]
            meta_text.append(f"[Meta]:{name}:{content}")
    meta_text = " ".join(meta_text)
    # Part two: Extract text in the body
    html_str = str(soup)
    handler = CustomHTMLParser()
    text = handler.handle(html_str)
    # Split the text by \n
    lines = text.split("\n")
    # Remove empty lines and lines with too long words
    filtered_lines = []
    for line in lines:
        # Remove leading and trailing spaces
        line = line.strip()
        # Check if the line is empty or contains too long words
        if len(line) > 0 and len(line) < TEXT_LEN_MAX_THRESHOLD:
            filtered_lines.append(line)
    # Join the filtered lines into a single string
    text = " ".join(filtered_lines)
    text = meta_text + " " + text
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def sequence_similarity(html_1: str, html_2: str):
    comparator = StructuralComparator()
    comparator.set_seq1(html_1.tags)
    comparator.set_seq2(html_2.tags)
    return comparator.ratio()
