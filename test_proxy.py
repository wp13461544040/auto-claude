#!/usr/bin/env python3
"""测试代理是否真的轮询"""
import random
import requests
from core.config import PROXY_LIST

print(f"代理总数: {len(PROXY_LIST)}\n")

# 随机选5个代理测试
for i in range(5):
    proxy = random.choice(PROXY_LIST)
    print(f"测试代理 {i+1}: {proxy[:60]}...")
    
    try:
        s = requests.Session()
        s.proxies = {"http": proxy, "https": proxy}
        r = s.get("http://ip-api.com/json", timeout=10)
        data = r.json()
        ip = data.get("query", "?")
        print(f"  -> 出口IP: {ip}\n")
    except Exception as e:
        print(f"  -> 失败: {e}\n")
