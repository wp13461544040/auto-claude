"""
Outlook 邮箱验证码取件模块
支持 IMAP (XOAUTH2) 和 Microsoft Graph API 两种模式

文档规范:
- IMAP: 通过 outlook.office365.com:993 + XOAUTH2 认证
- Graph: 通过 /me/mailFolders/inbox/messages API
- Token 刷新: 自动处理 access_token 过期
- 时间过滤: 只检测最近 2 分钟内的邮件
- 验证码提取: 正则 r'\\b(\\d{6})\\b'
"""

import imaplib
import time
import re
import base64
import requests
from datetime import datetime, timedelta
from email import message_from_bytes
from email.header import decode_header

from core.config import get_proxies_dict
from core.console import print_log


class OutlookOTPError(Exception):
    """Outlook 取件专用异常"""
    pass


class OutlookNotConnectedError(OutlookOTPError):
    """Outlook 后端未就绪异常 (不需要刷新 token)"""
    pass


def refresh_outlook_token(email, client_id, refresh_token, mode="imap", proxy=None, scope_override=None, tenant="consumers"):
    """
    刷新 Outlook Access Token
    
    Args:
        email: 邮箱地址
        client_id: Azure 应用 ClientID
        refresh_token: 永久刷新令牌
        mode: "imap" 或 "graph"
        proxy: 代理地址 (可选)
        scope_override: 手动指定 scope (可选,用于容错)
        tenant: 租户类型 (common/consumers/organizations,默认 common)
    
    Returns:
        str: access_token (有效期 1 小时)
    
    Raises:
        OutlookOTPError: 刷新失败
    """
    # 租户选择 (参考 Go 实现,默认 consumers):
    # - consumers: 个人 Microsoft 账户 (推荐,卡密标准)
    # - common: 适用于个人和组织账户
    # - organizations: 仅组织账户
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    
    # 根据模式选择 scope (参考 Go 实现)
    if scope_override:
        scope = scope_override
    elif mode == "imap":
        # IMAP 模式: 使用 IMAP.AccessAsUser.All (参考 Go 源码)
        scope = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"
    else:  # graph
        # Graph API 模式: 使用 Mail.Read
        scope = "https://graph.microsoft.com/Mail.Read offline_access"
    
    data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": scope
    }
    
    proxies = get_proxies_dict(proxy) if proxy else None
    
    def _try_refresh(use_proxy=True):
        """尝试刷新 token"""
        try:
            prox = proxies if use_proxy else None
            resp = requests.post(token_url, data=data, proxies=prox, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            
            if "access_token" not in result:
                raise OutlookOTPError(f"Token响应缺少access_token: {result}")
            
            print_log(f"[Outlook] Token刷新成功 ({mode} mode, scope={scope.split()[0]})")
            return result["access_token"]
        except requests.HTTPError as e:
            # 400 错误可能是 scope 不对
            if e.response.status_code == 400:
                error_data = e.response.json() if e.response.content else {}
                error_desc = error_data.get("error_description", "")
                raise OutlookOTPError(f"Token刷新失败(400): {error_desc}")
            raise
    
    try:
        # 优先使用代理
        return _try_refresh(use_proxy=True)
    
    except OutlookOTPError as e:
        # 代理失败时自动降级直连
        if proxies:
            print_log(f"[Outlook] 代理失败,尝试直连")
            try:
                return _try_refresh(use_proxy=False)
            except Exception as e2:
                raise OutlookOTPError(f"Token刷新失败(代理+直连): {e2}")
        else:
            raise
    
    except requests.RequestException as e:
        # 代理失败时自动降级直连
        if proxies:
            print_log(f"[Outlook] 代理失败,尝试直连: {e}")
            try:
                resp = requests.post(token_url, data=data, timeout=15)
                resp.raise_for_status()
                result = resp.json()
                return result["access_token"]
            except Exception as e2:
                raise OutlookOTPError(f"Token刷新失败(代理+直连): {e2}")
        else:
            raise OutlookOTPError(f"Token刷新失败: {e}")


class OutlookIMAPOTPClient:
    """
    Outlook IMAP 验证码取件客户端 (XOAUTH2 认证)
    """
    
    def __init__(self, email, client_id, refresh_token, proxy=None, tenant="consumers"):
        self.email = email
        self.client_id = client_id
        self.refresh_token = refresh_token
        self.proxy = proxy
        self.tenant = tenant  # 租户类型
        
        self.host = "outlook.office365.com"
        self.port = 993
        self.conn = None
        self.access_token = None
    
    def _refresh_token(self):
        """刷新 access token"""
        self.access_token = refresh_outlook_token(
            self.email, 
            self.client_id, 
            self.refresh_token, 
            mode="imap",
            proxy=self.proxy,
            tenant=self.tenant
        )
    
    def _xoauth2_string(self):
        """生成 XOAUTH2 认证字符串"""
        auth = f"user={self.email}\x01auth=Bearer {self.access_token}\x01\x01"
        return base64.b64encode(auth.encode()).decode()
    
    def connect(self):
        """
        连接到 Outlook IMAP 服务器并认证
        
        Raises:
            OutlookNotConnectedError: 后端未就绪
            OutlookOTPError: 其他连接/认证错误
        """
        # 关闭旧连接
        self.close()
        
        # 刷新 token
        if not self.access_token:
            self._refresh_token()
        
        try:
            # 建立 TLS 连接
            self.conn = imaplib.IMAP4_SSL(self.host, self.port, timeout=30)
            
            # XOAUTH2 认证
            auth_string = self._xoauth2_string()
            typ, data = self.conn.authenticate("XOAUTH2", lambda x: auth_string)
            
            if typ != "OK":
                err_msg = data[0].decode() if data else "认证失败"
                
                # 检测 "not connected" 错误 (Outlook 后端未就绪)
                if "not connected" in err_msg.lower():
                    raise OutlookNotConnectedError(err_msg)
                
                raise OutlookOTPError(f"XOAUTH2认证失败: {err_msg}")
            
            print_log(f"[Outlook IMAP] 连接成功: {self.email}")
        
        except OutlookNotConnectedError:
            raise  # 直接抛出,不重试 token
        except imaplib.IMAP4.error as e:
            # IMAP 协议错误
            raise OutlookOTPError(f"IMAP连接失败: {e}")
        except Exception as e:
            # 网络错误等
            raise OutlookOTPError(f"连接异常: {e}")
    
    def close(self):
        """关闭连接"""
        if self.conn:
            try:
                self.conn.logout()
            except:
                pass
            finally:
                self.conn = None
    
    def get_inbox_count(self):
        """
        获取收件箱邮件总数
        
        Returns:
            int: 邮件数量
        """
        if not self.conn:
            self.connect()
        
        typ, data = self.conn.select("INBOX", readonly=True)
        if typ != "OK":
            raise OutlookOTPError(f"SELECT INBOX失败: {data}")
        
        count = int(data[0].decode())
        print_log(f"[Outlook IMAP] 收件箱邮件数: {count}")
        return count
    
    def _decode_header(self, header_value):
        """解码邮件头"""
        if not header_value:
            return ""
        
        decoded = decode_header(header_value)
        result = []
        for content, charset in decoded:
            if isinstance(content, bytes):
                result.append(content.decode(charset or "utf-8", errors="ignore"))
            else:
                result.append(content)
        return "".join(result)
    
    def _is_recent_email(self, date_header, minutes=2):
        """
        检查邮件是否在最近 N 分钟内
        
        Args:
            date_header: Date 头字符串
            minutes: 时间窗口(分钟)
        
        Returns:
            bool: 是否在时间窗口内
        """
        if not date_header:
            return False
        
        try:
            # 解析 Date 头 (格式: "Mon, 1 Jan 2024 12:34:56 +0000")
            from email.utils import parsedate_to_datetime
            msg_time = parsedate_to_datetime(date_header)
            
            # 时区感知的当前时间
            now = datetime.now(msg_time.tzinfo)
            threshold = now - timedelta(minutes=minutes)
            
            return msg_time >= threshold
        except Exception as e:
            print_log(f"[Outlook IMAP] 时间解析失败: {date_header} - {e}")
            return True  # 解析失败时保守处理,认为是最近邮件
    
    def wait_for_otp(self, timeout=120, interval=5, before_count=None):
        """
        等待验证码邮件到达
        
        Args:
            timeout: 超时时间(秒)
            interval: 轮询间隔(秒)
            before_count: 之前的邮件数量(用于跳过历史邮件,可选)
        
        Returns:
            str: 验证码 (6位数字)
        
        Raises:
            TimeoutError: 超时未收到验证码
            OutlookOTPError: 连接/认证错误
        """
        deadline = time.time() + timeout
        code_regex = re.compile(r'\b(\d{6})\b')
        attempt = 0
        max_select_fails = 3
        select_fail_count = 0
        
        print_log(f"[Outlook IMAP] 开始等待验证码 (超时{timeout}s,间隔{interval}s)")
        
        while time.time() < deadline:
            attempt += 1
            
            try:
                # 每次轮询都重新连接 (避免连接超时)
                self.connect()
                
                # 获取当前邮件总数
                current_count = self.get_inbox_count()
                
                if before_count is not None and current_count <= before_count:
                    print_log(f"[Outlook IMAP] 尚无新邮件 ({current_count}/{before_count})")
                    time.sleep(interval)
                    continue
                
                # 从最新邮件往前扫描 (最多 10 封)
                start = max(1, current_count - 9)
                end = current_count
                
                print_log(f"[Outlook IMAP] 扫描邮件 {start}-{end}")
                
                for msg_num in range(end, start - 1, -1):
                    try:
                        # 先获取 Date 头做时间过滤
                        typ, header_data = self.conn.fetch(
                            str(msg_num), 
                            "(BODY.PEEK[HEADER.FIELDS (DATE)])"
                        )
                        
                        if typ != "OK":
                            continue
                        
                        # 解析 Date 头
                        msg = message_from_bytes(header_data[0][1])
                        date_header = msg.get("Date", "")
                        
                        # 只处理最近 2 分钟内的邮件
                        if not self._is_recent_email(date_header, minutes=2):
                            print_log(f"[Outlook IMAP] 邮件{msg_num}过旧,跳过")
                            continue
                        
                        # 获取正文
                        typ, body_data = self.conn.fetch(
                            str(msg_num), 
                            "(BODY.PEEK[TEXT])"
                        )
                        
                        if typ != "OK":
                            continue
                        
                        # 解码正文
                        body_raw = body_data[0][1]
                        if isinstance(body_raw, bytes):
                            # 尝试多种编码
                            body_text = None
                            for encoding in ["utf-8", "gbk", "latin-1"]:
                                try:
                                    body_text = body_raw.decode(encoding, errors="ignore")
                                    break
                                except:
                                    continue
                            
                            if not body_text:
                                body_text = body_raw.decode("utf-8", errors="replace")
                        else:
                            body_text = str(body_raw)
                        
                        # 提取验证码
                        match = code_regex.search(body_text)
                        if match:
                            code = match.group(1)
                            print_log(f"[Outlook IMAP] 找到验证码: {code}")
                            self.close()
                            return code
                    
                    except Exception as e:
                        print_log(f"[Outlook IMAP] 处理邮件{msg_num}失败: {e}")
                        continue
                
                # SELECT 失败计数器 (防止无限循环)
                select_fail_count = 0
            
            except OutlookNotConnectedError as e:
                # 后端未就绪,等待后重连
                print_log(f"[Outlook IMAP] 后端未就绪,等待重连: {e}")
                time.sleep(interval)
                continue
            
            except OutlookOTPError as e:
                # SELECT 连续失败多次时终止
                if "SELECT" in str(e):
                    select_fail_count += 1
                    if select_fail_count >= max_select_fails:
                        raise OutlookOTPError(f"SELECT连续失败{select_fail_count}次,终止等待")
                
                print_log(f"[Outlook IMAP] 轮询失败: {e}")
                
                # 认证失败时刷新 token
                if "认证" in str(e) or "auth" in str(e).lower():
                    print_log("[Outlook IMAP] 认证失败,刷新token重试")
                    self.access_token = None  # 强制刷新
                
                time.sleep(interval)
                continue
            
            except Exception as e:
                print_log(f"[Outlook IMAP] 未知错误: {e}")
                time.sleep(interval)
                continue
            
            # 每 5 次轮询才打印一次 (减少日志)
            if attempt % 5 == 0:
                remaining = int(deadline - time.time())
                print_log(f"[Outlook IMAP] 第{attempt}次轮询,剩余{remaining}s")
            
            time.sleep(interval)
        
        # 超时
        self.close()
        raise TimeoutError(f"{timeout}s内未收到验证码")
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class OutlookGraphOTPClient:
    """
    Outlook Graph API 验证码取件客户端
    """
    
    def __init__(self, email, client_id, refresh_token, proxy=None, tenant="consumers"):
        self.email = email
        self.client_id = client_id
        self.refresh_token = refresh_token
        self.proxy = proxy
        self.tenant = tenant  # 租户类型
        
        self.graph_url = "https://graph.microsoft.com/v1.0"
        self.access_token = None
    
    def _refresh_token(self):
        """刷新 access token"""
        self.access_token = refresh_outlook_token(
            self.email, 
            self.client_id, 
            self.refresh_token, 
            mode="graph",
            proxy=self.proxy,
            tenant=self.tenant
        )
    
    def _get_messages(self, minutes=2, limit=20):
        """
        获取最近 N 分钟内的邮件
        
        Args:
            minutes: 时间窗口(分钟)
            limit: 最多返回邮件数
        
        Returns:
            list: 邮件列表
        """
        if not self.access_token:
            self._refresh_token()
        
        # 计算时间过滤条件
        threshold = datetime.utcnow() - timedelta(minutes=minutes)
        filter_time = threshold.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        url = f"{self.graph_url}/me/mailFolders/inbox/messages"
        params = {
            "$filter": f"receivedDateTime ge {filter_time}",
            "$orderby": "receivedDateTime desc",
            "$top": limit
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Prefer": "outlook.body-content-type=\"text\""
        }
        
        proxies = get_proxies_dict(self.proxy)
        
        try:
            resp = requests.get(url, headers=headers, params=params, proxies=proxies, timeout=15)
            resp.raise_for_status()
            result = resp.json()
            
            return result.get("value", [])
        
        except requests.RequestException as e:
            # 代理失败时降级直连
            if proxies:
                print_log(f"[Outlook Graph] 代理失败,尝试直连: {e}")
                try:
                    resp = requests.get(url, headers=headers, params=params, timeout=15)
                    resp.raise_for_status()
                    return resp.json().get("value", [])
                except Exception as e2:
                    raise OutlookOTPError(f"Graph API调用失败(代理+直连): {e2}")
            else:
                raise OutlookOTPError(f"Graph API调用失败: {e}")
    
    def wait_for_otp(self, timeout=120, interval=5):
        """
        等待验证码邮件到达
        
        Args:
            timeout: 超时时间(秒)
            interval: 轮询间隔(秒)
        
        Returns:
            str: 验证码 (6位数字)
        
        Raises:
            TimeoutError: 超时未收到验证码
            OutlookOTPError: API调用错误
        """
        deadline = time.time() + timeout
        code_regex = re.compile(r'\b(\d{6})\b')
        seen_ids = set()
        attempt = 0
        
        print_log(f"[Outlook Graph] 开始等待验证码 (超时{timeout}s,间隔{interval}s)")
        
        while time.time() < deadline:
            attempt += 1
            
            try:
                # 获取最近 2 分钟内的邮件
                messages = self._get_messages(minutes=2, limit=20)
                
                print_log(f"[Outlook Graph] 拉取到{len(messages)}封最近邮件")
                
                for msg in messages:
                    msg_id = msg.get("id")
                    if msg_id in seen_ids:
                        continue
                    seen_ids.add(msg_id)
                    
                    # 在多个字段中搜索验证码
                    search_texts = [
                        msg.get("subject", ""),
                        msg.get("bodyPreview", ""),
                        msg.get("body", {}).get("content", "")
                    ]
                    
                    for text in search_texts:
                        match = code_regex.search(text)
                        if match:
                            code = match.group(1)
                            print_log(f"[Outlook Graph] 找到验证码: {code}")
                            return code
            
            except OutlookOTPError as e:
                print_log(f"[Outlook Graph] 轮询失败: {e}")
                
                # 认证失败时刷新 token
                if "401" in str(e) or "auth" in str(e).lower():
                    print_log("[Outlook Graph] 认证失败,刷新token重试")
                    self.access_token = None
                
                time.sleep(interval)
                continue
            
            except Exception as e:
                print_log(f"[Outlook Graph] 未知错误: {e}")
                time.sleep(interval)
                continue
            
            # 每 5 次轮询才打印一次
            if attempt % 5 == 0:
                remaining = int(deadline - time.time())
                print_log(f"[Outlook Graph] 第{attempt}次轮询,剩余{remaining}s")
            
            time.sleep(interval)
        
        # 超时
        raise TimeoutError(f"{timeout}s内未收到验证码")


def wait_for_outlook_otp(email, client_id, refresh_token, mode="imap", 
                         timeout=120, interval=5, before_count=None, proxy=None, tenant="consumers"):
    """
    统一的 Outlook 验证码等待接口
    
    Args:
        email: 邮箱地址
        client_id: Azure ClientID
        refresh_token: 永久刷新令牌
        mode: "imap" 或 "graph"
        timeout: 超时时间(秒)
        interval: 轮询间隔(秒)
        before_count: 之前的邮件数(仅 IMAP 模式)
        proxy: 代理地址(可选)
        tenant: 租户类型(consumers/common/organizations,默认 consumers)
    
    Returns:
        str: 验证码
    
    Raises:
        TimeoutError: 超时
        OutlookOTPError: 其他错误
    """
    if mode == "graph":
        client = OutlookGraphOTPClient(email, client_id, refresh_token, proxy, tenant)
        return client.wait_for_otp(timeout, interval)
    else:  # imap
        client = OutlookIMAPOTPClient(email, client_id, refresh_token, proxy, tenant)
        return client.wait_for_otp(timeout, interval, before_count)


# 向后兼容的快捷函数
def get_outlook_inbox_count(email, client_id, refresh_token, proxy=None, tenant="consumers"):
    """获取 Outlook 收件箱邮件数量 (IMAP)"""
    client = OutlookIMAPOTPClient(email, client_id, refresh_token, proxy, tenant)
    with client:
        return client.get_inbox_count()
