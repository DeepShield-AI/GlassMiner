# Clustering the collected LG webpages, then analyse thier templates.

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
from utils import *

def calculate_structure_similarity(verified_lg_info):
    """
    Calculate the similarity between each pair of webpages.
    """
    print("Calculating the structure similarity between each pair of webpages...")
    pair_count = 0
    mat_sim = np.zeros((len(verified_lg_info), len(verified_lg_info)))
    html_1 = None
    html_2 = None
    for i in range(len(verified_lg_info)):
        with open(os.path.join(SAVE_DIR, verified_lg_info[i]["filename"])) as f:
            html_1 = f.read()
        for j in range(i+1, len(verified_lg_info)):
            with open(os.path.join(SAVE_DIR, verified_lg_info[j]["filename"])) as f:
                html_2 = f.read()
            pair_count += 1
            mat_sim[i][j] = sequence_similarity(html_1, html_2)
            if pair_count % 50000 == 0:
                print(f"{pair_count} pairs of webpages have been calculated.")
    return mat_sim

def cluster_webpages_by_similarity(indices, mat_sim, threshold, abs_threshold):
    """
    For each webpage i, find its most similar webpage j (j > i) that has similarity > threshold,
    and merge them into the same cluster.
    """                
    print(f"Clustering webpages with threshold {threshold}...")
    clusters = DisjointSet({i : i for i in range(len(indices))})
    
    # For each webpage i, find its most similar webpage j
    for i in range(len(indices)):
        max_sim = 0
        max_j = -1
        # Find the most similar webpage j among remaining webpages
        for j in range(i+1, len(indices)):
            # For each webpage with similarity > abs_threshold, directly merge them
            if mat_sim[i][j] > abs_threshold:
                clusters.union(i, j)
            if mat_sim[i][j] > max_sim:
                max_sim = mat_sim[i][j]
                max_j = j
        # If found a similar enough webpage, merge them
        if max_sim > threshold and max_j != -1:
            clusters.union(i, max_j)
    
    cluster_dict = {}
    url2cluster = {}
    # Update the two dictionaries
    for idx, cluster in clusters.itersets(with_canonical_elements=True):
        cluster_dict[idx] = []
        for i in cluster:
            url = verified_lg_info[indices[i]]["url"]
            url2cluster[url] = idx
            cluster_dict[idx].append(url)            
    # sort by the number of webpages in the cluster
    cluster_dict = {k: v for k, v in sorted(cluster_dict.items(), key=lambda item: len(item[1]), reverse=True)}
    return cluster_dict, url2cluster

if __name__ == "__main__":
    # Load the seed pages, and their shingles
    verified_lg_info = None
    try:
        verified_lg_info = pkl.load(open(os.path.join(OUTPUT_DIR, "verified_lg_info.bin"), "rb"))
    except:
        # load the verified_lg_info
        unique_verified_pages = json.load(open(os.path.join(DATA_DIR, UNIQ_FILE), "r"))
        verified_lg_info = []
        
        # Test: filter out the page with "he.net/AS" in URL
        unique_verified_pages = [lg_info for lg_info in unique_verified_pages if "he.net/AS" not in lg_info["url"]]
        
        count = 0
        for lg_info in unique_verified_pages:
            url = lg_info["url"]
            filename = lg_info["filename"]
            filepath = os.path.join(SAVE_DIR, filename)
            if not os.path.exists(filepath):
                continue
            # Extract the content from the seed pages
            seed_content = None
            with open(filepath, "r") as f:
                seed_content = f.read()
                if len(seed_content) < TEXT_LEN_MIN_THRESHOLD:
                    continue
            verified_lg_info.append({
                "url": url,
                "filename": filename,
                "content": seed_content,
            })
            count += 1
            if count % 1000 == 0:
                print(f"{count} pages have been processed.")
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        pkl.dump(verified_lg_info, open(os.path.join(OUTPUT_DIR, "verified_lg_info.bin"), "wb"))

    os.makedirs(LOGS_DIR, exist_ok=True)
    print("\n=== Structure similarity ===")
    try:
        mat_sim_structure = pkl.load(open(os.path.join(LOGS_DIR, SIM_FILE.format(0)), "rb"))
    except:
        mat_sim_structure = calculate_structure_similarity(verified_lg_info)
        pkl.dump(mat_sim_structure, open(os.path.join(LOGS_DIR, SIM_FILE.format(0)), "wb"))
    
    clusters_1st, url2cluster_1st = cluster_webpages_by_similarity(
        [i for i in range(len(verified_lg_info))], mat_sim_structure, 
        threshold=STRUC_THRESHOLD, abs_threshold=STRUC_THRESHOLD + 0.1
    )
    
    # Sort clusters by size
    sorted_clusters_1st = {}
    cluster_sizes = [(cluster_id, len(urls)) for cluster_id, urls in clusters_1st.items()]
    cluster_sizes.sort(key=lambda x: x[1], reverse=True)
    for new_id, (old_id, _) in enumerate(cluster_sizes):
        sorted_clusters_1st[f"structure_cluster_{new_id}"] = clusters_1st[old_id]
    # Save structure clustering results
    with open(os.path.join(OUTPUT_DIR, "structure_clusters.json"), "w") as f:
        json.dump(sorted_clusters_1st, f, indent=2)
    print(f"{len(clusters_1st)} clusters found in stage 1.")

    # Analyze the webpages in each cluster, find thier API format and keyword for each parameters
    pass