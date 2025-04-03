from bs4 import BeautifulSoup, NavigableString
import regex as re
import warnings
import html2text

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

def collect_text_in_order(html_str):
    handler = html2text.HTML2Text()
    handler.ignore_emphasis = True
    handler.ignore_links = False
    handler.single_line_break = True
    handler.body_width = 0
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
    text = re.sub(r"\s+", " ", text)
    link_matches = re.findall(RTN_LINK, text)
    # two groups, the first group is the text, the second group is the link
    for match in link_matches:
        # check if the first group contains filter words, if not, remove the link
        if not contain_filter_words(match[0]):
            # replace the original match with the first group
            text = text.replace(f"[{match[0]}]({match[1]})", match[0])
    return text.strip()