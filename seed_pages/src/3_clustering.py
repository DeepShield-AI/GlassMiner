# Post-processing of the seed pages to cluster them based on the similarity of the content.
# We just check if the seed pages have the keyword "Looking Glass" in the title or body.

# Import the required libraries
import json
import sys
import numpy as np
import pandas as pd
import pickle as pkl
import regex as re
from disjoint_set import DisjointSet

# Import the customized content
from configs import *

TOKINIZER = None

def is_symbols(token):
    if re.match(PTN_CHAR, token):
        return True
    return False

def shingle(text, k):
    """
    1. Lowercase the text and remove all the punctuations.
    2. Tokenize the text into words.
    3. Create the shingles by combining consecutive k words.
    """
    text = text.lower()
    tokens = TOKINIZER.tokenize(text)
    words = TOKINIZER.convert_tokens_to_string(tokens).split()
    words = [word for word in words if not is_symbols(word)]
    shingles = {tuple(words[i:i+k]) for i in range(len(words) - k + 1)}
    return shingles

def jaccard_similarity(shingles1, shingles2):
    intersection = shingles1.intersection(shingles2)
    if len(intersection) == 0:
        return 0
    # Must not be empty strings
    len_min = min(len(shingles1), len(shingles2))
    log_len_max = np.log(max(len(shingles1), len(shingles2)))
    # using a symmetric factor to make the similarity symmetric
    return len(intersection) / (log_len_max + len_min)

def calculate_jaccard_similarity(verified_lg_info, single_size):
    """
    Calculate the similarity between each pair of webpages.
    """
    print("Calculating the Jaccard similarity between each pair of webpages...")
    pair_count = 0
    mat_sim = np.zeros((len(verified_lg_info), len(verified_lg_info)))
    for i in range(len(verified_lg_info)):
        for j in range(i+1, len(verified_lg_info)):
            pair_count += 1
            mat_sim[i][j] = jaccard_similarity(verified_lg_info[i]["shingle"][single_size], verified_lg_info[j]["shingle"][single_size])
            if pair_count % 100000 == 0:
                print(f"{pair_count} pairs of webpages have been calculated.")
    return mat_sim

def cluster_webpages_by_similarity(verified_lg_info, mat_sim, threshold):
    """
    For one cluster, we add a new webpage when it is similar to over half of the cluster.
    """                
    # Testing Logic: change different threshold to see the clustering results
    print(f"Clustering webpages with threshold {threshold}...")
    # Then, using disjoint set to cluster the webpages
    clusters = DisjointSet({i : i for i in range(len(verified_lg_info))})
    
    # Check the similarity between disjoint sets rather than the webpages
    for i in range(len(verified_lg_info)):
        for j in range(i+1, len(verified_lg_info)):
            if mat_sim[i][j] > threshold:
                clusters.union(i, j)
    
    cluster_dict = {}
    url2cluster = {}
    # Update the two dictionaries
    for idx, cluster in clusters.itersets(with_canonical_elements=True):
        cluster_dict[idx] = []
        for i in cluster:
            url = verified_lg_info[i]["url"]
            url2cluster[url] = idx
            cluster_dict[idx].append(url)            
    # sort by the number of webpages in the cluster
    cluster_dict = {k: v for k, v in sorted(cluster_dict.items(), key=lambda item: len(item[1]), reverse=True)}
    return cluster_dict, url2cluster

