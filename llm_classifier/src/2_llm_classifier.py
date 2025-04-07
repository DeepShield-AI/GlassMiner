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

def build_dataset(file_path, label):
    """
    Build the dataset for the LLM classifier.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    dataset = []
    for line in lines:
        text_path = line.strip()
        with open(text_path, "r", encoding="utf-8") as f:
            data = f.read()
        dataset.append((data, label, text_path))
    return dataset

# 有三种网页：1. 与 LG 无关的网页；2. 与 LG有关但是不直接提供 LG 服务的网页；3. 直接提供LG服务的网页。
# 我们构造三种不同的LLM分类器，它们调用同样的模型，但是使用不同的提示。

def direct_multi_classification(data):
    """
    直接要求模型进行多分类
    """
    html_text, label, text_path = data
    new_base_prompt = {
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
    new_base_prompt["messages"].append({
        "content": "Categorize webpage content: 1. Unrelated; 2. Looking Glass-related but do not provide LG service; 3. LG service (ping, traceroute, bgp, etc.) provider. Output 1, 2 or 3 only.",
        "role": "system"
    })
    new_base_prompt["messages"].append({
        "content": html_text,
        "role": "user"
    })
    result = request_llm_and_get_response(new_base_prompt)
    if result is None:
        result = 1
    return result, label, text_path

def direct_binary_classification(data):
    """
    直接要求模型进行两次二分类
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
        "content": "Categorize webpage content: 1. Unrelated; 2. Looking Glass-related (includes links to LG or similar network tools). Output 1 or 2 only.",
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
        "content": "Categorize webpage content: 1. Looking Glass-related but no direct service; 2. LG service (traceroute, ping, bgp, etc.) provider. Output 1 or 2 only.",
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
    return result, label, text_path

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


def test_for_one_method(dataset, method: Callable):
    with ThreadPoolExecutor(max_workers=12) as executor:
        future_list = []
        for data in dataset:
            future = executor.submit(method, data)
            future_list.append(future)
            time.sleep(0.5)
        
        result_log = []
        for future in as_completed(future_list):
            result, label, text_path = future.result()
            result_log.append((result, label, text_path))

    # save the result to a file
    with open(os.path.join(TEST_DIR, "result_{}.txt".format(method.__name__)), "w", encoding="utf-8") as f:
        for result, label, text_path in result_log:
            f.write(f"{result}\t{label}\t{text_path}\n")
            
TEST_DIR = os.path.join(DATA_DIR, "..", "test")
RELATED_FILE = os.path.join(TEST_DIR, "related.txt")
UNRELATED_FILE = os.path.join(TEST_DIR, "unrelated.txt")
SERVICE_FILE = os.path.join(TEST_DIR, "service.txt")
dataset_1 = build_dataset(UNRELATED_FILE, 1)
dataset_2 = build_dataset(RELATED_FILE, 2)
dataset_3 = build_dataset(SERVICE_FILE, 3)
dataset = dataset_1 + dataset_2 + dataset_3
# dataset = dataset_2 + dataset_3
print("Total dataset: ", len(dataset))
# shuffle the dataset
random.shuffle(dataset)

print("Start testing...")
# Test the three classification methods parallelly, max QPS = 100
test_for_one_method(dataset, direct_multi_classification)
print("Direct multi classification finished.")
test_for_one_method(dataset, direct_binary_classification)
print("Direct binary classification finished.")
test_for_one_method(dataset, prompted_binary_classification)
print("Prompted binary classification finished.")
