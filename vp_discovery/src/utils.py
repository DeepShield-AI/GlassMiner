from bs4 import BeautifulSoup
import warnings
import random
import requests
import ssl
import regex as re
from math import log2
import html2text
from difflib import SequenceMatcher
import zstandard as zstd
import io
import pickle as pkl
import geoip2.database
from string import digits
import reverse_geocoder
import pytricia

from configs import *

requests.packages.urllib3.disable_warnings()
context = ssl.create_default_context()
context.set_ciphers('HIGH:!DH:!aNULL')

class CustomHTMLParser(html2text.HTML2Text):
    """
    Custom HTML parser to handle specific cases.
    """
    def __init__(self):
        super().__init__()

        self.ignore_emphasis = True
        self.ignore_links = True
        self.single_line_break = True
        self.body_width = 0

# For structure similarity computation.
class StructuralComparator(SequenceMatcher):
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            super().__init__()
            self._initialized = True
    
    def ratio(self) -> float:
        matches = sum(triple[-1] for triple in self.get_matching_blocks())
        modified_len = min(len(self.a), len(self.b)) + log2(max(len(self.a), len(self.b)))
        if modified_len == 0:
            return 0
        return 1.0 * matches / modified_len

def fetch_one_page(url, session: requests.Session, retry_count=0) -> dict:
    header = BASE_HEADER
    header["User-Agent"] = random.choice(USER_AGENT_LIST)
    try:
        # First send a HEAD request to check content size, discard if > 10 MB
        head_response = session.head(url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True)
        content_size = head_response.headers.get('Content-Length', 0)
        if content_size and int(content_size) > 10 * 1024 * 1024:
            return {
                "original_url": url,
                "error": "Content size too large",
                "success": False
            }
        else:
            response = session.get(url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True, stream=True)
            # check if the content encoding is zstandard
            if response.headers.get('Content-Encoding') == 'zstd':
                # decompress the content
                dctx = zstd.ZstdDecompressor()
                with dctx.stream_reader(io.BytesIO(response.raw.read())) as reader:
                    decompressed = reader.read()
                    response_text = decompressed.decode("utf-8")
            else:
                response_text = response.text
            final_url = response.url.rstrip('/')
    except Exception as e:
        if retry_count < MAX_RETRY:
            return fetch_one_page(url, session, retry_count + 1)
        return {
            "original_url": url,
            "error": str(e),
            "success": False
        }
    soup = parse_webpages(response_text)
    filename = url_to_filename(final_url)
    filepath = os.path.join(SAVE_DIR, filename)
    with open(filepath, 'w', encoding='utf-8', errors='ignore') as f:
        f.write(str(soup))
    return {
        "original_url": url,
        "final_url": final_url,
        "success": True
    }

def url_to_filename(url: str) -> str:
    """
    Convert the URL to a filename by replacing the special characters.
    """
    filename = url.split('://')[1]    
    # remove the tailing slash, and only keep the first 40 characters
    if filename.endswith('/'):
        filename = filename[:-1]
    filename = filename.replace('/', '_')
    if len(filename) > FILE_NAME_MAX_LENGTH:
        filename = filename[:FILE_NAME_MAX_LENGTH]
    return filename

def contain_filter_words(contents: str) -> bool:
    """
    Check if the webpage contains any filter words.
    """
    text_lower = contents.lower()
    for word in SIMPLE_FILETER_WORDS:
        if word.lower() in text_lower:
            return True
    return False

def parse_webpages(webpage) -> BeautifulSoup:
    """
    Adaptive parsing of the webpage content by html parser or lxml parser.
    """
    try:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            soup = BeautifulSoup(webpage, "html.parser")
            # Check for XML parsed as HTML warnings
            if any("XMLParsedAsHTMLWarning" in str(warning.message) for warning in w):
                soup = BeautifulSoup(webpage, "xml")
    except Exception as e:
        print(f"Error parsing webpage: {e}")
        return None
    return soup
    
