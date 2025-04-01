# For all crwaled web pages, check if the wen page content contains at least 2 keywords from the list of keywords.

import json
import os
import pickle as pkl

from configs import *
from utils import *

def extract_context_around_keywords(list_text):
    """
    If the web page content length is too long, we need to extract the context between the keywords.
    """
    context = " ".join(list_text)
    match_strs = re.finditer(PTN_KEYWORD, context)
    list_match_pos = []
    for match_str in match_strs:
        list_match_pos.append(match_str.start())
    # If no match, return None
    if len(list_match_pos) == 0:
        return None
    # 3000 characters, usually less than 1000 words.
    if len(context) > 3000:
        # Find every keyword index in the whole text
        slice_len = min(3000 // len(list_match_pos), 300)
        list_slices = [(max(0, i - slice_len), min(i + slice_len, len(context))) for i in list_match_pos]
        # For each slice, expand to both sides to find one blank space
        for i in range(len(list_slices)):
            start, end = list_slices[i]
            # Expand to the left
            while start > 0 and context[start - 1] != " ":
                start -= 1
            # Expand to the right
            while end < len(context) and context[end] != " ":
                end += 1
            list_slices[i] = (start, end)
        merged_slices = []
        for start, end in list_slices:
            # If the merged_slices is empty, add the first slice
            if merged_slices and merged_slices[-1][1] >= start:
                merged_slices[-1][1] = max(merged_slices[-1][1], end)
            else:
                merged_slices.append([start, end])

        # Extract the context around the keywords
        context_list = []
        for start, end in merged_slices:
            context_list.append(context[start:end])
        context = " ".join(context_list)
    return context
        
        
if __name__ == "__main__":
    # Load the candidate page list (Now using available page list as the candidate page list)
    # TMP: Now check if it is existing in the SAVE_DIR
    candidate_page_list = []
    available_page_list = json.load(open(os.path.join(DATA_DIR, AVAI_FILE), "r"))
    for lg_info in available_page_list:
        file_path = os.path.join(SAVE_DIR, lg_info["filename"])
        if os.path.exists(file_path):
            candidate_page_list.append(lg_info)
    print("Total candidate pages: ", len(candidate_page_list))
    # Check all the candidate pages, filter out the web pages that are not looking glass pages.
    os.makedirs(PROCS_DIR, exist_ok=True)
    filtered_page_list = []
    count = 0
    for lg_info in candidate_page_list:
        # Check if the webpage contains any filter words.
        html_str = open(os.path.join(SAVE_DIR, lg_info["filename"]), "r", encoding="utf-8").read()
        soup = parse_webpages(html_str)
        # Remove script and style tags
        cleaned_soup = remove_script_and_style(soup)
        # Remove all the tags
        list_text = remove_tags_and_get_short_text(cleaned_soup)
        context_content = extract_context_around_keywords(list_text)
        if context_content:
            # save the content to the PROCS_DIR
            filename = lg_info["filename"]
            filepath = os.path.join(PROCS_DIR, filename)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(context_content)
            filtered_page_list.append(lg_info)
        count += 1
        if count % 500 == 0:
            print("{} processed, {} filtered".format(count, len(filtered_page_list)))
    print("Total filtered pages: ", len(filtered_page_list))