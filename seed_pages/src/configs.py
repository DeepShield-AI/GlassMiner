import os
import numpy as np
# ====================== Directory & path Configs ====================== #

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
SAVE_DIR = os.path.join(OUTPUT_DIR, "downloaded")
PROCS_DIR = os.path.join(OUTPUT_DIR, "processed")
VERIFIED_DIR = os.path.join(OUTPUT_DIR, "verified")
UNVERIFIED_DIR = os.path.join(OUTPUT_DIR, "unverified")
UNRELATED_DIR = os.path.join(OUTPUT_DIR, "unrelated")
LOGS_DIR = os.path.join(OUTPUT_DIR, "logs")
OLD_LOGS_DIR = os.path.join(OUTPUT_DIR, "old_logs")

AVAI_FILE = "available_lg_page_list.json"
FAIL_FILE = "failed_lg_page_list.json"
SIM_FILE = "similar_matrix_{}.bin"

# ====================== Crawler Configs ====================== #

# crawler configs
MAX_RETRY = 2
TIMEOUT = 15
MAX_WORKERS = 24
# A list of headers to avoid being blocked
USER_AGENT_LIST = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.81 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.97 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.96 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.81 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.96 Safari/537.3",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
]
BASE_HEADER = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6",
    "Cache-Control": "max-age=0",
    "Connection": "keep-alive"
}
SIMPLE_FILETER_WORDS = {
    "looking glass",
    "hyperglass",
    "traceroute",
    "ping",
    "show route",
    "show ip bgp",
}
SIMPLE_FILETER_URLS = {
    "looking-glass",
    "lg",
    "lookingglass",
    "looking",
    "glass",
}
SIMPLE_STOP_WORDS = {
    "not found",
    "forbidden",
    "error",
    "notfound"
}
FILE_NAME_MAX_LENGTH = 200

# ====================== Clustering Configs ====================== #
PTN_CHAR = r'^[^\p{L}\u4e00-\u9fff\u0400-\u04FF]*$'

SHINGLE_SIZE = 3  # The size of the shingle, important for the Jaccard similarity
IGNORE_THRESHOLD = 4 # The text with characters less than this threshold will be ignored
TEXT_LEN_MAX_THRESHOLD = 100  # The threshold of the text length, remove the text if it's too long
TEXT_LEN_MIN_THRESHOLD = 10  # The threshold of the text length, remove the text if it's too short
CLUSTER_THRESHOLD = 0.48  # The threshold of the Jaccard similarity for clustering

SHINGLE_LEN_LIST = [1, 2, 3, 4, 5, 6, 7]
# From 0.1 to 0.6 with step 0.01
CLUSTER_THR_LIST = np.linspace(0.1, 0.9, 81)