from bs4 import BeautifulSoup
import regex as re
import warnings
import html2text

from configs import *

class CustomHTMLParser(html2text.HTML2Text):
    """
    Custom HTML parser to handle specific cases.
    """
    def __init__(self):
        super().__init__()

        self.ignore_emphasis = True
        self.ignore_links = False
        self.single_line_break = True
        self.body_width = 0

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
    link_matches = re.findall(RTN_LINK, text)
    # two groups, the first group is the text, the second group is the link
    for match in link_matches:
        # check if the first group contains filter words, if not, remove the link
        if not contain_filter_words(match[0]):
            # replace the original match with the first group
            text = text.replace(f"[{match[0]}]({match[1]})", match[0])
    return text.strip()