import base64
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from requests.exceptions import SSLError, ConnectionError as ReqConnError
from requests.utils import dict_from_cookiejar

from account.storage import save_account
from core.config import (
    ACCOUNTS_FILE, OUTLOOK_ACCOUNTS_FILE, BASE_URL, get_proxies_dict, build_headers,
    get_email_service,
    get_moemail_api_key, get_moemail_base_url,
    get_remail_api_key, get_remail_api_url, get_remail_project_id,
    get_remail_product_id, get_remail_mode, get_remail_suffix
)
from core.console import print_log

from .moemail import MoeMailClient
from .remail import RemailClient
from .outlook import OutlookClient, OutlookGraphClient, parse_outlook_line

# 常见美国人名/姓氏，用于生成邮箱前缀
_FIRST_NAMES = [
    "james", "john", "robert", "michael", "william", "david", "richard",
    "joseph", "thomas", "charles", "christopher", "daniel", "matthew",
    "anthony", "mark", "donald", "steven", "paul", "andrew", "joshua",
    "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara",
    "susan", "jessica", "sarah", "karen", "nancy", "lisa", "betty",
    "margaret", "sandra", "ashley", "kimberly", "emily", "donna", "michelle",
]
_LAST_NAMES = [
    "smith", "johnson", "williams", "brown", "jones", "garcia", "miller",
    "davis", "rodriguez", "martinez", "hernandez", "lopez", "gonzalez",
    "wilson", "anderson", "thomas", "taylor", "moore", "jackson", "martin",
    "lee", "perez", "thompson", "white", "harris", "sanchez", "clark",
    "ramirez", "lewis", "robinson", "walker", "young", "allen", "king",
]


def _random_name() -> str:
    """生成类似美国人的邮箱前缀，如 john.smith82、msarah_lee。"""
    first = random.choice(_FIRST_NAMES)
    last = random.choice(_LAST_NAMES)
    sep = random.choice([".", "_", ""])
    num = random.choice(["", str(random.randint(1, 99)),
                         str(random.randint(1970, 2005))])
    return f"{first}{sep}{last}{num}"


def _bare_session(seed=None):
    """注册专用 session：带完整浏览器头，禁用 keep-alive 避免代理断连。

    传入 seed（账号邮箱）时，anonymous-id / device-id 按其哈希派生，
    使每个账号拥有稳定且互不相同的指纹。
    每次调用自动轮询使用下一个代理。
    """
    s = requests.Session()
    s.headers.update(build_headers(seed))
    s.headers.update({"Connection": "close"})
    
    # 轮询获取下一个代理
    proxies = get_proxies_dict()
    if proxies:
        s.proxies.update(proxies)
        # 强制使用代理，禁止 fallback 到直连
        s.trust_env = False
    return s


def _get_exit_ip(proxies=None):
    """通过代理查询出口 IP及类型，返回详细信息dict或None。"""
    try:
        s = requests.Session()
        s.headers.update(build_headers())
        s.headers.update({"Connection": "close"})
        if proxies:
            s.proxies.update(proxies)
            s.trust_env = False
        
        # ip-api.com 免费接口（HTTP），返回 IP + 类型字段
        r = s.get(
            "http://ip-api.com/json",
            params={"fields": "query,country,city,isp,mobile,proxy,hosting"},
            timeout=8,
        )
        d = r.json()
        
        ip = d.get("query", "?")
        country = d.get("country", "?")
        city = d.get("city", "?")
        isp = d.get("isp", "?")

        if d.get("proxy"):
            ip_type = "代理/VPN"
        elif d.get("hosting"):
            ip_type = "数据中心"
        elif d.get("mobile"):
            ip_type = "移动网络"
        else:
            ip_type = "住宅IP"
        
        # 提取代理地址
        proxy_addr = proxies.get("https", "直连") if proxies else "直连"

        return {
            "ip": ip,
            "type": ip_type,
            "country": country,
            "city": city,
            "isp": isp,
            "proxy": proxy_addr,
        }
    except Exception as e:
        return None

_MAX_RETRIES = 5


