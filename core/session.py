import random
import requests
from .config import PROXY_LIST, build_headers


def make_session(cookies=None, seed=None):
    s = requests.Session()
    s.headers.update(build_headers(seed))
    
    # 如果有多个代理，随机选一个（轮询）
    if PROXY_LIST:
        proxy = random.choice(PROXY_LIST)
        s.proxies.update({"http": proxy, "https": proxy})
    
    if cookies:
        for k, v in cookies.items():
            s.cookies.set(k, v, domain="claude.ai")
    return s
