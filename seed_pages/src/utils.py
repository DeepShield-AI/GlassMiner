import time
from bs4 import BeautifulSoup
import warnings
import random
import requests
import ssl

from configs import *

requests.packages.urllib3.disable_warnings()
context = ssl.create_default_context()
context.set_ciphers('HIGH:!DH:!aNULL')

def request_with_random_header(url: str) -> BeautifulSoup:
    """
    Send a request to the target URL with a random User-Agent
    """
    header = BASE_HEADER
    header["User-Agent"] = random.choice(USER_AGENT_LIST)
    response = requests.get(url, headers=header)
    soup = parse_webpages(response.text)
    return soup

def fetch_one_page(url, session: requests.Session, retry_count=0) -> dict:
    try:
        header = BASE_HEADER
        header["User-Agent"] = random.choice(USER_AGENT_LIST)
        # First send a HEAD request to check content type
        head_response = session.head(url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True)
        content_type = head_response.headers.get('Content-Type', '')
        # Skip if it's a file download
        if not content_type.startswith(('text/', 'application/json', 'application/xml')):
            return {
                "original_url": url,
                "error": "Skipped file download",
                "content": None,
                "success": False
            }
        # ignore the https insecure warning, and allow the redirect
        response = session.get(url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True)

    except Exception as e:
        if retry_count < MAX_RETRY:
            if url.startswith("http:"):
                url = "https" + url[4:]
            else:
                url = "http" + url[5:]
            time.sleep(1 * retry_count)
            return fetch_one_page(url, session, retry_count + 1)
        return {
            "original_url": url,
            "error": str(e),
            "retries": retry_count,
            "success": False
        }
    # remove tailing slash
    final_url = response.url.rstrip('/')
    return {
        "original_url": url,
        "final_url": final_url,
        "content": response.text,
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

def count_filter_words(contents: str) -> int:
    """
    Check if the webpage is a Looking Glass page by checking the title and body.
    Return the count of appeared filter words.
    """
    # check the content to verify if it's a looking glass page
    appeared_set = set()
    text_lower = contents.lower()
    for word in SIMPLE_FILETER_WORDS:
        if word.lower() in text_lower:
            appeared_set.add(word)
    return len(appeared_set)

def parse_webpages(webpage) -> BeautifulSoup:
    """
    Adaptive parsing of the webpage content by html parser or lxml parser.
    """
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            soup = BeautifulSoup(webpage, "html.parser")
            # 检查是否有 XML 解析警告
            if any("XMLParsedAsHTMLWarning" in str(warning.message) for warning in w):
                raise Warning("Detected XML parsed as HTML, switching to XML parser.")
    except Warning:
        # 重新使用 xml 解析器解析
        soup = BeautifulSoup(webpage, "xml")
    return soup

def filter_out_useless_text(list_of_text):
    """
    Filter out the text whose length is longer than the threshold.
    Remove the text with less than 
    """
    new_list = []
    for text in list_of_text:
        if len(text) > TEXT_LEN_MAX_THRESHOLD or len(text) < IGNORE_THRESHOLD:
            continue
        new_list.append(text)
    return new_list

def remove_script_and_style(soup: BeautifulSoup):
    """
    Using BeautifulSoup to remove all the script style tages
    """
    for script in soup.find_all('script'):
        script.decompose()
    for style in soup.find_all('style'):
        style.decompose()
    return soup

def remove_tags_and_get_short_text(soup: BeautifulSoup):
    """
    Remove all the content within tags from the soup, keep the meta content and text only.
    DO NOT include the text from its children!
    Return the list of texts for given soup.
    """
    list_of_text = []    
    for tag in soup.find_all():
        # If the tag is a script or style tag, we skip it
        if tag.name in ["script", "style"]:
            continue
        # First, we get the content in the meta tag
        if tag.name == "meta":
            if tag.get("content") and tag.get("name"):
                list_of_text.append(tag.get("content"))
        # Get the direct text of the current label (without recursion)
        direct_texts = tag.find_all(string=True, recursive=False)
        
        text_list = [text.strip() for text in direct_texts]
        list_of_text.extend(text_list)
        # if tag is an input tag, we can extract the "value" attr
        if tag.name == "input" and tag.get("value"):
            list_of_text.append(tag.get("value"))
    list_of_text = filter_out_useless_text(list_of_text)
    return list_of_text