def _req(s, method, url, max_retries=_MAX_RETRIES, **kwargs):
    """在已有 session 上执行请求，保留 Cookie。SSL 错误时原地重试（urllib3 自动重建 TCP）。"""
    last_err = None
    for attempt in range(max_retries):
        try:
            r = getattr(s, method)(url, timeout=20, **kwargs)
            
            # ===== 检查响应头中的CF标识 =====
            cf_ray = r.headers.get('cf-ray')
            if cf_ray:
                print_log(f"    ℹ️  请求通过Cloudflare (CF-Ray: {cf_ray})")

            # ===== CF验证检测 =====
            if r.status_code == 403:
                # 检查响应内容是否包含CF特征
                response_text = r.text[:500]
                if any(cf_sign in response_text.lower() for cf_sign in [
                    'cloudflare', 'cf-ray', 'cf_clearance', 'turnstile',
                    'just a moment', 'checking your browser'
                ]):
                    print_log("    ⚠️  检测到Cloudflare人机验证!")
                    print_log("    提示: 当前使用requests库无法绕过CF验证")
                    print_log("    建议: 1) 使用住宅代理 2) 降低并发 3) 集成浏览器方案")
                    raise RuntimeError("HTTP 403: Cloudflare人机验证拦截")
                else:
                    raise RuntimeError(f"HTTP 403: {r.text[:100]}")

            if r.status_code == 429:
                wait = 3 * (attempt + 1)
                print_log(f"    [重试 {attempt+1}/{max_retries}] HTTP 429，等待 {wait}s…")
                time.sleep(wait)
                last_err = Exception("HTTP 429")
                continue

            if r.status_code not in (200, 201, 204):
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")

            r.raise_for_status()

            ct = r.headers.get("content-type", "")
            if "json" not in ct:
                m = re.search(r"<title>(.*?)</title>", r.text[:500])
                title = m.group(1) if m else ct
                
                # 检测title中是否有CF标记
                if title and any(cf_sign in title.lower() for cf_sign in [
                    'cloudflare', 'attention required', 'just a moment'
                ]):
                    print_log("    ⚠️  检测到Cloudflare人机验证页面!")
                    print_log(f"    页面标题: {title}")
                    print_log("    提示: 请检查代理质量或考虑使用浏览器方案")
                    raise RuntimeError(f"Cloudflare验证页面: {title}")
                
                raise RuntimeError(f"非 JSON 响应 ({r.status_code}): {title}")

            # 空 body（如 send_magic_link 成功）返回空 dict
            if not r.text.strip():
                return {}
            return r.json()

        except (SSLError, ReqConnError) as e:
            last_err = e
            wait = 2 ** attempt
            print_log(
                f"    [重试 {attempt+1}/{max_retries}] "
                f"{type(e).__name__}，等待 {wait}s…"
            )
            time.sleep(wait)
        except Exception:
            raise

    raise last_err


def _get_login_methods(s, email):
    return _req(s, "get", f"{BASE_URL}/api/auth/login_methods",
                params={"email": email, "source": "claude"})


def _send_magic_link(s, email, utc_offset=-480):
    body = {"utc_offset": utc_offset, "email_address": email,
            "login_intent": None, "locale": "en-US",
            "return_to": None, "source": "claude"}
    _req(s, "post", f"{BASE_URL}/api/auth/send_magic_link", data=json.dumps(body))


def _verify_magic_link(s, email, nonce, encoded_email=None):
    if not encoded_email:
        encoded_email = base64.b64encode(email.encode()).decode()
    body = {
        "credentials": {"method": "nonce", "nonce": nonce,
                        "encoded_email_address": encoded_email},
        "locale": "en-US",
        "source": "claude",
    }
    return _req(s, "post", f"{BASE_URL}/api/auth/verify_magic_link", data=json.dumps(body))


def _serialize_cookies(cookie_jar):
    """遍历 Cookie 条目，避免同名但不同域的 Cookie 触发冲突。"""
    return dict_from_cookiejar(cookie_jar)


def _extract_nonce(text):
    """从邮件内容中提取nonce和encoded_email"""
    # 尝试1: 标准格式 /magic-link#nonce:encoded_email
    m = re.search(r'/magic-link#([0-9a-fA-F]+):([A-Za-z0-9+/=]+)', text)
    if m:
        return m.group(1), m.group(2)
    
    # 尝试2: 带域名的完整URL
    m = re.search(r'claude\.ai/magic-link#([0-9a-fA-F]+):([A-Za-z0-9+/=]+)', text)
    if m:
        return m.group(1), m.group(2)
    
    # 尝试3: 查询参数格式 ?nonce=xxx
    m = re.search(r'[?&]nonce=([0-9a-fA-F]+)', text)
    if m:
        return m.group(1), None
    
    # 尝试4: 更宽松的magic-link匹配（处理URL编码等情况）
    m = re.search(r'magic-link[#/]([0-9a-zA-Z]+)[:\-]([A-Za-z0-9+/=%]+)', text)
    if m:
        return m.group(1), m.group(2)
    
    return None, None


