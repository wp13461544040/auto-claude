import time
import re
import uuid
import requests
from requests.exceptions import SSLError, ConnectionError as ConnError

_MAX_RETRIES = 4


def _request(s, method, url, **kwargs):
    """带重试的HTTP请求"""
    for attempt in range(_MAX_RETRIES):
        try:
            r = getattr(s, method)(url, timeout=15, **kwargs)
            r.raise_for_status()
            return r.json()
        except (SSLError, ConnError):
            if attempt < _MAX_RETRIES - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise


class RemailClient:
    """Remail 临时邮箱客户端,支持接包模式和购买模式"""
    
    def __init__(self, api_key, project_id, product_id, 
                 api_url="https://remail.aishop6.com",
                 mode="package", suffix=""):
        """
        初始化 Remail 客户端
        
        Args:
            api_key: API密钥 (格式: rk-xxx)
            project_id: 项目ID
            product_id: 产品ID
            api_url: API地址
            mode: 服务模式, package(接包) 或 purchase(购买)
            suffix: 邮箱后缀(可选,如 com.cn)
        """
        self.api_key = api_key
        self.project_id = project_id
        self.product_id = product_id
        self.base = api_url.rstrip("/")
        self.mode = mode
        self.suffix = suffix
        
        # 创建session,直连不走代理
        self.s = requests.Session()
        self.s.trust_env = False
        self.s.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Python-ClaudeX/1.0"
        })
        
        # 邮箱相关信息
        self.email = None
        self.token = None
        self.order_no = None
        self.created_at = None
    
    def create_mailbox(self, name="test"):
        """
        创建邮箱(下单)
        
        Args:
            name: 邮箱前缀名称(被项目ID/产品ID覆盖,实际无效)
            
        Returns:
            dict: 包含email, token, order_no的字典
        """
        url = f"{self.base}/v1/open/orders"
        params = {
            "serviceMode": "code" if self.mode == "package" else "purchase",
            "supply": "private_first"
        }
        data = {
            "projectId": self.project_id,
            "productId": self.product_id,
            "emailSuffix": self.suffix
        }
        
        # 生成幂等性key (每次请求都要唯一)
        idempotency_key = str(uuid.uuid4())
        headers = {"Idempotency-Key": idempotency_key}
        
        result = _request(self.s, "post", url, json=data, params=params, headers=headers)
        
        # 保存邮箱信息
        self.email = result["deliveryEmail"]
        self.token = result["serviceToken"]
        self.order_no = result["orderNo"]
        self.created_at = time.time()
        
        return {
            "email": self.email,
            "token": self.token,
            "orderNo": self.order_no,
            "id": self.order_no  # 兼容moemail的id字段
        }
    
    def list_messages(self):
        """
        获取邮件列表
        
        Returns:
            dict: 包含messages列表的字典
        """
        if not self.email or not self.token:
            raise ValueError("邮箱未创建,请先调用create_mailbox()")
        
        url = f"{self.base}/v1/pickup"
        params = {
            "email": self.email,
            "token": self.token
        }
        
        try:
            result = _request(self.s, "get", url, params=params)
        except requests.exceptions.HTTPError as e:
            # 401可能是token失效,尝试刷新
            if e.response.status_code == 401:
                self._refresh_token()
                result = _request(self.s, "get", url, params=params)
            else:
                raise
        
        # 转换为moemail兼容格式
        items = result.get("items", [])
        messages = []
        for item in items:
            messages.append({
                "id": item.get("id"),
                "from_address": item.get("sender", ""),
                "from": item.get("sender", ""),
                "subject": item.get("subject", ""),
                "received_at": item.get("receivedAt", ""),
                "_full_item": item
            })
        
        return {"messages": messages}
    
    def get_message(self, message_id):
        """
        获取单个邮件详情
        
        Args:
            message_id: 邮件ID
            
        Returns:
            dict: 邮件详情
        """
        result = self.list_messages()
        for msg in result.get("messages", []):
            if msg["id"] == message_id:
                full = msg["_full_item"]
                return {
                    "id": full.get("id"),
                    "from_address": full.get("sender", ""),
                    "from": full.get("sender", ""),
                    "recipient": full.get("recipient", ""),
                    "subject": full.get("subject", ""),
                    "bodyPreview": full.get("bodyPreview", ""),
                    "body": full.get("bodyPreview", ""),
                    "text": full.get("bodyPreview", ""),
                    "receivedAt": full.get("receivedAt", ""),
                    "verificationCode": full.get("verificationCode", "")
                }
        
        raise ValueError(f"未找到邮件ID: {message_id}")
    
    def wait_for_message(self, email_id=None, sender_contains=None, timeout=120, interval=3):
        """
        等待邮件到达
        
        Args:
            email_id: 邮箱ID(兼容moemail,remail中忽略)
            sender_contains: 发件人包含的字符串(不区分大小写)
            timeout: 超时时间(秒)
            interval: 轮询间隔(秒)
            
        Returns:
            dict: 邮件详情
        """
        if not self.email or not self.token:
            raise ValueError("邮箱未创建,请先调用create_mailbox()")
        
        deadline = time.time() + timeout
        seen = set()
        
        # 验证码提取正则(兼容中英文)
        code_pattern = re.compile(
            r'(?i)(?:验证码|code|OTP|security code is)[：:\s]*([A-Z0-9]{6,8})'
        )
        
        while time.time() < deadline:
            try:
                result = self.list_messages()
                
                for msg in result.get("messages", []):
                    mid = msg.get("id")
                    if mid in seen:
                        continue
                    seen.add(mid)
                    
                    # 检查发件人
                    frm = msg.get("from_address") or msg.get("from") or ""
                    if sender_contains and sender_contains.lower() not in frm.lower():
                        continue
                    
                    # 找到匹配的邮件,获取完整信息
                    full_msg = self.get_message(mid)
                    
                    # 尝试提取验证码(优先使用API提取的)
                    if full_msg.get("verificationCode"):
                        full_msg["_extracted_code"] = full_msg["verificationCode"]
                    else:
                        # 从主题和正文中提取
                        for text in [full_msg.get("subject", ""), 
                                    full_msg.get("bodyPreview", ""),
                                    full_msg.get("text", "")]:
                            match = code_pattern.search(text)
                            if match:
                                full_msg["_extracted_code"] = match.group(1)
                                break
                    
                    return full_msg
                
            except Exception as e:
                # 查询失败不中断,继续重试
                pass
            
            time.sleep(interval)
        
        raise TimeoutError(f"{timeout}s 内未等到邮件")
    
    def _refresh_token(self):
        """刷新token(通过查询订单详情)"""
        if not self.order_no:
            raise ValueError("无订单号,无法刷新token")
        
        url = f"{self.base}/v1/open/orders/{self.order_no}"
        result = _request(self.s, "get", url)
        
        self.token = result["serviceToken"]
        self.email = result["deliveryEmail"]
        
        return self.token
    
    def get_projects(self, offset=0, limit=100):
        """
        查询项目列表(用于配置和调试)
        
        Returns:
            dict: 项目列表
        """
        url = f"{self.base}/v1/open/projects"
        params = {"offset": offset, "limit": limit}
        return _request(self.s, "get", url, params=params)


