# Post-processing of the seed pages to cluster them based on the similarity of the content.
# We just check if the seed pages have the keyword "Looking Glass" in the title or body.

# Import the required libraries
import json
import hashlib
import re
from typing import List
from bs4 import BeautifulSoup

# Import the customized content
from configs import *

def filter_out_useless_text(list_of_text: List[str]) -> List[str]:
    """
    Filter out the text whose length is longer than the threshold.
    Remove the text with less than 
    """
    new_list = []
    for text in list_of_text:
        if len(text) > TEXT_LEN_THRESHOLD or len(text) < IGNORE_THRESHOLD:
            continue
        new_list.append(text)
    return new_list
    
def remove_tags_and_get_short_text(soup: BeautifulSoup) -> List[str]:
    """
    Remove all the content within tags from the soup, keep the text only.
    DO NOT include the text from its children!
    Return the list of texts for given soup.
    """
    list_of_text = []    
    for tag in soup.find_all():
        # If the tag is a script or style tag, we skip it
        if tag.name in ["script", "style"]:
            continue
        # Get the direct text of the current label (without recursion)
        direct_texts = tag.find_all(string=True, recursive=False)
        combined = ' '.join(text.strip() for text in direct_texts).strip()
        if combined:
            list_of_text.append(combined)
        # if tag is an input tag, we can extract the "value" attr
        if tag.name == "input" and tag.get("value"):
            list_of_text.append(tag.get("value"))
    list_of_text = filter_out_useless_text(list_of_text)
    return list_of_text

def check_webpage_content_and_verify(contents: list[str], url: str) -> int:
    """
    Check if the webpage is a Looking Glass page by checking the title and body.
    Return 1 if the webpage is a Looking Glass page, -1 if not， 0 for unknown.
    """
    # check the content to verify if it's a looking glass page
    is_verified = False
    for text in contents:
        for word in SIMPLE_FILETER_WORDS:
            if word in text.lower():
                is_verified = True
                break
    if is_verified:
        return 1
    else:
        # check the url if there're "lg" or "looking glass" in the url
        # and the content didn't contain "not found" or "404"
        url = url.lower()
        # split the url by non-alphabet characters except for "-"
        url_parts = re.split(r"[^a-zA-Z-]+", url)
        is_related = False
        for part in url_parts:
            if part in SIMPLE_FILETER_URLS:
                is_related = True
                break
        if is_related:
            for text in contents:
                for word in SIMPLE_STOP_WORDS:
                    if word in text.lower():
                        return -1
            return 0
        return -1
        

if __name__ == "__main__":
    # Load the seed pages
    available_pages = json.load(open(os.path.join(OUTPUT_DIR, AVAI_FILE), "r"))
    print(f"Total {len(available_pages)} seed pages are loaded.")
    dict_page_contents = {}
    verified_cnt = 0
    unverified_cnt = 0
    unrelated_cnt = 0
    duplicate_cnt = 0
    total_cnt = 0
    # clear the three directories
    for dir_path in [VERIFIED_DIR, UNVERIFIED_DIR, PROCS_DIR, UNRELATED_DIR]:
        os.makedirs(dir_path, exist_ok=True)
        for filename in os.listdir(dir_path):
            os.remove(os.path.join(dir_path, filename))
    for lg_info in available_pages:
        filename = lg_info["filename"]
        url = lg_info["url"]
        with open(os.path.join(SAVE_DIR, filename), "r") as f:
            current_page = f.read()

        # Extract the content from the seed pages
        seed_contents = []
        soup = BeautifulSoup(current_page, "html.parser")
        seed_contents = remove_tags_and_get_short_text(soup)
        # save to the output directory
        with open(os.path.join(PROCS_DIR, filename), "w") as f:
            f.write("\n".join(seed_contents))

        total_cnt += 1
        if total_cnt % 100 == 0:
            print(f"Processed {total_cnt} seed pages.")
        
        # hash the content to avoid duplication
        hash_content = hashlib.md5("".join(seed_contents).encode()).hexdigest()
        if hash_content not in dict_page_contents.keys():
            dict_page_contents[hash_content] = [url] 
        else:
            duplicate_cnt += 1
            dict_page_contents[hash_content].append(url)
            continue

        # Verify the seed pages
        result = check_webpage_content_and_verify(seed_contents, url)
        if result == 1:
            verified_cnt += 1
            os.rename(os.path.join(PROCS_DIR, filename), os.path.join(VERIFIED_DIR, filename))
        elif result == -1:
            unrelated_cnt += 1
            os.rename(os.path.join(PROCS_DIR, filename), os.path.join(UNRELATED_DIR, filename))
        elif result == 0:
            unverified_cnt += 1
            os.rename(os.path.join(PROCS_DIR, filename), os.path.join(UNVERIFIED_DIR, filename))

    print("=====================================")
    print(f"Total {total_cnt} seed pages are processed.")
    print(f"{verified_cnt} unique seed pages are verified.")
    print(f"{unverified_cnt} unique seed pages are unverified.")
    print(f"{unrelated_cnt} unique seed pages are unrelated.")
    print(f"{duplicate_cnt} seed pages are duplicated.")
    print("Now you need to verifiy the unverified seed pages manually.")
    print("Just move the verified seed pages to the verified folder.")
    print("=====================================")
    
    # dump the dict_page_contents with more than one urls to the output directory
    with open(os.path.join(OUTPUT_DIR, "duplicated_seed_pages.json"), "w") as f:
        for hash_val, urls in dict_page_contents.items():
            if len(urls) > 1:
                f.write(f"{', '.join(urls)}\n")