def is_symbols(token):
    if re.match(PTN_CHAR, token):
        return True
    return False

def collect_text_in_order(html_str):
    if len(html_str) > 500000:
        return None
    # Part one: Extract text in input / meta, change them into direct text
    soup = parse_webpages(html_str)
    if soup is None:
        return None
    # Find all input with "placeholder" or "value" attributes
    input_tags = soup.find_all("input")
    for input_tag in input_tags:
        text = ""
        # Check if the input tag has a placeholder or value attribute
        if "placeholder" in input_tag.attrs:
            text = input_tag["placeholder"]    
        elif "value" in input_tag.attrs:
            text = input_tag["value"]
        # replace input tags by [Input]:{text}
        if text:
            input_tag.replace_with(f"[Input]:{text}")
    # fing the meta tags with "content" and "name" attributes
    meta_tags = soup.find_all("meta", attrs={"name": True, "content": True})
    # repalce meta tags with [Meta]{name}:{content}
    meta_text = []
    for meta_tag in meta_tags:
        # Check if the meta tag has a name attribute
        name = meta_tag["name"]
        if "hyperglass" in name or "title" in name or "description" in name:            
            content = meta_tag["content"]
            meta_text.append(f"[Meta]:{name}:{content}")
    meta_text = " ".join(meta_text)
    # Part two: Extract text in the body
    html_str = str(soup)
    handler = CustomHTMLParser()
    text = handler.handle(html_str)
    # Split the text by \n
    lines = text.split("\n")
    # Remove empty lines and lines with too long words
    filtered_lines = []
    for line in lines:
        # Remove leading and trailing spaces
        line = line.strip()
        # Check if the line is empty or contains too long words
        if len(line) > 0 and len(line) < TEXT_LEN_MAX_THRESHOLD:
            filtered_lines.append(line)
    # Join the filtered lines into a single string
    text = " ".join(filtered_lines)
    text = meta_text + " " + text
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def sequence_similarity(html_1: str, html_2: str):
    comparator = StructuralComparator()
    comparator.set_seq1(html_1.tags)
    comparator.set_seq2(html_2.tags)
    return comparator.ratio()


# =================== Geolocation Utility =================== #
GEOLITE_READER = geoip2.database.Reader(os.path.join(DATA_DIR, "GeoLite.mmdb"))                      

def split_word(name: str):
    name_split = set()
    # remove digits
    table = str.maketrans('', '', digits)
    name = name.translate(table).lower()

    if name.count(',') > 0 and '(' not in name:
        # For '-', there are two choices, one is to remove it, the other is to replace it with ','
        new_name = name.replace('-', '')
        name_split.update([x.replace(' ', '') for x in new_name.split(',')])
        new_name = name.replace('-', ',')
        name_split.update([x.replace(' ', '') for x in new_name.split(',')])
    # check format 'xx (AS number)'
    elif '(as' in name:
        pass
    else:
        name = name.replace('(', ' ')
        name = name.replace(')', ' ')
        name = name.replace(',', ' ')
        name = name.replace('，', ' ')
        name = name.replace('/', ' ')
        name_split.update(name.replace('-',' ').split())
    return name_split

