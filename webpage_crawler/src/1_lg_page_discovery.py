# According to the corpus given by the previous step, we now use them to build search queries and crawl the webpages.
# The whole process includes three steps:
# 1. Data Preparation: Load the corpus, and the AS-Rank related information. Process the corpus and AS-Rank data.
# 2. Non-Targeted Crawling: Use the corpus in each cluster to build search queries and crawl the webpages.
# 3. Targeted Crawling: Use the AS-Rank information to build search queries and crawl the webpages.

from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import json
import pickle as pkl
import random
import threading
from bs4 import BeautifulSoup as bs
from selenium import webdriver
import time
import json
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import selenium


from configs import *
from utils import *

def build_cluster_search_terms(dict_set_cluster_keywords):
    """
    Build the search terms for the search engine.
    Every time we choose one cluster, find all pairs of keywords in the cluster.
    Then we deduplicate all the pairs and using them as the search terms.
    """
    search_terms = set()
    for cluster_id, cluster_keywords in dict_set_cluster_keywords.items():
        # sort the keywords
        list_sorted_keywords = sorted(list(cluster_keywords))
        for i in range(len(list_sorted_keywords)):
            for j in range(i+1, len(list_sorted_keywords)):
                search_terms.add((list_sorted_keywords[i], list_sorted_keywords[j]))
    return search_terms

def purify_the_corpus(dict_city_by_name):
    """
    Load the general corpus and the clustered corpus.
    Purify the corpus by removing the geolocation related terms.
    """
    dict_general_keyword_corpus = json.load(open(os.path.join(DATA_DIR, "general_keyword_values.json"), "r"))
    dict_cluster_keyword_corpus = json.load(open(os.path.join(DATA_DIR, "cluster_keyword_values.json"), "r"))
    # First, remove all the terms that are below the threshold
    set_raw_general_keywords = set([key for key, value in dict_general_keyword_corpus.items() if value > GENERAL_WEIGHT_THRESHOLD])
    dict_set_raw_cluster_keywords = {}
    for cluster_id, cluster_info in dict_cluster_keyword_corpus.items():
        dict_set_raw_cluster_keywords[cluster_id] = set([key for key, value in cluster_info.items() if value > CLUSTER_WEIGHT_THRESHOLD])
    
    print(f"Raw general keywords: {len(set_raw_general_keywords)}")
    
    
    cluster_info = json.load(open(os.path.join(DATA_DIR, "hybrid_clusters.json"), "r"))
    
    # Second, remove all the geolocation related terms from both general and clustered corpus
    set_general_keywords = set()
    for keyword in set_raw_general_keywords:
        if keyword not in dict_city_by_name and len(keyword) < TERM_LEN_MAX_THRESHOLD:
            set_general_keywords.add(keyword)
            
    dict_set_cluster_keywords = {}
    for cluster_id, cluster_keywords in dict_set_raw_cluster_keywords.items():
        if len(cluster_info[cluster_id]) < CLUSTER_SIZE_THRESHOLD:
            continue
        set_cluster_keywords = set()
        for keyword in cluster_keywords:
            if keyword not in dict_city_by_name and len(keyword) < TERM_LEN_MAX_THRESHOLD:
                set_cluster_keywords.add(keyword)
        dict_set_cluster_keywords[cluster_id] = set_cluster_keywords
    
    print(f"Purified general keywords: {len(set_general_keywords)}")
    
    # Third, remove all the terms appeared in the clustered corpus from the general corpus
    for cluster_id, cluster_keywords in dict_set_cluster_keywords.items():
        set_general_keywords -= cluster_keywords
    
    return set_general_keywords, dict_set_cluster_keywords

def init_browser():
    """
    Initialize Chrome browser in headless mode with necessary options.
    Hide from anti-crawler detection
    """
    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_argument("--headless")
    options.add_argument("--disable-blink-features")
    options.add_argument("--disable-blink-features=AutomationControlled")
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def extract_url_from_bing_search(driver: webdriver.Chrome):
    urls = []
    time.sleep(1)
    js = 'window.scrollTo(0, document.body.scrollHeight);'
    driver.execute_script(js)
    tmp_gap = random.randint(20, 40) / 10
    time.sleep(tmp_gap)
    driver.execute_script(js)
    time.sleep(1)
    source_code = driver.page_source
    
    if('There are no results for' in source_code.replace('\n','')):
        print('No results found')
        
    else:
        soup = bs(source_code, "html.parser")
        # eg: https://learn.microsoft.com › en-us › advertising › guides -> https://learn.microsoft.com/en-us/advertising/guides
        for cite in soup.find_all('cite'):
            raw_text = cite.get_text()
            url = ''
            # Split the text by space, and then join them with '/'
            # If the last character is '…', remove it
            slices = raw_text.split(' ')
            if slices[-1].endswith('…') or slices[-1].endswith('...'):
                slices = slices[:-1]
            for slice in slices:
                if slice == '›':
                    continue
                url += slice + '/'
            if len(url) == 0:
                continue                  
            url = url.rstrip('/')
            # if the url are not start with http, add it
            if not url.startswith('http'):
                url = 'https://' + url
            urls.append(url)
    return urls

