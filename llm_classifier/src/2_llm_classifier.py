import json
import time
import requests
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from configs import *

url = "https://api.siliconflow.cn/v1/chat/completions"

headers = {
    "Authorization": "Bearer sk-jdranwtijmbzifcthjiueaghrxgvsunnqwmiksixareqsvnz",
    "Content-Type": "application/json"
}

base_prompt = {
    "model": "Pro/deepseek-ai/DeepSeek-V3",
    "stream": False,
    "max_tokens": 256,
    "temperature": 0.5,
    "top_p": 0.7,
    "top_k": 50,
    "frequency_penalty": 0.5,
    "n": 1,
    "messages": []
}

def request_llm_and_get_response(payload):
    """
    Request the LLM and get the response.
    """
    response = requests.request("POST", url, json=payload, headers=headers)
    response_dict = response.json()
    print("Response: ", response_dict)
    result = response_dict["choices"][0]["message"]["content"]
    # find the first number in the result
    res = re.search(r"\d+", result)
    if res:
        result = int(res.group())
    else:
        print("No number found in the result: ", result)
        result = None
    return result

def build_dataset(label=None):
    """
    Build the dataset for the LLM classifier.
    """
    with open(os.path.join(OUTPUT_DIR, "filtered_page_list.json"), "r") as f:
        filtered_page_list = json.load(f)
        
    dataset = []
    for page_info in filtered_page_list:
        text_path = os.path.join(PROCS_DIR, page_info["filename"])
        with open(text_path, "r", encoding="utf-8") as f:
            data = f.read()
        dataset.append((data, label, text_path))
    return dataset

def prompted_binary_classification(data):
    """
    通过提示模型进行两次二分类
    """
    html_text, label, text_path = data
    new_base_prompt_1 = {
        "model": "Pro/deepseek-ai/DeepSeek-V3",
        "stream": False,
        "max_tokens": 256,
        "temperature": 0.5,
        "top_p": 0.7,
        "top_k": 50,
        "frequency_penalty": 0.5,
        "n": 1,
        "messages": []
    }
    new_base_prompt_1["messages"].append({
        "content": "Categorize webpage content: 1. Unrelated; 2. Looking Glass-related (links to LG or similar network tools). Example A: ```Innovative Technological Solutions ### Network Tools * Network Status * DNS Propagator * Looking Glass * DNS Lookup * IP Lookup * WhoIs``` contains word Looking Glass, but no related links -> classify as 1. Example B: ```Welcome to the webserver of RLP-NET. The only public service offered so far on this server is a [traceroute](/cgi-bin/tracer.cgi) server.``` contains link to traceroute server -> classify as 2. Output 1 or 2 only.",
        "role": "system"
    })
    
    new_base_prompt_2 = {
        "model": "Pro/deepseek-ai/DeepSeek-V3",
        "stream": False,
        "max_tokens": 256,
        "temperature": 0.5,
        "top_p": 0.7,
        "top_k": 50,
        "frequency_penalty": 0.5,
        "n": 1,
        "messages": []
    }
    
    new_base_prompt_2["messages"].append({
        "content": "Categorize webpage content: 1. Looking Glass-related (link to LG or similar tools) but no direct service; 2. LG service. If it contains network terms, commands (traceroute, ping, bgp, etc.), selection of parameters (commands, locations, addresses, etc.), it should be class 2. Example A: ```[ Ping Testi ](https://atlantisnet.com.tr/internet-ping-testi/) *  İnternet Başvurusu  *  Gizlilik ve Güvenlik  ##### Yardım * [ Atlantis Looking Glass ](https://lg.atlantisnet.com.tr/)``` contains links but no direct service -> class 1; Example B: ```Members should contact their local network administrators. The only public service offered so far on this server is a [traceroute](/cgi-bin/tracer.cgi) server.``` contains links but no direct service -> class 1; Example C: ```Web Browser User Agents * Web Technologies Cheat Sheets ## Online Traceroute Your IP address is 107.172.231.79 IP to traceroute to : [Input]: TYPE: [Input]:ICMP [Input]:TCP``` provide traceroute service -> class 2; Example D: ```[Meta]:og:title:INS BGP looking glass [Meta]:description:International Network Services Network Looking Glass [Meta]:hyperglass-version:2.0.4 * ## FRA Marseille, MRS1 FM * ## ZAF Durban, DMO ZD * ## ZAF Midrand, MTB ZM Help Terms ZANOG``` contains `hyperglass` from template LG webpage. -> class 2. Output 1 or 2 only.",
        "role": "system"
    })
    
    new_base_prompt_1["messages"].append({
        "content": html_text,
        "role": "user"
    })
    result = request_llm_and_get_response(new_base_prompt_1)
    if result == 2:
        new_base_prompt_2["messages"].append({
            "content": html_text,
            "role": "user"
        })
        result = request_llm_and_get_response(new_base_prompt_2)
        if result is None:
            result = 1
        else:
            result +=1
    if result is None:
        result = 1
    return result, label, text_path

def non_batched_classification(dataset, method: Callable):
    with ThreadPoolExecutor(max_workers=18) as executor:
        future_list = []
        for data in dataset:
            future = executor.submit(method, data)
            future_list.append(future)
            time.sleep(0.5)
        
        result_log = []
        for future in as_completed(future_list):
            result, label, text_path = future.result()
            result_log.append((result, label, text_path))
    return result_log
            
dataset = build_dataset()
print("Total dataset: ", len(dataset))
random.shuffle(dataset)

print("Start testing...")
res_log = non_batched_classification(dataset, prompted_binary_classification)
print("Prompted binary classification finished.")

# save the result to file
with open(os.path.join(OUTPUT_DIR, "classification_result.json"), "w") as f:
    json.dump(res_log, f, indent=4)