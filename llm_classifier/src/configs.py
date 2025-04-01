import os
import regex as re
import numpy as np
# ====================== Directory & path Configs ====================== #

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
SAVE_DIR = os.path.join(DATA_DIR, "downloaded")
PROCS_DIR = os.path.join(OUTPUT_DIR, "processed")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")

AVAI_FILE = "available_lg_page_list.json"

SIMPLE_FILETER_WORDS = {
    "looking glass",
    "lookingglass",
    "hyperglass",
    "traceroute",
    "ping",
    "route",
    "bgp",
    "ip address",
    "mtr"
}

PTN_CHAR = r'^[^\p{L}\u4e00-\u9fff\u0400-\u04FF]*$'
PTN_IP = r'\b([0-9]{1,3}\.){3}[0-9]{1,3}\b'
PTN_KEYWORD = re.compile(r'\b(?:' + '|'.join(SIMPLE_FILETER_WORDS) + r')\b', re.IGNORECASE)

IGNORE_THRESHOLD = 3 # The text with characters less than this threshold will be ignored
TEXT_LEN_MAX_THRESHOLD = 50  # The threshold of the text length, remove the text if it's too long
TEXT_LEN_MIN_THRESHOLD = 10  # The threshold of the text length, remove the text if it's too short