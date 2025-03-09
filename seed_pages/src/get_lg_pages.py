# Parse or crawl Looking Glass webpages from all the sources.
# Different sources have different formats, so we need to write different parsers for each source.
# Here include the parsers for the following sources:
# - PeeringDB
# - BGP4.as
# - bgplookingglass
# - traceroute.org
# - whois.ipinsight.io
# - looking.house

# Note: Every LG page info entry includes the following fields:
# - name: The name of the network or organization
# - url: Looking Glass URL
# - TODO: Add more fields

# Import necessary libraries
import random
import time
import ssl
import requests
import json
import bs4
import os
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import partial

# Import the customized content
from configs import *

requests.packages.urllib3.disable_warnings()
context = ssl.create_default_context()
context.set_ciphers('HIGH:!DH:!aNULL')

def request_with_random_header(url: str) -> bs4.BeautifulSoup:
    """
    Send a request to the target URL with a random User-Agent
    """
    header = BASE_HEADER
    header["User-Agent"] = random.choice(USER_AGENT_LIST)
    response = requests.get(url, headers=header)
    soup = bs4.BeautifulSoup(response.text, "html.parser")
    return soup

# ================== Parsers for different sources ================== #

def get_from_peeringdb() -> list:
    """s
    Get Looking Glass URLs from PeeringDB.
    """
    src_file = os.path.join(DATA_DIR, "peeringdb_net.json")
    lg_page_info = []
    with open(src_file, "r") as f:
        data = json.load(f)["data"]
        for entry in data:
            if "looking_glass" in entry.keys() and entry["looking_glass"]:
                lg_page_info.append({
                    "name": entry["name"].strip(),
                    "url": entry["looking_glass"].strip()
                })
    return lg_page_info

def get_from_bgp4_as() -> list:
    """
    Get Looking Glass URLs from BGP4.as.
    """
    src_url = "https://www.bgp4.as/looking-glasses/"
    lg_page_info = []
    soup = request_with_random_header(src_url)
    # Find the table with "BGP Looking Glass website" in the first row
    tables = soup.find_all("table", recursive=True)
    is_found = False
    # check which table contains a <td> with substring "BGP Looking Glass website"
    for table in tables:
        # iterativly check each row in the table, if one td contains substring "BGP Looking Glass website", then parse the table
        for row in table.find_all("tr", recursive=False):
            if "BGP Looking Glass website" in row.text and len(row.find_all("td", recursive=False)) == 7:
                is_found = True
                break
        if is_found:
            # check each row and parse the table
            for row in table.find_all("tr", recursive=False):
                # if the row include more than 3 <td>, and include herf attribute in 4th <td> tag, then parse the row
                if len(row.find_all("td", recursive=False)) > 3 and row.find_all("td", recursive=False)[3].find("a"):
                    name = row.find_all("td")[2].find("a").text
                    url = row.find_all("td")[3].find("a")["href"]
                    lg_page_info.append({
                        "name": name.strip(),
                        "url": url.strip()
                    })
            break
    return lg_page_info

def get_from_bgplookingglass() -> list:
    """
    Get Looking Glass URLs from bgplookingglass.
    """
    src_url = "https://www.bgplookingglass.com/"
    lg_page_info = []
    soup = request_with_random_header(src_url)
    # Find the table with "Looking Glass Database" in the first row
    table = soup.find("table", recursive=True)
    for row in table.find_all("tr"):
        # if the row include more than 1 <td>, and include herf attribute in 2nd <td> tag, then parse the row
        if len(row.find_all("td", recursive=False)) == 3 and row.find_all("td", recursive=False)[2].find("a"):
            name = row.find_all("td")[0].text
            # if href exists, using the href, otherwise using the text
            url_cell = row.find_all("td")[2].find("a")
            if "href" in url_cell.attrs:
                url = url_cell["href"]
            else:
                url = url_cell.text
            lg_page_info.append({
                "name": name.strip(),
                "url": url.strip()
            })
    return lg_page_info

def get_from_traceroute_org() -> list:
    """
    Get Looking Glass URLs from traceroute.org.
    """
    src_url = "http://www.traceroute.org/"
    lg_page_info = []
    soup = request_with_random_header(src_url)
    # Find the header with text "Looking Glass", then find the next element which is a <ul>
    header = soup.find("a", attrs={"name": "Looking Glass"})
    ul = header.find_next("ul")
    for li in ul.find_all("li"):
        name = li.text
        url = li.find("a")["href"]
        lg_page_info.append({
            "name": name.strip(),
            "url": url.strip()
        })
    return lg_page_info