def register_account(accounts_file=ACCOUNTS_FILE):
    """注册单个账号，成功后追加到 accounts_file 并返回记录 dict。"""
    # ── 获取轮询代理 ──────────────────────────────────────────────────────
    current_proxies = get_proxies_dict()
    proxy_info = current_proxies.get("https", "直连") if current_proxies else "直连"
    print_log(f"  [代理] 使用: {proxy_info}")
    
    # ── 步骤 1/7：检查出口 IP ────────────────────────────────────────────
    print_log("  [1/7] 检查出口 IP…")
    ip_info = _get_exit_ip(current_proxies)
    
    if ip_info:
        print_log(f"        出口 IP: {ip_info['ip']}")
        print_log(f"        类型: {ip_info['type']}")
        print_log(f"        位置: {ip_info['country']}, {ip_info['city']}")
        print_log(f"        ISP: {ip_info['isp']}")
    else:
        print_log("        出口 IP: 查询失败")
        ip_info = None

    # ── 步骤 2/7：初始化邮箱服务 ──────────────────────────────────────────
    EMAIL_SERVICE = get_email_service()  # 动态获取当前配置
    print_log(f"  [2/7] 初始化邮箱服务 ({EMAIL_SERVICE})…")
    
    if EMAIL_SERVICE == "remail":
        # 使用 Remail，支持已注册重试
        REMAIL_API_KEY = get_remail_api_key()
        REMAIL_PROJECT_ID = get_remail_project_id()
        REMAIL_PRODUCT_ID = get_remail_product_id()
        
        if not REMAIL_API_KEY or not REMAIL_PROJECT_ID or not REMAIL_PRODUCT_ID:
            raise ValueError(
                "Remail 配置不完整! 请在 .env 中设置:\n"
                "REMAIL_API_KEY, REMAIL_PROJECT_ID, REMAIL_PRODUCT_ID"
            )
        
        mail = RemailClient(
            api_key=REMAIL_API_KEY,
            project_id=REMAIL_PROJECT_ID,
            product_id=REMAIL_PRODUCT_ID,
            api_url=get_remail_api_url(),
            mode=get_remail_mode(),
            suffix=get_remail_suffix()
        )
        print_log(f"        API: {get_remail_api_url()}")
        print_log(f"        项目ID: {REMAIL_PROJECT_ID}")
        print_log(f"        产品ID: {REMAIL_PRODUCT_ID}")
        print_log(f"        模式: {get_remail_mode()}")
        
        # ── 步骤 3/7：生成临时邮箱 (Remail) ──────────────────────────────────
        print_log("  [3/7] 创建临时邮箱 (Remail)…")
        name = _random_name()
        box = mail.create_mailbox(name=name)
        email = box["email"]
        email_id = box["id"]
        print_log(f"        邮箱: {email}")
        print_log(f"        订单号: {email_id}")
        
        s = _bare_session(seed=email)
        
    else:
        # 使用 Moemail (默认)
        mail = MoeMailClient(api_key=get_moemail_api_key(), base_url=get_moemail_base_url())
        
        cfg = mail.get_config()
        raw = cfg.get("emailDomains") or cfg.get("domains") or "moemail.app"
        domains = [x.strip() for x in raw.split(",")] if isinstance(raw, str) else raw
        domain = random.choice(domains)
        print_log(f"        可用域名: {domains}")
        print_log(f"        选用域名: {domain}")
        
        # ── 步骤 3/7：生成临时邮箱 (Moemail) ──────────────────────────────────
        print_log("  [3/7] 生成临时邮箱 (Moemail)…")
        name = _random_name()
        box = mail.generate_email(name=name, expiry_time=3600000, domain=domain)
        email = box["email"]
        email_id = box["id"]
        print_log(f"        邮箱: {email}")
        print_log(f"        邮箱 ID: {email_id}")
        
        s = _bare_session(seed=email)
        
        # ── 步骤 4/7：查询登录方式 ───────────────────────────────────────────
        print_log("  [4/7] 查询 claude.ai 登录方式…")
        methods = _get_login_methods(s, email)
        print_log(f"        可用方式: {methods.get('methods', methods)}")

    # ── 步骤 5/7：发送 magic link ────────────────────────────────────────
    print_log("  [5/7] 发送 magic link 邮件…")
    time.sleep(1)
    _send_magic_link(s, email)
    print_log("        已发送，等待邮件到达…")

    # ── 步骤 6/7：等待邮件并提取 nonce ───────────────────────────────────
    print_log("  [6/7] 轮询邮箱，等待 Anthropic 验证邮件…")
    msg = mail.wait_for_message(email_id, sender_contains="anthropic",
                                timeout=120, interval=3)
    print_log("        收到验证邮件，提取 nonce…")
    
    # 调试：打印邮件内容
    msg_json = json.dumps(msg, ensure_ascii=False)
    print_log(f"        [调试] 邮件内容长度: {len(msg_json)} 字符")
    print_log(f"        [调试] 邮件预览: {msg_json[:300]}...")
    
    nonce, enc_email = _extract_nonce(msg_json)
    if not nonce:
        # 提取失败，打印更多信息
        print_log(f"        [错误] 无法从邮件中提取nonce")
        print_log(f"        [调试] 完整邮件内容:")
        print_log(msg_json[:1000])  # 打印前1000字符
        raise RuntimeError("未能从邮件中提取 nonce")
    print_log(f"        nonce: {nonce}")
    print_log(f"        encoded_email: {enc_email}")

    # ── 步骤 7/7：换取会话并保存 ─────────────────────────────────────────
    print_log("  [7/7] 用 nonce 换取登录会话…")
    data = _verify_magic_link(s, email, nonce, encoded_email=enc_email)
    acct = data.get("account", {})
    mems = acct.get("memberships", [])
    org = mems[0]["organization"] if mems else {}

    record = {
        "email": email,
        "uuid": acct.get("uuid"),
        "email_address": acct.get("email_address") or acct.get("email"),
        "org_uuid": org.get("uuid"),
        "org_name": org.get("name"),
        "cookies": _serialize_cookies(s.cookies),
        "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "ip_info": ip_info,  # 保存完整IP信息
        "health": "healthy",  # 注册成功时自动标记为健康
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),  # 检查时间=注册时间
    }
    print_log(f"        账号 UUID: {record['uuid']}")
    print_log(f"        组织: {record['org_name']}")
    print_log(f"        会话 Cookie: {list(record['cookies'].keys())}")

    save_account(record, accounts_file)
    print_log(f"        已保存到 {accounts_file}")
    print_log(f"  [成功] 注册完成: {email}")
    return record


