from concurrent.futures import ThreadPoolExecutor, as_completed, wait, FIRST_COMPLETED
import pickle as pkl
import json
from urllib.parse import quote_plus
from collections import deque

from configs import *
from utils import *

QUEUE_LOCK = threading.Lock()

def get_general_asn_info():
    with open(os.path.join(OUTPUT_DIR, "candidate_urls_old.bin"), "rb") as f:
        candidate_urls = pkl.load(f)

    set_asn_logs = set()
    count = 0
    # Parallelize the process of getting ASN info
    with ThreadPoolExecutor(max_workers=NUM_THREADS) as executor:
        future_to_url = {executor.submit(get_asn_from_url, url): url for url in candidate_urls}
        count = 0
        
        for future in as_completed(future_to_url):
            asn_set = future.result()
            set_asn_logs.update(asn_set)
            count += 1
            if count % 3000 == 0:
                print(f"{count} URLs have been processed.")

    return set_asn_logs

def search_for_one_asn(dict_as_info_slice, index=1):
    """
    Search for one small slice of ASNs
    """    
    browser = init_browser()    
    time.sleep(5 * (index % 10))
    candidate_urls = set()
    for asn, info in dict_as_info_slice.items():
        orgname = info["organization"]["orgName"]
        if len(orgname) == 0:
            keyword = quote_plus(f'AS{asn} looking glass')
        else:
            keyword = quote_plus(f'AS{asn} {orgname} looking glass')
        tmp_urls = search_for_one_keyword(browser, keyword, num=5)[:5]
        if len(tmp_urls) == 0:
            print(f"Cannot find any urls for AS{asn}")
            continue
        else:
            candidate_urls.update(tmp_urls)
    return candidate_urls

def generate_one_asn_slice(dict_queue_asn_rank: deque, slice_size=20):
    """
    Generate the task for one slice of ASNs.
    Remove the selected ASNs from the dict_asn_rank.
    """
    # Split the dict_asn_rank into slices
    dict_as_slice = {}
    for asn, info in dict_queue_asn_rank.items():
        if len(dict_as_slice) >= slice_size:
            break
        dict_as_slice[asn] = info
    QUEUE_LOCK.acquire()
    for asn in dict_as_slice.keys():
        if asn in dict_queue_asn_rank:
            del dict_queue_asn_rank[asn]
    QUEUE_LOCK.release()
    return dict_as_slice

if __name__ == "__main__":
    # Get the ASN information from the crawled URLs
    # set_asn_logs = get_general_asn_info()
    with open(os.path.join(OUTPUT_DIR, "asn_info.bin"), "rb") as f:
        set_asn_logs = pkl.load(f)
    # build the priority list
    dict_as_info = {}
    with open(os.path.join(DATA_DIR, "as_info.json"), "r") as f:
        dict_as_info = json.load(f)
    # build deque of ASN by rank
    # sort the dict_asn_rank by rank
    dict_as_info = {k: v for k, v in sorted(dict_as_info.items(), key=lambda item: item[1]['rank'], reverse=True)}
    dict_queue_asn_rank = {}
    for asn, info in dict_as_info.items():
        if asn not in set_asn_logs:
            dict_queue_asn_rank[asn] = dict_as_info[asn]

    # Split the results into pieces, with each piece containing 20 ASNs
    # Parallelize the process of getting results, allowing no more than NUM_THREADS threads running at the same time
    new_candidate_urls = set()
    with ThreadPoolExecutor(NUM_THREADS) as executor:
        index = 0
        futures = set()
        initial_slices = []
        
        for i in range(NUM_THREADS):
            # Generate the task for one slice of ASNs
            as_info_slice = generate_one_asn_slice(dict_queue_asn_rank, slice_size=20)
            if len(as_info_slice) == 0:
                break
            # Submit the task to the executor
            futures.add(executor.submit(search_for_one_asn, as_info_slice, index))
            index += 1
        
        while futures:
            # 等待任意一个任务完成
            done, futures = wait(futures, return_when=FIRST_COMPLETED)
            
            # 处理已完成任务
            for future in done:
                candidate_url = future.result()
                new_candidate_urls.update(candidate_url)
                # 解析URL所在的ASN，更新dict_asn_rank
                candidate_asn = set()
                for url in candidate_url:
                    asn = get_asn_from_url(url)
                    if len(asn) == 0:
                        continue
                    candidate_asn.update(asn)
                
                QUEUE_LOCK.acquire()
                for asn in candidate_asn:
                    if asn in dict_queue_asn_rank:
                        del dict_queue_asn_rank[asn]
                QUEUE_LOCK.release()
                
                # 动态补充新任务
                while len(futures) < NUM_THREADS:
                    as_info_slice = generate_one_asn_slice(dict_queue_asn_rank, slice_size=20)
                    if len(as_info_slice) != 0:
                        futures.add(executor.submit(search_for_one_asn, as_info_slice, index))
                        index += 1
    
    # Save the results
    with open(os.path.join(OUTPUT_DIR, "new_candidate_urls.bin"), "wb") as f:
        pkl.dump(new_candidate_urls, f)