def evaluate_the_clustering(gt_clusters, url2cluster):
    """
    Evaluate the clustering results by comparing with the ground truth clusters.
    We check the entropy of the cluster results of gt_clusters.
    For each cluster in gt_clusters, we calculate the -sum(p_i*log(p_i)) for type i after clustering. 
    """
    gt_cluster_res = {}
    res_cluster_to_gt = {}
    for gt_id, cluster in gt_clusters.items():
        gt_cluster_res[gt_id] = []
        for info in cluster:
            url = info['url']
            res = url2cluster[url]
            if res not in res_cluster_to_gt:
                res_cluster_to_gt[res] = []
            res_cluster_to_gt[res].append(gt_id)
            gt_cluster_res[gt_id].append(res)

    # Metric 1: calculate the entropy of the clustering results
    gt_entropy = 0
    for gt_id, cluster in gt_cluster_res.items():
        if len(cluster) == 0:
            continue
        cluster_size = len(cluster)
        cluster_type = {}
        for res_id in cluster:
            if res_id not in cluster_type:
                cluster_type[res_id] = 0
            cluster_type[res_id] += 1
        cluster_entropy = 0
        for res_id, count in cluster_type.items():
            cluster_entropy += count / cluster_size * np.log(count / cluster_size)
        gt_entropy -= cluster_entropy
    
    # Metric 2: calculate the number of the clustered results
    res_entropy = 0
    for res_id, gt_ids in res_cluster_to_gt.items():
        cluster_size = len(gt_ids)
        cluster_type = {}
        for gt_id in gt_ids:
            if gt_id not in cluster_type:
                cluster_type[gt_id] = 0
            cluster_type[gt_id] += 1
        cluster_entropy = 0
        for gt_id, count in cluster_type.items():
            cluster_entropy += count / cluster_size * np.log(count / cluster_size)
        res_entropy -= cluster_entropy
    return gt_entropy, res_entropy

def load_gt_clusters(verified_lg_info):
    """
    Load the ground truth clusters from the file, find thier indexes in the verified_lg_info.
    This is used for select the reasonable threshold for clustering only.
    """
    gt_clusters = {}
    with open(os.path.join(DATA_DIR, "ground_truth_clusters.json"), "r") as f:
        gt_clusters = json.load(f)
    gt_clusters_with_idx = {}
    for cluster_id, cluster in gt_clusters.items():
        cluster_idx = []
        for url in cluster:
            for idx, page in enumerate(verified_lg_info):
                if page["url"] == url:
                    cluster_idx.append({
                        "url": url,
                        "idx": idx
                    })
                    break
        gt_clusters_with_idx[cluster_id] = cluster_idx
    return gt_clusters_with_idx