def register_batch(count, concurrent=1, accounts_file=ACCOUNTS_FILE,
                   on_success=None):
    """批量注册账号。"""
    results = []
    failed = 0

    if concurrent <= 1:
        for i in range(count):
            print_log(f"\n[{i+1}/{count}] 注册中…")
            try:
                account = register_account(accounts_file)
                results.append(account)
                if on_success:
                    on_success(account)
            except Exception as e:
                failed += 1
                print_log(f"  [失败] {e}")
            time.sleep(1)
    else:
        def _task(idx):
            print_log(f"\n[{idx}/{count}] 注册中…")
            return register_account(accounts_file)

        with ThreadPoolExecutor(max_workers=concurrent) as pool:
            futures = {pool.submit(_task, i + 1): i + 1 for i in range(count)}
            for fut in as_completed(futures):
                idx = futures[fut]
                try:
                    account = fut.result()
                    results.append(account)
                    if on_success:
                        on_success(account)
                except Exception as e:
                    failed += 1
                    print_log(f"[{idx}/{count}] 失败: {e}")

    print_log(f"\n[注册] 完成: 成功 {len(results)} 个, 失败 {failed} 个")
    return results


def register_with_outlook(outlook_line, accounts_file=None):
    """
    使用Outlook邮箱注册账号
    
    Args:
        outlook_line: Outlook配置行,格式: 邮箱----密码----ClientID----RefreshToken----imap/graph
        accounts_file: 保存账号的文件路径(默认使用OUTLOOK_ACCOUNTS_FILE)
        
    Returns:
        dict: 账号信息记录
        
    Raises:
        ValueError: 配置格式错误
        RuntimeError: 注册失败
    """
    # 默认保存到outlook_accounts.json
    if accounts_file is None:
        accounts_file = OUTLOOK_ACCOUNTS_FILE
    
    # ── 解析Outlook配置 ────────────────────────────────────────────────
    print_log(f"  [Outlook] 解析配置...")
    try:
        outlook_cfg = parse_outlook_line(outlook_line)
    except ValueError as e:
        print_log(f"  [失败] 配置格式错误: {e}")
        raise
    
    email = outlook_cfg["email"]
    password = outlook_cfg["password"]
    client_id = outlook_cfg["client_id"]
    refresh_token = outlook_cfg["refresh_token"]
    
    print_log(f"        邮箱: {email}")
    print_log(f"        智能模式: 自动选择最佳连接方式")
    
    # ── 获取轮询代理 ──────────────────────────────────────────────────────
    current_proxies = get_proxies_dict()
    proxy_info = current_proxies.get("https", "直连") if current_proxies else "直连"
    print_log(f"  [代理] 使用: {proxy_info}")
    
    # ── 步骤 1/7：检查出口 IP ────────────────────────────────────────────
    print_log("  [1/7] 检查出口 IP…")
    ip_info = _get_exit_ip(current_proxies)
    
    if ip_info:
        print_log(f"        出口 IP: {ip_info['ip']}")
        print_log(f"        类型: {ip_info['type']}")
        print_log(f"        位置: {ip_info['country']}, {ip_info['city']}")
        print_log(f"        ISP: {ip_info['isp']}")
    else:
        print_log("        出口 IP: 查询失败")
        ip_info = None
    
    # ── 步骤 2/7：初始化邮箱客户端(智能重试) ──────────────────────────
    print_log(f"  [2/7] 初始化Outlook客户端(智能模式)…")
    
    mail = None
    connection_error = None
    
    # 策略1: 如果有ClientID和RefreshToken,优先尝试Graph API
    if client_id and refresh_token:
        print_log(f"        尝试Graph API模式...")
        try:
            mail = OutlookGraphClient(email, client_id, refresh_token)
            mail.connect()
            print_log(f"        ✓ Graph API连接成功")
            mode = "graph"
        except Exception as e:
            print_log(f"        ✗ Graph API失败: {e}")
            connection_error = e
    
    # 策略2: Graph失败或没有token,尝试IMAP
    if mail is None and password:
        print_log(f"        尝试IMAP模式...")
        try:
            mail = OutlookClient(email, password)
            mail.connect()
            print_log(f"        ✓ IMAP连接成功")
            mode = "imap"
        except Exception as e:
            print_log(f"        ✗ IMAP失败: {e}")
            connection_error = e
    
    # 如果两种方式都失败了
    if mail is None:
        print_log(f"  [失败] 所有连接方式都失败")
        raise RuntimeError(f"无法连接到Outlook邮箱: {connection_error}")
    
    # ── 创建session ─────────────────────────────────────────────────────
    s = _bare_session(seed=email)
    
    # ── 步骤 3/7：查询登录方式并检测账号状态 ─────────────────────────
    print_log("  [3/7] 查询 claude.ai 登录方式…")
    try:
        methods = _get_login_methods(s, email)
        available_methods = methods.get('methods', [])
        print_log(f"        可用方式: {available_methods}")
        
        # 注意：Claude API对所有邮箱都返回相同的methods列表
        # 因此无法通过此API判断邮箱是否已注册
        # 策略：Outlook邮箱应由用户提前筛选，确保未注册
        
    except Exception as e:
        mail.disconnect()
        print_log(f"  [失败] 查询登录方式失败: {e}")
        raise
    
    # ── 步骤 4/7：发送 magic link (仅新账号) ────────────────────────────
    print_log(f"  [4/7] 发送 magic link 邮件 (新账号注册)…")
    try:
        time.sleep(1)
        _send_magic_link(s, email)
        print_log(f"        已发送，等待邮件到达…")
    except Exception as e:
        mail.disconnect()
        print_log(f"  [失败] 发送magic link失败: {e}")
        raise
    
    # ── 步骤 5/7：等待邮件并提取 nonce ───────────────────────────────────
    print_log(f"  [5/7] 轮询Outlook邮箱({mode.upper()}模式)，等待 Anthropic 验证邮件…")
    try:
        msg = mail.wait_for_message(sender_contains="anthropic", 
                                    timeout=120, interval=5)
        print_log("        收到验证邮件，提取 nonce…")
        
        # 调试：打印邮件内容
        msg_json = json.dumps(msg, ensure_ascii=False)
        print_log(f"        [调试] 邮件内容长度: {len(msg_json)} 字符")
        print_log(f"        [调试] 邮件预览: {msg_json[:300]}...")
        
        nonce, enc_email = _extract_nonce(msg_json)
        
        if not nonce:
            # 提取失败，打印更多信息
            print_log(f"        [错误] 无法从邮件中提取nonce")
            print_log(f"        [调试] 完整邮件内容:")
            print_log(msg_json[:1000])  # 打印前1000字符
            raise RuntimeError("未能从邮件中提取 nonce")
        
        print_log(f"        nonce: {nonce}")
        print_log(f"        encoded_email: {enc_email}")
    except TimeoutError as e:
        mail.disconnect()
        print_log(f"  [失败] {e}")
        raise
    except Exception as e:
        mail.disconnect()
        print_log(f"  [失败] 获取验证邮件失败: {e}")
        raise
    finally:
        # 关闭连接
        mail.disconnect()
    
    # ── 步骤 6/7：换取会话并保存 ─────────────────────────────────────────
    print_log(f"  [6/7] 用 nonce 换取注册会话…")
    try:
        data = _verify_magic_link(s, email, nonce, encoded_email=enc_email)
        acct = data.get("account", {})
        mems = acct.get("memberships", [])
        org = mems[0]["organization"] if mems else {}
        
        record = {
            "email": email,
            "password": password,
            "uuid": acct.get("uuid"),
            "email_address": acct.get("email_address") or acct.get("email"),
            "org_uuid": org.get("uuid"),
            "org_name": org.get("name"),
            "cookies": _serialize_cookies(s.cookies),
            "saved_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "ip_info": ip_info,
            "health": "healthy",
            "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "outlook_mode": mode,  # 标记使用的模式
            "outlook_client_id": client_id,  # 保存ClientID
            "outlook_refresh_token": refresh_token,  # 保存RefreshToken
            "registration_mode": "outlook",
        }
        
        print_log(f"        账号 UUID: {record['uuid']}")
        print_log(f"        组织: {record['org_name']}")
        print_log(f"        会话 Cookie: {list(record['cookies'].keys())}")
        print_log(f"        账号类型: 新账号(注册成功)")
        
        # ── 步骤 7/7：验证账号额度 ────────────────────────────────────────
        print_log(f"  [7/7] 验证账号额度和订阅状态…")
        try:
            usage_info = check_usage(record)
            record.update(usage_info)
            print_log(f"        订阅: {usage_info.get('subscription', 'N/A')}")
            print_log(f"        额度: {usage_info.get('credit_used', 0)}/{usage_info.get('credit_limit', 0)}")
        except Exception as e:
            print_log(f"        ⚠️  额度查询失败: {e}")
        
        save_account(record, accounts_file)
        print_log(f"        已保存到 {accounts_file}")
        print_log(f"  [成功] Outlook 注册完成: {email}")
        
        return record
    except Exception as e:
        print_log(f"  [失败] 换取会话失败: {e}")
        raise


