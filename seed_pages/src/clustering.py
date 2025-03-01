# Post-processing of the seed pages to cluster them based on the similarity of the content.
# We just check if the seed pages have the keyword "Looking Glass" in the title or body.

# Import the required libraries
import json
from typing import List
from bs4 import BeautifulSoup

# Import the customized content
from configs import *

def shingle(text, k):
    return {text[i:i+k] for i in range(len(text) - k + 1)}

def jaccard_similarity(shingles1, shingles2):
    intersection = shingles1.intersection(shingles2)
    union = shingles1.union(shingles2)
    return len(intersection) / len(union)

def cluster_webpages_by_jaccard_similarity(verified_lg_pages):
    """
    Split each webpage content into shingles. 
    Then compute the pair-wise similarity between webpages.
    For one cluster, we add a new webpage when it is similar to over half of the cluster.
    """
    # Calculate the pairwise Jaccard similarity
    for i, lg_1 in enumerate(verified_lg_pages):
        for j, lg_2 in enumerate(verified_lg_pages):
            if i == j:
                continue
            similarity = jaccard_similarity(lg_1["single"], lg_2["single"])
            similarity[i][j] = similarity[j][i] = similarity
    # Clustering the seed pages
    clusters = []
    for i, lg in enumerate(verified_lg_pages):
        for cluster in clusters:
            if sum(similarity[i][j] > CLUSTER_THRESHOLD for j in cluster) > len(cluster) // 2:
                cluster.append(i)
                break
        else:
            clusters.append([i])
    # Print the clustering results
    print(f"Total {len(clusters)} clusters are found.")
    for i, cluster in enumerate(clusters):
        print(f"Cluster {i}: {', '.join(verified_lg_pages[i]['url'] for i in cluster)}")

if __name__ == "__main__":
    # Load the seed pages
    available_pages = json.load(open(os.path.join(OUTPUT_DIR, AVAI_FILE), "r"))
    verified_lg_pages = []
    for lg_info in available_pages:
        url = lg_info["url"]
        filename = lg_info["filename"]
        filepath = os.path.join(VERIFIED_DIR, filename)
        if not os.path.exists(filepath):
            continue
        # Extract the content from the seed pages
        seed_content = None
        with open(filepath, "r") as f:
            seed_content = f.read()
    verified_lg_pages.append({
        "url": url,
        "filename": filename,
        "content": seed_content,
        "single": shingle(seed_content, SHINGLE_SIZE)
    })
    # calculate the Jaccard similarity and cluster the seed pages
    cluster_webpages_by_jaccard_similarity(verified_lg_pages)