def check_raw_word(raw_word):
    raw_word = raw_word.lower()

    # check if the word is a city name with space
    for name in dict_hasspace_city:
        if name in raw_word:
            return dict_hasspace_city[name]

    set_oneword = split_word(raw_word)
    candidates = list()
    for word in set_oneword:
        # check if the word is a city name
        if word in dict_iata_code:
            if dict_iata_code[word][1] in set_oneword:
                candidates.append(dict_iata_code[word])
            if 'ixp' in set_oneword:
                candidates.append(dict_iata_code[word])

        # check if the word is a city name
        if word in dict_city_by_name:
            candidates.append(dict_city_by_name[word])
   
    # If there are two candidates, check if they are the same city
    if len(candidates) == 2:
        _, _, admin_0, city_0, _  = candidates[0]
        _, _, admin_1, city_1, _  = candidates[1]
        if city_0 == admin_1:
            return candidates[1]
        if city_1 == admin_0:
            return candidates[0]    
    # if there are more than two candidates, check if they are the same city
    if len(candidates) > 0:
        coor_candidates = [x[0] for x in candidates]
        for cdx_1 in range(0, len(coor_candidates)):
            for cdx_2 in range(cdx_1 + 1, len(coor_candidates)):
                if abs(coor_candidates[cdx_1][0] - coor_candidates[cdx_2][0]) > 0.5 or \
                    abs(coor_candidates[cdx_1][1] - coor_candidates[cdx_2][1]) > 0.5:
                    return None
        return candidates[0]
    elif len(candidates) == 0:
        return None

def normalize_geolocation(coord):
    """
    Using reverse_geocoder to normalize the geolocation.
    """
    try:
        result = reverse_geocoder.search(coord, mode=1)
    except Exception as e:
        print(f"Error normalizing geolocation {coord}: {e}")
        return None
    if result:
        # get the country code and city
        country_code = result[0]['cc']
        city = result[0]['name']
        latitude = result[0]['lat']
        longitude = result[0]['lon']
        return {
            "country_code": country_code,
            "city": city,
            "latitude": latitude,
            "longitude": longitude
        }
    

def geolocate_ip(ip_addr):
    """
    Geolocate the IP address using an external API.
    Need country code, city only, 
    """
    try:
        response = GEOLITE_READER.city(ip_addr)
    except:
        return None
    raw_lat = response.location.latitude
    raw_lon = response.location.longitude
    raw_coord = (raw_lat, raw_lon)
    location = None
    if raw_coord:
        location = normalize_geolocation(raw_coord)
    return location

dict_city_by_name = pkl.load(open(os.path.join(DATA_DIR, "dict_city_by_name.bin"), "rb"))
dict_hasspace_city = pkl.load(open(os.path.join(DATA_DIR, "dict_hasspace_city.bin"), "rb"))
dict_iata_code = pkl.load(open(os.path.join(DATA_DIR, "dict_iata_code.bin"), "rb"))
dict_city_alter_name = pkl.load(open(os.path.join(DATA_DIR, "dict_city_alter_name.bin"), "rb"))
def geolocate_hint(hint):
    """
    Geolocate the hint using an external API.
    """
    geo_info = check_raw_word(hint)
    location = None
    if geo_info:
        coord = geo_info[0]
        location = normalize_geolocation(coord)
    return location

def geolocate_one_vp(vp_info):
    """
    Geolocate one VP by IP or Geo-Hint.
    """
    location = {}
    ip_addr = vp_info["ip_addr"]
    is_hint = False
    if ip_addr:
        # Geolocate by IP
        location = geolocate_ip(ip_addr)
    else:
        # Geolocate by Geo-Hint
        hint = vp_info["hint"]
        if hint:
            location = geolocate_hint(hint)
            if location:
                is_hint = True
    return location, is_hint

BOGON_NETWORKS = [
    "0.0.0.0/8",
    "10.0.0.0/8",
    "100.64.0.0/10",
    "127.0.0.0/8",
    "169.254.0.0/16",
    "172.16.0.0/12",
    "192.0.0.0/24",
    "192.0.2.0/24",
    "192.168.0.0/16",
    "198.18.0.0/15",
    "198.51.100.0/24",
    "203.0.113.0/24",
    "224.0.0.0/4",
    "240.0.0.0/4",
    "255.255.255.255/32",
]
PT = None
def is_bogon(ip_str):
    global PT
    if PT is None:
        PT = pytricia.PyTricia()
        for net in BOGON_NETWORKS:
            PT.insert(net, True)
    try:
        return PT.has_key(ip_str)
    except ValueError:
        return False