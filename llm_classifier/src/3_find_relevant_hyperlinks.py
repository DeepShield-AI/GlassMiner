# TODO: According to the hyperlinks in the realted or LG web pages, add new target for crawling
# 1. If it is a related page, find all the urls around the tag with text in filter words.
# 2. If it is a LG page, find all the urls within any list with the same secondary domain, without content in the footer and the header.
import json
from urllib.parse import urljoin
import regex as re
import pickle as pkl

from configs import *
from utils import *

def get_candidate_urls_from_related(html_txt: str):
    """
    Extract the candidate URLs from the related page.
    """
    candidate_urls = set()
    soup = parse_webpages(html_txt)
    if soup is None:
        return candidate_urls
        
    tags_with_lg = []
    for text_node in soup.find_all(string=True):
        text_str = text_node.strip().lower()
        if "looking glass" in text_str or "lookingglass" in text_str:
            tags_with_lg.append(text_node)

    for tag in tags_with_lg:
        parent_tag = tag.parent if tag.parent is not None else tag
        a_tags = parent_tag.find_all("a", href=True)
        for a in a_tags:
            link = a['href'].rstrip("/")
            link = urljoin(url, link)
            candidate_urls.add(link)
    return candidate_urls

def get_candidate_urls_from_lg(html_txt:str):
    """
    Extract the candidate URLs from the LG page.
    Directly find all the urls with the same 
    """
    urls = set()
    # Directly find all the urls using regex
    pattern = re.compile(r'https?://[^\s\'"<>]+')
    matched_urls = re.findall(pattern, html_txt)
    # Remove the urls that are not looking glass pages
    for url in matched_urls:
        url_lower = url.lower()
        # Check if the url is a looking glass page
        for word in URL_FILTER_WORDS:
            if word in url_lower:
                urls.add(url)
                break
    return urls

def get_candidate_urls_from_html(html_txt:str, is_lg=False):
    if is_lg:
        urls = get_candidate_urls_from_lg(html_txt)
    else:
        urls = get_candidate_urls_from_related(html_txt)
    # filter out all the shown urls
    return urls

if __name__ == "__main__":
    with open(os.path.join(DATA_DIR, CAND_FILE), "r") as f:
        candidate_page_list = json.load(f)
    # build the set of all the appeared urls
    set_crawled_url = {info["url"] for info in candidate_page_list}
    
    with open(os.path.join(OUTPUT_DIR, RELATED_FILE), "r") as f:
        related_page_list = json.load(f)
    with open(os.path.join(OUTPUT_DIR, UNIQ_FILE), "r") as f:
        lg_page_list = json.load(f)        
    set_candidate_urls = set()
    
    for page_info in related_page_list:
        url = page_info["url"]
        filename = page_info["filename"]
        filepath = os.path.join(RELATED_DIR, filename)
        html_str = open(filepath, "r", encoding="utf-8").read()
        urls = get_candidate_urls_from_html(html_str, is_lg=False)
        urls = urls - set_crawled_url
        set_candidate_urls.update(urls)
        set_crawled_url.update(urls)
        
    for lg_info in lg_page_list:
        url = lg_info["url"]
        filename = lg_info["filename"]
        filepath = os.path.join(SAVE_DIR, filename)
        html_str = open(filepath, "r", encoding="utf-8").read()
        urls = get_candidate_urls_from_html(html_str, is_lg=True)
        urls = urls - set_crawled_url
        set_candidate_urls.update(urls)
        set_crawled_url.update(urls)
    
    print("Total candidate urls: ", len(set_candidate_urls))
    with open(os.path.join(OUTPUT_DIR, "new_candidate_urls.bin"), "wb") as f:
        pkl.dump(set_candidate_urls, f)