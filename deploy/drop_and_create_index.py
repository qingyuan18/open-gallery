#!/usr/bin/env python3
import boto3
import json
import requests
from requests_aws4auth import AWS4Auth

# AWS 配置
region = 'us-west-2'
service = 'es'
credentials = boto3.Session().get_credentials()
awsauth = AWS4Auth(credentials.access_key, credentials.secret_key, region, service, session_token=credentials.token)

# OpenSearch endpoint
host = 'https://search-aos-3-x5cqwufloswi2vlsoblpcjdylu.us-west-2.es.amazonaws.com'

# 删除索引 - 使用 Index Management API
print("删除现有索引...")
delete_url = f'{host}/_plugins/_ism/policies/covering'
response = requests.delete(delete_url, auth=awsauth)
print(f"删除策略响应: {response.status_code}")

# 尝试删除索引本身
delete_index_url = f'{host}/covering'
response = requests.delete(delete_index_url, auth=awsauth)
print(f"删除索引响应: {response.status_code}")
print(f"响应内容: {response.text}")

# 检查现有索引
print("\n检查现有索引...")
list_url = f'{host}/_cat/indices?v'
response = requests.get(list_url, auth=awsauth)
print(f"索引列表: {response.text}")

# 使用 Index Management API 创建覆盖索引
print("\n创建覆盖索引...")
create_url = f'{host}/_plugins/_ism/policies/covering'
policy = {
    "policy": {
        "description": "Covering index policy",
        "default_state": "active",
        "states": [
            {
                "name": "active",
                "actions": [],
                "transitions": []
            }
        ]
    }
}

response = requests.put(create_url, auth=awsauth, json=policy)
print(f"创建策略响应: {response.status_code}")
print(f"响应内容: {response.text}")

# 尝试直接创建索引
print("\n直接创建索引...")
create_index_url = f'{host}/covering'
index_config = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0
    },
    "mappings": {
        "properties": {
            "url_host_name": {"type": "keyword"},
            "fetch_status": {"type": "keyword"},
            "fetch_time": {"type": "date"}
        }
    }
}

response = requests.put(create_index_url, auth=awsauth, json=index_config)
print(f"创建索引响应: {response.status_code}")
print(f"响应内容: {response.text}")