def get_from_whois_ipinsight_io() -> list:
    """
    Get Looking Glass URLs from whois.ipinsight.io.
    """
    src_url = "https://whois.ipinsight.io/looking-glass/"
    lg_page_info = []
    soup = request_with_random_header(src_url)
    # Find the table with "Looking Glass" in the first row
    table = soup.find("table", recursive=True)
    for row in table.find_all("tr"):
        # if the row include more than 1 <td>, and include herf attribute in 2nd <td> tag, then parse the row
        if len(row.find_all("td", recursive=False)) == 4 and row.find_all("td", recursive=False)[3].find("a"):
            name = row.find_all("td")[2].text
            url = row.find_all("td")[3].find("a")["href"]
            lg_page_info.append({
                "name": name.strip(),
                "url": url.strip()
            })
    return lg_page_info

def get_from_looking_house() -> list:
    """
    Get Looking Glass URLs from looking.house.
    This is more complex because we need to manually concat the links
    """
    src_url = "https://looking.house/companies"
    base_url = "https://looking.house"
    lg_page_info = []
    home_soup = request_with_random_header(src_url)
    # Find the table with "Looking Glass" in the first row
    cards = home_soup.find_all("a", attrs={"class": "link py-3 text-center border-bottom"})
    for card in cards:
        suffix = card["href"]
        company_name = card.find_next("div").text
        lg_list_page_url = base_url + suffix + "/looking-glass"
        lg_list_soup = request_with_random_header(lg_list_page_url)
        lg_list = lg_list_soup.find_all("a", attrs={"class": "link fs-5 d-flex justify-content-start align-items-center me-1"})
        for lg in lg_list:
            pos_strs = [pos.contents[0].strip() for pos in lg.find_all("span")[1:]]
            # concate the text in the span tags
            name = " ".join([company_name] + pos_strs)
            url = base_url + lg["href"]
            lg_page_info.append({
                "name": name.strip(),
                "url": url.strip()
            })
        print(f"Get {len(lg_list)} LG pages from {company_name}")
        # random sleep 0.5-2 seconds to avoid being blocked
        time.sleep(0.1 * random.randint(5, 20))
    return lg_page_info

def get_from_asset_engine() -> list:
    """
    Get Looking Glass URLs from the csv file dump from asset engines.
    """
    src_file = os.path.join(DATA_DIR, "asset_engine.csv")
    lg_page_info = []
    # parse the csv and get the pages
    asset_info = pd.read_csv(src_file)
    for row in asset_info.itertuples(index=False):
        host = row[0]
        proto = row[3]
        # Using IP for the name
        name = row[1]
        # if the host is empty, then skip
        if host == "":
            continue
        if host.startswith("http"):
            url = host
        else:
            url = proto + "://" + host
        lg_page_info.append({
            "name": name.strip(),
            "url": url.strip()
        })
    return lg_page_info

lg_collection_funcs = [
    get_from_peeringdb,
    get_from_bgp4_as,
    get_from_bgplookingglass,
    get_from_traceroute_org,
    get_from_whois_ipinsight_io,
    get_from_looking_house,
    get_from_asset_engine
]

# ================== Other utils functions ================== #

def deduplicate_lg_page_by_url(raw_lg_page_list: list) -> list:
    """
    Deduplicate the LG page list by URL. We treat below URLs as the same:
    1. Two urls with only tailing slash difference: http://example.com/ and http://example.com
    2. Two urls with only different protocol: http://example.com and https://example.com
    3. TODO. more specific deduplication rules, but not necessary now.
    """
    unsupported_cnt = 0
    preprocessed_lg_page_dict = {}
    # remove all the tailing slash, split the urls by protocol and domain
    for lg_page in raw_lg_page_list:
        url = lg_page["url"]
        # other protocol, such as telnet, ssh, etc.
        if not url.startswith("http"):
            unsupported_cnt += 1
            continue
        proto, domain = url.split("://")
        domain = domain.rstrip("/")
        if domain not in preprocessed_lg_page_dict:
            preprocessed_lg_page_dict[domain] = {
                "name": lg_page["name"],
                "proto": proto
            }
        elif proto == "http":
            preprocessed_lg_page_dict[domain]["proto"] = proto
    deduplicated_lg_page_list = []
    for domain, info in preprocessed_lg_page_dict.items():
        deduplicated_lg_page_list.append({
            "name": info["name"],
            "url": info["proto"] + "://" + domain
        })
    print(f"Unsupported urls: {unsupported_cnt}")
    return deduplicated_lg_page_list

