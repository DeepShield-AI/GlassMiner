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
from niteru.html_parser import parse_html

from configs import *

requests.packages.urllib3.disable_warnings()
context = ssl.create_default_context()
context.set_ciphers('HIGH:!DH:!aNULL')

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
        min_len = min(len(self.a), len(self.b))
        log_max_len = log2(max(len(self.a), len(self.b)))
        return 1.0 * matches / (min_len + log_max_len)

def request_with_random_header(url: str) -> BeautifulSoup | None:
    """
    Send a request to the target URL with a random User-Agent
    """
    header = BASE_HEADER
    header["User-Agent"] = random.choice(USER_AGENT_LIST)
    response = requests.get(url, headers=header)
    soup = parse_webpages(response.text)
    return soup

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
            response = session.get(url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True)
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

def is_symbols(token):
    if re.match(PTN_CHAR, token):
        return True
    return False

def parse_webpages(webpage: str) -> BeautifulSoup | None:
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

def sequence_similarity(html_1: str, html_2: str):
    comparator = StructuralComparator()
    parsed1 = parse_html(html_1)
    parsed2 = parse_html(html_2)
    comparator.set_seq1(parsed1.tags)
    comparator.set_seq2(parsed2.tags)
    return comparator.ratio()