def register_batch_outlook(outlook_lines, accounts_file=None, on_success=None):
    """
    批量使用Outlook邮箱注册账号
    
    注意：Outlook使用IMAP/Graph API连接，有严格的频率限制
    因此强制单线程执行，避免账号被封
    
    Args:
        outlook_lines: Outlook配置行列表
        accounts_file: 保存账号的文件路径(默认使用OUTLOOK_ACCOUNTS_FILE)
        on_success: 成功回调函数
        
    Returns:
        list: 成功注册的账号列表
    """
    # 默认保存到outlook_accounts.json
    if accounts_file is None:
        accounts_file = OUTLOOK_ACCOUNTS_FILE
    
    results = []
    failed = 0
    total = len(outlook_lines)
    
    # 强制单线程，避免IMAP频率限制
    for i, line in enumerate(outlook_lines):
        print_log(f"\n[{i+1}/{total}] Outlook注册中…")
        try:
            account = register_with_outlook(line, accounts_file)
            results.append(account)
            if on_success:
                on_success(account)
        except Exception as e:
            failed += 1
            print_log(f"  [失败] {e}")
        
        # IMAP/Graph API请求间隔，避免频率限制
        time.sleep(3)
    
    print_log(f"\n[Outlook注册] 完成: 成功 {len(results)} 个, 失败 {failed} 个")
    return results
