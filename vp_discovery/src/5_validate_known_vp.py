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
import paramiko
import time
from scp import SCPClient

from templates import *
from configs import *
from utils import *

requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
requests_get = partial(requests.get, timeout=10, verify=False)
requests_post = partial(requests.post, timeout=10, verify=False)

def process_params(vp_info, target_ip='8.8.8.8') -> Tuple[str, str]:
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
    return base_url, query

# a function to ping to one lg
def ping_to_one_lg(m_idx, lg_idx, vp_info):
    """
    According to the machine index and lg index, ping to the lg and get the result.
    """
    ping_url, query = process_params(vp_info, HOSTS[m_idx]['public_ip'])
    header = BASE_HEADER
    header["User-Agent"] = random.choice(USER_AGENT_LIST)
    start_time = time.time()
    try:
        session = requests.Session()
        method = vp_info["method"]
        if method == "get":
            ping_url = ping_url + '?' + query
            response = session.get(ping_url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True, stream=True)
        elif method == "post":
            if 'csrfToken' in vp_info["params"]:
                header['content-type'] = 'application/x-www-form-urlencoded'
                response = session.post(ping_url, data=query, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True, stream=True)
            else:
                ping_url = ping_url + '?' + query
                response = session.post(ping_url, timeout=TIMEOUT, headers=header, verify=False, allow_redirects=True, stream=True)
        response.raise_for_status()
    except Exception as e:
        pass
    finally:
        return m_idx, lg_idx, start_time

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
    known_vp_list = json.load(open(os.path.join(OUTPUT_DIR, "known_vp_list.json"), "r"))
    known_vp_list = known_vp_list
    vp_num = len(known_vp_list)
    print('Total known VPS:', vp_num)
    # generate tasks at random order
    task_params = [(m_idx, lg_idx) for m_idx in range(len(HOSTS)) for lg_idx in range(vp_num)]
    random.seed(time.time())
    random.shuffle(task_params)
    print(f"Total tasks: {len(task_params)}")

    clients, pids = [], []
    for host in HOSTS:
        client = create_ssh_client(host["public_ip"], host["username"])
        pid = start_tcpdump(client, host["pcap_path"])
        print(f"[{host['public_ip']}] tcpdump started with PID {pid}")
        clients.append(client)
        pids.append(pid)
    os.makedirs(OUTPUT_DIR, exist_ok=True)    
    try:
        TASK_NUM = 12
        futures = []
        finish_count = 0
        with concurrent.futures.ProcessPoolExecutor(max_workers=TASK_NUM) as executor:
            for m_idx, lg_idx in task_params:
                futures.append(executor.submit(ping_to_one_lg, m_idx, lg_idx, known_vp_list[lg_idx]))
            
            # get the result and write to file
            for future in concurrent.futures.as_completed(futures):
                finish_count += 1
                m_idx, lg_idx, start_time = future.result()
                if finish_count % 500 == 0:
                    print(f"Finish {finish_count} tasks, {len(futures) - finish_count} tasks left")
        print(f'Finish all probing')
    finally:
        for client, host, pid in zip(clients, HOSTS, pids):
            print(f"[{host['public_ip']}] Stopping tcpdump...")
            stop_tcpdump(client, pid)
            local_path = os.path.join(OUTPUT_DIR, host['local_path'])
            download_pcap(client, host["pcap_path"], local_path)
            client.close()
            print(f"[{host['public_ip']}] Done.")