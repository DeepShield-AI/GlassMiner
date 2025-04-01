from bs4 import BeautifulSoup
import regex as re
import warnings

from configs import *

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

def filter_out_useless_text(list_of_text):
    """
    Filter out the text whose length is longer than the threshold.
    Remove the text with less than 
    """
    new_list = []
    for text in list_of_text:
        if len(text) > TEXT_LEN_MAX_THRESHOLD or len(text) < IGNORE_THRESHOLD:
            continue
        if is_symbols(text):
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
