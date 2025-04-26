# GlassMiner: A Structural-Semantic Fusion Framework for Mining Internet-Wide Looking Glass Services

## Introduction

GlassMiner is a framework designed to mine and analyze the Looking Glass (LG) services on the Internet. It consists of three main modules:

- **Template clustering analysis**: This module processes the seed pages of LG services and performs clustering analysis by fused structural and semantic features, and then performs selective TF-IDF analysis to extract the most representative keywords for each cluster.

- **Network-aware crawler**: This module implements a network-aware crawler to collect webpages of LG services. It uses the clustering results from the previous module and the AS (Autonomous System) information to guide the crawling process. The crawler is designed to be efficient and effective in collecting relevant webpages.

- **LLM-driven classification**: This module uses large language models (LLMs) to classify the webpages collected by the crawler. It employs a few-shot learning approach to improve classification accuracy and reduce the need for extensive labeled data.

- **LG VP discovery**: This module implements a distributed system to discover the VPs of LG services and confirm their availability and API functionality. It uses a set of templates to identify the VPs and employs a distributed approach to improve efficiency.

## Result List

You can find the result list of our paper [here](https://glassminer.github.io/GlassMiner/).

## How to use

The GlassMiner framework is designed to be modular, allowing users to run each component independently.
<!-- 我们基本上已使得每个模块内部可以直接按照序号顺序执行，以下我们会讲解各个模块的具体使用方法。 -->
We have made each module **executable in sequence**, and below we will explain how to use each module.

### 0. Environment Setup

GlassMiner is implemented in Python 3.11. You can create a virtual environment, then install the required packages using the following commands:

```bash
# Create a virtual environment
conda create -n glassminer python=3.11
# Activate the virtual environment
conda activate glassminer
# Install the required packages
pip install -r requirements.txt
```

### 1. Seedpage processing and clustering

This part corresponds to the logic in the subdirectory `seed_pages`, including seed page processing and **template clustering analysis**.

We have placed some necessary files in the `/data` subdirectory, and you can directly execute the files in the `/src` subdirectory in sequential order.
After executing, you will find the corresponding clustering results and corpus analysis results in the `/output` subdirectory.


### 2. Webpage crawling

This part corresponds to the logic in the subdirectory `webpage_crawler`, including the **network-aware crawler**.

The input of this module mainly includes the output of the previous module and some necessary AS-related data, we have placed all the necessary files in the `/data` subdirectory, and you can directly execute the files in the `/src` subdirectory in sequential order.

### 3. LLM-driven Classification

This part corresponds to the logic in the subdirectory `llm_classifier`, including the **LLM-driven classification** module.

> **Preliminary**:
>
> To use the paid LLM service, you need to fill in your personal API Key in `/src/utils.py` to use the [silicon-based flow LLM service](https://cloud.siliconflow.cn/account/ak):
>
> ```python
> API_HEADER = {
>     "Authorization": "Bearer <Your API Key>",
>     "Content-Type": "application/json"
> }
> ```
> Of course, you can also connect to other LLM models that you have deployed yourself!


We have provided the selected prompts, so you can skip running `/src/2_autoselection.py`.
If you want to build this part yourself, you can run `/src/2_autoselection.py` to select the optimal few-shot samples.


You may need to manually trim the content of the few-shot samples after running `/src/2_autoselection.py` to reduce inference costs, and update it in the `prompted_binary_classification()` function in `/src/utils.py`.


### 4. VP Discovery

This part corresponds to the logic in the subdirectory `vp_discovery`, including the **LG VP discovery** module.

> **Preliminary**:
>
> You need to replace the machine IP addresses in the `/src/configs.py` file with your own machine IP address (and the usernames and the file paths). We strongly recommend using at least 3 machines to run this module.
>
> ```python
> HOSTS = [
>    {
>        "public_ip": "<Your Public IP Address #1>",
>        "private_ip": "<Your Private IP Address #1>",
>        "username": "root",
>        "pcap_path": "~/0_receive.pcap",
>        "local_path": "0_receive.pcap",
>    },
>    ...
> ]
> ```

**Note**: 
1. We have manually processed the templates in `/src/templates.py`, but we have not checked all the templates as it is a time-consuming task. We only checked and reported the more frequent templates in the paper. We believe that **there are actually more automatable templates**, and you can modify them according to your needs.
2. We discard those LG services that only provide BGP summary queries and do not provide any other valuable services. They can be classified as LG services, but we just ignore them in successive steps. If you want to include them, you can parse and add more logic in the `/src/templates.py` file.