def remove_scripts(html):
    """使用BeautifulSoup移除所有script标签"""
    soup = bs4.BeautifulSoup(html, 'html.parser')
    for script in soup.find_all('script'):
        script.decompose()
    return str(soup)

def fetch_one_lg_page(url, session: requests.Session, retry_count=0) -> dict:
    try:
        header = BASE_HEADER
        header["User-Agent"] = random.choice(USER_AGENT_LIST)
        # ignore the https insecure warning, and allow the redirect
        response = session.get(url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True)
    except Exception as e:
        if retry_count < MAX_RETRY:
            if url.startswith("http:"):
                url = "https" + url[4:]
            else:
                url = "http" + url[5:]
            time.sleep(1 * retry_count)
            return fetch_one_lg_page(url, session, retry_count + 1)
        return {
            "original_url": url,
            "error": str(e),
            "retries": retry_count,
            "success": False
        }
    final_url = response.url
    return {
        "original_url": url,
        "final_url": final_url,
        "content": response.text,
        "success": True
    }

def check_availabilty_and_download(dedup_lg_page_list: list) -> list:
    """
    Concurrently check the availability of LG pages.
    If the target couldn't response, return False.
    If the target can normally response, download the webpage and return True.
    Schedule the download task to avoid being blocked, and give one task at most 3 times.
    """
    succ_cnt = 0
    failed_cnt = 0
    processed_cnt = 0
    available_lg_page_list = []
    failed_lg_page_list = []
    redirected_lg_page_list = {}
    # random shuffle the list to avoid being blocked
    random.shuffle(dedup_lg_page_list)
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        with requests.Session() as session:
            partial_crawl = partial(fetch_one_lg_page, session=session)
            futures = {executor.submit(partial_crawl, lg["url"]): lg for lg in dedup_lg_page_list}
            
            for future in as_completed(futures):
                result = future.result()
                # update the success and failed count
                processed_cnt += 1
                if result['success']:
                    cleaned_html = remove_scripts(result['content'])
                    filename = result['final_url'].split('://')[1]
                    # remove the tailing slash, and only keep the first 40 characters
                    if filename.endswith('/'):
                        filename = filename[:-1]
                    filename = filename.replace('/', '_')
                    if len(filename) > FILE_NAME_MAX_LENGTH:
                        filename = filename[:FILE_NAME_MAX_LENGTH]
                    filepath = os.path.join(SAVE_DIR, filename)
                    redirected_lg_page_list[result["original_url"]] = result["final_url"]
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(cleaned_html)
                    succ_cnt += 1
                    available_lg_page_list.append({
                        "url": result['final_url'],
                        "filename": filename,
                    })
                else:
                    failed_cnt += 1
                    failed_lg_page_list.append({
                        "url": result["original_url"], 
                        "err": str(result["error"]),
                    })            
                if processed_cnt % 50 == 0:
                    print("{} processed, {} success, {} failed".format(processed_cnt, succ_cnt, failed_cnt))
    return available_lg_page_list, failed_lg_page_list

if __name__ == "__main__":
    raw_lg_page_list = []
    for func in lg_collection_funcs:
        tmp_lg_list = func()
        raw_lg_page_list += tmp_lg_list
        print(f"Get {len(tmp_lg_list)} LG pages from {func.__name__}, {len(raw_lg_page_list)} LG pages are collected in total.")    
    print("Now Start deduplication...")
    dedup_lg_page_list = deduplicate_lg_page_by_url(raw_lg_page_list)    
    print(f"Get {len(dedup_lg_page_list)} LG pages after deduplication.")
    
    print("Now Start checking the availability of LG pages...")
    available_lg_page_list, failed_lg_page_list = check_availabilty_and_download(dedup_lg_page_list)
    with open(os.path.join(OUTPUT_DIR, AVAI_FILE), "w") as f:
        json.dump(available_lg_page_list, f, indent=4)
    with open(os.path.join(OUTPUT_DIR, FAIL_FILE), "w") as f:
        json.dump(failed_lg_page_list, f, indent=4)
    print(f"Get {len(available_lg_page_list)} available LG pages.")