# According to the corpus given by the previous step, we now use them to build search queries and crawl the webpages.
# The whole process includes three steps:
# 1. Data Preparation: Load the corpus, and the AS-Rank related information. Process the corpus and AS-Rank data.
# 2. Non-Targeted Crawling: Use the corpus in each cluster to build search queries and crawl the webpages.
# 3. Targeted Crawling: Use the AS-Rank information to build search queries and crawl the webpages.

import os
import json
import numpy as np
import pandas as pd
import pickle as pkl
import regex as re

from configs import *
from utils import *

def build_search_terms(list_doc: list[str], list_asn: list[str], list_asn_name: list[str], list_asn_desc: list[str], list_asn_country: list[str]):
    """
    Build the search terms for the search engine.
    """
    list_search_terms = []
    for doc in list_doc:
        list_search_terms.append(doc)
    for asn in list_asn:
        list_search_terms.append(asn)
    for asn_name in list_asn_name:
        list_search_terms.append(asn_name)
    for asn_desc in list_asn_desc:
        list_search_terms.append(asn_desc)
    for asn_country in list_asn_country:
        list_search_terms.append(asn_country)
    return list_search_terms




