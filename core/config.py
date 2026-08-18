import os
import uuid


def load_env(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.split("#", 1)[0].strip().strip('"').strip("'")
            os.environ.setdefault(key, val)


load_env()

# 动态获取配置的函数
def get_moemail_api_key():
    return os.environ.get("MOEMAIL_API_KEY", "")

def get_moemail_base_url():
    return os.environ.get("MOEMAIL_BASE_URL", "")

def get_remail_api_key():
    return os.environ.get("REMAIL_API_KEY", "")

def get_remail_api_url():
    return os.environ.get("REMAIL_API_URL", "https://remail.aishop6.com")

def get_remail_project_id():
    return int(os.environ.get("REMAIL_PROJECT_ID", "0"))

def get_remail_product_id():
    return int(os.environ.get("REMAIL_PRODUCT_ID", "0"))

def get_remail_mode():
    return os.environ.get("REMAIL_MODE", "package")

def get_remail_suffix():
    return os.environ.get("REMAIL_SUFFIX", "")

def get_email_service():
    """动态获取当前邮箱服务配置"""
    return os.environ.get("EMAIL_SERVICE", "moemail")

# 兼容旧代码的模块常量（使用时会是初始值，新代码应该用get_*函数）
MOEMAIL_API_KEY  = get_moemail_api_key()
MOEMAIL_BASE_URL = get_moemail_base_url()

# Remail 邮箱配置
REMAIL_API_KEY    = get_remail_api_key()
REMAIL_API_URL    = get_remail_api_url()
REMAIL_PROJECT_ID = get_remail_project_id()
REMAIL_PRODUCT_ID = get_remail_product_id()
REMAIL_MODE       = get_remail_mode()
REMAIL_SUFFIX     = get_remail_suffix()

# 邮箱服务选择: moemail 或 remail
EMAIL_SERVICE = get_email_service()

# Outlook注册单独保存的文件
OUTLOOK_ACCOUNTS_FILE = os.environ.get("OUTLOOK_ACCOUNTS_FILE", "outlook_accounts.json")

# 从 proxy.text 文件或环境变量读取代理
def _load_proxies():
    proxies = []
    
    # 1. 优先从 proxy.text 文件读取
    proxy_file = os.path.join(os.path.dirname(__file__), "..", "proxy.text")
    if os.path.exists(proxy_file):
        with open(proxy_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                # 自动添加协议头（默认 socks5）
                if not line.startswith(("http://", "https://", "socks5://", "socks5h://")):
                    line = "socks5://" + line
                proxies.append(line)
    
    # 2. 如果文件没找到或为空，尝试从环境变量读取
    if not proxies:
        proxy_env = os.environ.get("PROXY", "")
        if proxy_env:
            proxies = [p.strip() for p in proxy_env.split(",") if p.strip()]
    
    return proxies

PROXY_LIST = _load_proxies()

def reload_proxies():
    """重新加载代理配置（用于动态更新）"""
    global PROXY_LIST, PROXY, PROXIES, _proxy_index
    
    with _proxy_lock:
        PROXY_LIST = _load_proxies()
        PROXY = PROXY_LIST[0] if PROXY_LIST else ""
        PROXIES = {"http": PROXY, "https": PROXY} if PROXY else None
        _proxy_index = 0  # 重置索引

# 代理轮询索引（全局变量，线程安全）
import threading
_proxy_lock = threading.Lock()
_proxy_index = 0

def get_next_proxy():
    """轮询获取下一个代理"""
    global _proxy_index
    
    if not PROXY_LIST:
        return None
    
    with _proxy_lock:
        proxy = PROXY_LIST[_proxy_index % len(PROXY_LIST)]
        _proxy_index += 1
        return proxy

def get_proxies_dict(proxy=None):
    """获取代理字典，用于requests"""
    if proxy is None:
        proxy = get_next_proxy()
    
    if proxy:
        return {"http": proxy, "https": proxy}
    return None

# 向后兼容：PROXIES 用第一个代理（旧代码可能直接用）
PROXY = PROXY_LIST[0] if PROXY_LIST else ""
PROXIES = {"http": PROXY, "https": PROXY} if PROXY else None

REGISTER_COUNT      = int(os.environ.get("REGISTER_COUNT", "1"))
REGISTER_CONCURRENT = int(os.environ.get("REGISTER_CONCURRENT", "1"))

ACCOUNTS_FILE = os.environ.get("ACCOUNTS_FILE", "accounts.json")

BASE_URL = "https://claude.ai"

# 固定命名空间保证同一 seed 跨进程稳定，同时让不同字段互不关联。
_ANON_NS = uuid.UUID("6f4a1c2e-1b3d-4e5f-8a90-0c1d2e3f4a5b")
_DEVICE_NS = uuid.UUID("9d8c7b6a-5e4f-4321-9a8b-7c6d5e4f3a2b")
_PROFILE_NS = uuid.UUID("3c2b1a09-8f7e-4d6c-b5a4-9382716f5e4d")
_DEFAULT_SEED = "claudex-default"

# 每个资料包含互相匹配的浏览器 UA 和语言偏好；只选择真实组合，不拼接随机 UA。
_BROWSER_PROFILES = (
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36",
        "en-US,en;q=0.9",
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36",
        "en-US,en;q=0.9",
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36 "
        "Edg/149.0.0.0",
        "en-GB,en;q=0.9",
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) "
        "Gecko/20100101 Firefox/133.0",
        "de-DE,de;q=0.9,en;q=0.8",
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/18.1 Safari/605.1.15",
        "en-US,en;q=0.9",
    ),
)

_CLIENT_PLATFORM = "web_claude_ai"
_CLIENT_VERSION = "1.0.0"
_CLIENT_SHA = "882d9a7d43eced6a100e636e1dfdebc55764bd78"


def _derive_anonymous_id(seed):
    """由 seed（通常是邮箱）哈希派生 anonymous-id：同账号稳定、跨账号各异。"""
    return "claudeai.v1." + str(uuid.uuid5(_ANON_NS, seed))


def _derive_device_id(seed):
    """由 seed 哈希派生 device-id（标准 UUID 形式）。"""
    return str(uuid.uuid5(_DEVICE_NS, seed))


def _derive_browser_profile(seed):
    """由 seed 稳定选择一套完整浏览器资料。"""
    index = uuid.uuid5(_PROFILE_NS, seed).int % len(_BROWSER_PROFILES)
    return _BROWSER_PROFILES[index]


def build_headers(seed=None):
    """构造发往 claude.ai 的请求头。

    anonymous-id、device-id 和浏览器资料都由 seed 哈希派生，保证同账号
    稳定、跨账号不同。不传 seed 时使用固定的默认 seed，结果仍可重复。

    client platform/version/sha 是协议构建元数据，使用代码常量而不伪造。
    """
    stable_seed = str(seed or _DEFAULT_SEED)
    user_agent, accept_language = _derive_browser_profile(stable_seed)

    return {
        "accept": "*/*",
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL + "/",
        "user-agent": user_agent,
        "accept-language": accept_language,
        "anthropic-client-platform": _CLIENT_PLATFORM,
        "anthropic-client-version": _CLIENT_VERSION,
        "anthropic-client-sha": _CLIENT_SHA,
        "anthropic-anonymous-id": _derive_anonymous_id(stable_seed),
        "anthropic-device-id": _derive_device_id(stable_seed),
    }


# 无种子时的默认头（向后兼容旧引用）
COMMON_HEADERS = build_headers()
