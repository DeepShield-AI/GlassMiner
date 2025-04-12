# Accroding to the result in 3_discover_vps.py and all the tcpdump files, 
# cross check to find the ip of unknown VPs
import dpkt
import socket
import sys
import os
import pickle
import operator
import ast
import json
from pytz import timezone

from configs import *
from utils import *

result_each_time = []

def get_valid_ip(src, dst, idx):
    if (src == HOSTS[idx]['public_ip']) or (src == HOSTS[idx]['private_ip']):
        return dst
    else:
        return src
        
if __name__ == "__main__":
    unknown_vp_list = json.load(open(os.path.join(OUTPUT_DIR, "unknown_vp_list.json"), "r"))
    # only choose the first 100 VPs for testing
    unknown_vp_list = unknown_vp_list[:100]
    # start_time & end_time timestamp list
    time_lists = []
    vp_num = len(unknown_vp_list)
    # read the start_time and end_time from the tcpdump file
    for m_idx in range(0, len(HOSTS)):
        time_list = []
        time_file_path = os.path.join(OUTPUT_DIR, f'{m_idx}_send.txt')
        with open(time_file_path, 'r') as srcfile:
            # 2 rows in a pair, start and end
            lines = srcfile.readlines()
            for idx in range(len(unknown_vp_list)):
                start_time = float(lines[2 * idx])
                end_time = float(lines[2 * idx + 1])
                time_list.append((start_time, end_time))
        time_lists.append(time_list)

    ip_count_list = [{} for idx in range(vp_num)]

    # log the timestamp of the icmp packet
    icmp_timestamp_list = [[] for _ in range(len(HOSTS))]
    for m_idx in range(0, len(HOSTS)):
        with open(os.path.join(OUTPUT_DIR, HOSTS[m_idx]['local_path']), 'rb') as fr:
            pcap = dpkt.pcap.Reader(fr)
            for timestamp, buffer in pcap:
                ethernet = dpkt.ethernet.Ethernet(buffer)
                if not isinstance(ethernet.data, dpkt.ip.IP):
                    continue
                ip = ethernet.data
                if not isinstance(ip.data, dpkt.icmp.ICMP):
                    continue

                icmp = ip.data
                src_ip = socket.inet_ntoa(ip.src)
                dst_ip = socket.inet_ntoa(ip.dst)
                this_ip = get_valid_ip(src_ip, dst_ip, m_idx)
                # mark the timestamp of the icmp packet
                icmp_timestamp_list[m_idx].append((timestamp, this_ip))
            # sort by timestamp, ascending
            icmp_timestamp_list[m_idx].sort(key=operator.itemgetter(0))
            
    # intersection the icmp timestamp with time_list duration 
    intersect_list = [[set() for _ in range(vp_num)] for _ in range(len(HOSTS))]
    for m_idx in range(0, len(HOSTS)):
        for lg_idx in range(vp_num):
            start_time, end_time = time_lists[m_idx][lg_idx]
            cur_idx = 0
            while icmp_timestamp_list[m_idx][cur_idx][0] <= start_time:
                cur_idx += 1
            for timestamp, this_ip in icmp_timestamp_list[m_idx][cur_idx:]:
                if timestamp < end_time:
                    intersect_list[m_idx][lg_idx].add(this_ip)
                else:
                    break

    new_lg_list = []
    bad_lg_info = []
    threshold = 2 * len(HOSTS) / 3
    for lg_idx in range(vp_num):
        intersection_candidates = set()
        threshold_candidates = set()
        show_up_count = {}
        for m_idx in range(len(HOSTS)):
            for ip in intersect_list[m_idx][lg_idx]:
                if ip not in show_up_count:
                    show_up_count[ip] = 1
                else:
                    show_up_count[ip] += 1
                    if show_up_count[ip] >= threshold:
                        threshold_candidates.add(ip)
                    if show_up_count == len(HOSTS):
                        intersection_candidates.add(ip)
        print('Intersection candidates:', intersection_candidates)
        print('Threshold candidates:', threshold_candidates)
        print('----------------------')
        ip_addr = None
        if len(intersection_candidates) == 1:
            ip_addr = intersection_candidates.pop()
        elif len(threshold_candidates) == 1:
            ip_addr = threshold_candidates.pop()
        if ip_addr:
            lg_info = unknown_vp_list[lg_idx]
            lg_info['ip_addr'] = ip_addr
            new_lg_list.append(lg_info)
            geolocation = geolocate_one_vp(lg_info)
            lg_info['location'] = geolocation
        else:
            bad_lg_info.append(unknown_vp_list[lg_idx])
    print('----------------------')
    print('New LG list:', len(new_lg_list))
    print('Bad LG list:', len(bad_lg_info))
    
    # load the old vp_list
    old_vp_list = json.load(open(os.path.join(OUTPUT_DIR, "known_vp_list.json"), "r"))
    dict_new_ip_to_lg = {}
    raw_total_vp_list = []
    for vp_info in old_vp_list:
        raw_total_vp_list.append(vp_info)
    for vp_info in new_lg_list:
        raw_total_vp_list.append(vp_info)
        dict_new_ip_to_lg[vp_info['ip_addr']] = vp_info
    
    dict_ip_to_lg = {}
    for lg_info in raw_total_vp_list:
        ip_addr = lg_info['ip_addr']
        if ip_addr not in dict_ip_to_lg:
            dict_ip_to_lg[ip_addr] = [lg_info]
        else:
            dict_ip_to_lg[ip_addr].append(lg_info)
    unique_lg_list = []
    for ip_addr, lg_info_list in dict_ip_to_lg.items():
        if len(lg_info_list) == 1:
            unique_lg_list.append(lg_info_list[0])
        elif ip_addr in dict_new_ip_to_lg:
            unique_lg_list.append(dict_new_ip_to_lg[ip_addr])
        else:
            unique_lg_list.append(lg_info_list[0])
    # write to files
    with open(os.path.join(OUTPUT_DIR, "total_known_vp_list.json"), "w") as f:
        json.dump(unique_lg_list, f, indent=4)