if __name__ == "__main__":
    # check the input arguments to select the clustering method
    if len(sys.argv) != 2:
        print("Usage: python clustering.py <mode>")
        print("Mode: 1 - clustering based on current configuration.")
        print("Mode: 2 - find the best threshold for clustering by validating the ground truth clusters.")
        print("Now using default mode 1.")
        mode = 1
    else:
        mode = int(sys.argv[1])
        if mode not in [1, 2]:
            print("Invalid mode. Please select 1 or 2.")
            sys.exit(1)
    # Load the seed pages
    try:
        verified_lg_info = json.load(open(os.path.join(LOGS_DIR, "verified_lg_info.bin"), "r"))
    except:
        # Initialize the tokenizer
        from transformers import BertTokenizer
        TOKINIZER = BertTokenizer.from_pretrained("bert-base-multilingual-uncased")
        
        unique_verified_pages = pkl.load(open(os.path.join(OUTPUT_DIR, UNIQ_FILE), "rb"))
        verified_lg_info = []
        count = 0
        for lg_info in unique_verified_pages:
            url = lg_info["url"]
            filename = lg_info["filename"]
            filepath = os.path.join(VERIFIED_DIR, filename)
            if not os.path.exists(filepath):
                continue
            # Extract the content from the seed pages
            seed_content = None
            with open(filepath, "r") as f:
                seed_content = f.read()
                if len(seed_content) < TEXT_LEN_MIN_THRESHOLD:
                    continue
            # Default shingle size only
            verified_lg_info.append({
                "url": url,
                "filename": filename,
                "content": seed_content,
                "shingle": {
                    k: shingle(seed_content, k) for k in SHINGLE_LEN_LIST
            }})
            count += 1
            if count % 500 == 0:
                print(f"{count} pages have been processed.")
        os.makedirs(LOGS_DIR, exist_ok=True)
        pkl.dump(verified_lg_info, open(os.path.join(LOGS_DIR, "verified_lg_info.bin"), "wb"))
    # calculate the Jaccard similarity and cluster the seed pages    
    if mode == 1:
        try:
            mat_sim = pkl.load(open(os.path.join(LOGS_DIR, SIM_FILE.format(SHINGLE_SIZE)), "rb"))
        except:
            mat_sim = calculate_jaccard_similarity(verified_lg_info, SHINGLE_SIZE)
            pkl.dump(mat_sim, open(os.path.join(LOGS_DIR, SIM_FILE.format(SHINGLE_SIZE)), "wb"))
        clusters, url2cluster = cluster_webpages_by_similarity(verified_lg_info, mat_sim, CLUSTER_THRESHOLD)
        print(f"Total {len(clusters)} clusters are found.")
        # save the clustering results to file
        with open(os.path.join(OUTPUT_DIR, "clusters.json".format(SHINGLE_SIZE, CLUSTER_THRESHOLD)), "w") as f:
            json.dump(clusters, f)
    else:
        gt_clusters = load_gt_clusters(verified_lg_info)
        # log three 2-D matrices for the metrics with shape (len(CLUSTER_THR_LIST), len(SHINGLE_LEN_LIST))
        mat_gt_entropy = np.zeros((len(CLUSTER_THR_LIST), len(SHINGLE_LEN_LIST)), dtype=np.float32)
        mat_res_entropy = np.zeros((len(CLUSTER_THR_LIST), len(SHINGLE_LEN_LIST)), dtype=np.float32)
        mat_clst_count = np.zeros((len(CLUSTER_THR_LIST), len(SHINGLE_LEN_LIST)), dtype=np.int32)
        for idx_1, shingle_size in enumerate(SHINGLE_LEN_LIST):
            try:
                mat_sim = pkl.load(open(os.path.join(LOGS_DIR, SIM_FILE.format(shingle_size)), "rb"))
            except:
                mat_sim = calculate_jaccard_similarity(verified_lg_info, shingle_size)
                pkl.dump(mat_sim, open(os.path.join(LOGS_DIR, SIM_FILE.format(shingle_size)), "wb"))
            # Testing Logic: change different threshold to see the clustering results
            for idx_2, threshold in enumerate(CLUSTER_THR_LIST):
                clusters, url2cluster = cluster_webpages_by_similarity(verified_lg_info, mat_sim, threshold)
                gt_entropy, res_entropy = evaluate_the_clustering(gt_clusters, url2cluster)
                mat_gt_entropy[idx_2][idx_1] = gt_entropy
                mat_res_entropy[idx_2][idx_1] = res_entropy
                mat_clst_count[idx_2][idx_1] = len(clusters)
                print(f"Total {len(clusters)} clusters are found.")
                # save the clustering results to file
                with open(os.path.join(LOGS_DIR, "clusters_sh={}_th={}.json".format(shingle_size, threshold)), "w") as f:
                    json.dump(clusters, f)
        # save the metrics to 2-D tables for analysis with headers
        df_entropy = pd.DataFrame(mat_gt_entropy, columns=SHINGLE_LEN_LIST, index=CLUSTER_THR_LIST)
        df_minority = pd.DataFrame(mat_res_entropy, columns=SHINGLE_LEN_LIST, index=CLUSTER_THR_LIST)
        df_clst_count = pd.DataFrame(mat_clst_count, columns=SHINGLE_LEN_LIST, index=CLUSTER_THR_LIST)
        with pd.ExcelWriter(os.path.join(OUTPUT_DIR, "clustering_metrics.xlsx")) as writer:
            df_entropy.to_excel(writer, sheet_name="gt_entropy")
            df_minority.to_excel(writer, sheet_name="res_entropy")
            df_clst_count.to_excel(writer, sheet_name="cluster_count")