# For those VPs without unknown IP, we can use the Geo-Hint to find their location
# Schedule the unknown VPS to be geolocated, make them ping to hosted machine
import os
import random
import time
import pickle
import json
from typing import Tuple
from urllib.parse import urlencode, urljoin
import requests
from functools import partial
import concurrent.futures

from templates import *
from configs import *
from utils import *

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
requests_get = partial(requests.get, timeout=10, verify=False)
requests_post = partial(requests.post, timeout=10, verify=False)

def make_ping_str(vp_info, target_ip='8.8.8.8'):
    url = vp_info["url"]
    action = vp_info["action"]
    base_url = urljoin(url, action)
    dict_params = {}
    params = dict(vp_info["params"])

    for name, value in params.items():
        dict_params[name] = value
    dict_params[vp_info["command"]['name']] = 'ping'
    dict_params[vp_info["input"]['name']] = target_ip
    query = urlencode(dict_params)
    final_url = f"{base_url}?{query}"
    return final_url

# a function to ping to one lg
def ping_to_one_lg(m_idx, lg_idx, vp_info):
    """
    According to the machine index and lg index, ping to the lg and get the result.
    """
    ping_url = make_ping_str(vp_info, HOSTS[m_idx]['public_ip'])
    header = BASE_HEADER
    header["User-Agent"] = random.choice(USER_AGENT_LIST)
    start_time = time.time()
    try:
        session = requests.Session()
        method = vp_info["method"]
        if method == "get":
            response = session.get(ping_url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True, stream=True)
        elif method == "post":
            response = session.post(ping_url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True, stream=True)
        # check if the content encoding is zstandard
        if response.headers.get('Content-Encoding') == 'zstd':
            # decompress the content
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(io.BytesIO(response.raw.read())) as reader:
                decompressed = reader.read()
                response_text = decompressed.decode("utf-8")
        else:
            response_text = response.text
        # check the status code
    except Exception as e:
        pass
    finally:
        return m_idx, lg_idx, start_time

# ============================================= #
import paramiko
import time
from scp import SCPClient

def create_ssh_client(hostname: str, username: str) -> paramiko.SSHClient:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, username=username)
    return client

def start_tcpdump(client: paramiko.SSHClient, pcap_path: str) -> str:
    cmd = f"sudo tcpdump icmp -i eth0 -w {pcap_path} > /dev/null 2>&1 & echo $!"
    stdin, stdout, _ = client.exec_command(cmd)
    return stdout.read().decode().strip()

def stop_tcpdump(client: paramiko.SSHClient, pid: str):
    client.exec_command(f"sudo kill {pid}")

def download_pcap(client: paramiko.SSHClient, remote_path: str, local_path: str):
    with SCPClient(client.get_transport()) as scp:
        scp.get(remote_path, local_path)

if __name__ == "__main__":
    unknown_vp_list = json.load(open(os.path.join(OUTPUT_DIR, "unknown_vp_list.json"), "r"))
    # only preserve 1000 VPs for testing
    unknown_vp_list = unknown_vp_list[:100]
    vp_num = len(unknown_vp_list)
    print('Total unknown VPS:', vp_num)
    # generate tasks at random order
    task_params = []
    timestamp_list = []
    for m_idx in range(len(HOSTS)):
        timestamp_list.append([0 for _ in range(2 * vp_num)])
        for lg_idx in range(len(unknown_vp_list)):
            task_params.append((m_idx, lg_idx))
    # shuffle with fixed seed
    random.seed(123456789)
    random.shuffle(task_params)

    clients, pids = [], []
    for host in HOSTS:
        client = create_ssh_client(host["public_ip"], host["username"])
        pid = start_tcpdump(client, host["pcap_path"])
        print(f"[{host['public_ip']}] tcpdump started with PID {pid}")
        clients.append(client)
        pids.append(pid)
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    try:
        TASK_NUM = 8
        futures = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=TASK_NUM) as executor:
            for m_idx, lg_idx in task_params:
                futures.append(executor.submit(ping_to_one_lg, m_idx, lg_idx, unknown_vp_list[lg_idx]))
            
            # get the result and write to file
            for future in concurrent.futures.as_completed(futures):
                m_idx, lg_idx, start_time = future.result()
                end_time = time.time()
                ingress_tolerance = 1
                egress_tolerance = max(0, 2 - (end_time - start_time))
                timestamp_list[m_idx][2 * lg_idx] = str(start_time - ingress_tolerance)
                timestamp_list[m_idx][2 * lg_idx + 1] = str(end_time + egress_tolerance)
                print(f'machine {m_idx} lg {lg_idx}, duration:{end_time- start_time}')
                
        for m_idx in range(len(HOSTS)):
            time_list = timestamp_list[m_idx]
            with open(os.path.join(OUTPUT_DIR, f'{m_idx}_send.txt'), 'w') as time_file:
                time_file.writelines('\n'.join(time_list))
        print(f'Finish all probing')
    finally:
        for client, host, pid in zip(clients, HOSTS, pids):
            print(f"[{host['public_ip']}] Stopping tcpdump...")
            stop_tcpdump(client, pid)
            local_path = os.path.join(OUTPUT_DIR, host['local_path'])
            download_pcap(client, host["pcap_path"], local_path)
            client.close()
            print(f"[{host['public_ip']}] Done.")