def search_for_one_keyword(browser, keyword, is_first=False):
    # Search term: key+looking+glass
    candidate_urls = set()
    url = 'https://cn.bing.com/search?q=' + keyword + '&first=1&FORM=PERE1'
    browser.get(url)
    ## 获取当前页面中的结果的 URL，记录总数，直到满 500 条或者没有更多结果
    tmp_urls = extract_url_from_bing_search(browser)
    
    if is_first:
        gap_time = random.randint(70, 120) / 10    
        time.sleep(gap_time)
    
    time.sleep(1)
    js = 'window.scrollTo(0, document.body.scrollHeight);'
    browser.execute_script(js)
    time.sleep(2)
    collected_count = len(tmp_urls)
    candidate_urls.update(tmp_urls)
    
    while collected_count < 500:
        url = 'https://cn.bing.com/search?q=' + keyword + '&first='+str(collected_count+1)+'&FORM=PERE1'
        try:
            browser.get(url)
        except selenium.common.exceptions.TimeoutException as e:
            print(e)
            continue
        # If reach the end of the search results, stop
        if('There are no results for' in browser.page_source.replace('\n','')):
            break
        tmp_urls = extract_url_from_bing_search(browser)
        candidate_urls.update(tmp_urls)
        collected_count+=len(tmp_urls)
    return candidate_urls

def fetch_one_piece_of_webpages(list_terms, thread_index):
    # Sleep for index * 20 seconds to avoid the anti-crawler detection
    time.sleep(thread_index * 20)
    print('Thread ' + str(thread_index) + ' start')
    
    timer_start = time.time()
    browser = init_browser()
    candidate_urls = set()
    
    # Log the processed terms
    log_term_file = open(os.path.join(LOGS_DIR, 'log_terms_' + str(thread_index) + '.txt'), 'a')
    log_url_file = open(os.path.join(LOGS_DIR, 'log_urls_' + str(thread_index) + '.txt'), 'a')
    
    # Search for the urls
    count = 0
    for terms in list_terms:
        # Search term: key+looking+glass
        key = f"{terms[0]}+{terms[1]}+looking+glass"
        tmp_urls = search_for_one_keyword(browser, key)
        # write the terms to log file
        log_term_file.write(terms[0] + ' ' + terms[1] + '\n')
        # flush the buffer
        log_term_file.flush()
        # write the urls to file
        for url in tmp_urls:
            log_url_file.write(url + '\n')
        # flush the buffer
        log_url_file.flush()
        candidate_urls.update(tmp_urls)
        count += 1
        if count % 10 == 0:
            print('Thread {} processed {} terms, {} left.'.format(thread_index, count, len(list_terms) - count))
 
    # close the log files
    log_term_file.close()
    log_url_file.close()
    browser.quit()
    timer_end = time.time()
    print('Thread {} end, time cost: {}, {} urls are collected'.format(thread_index, timer_end - timer_start, len(candidate_urls)))
    return candidate_urls

if __name__ == "__main__":
    dict_city_by_name = pkl.load(open(os.path.join(DATA_DIR, "dict_city_by_name.bin"), "rb"))
    # dict_asn_by_name = pkl.load(open(os.path.join(DATA_DIR, "dict_asn_by_name.bin"), "rb"))
    set_general_keywords, dict_set_cluster_keywords = purify_the_corpus(dict_city_by_name)
    # Build the search terms for the search engine
    cluster_search_terms = build_cluster_search_terms(dict_set_cluster_keywords)
    print(f"Cluster search terms: {len(cluster_search_terms)}")
    
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    # Split the cluster search terms into pieces
    list_cluster_search_terms = list(cluster_search_terms)
    
    # only care about the first half
    list_cluster_search_terms = list_cluster_search_terms[:len(list_cluster_search_terms)//2]
    
    num_terms = len(list_cluster_search_terms)
    list_term_slices = [list_cluster_search_terms[i*num_terms // NUM_THREADS:(i+1)*num_terms // NUM_THREADS] for i in range(NUM_THREADS)]
    
    # Start searching for the webpages by using the cluster search terms
    # Parallelize the searching process, and use future to capture the results
    futures = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for i in range(NUM_THREADS):
            future = executor.submit(fetch_one_piece_of_webpages, list_term_slices[i], i)
            futures.append(future)
        # Collect the results
        all_urls = set()
        for future in as_completed(futures):
            all_urls.update(future.result())
        # Save the results
        with open(os.path.join(OUTPUT_DIR, "candidate_urls.bin"), "wb") as f:
            pkl.dump(all_urls, f)