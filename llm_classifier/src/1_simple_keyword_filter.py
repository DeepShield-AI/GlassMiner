# For all crwaled web pages, check if the wen page content contains at least 2 keywords from the list of keywords.

import json
import os
import pickle as pkl

from configs import *
from utils import *

def extract_context_around_keywords(content: str) -> str | None:
    """
    If the web page content length is too long, we need to extract the context between the keywords.
    """
    match_strs = re.finditer(PTN_KEYWORD, content)
    list_match_pos = []
    for match_str in match_strs:
        list_match_pos.append(match_str.start())
    # If no match, return None
    if len(list_match_pos) == 0:
        return None
    # 3000 characters, usually less than 1000 words.
    if len(content) > 2000:
        # If there are more than 10 keywords, we only keep the last 10 keywords
        if len(list_match_pos) > 10:
            list_match_pos = list_match_pos[-10:]
        # Find every keyword index in the whole text
        slice_len = 200
        list_slices = [(max(0, i - slice_len), min(i + slice_len, len(content))) for i in list_match_pos]
        # For each slice, expand to both sides to find one blank space
        for i in range(len(list_slices)):
            start, end = list_slices[i]
            # Expand to the left
            while start > 0 and content[start - 1] != " ":
                start -= 1
            # Expand to the right
            while end < len(content) and content[end] != " ":
                end += 1
            list_slices[i] = (start, end)
        merged_slices = []
        for start, end in list_slices:
            # If the merged_slices is empty, add the first slice
            if merged_slices and merged_slices[-1][1] >= start:
                merged_slices[-1][1] = max(merged_slices[-1][1], end)
            else:
                merged_slices.append([start, end])

        # Extract the content around the keywords
        context_list = []
        for start, end in merged_slices:
            context_list.append(content[start:end])
        content = " ".join(context_list)
    return content
        
if __name__ == "__main__":
    # Load the candidate page list (Now using available page list as the candidate page list)
    # TMP: Now check if it is existing in the SAVE_DIR
    candidate_page_list = json.load(open(os.path.join(DATA_DIR, CAND_FILE), "r")) 
    print("Total candidate pages: ", len(candidate_page_list))
    # Check all the candidate pages, filter out the web pages that are not looking glass pages.
    os.makedirs(PROCS_DIR, exist_ok=True)
    filtered_page_list = []
    count = 0
    processed_count = 0      # For breakpoint resume
    for lg_info in candidate_page_list:
        # Check if the webpage contains any filter words.
        dst_filepath = os.path.join(PROCS_DIR, lg_info["filename"])
        if not os.path.exists(dst_filepath) and count > processed_count:
            src_filepath = os.path.join(SAVE_DIR, lg_info["filename"])
            html_str = open(src_filepath, "r", encoding="utf-8").read()
            cleaned_str = collect_text_in_order(html_str)
            if cleaned_str is not None:
                context_content = extract_context_around_keywords(cleaned_str)
                if context_content:
                    # save the content to the PROCS_DIR
                    filename = lg_info["filename"]
                    filepath = os.path.join(PROCS_DIR, filename)
                    with open(filepath, "w", encoding="utf-8") as f:
                        f.write(context_content)
                    filtered_page_list.append(lg_info)
        elif os.path.exists(dst_filepath):
            filtered_page_list.append(lg_info)
        count += 1
        if count % 1000 == 0:
            print("{} processed, {} filtered".format(count, len(filtered_page_list)))
    print("Total filtered pages: ", len(filtered_page_list))
    # Save the filtered page list to file
    with open(os.path.join(OUTPUT_DIR, "filtered_page_list.json"), "w", encoding="utf-8") as f:
        json.dump(filtered_page_list, f, indent=4)