"""
Outlook邮箱客户端 - 支持IMAP和Microsoft Graph API两种模式
格式: 邮箱----密码----ClientID----RefreshToken----imap/graph
"""
import time
import re
import imaplib
import email
import requests
from email.header import decode_header


class OutlookGraphClient:
    """Outlook Graph API客户端"""
    
    def __init__(self, email_address, client_id, refresh_token):
        """
        初始化Graph API客户端
        
        Args:
            email_address: 邮箱地址
            client_id: Azure应用ClientID
            refresh_token: RefreshToken
        """
        self.email_address = email_address
        self.client_id = client_id
        self.refresh_token = refresh_token
        self.access_token = None
        
        # Graph API配置 (参考 Go 实现)
        self.token_url = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
        self.graph_url = "https://graph.microsoft.com/v1.0"
    
    def _get_access_token(self):
        """用RefreshToken获取AccessToken"""
        data = {
            'client_id': self.client_id,
            'refresh_token': self.refresh_token,
            'grant_type': 'refresh_token',
            # Graph API 使用 Mail.Read (参考 Go 源码)
            'scope': 'https://graph.microsoft.com/Mail.Read offline_access'
        }
        
        try:
            r = requests.post(self.token_url, data=data, timeout=15)
            r.raise_for_status()
            result = r.json()
            self.access_token = result['access_token']
            return self.access_token
        except Exception as e:
            raise ConnectionError(f"获取AccessToken失败: {e}")
    
    def connect(self):
        """连接(获取token)"""
        self._get_access_token()
        return True
    
    def disconnect(self):
        """断开连接(无操作)"""
        pass
    
    def list_messages(self, folder="Inbox", limit=10):
        """
        获取邮件列表
        
        Args:
            folder: 文件夹名(默认Inbox)
            limit: 最多返回邮件数
            
        Returns:
            list: 邮件列表
        """
        if not self.access_token:
            self.connect()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.graph_url}/me/mailFolders/{folder}/messages"
        params = {'$top': limit, '$orderby': 'receivedDateTime DESC'}
        
        try:
            r = requests.get(url, headers=headers, params=params, timeout=15)
            r.raise_for_status()
            result = r.json()
            
            messages = []
            for msg in result.get('value', []):
                messages.append({
                    'id': msg.get('id'),
                    'from_address': msg.get('from', {}).get('emailAddress', {}).get('address', ''),
                    'from': msg.get('from', {}).get('emailAddress', {}).get('address', ''),
                    'subject': msg.get('subject', ''),
                    'received_at': msg.get('receivedDateTime', ''),
                    '_graph_msg': msg
                })
            
            return messages
        except Exception as e:
            raise RuntimeError(f"获取邮件列表失败: {e}")
    
    def get_message(self, message_id):
        """
        获取单个邮件详情
        
        Args:
            message_id: 邮件ID
            
        Returns:
            dict: 邮件详情
        """
        if not self.access_token:
            self.connect()
        
        headers = {'Authorization': f'Bearer {self.access_token}'}
        url = f"{self.graph_url}/me/messages/{message_id}"
        
        try:
            r = requests.get(url, headers=headers, timeout=15)
            r.raise_for_status()
            msg = r.json()
            
            # 保留原始HTML内容，不要删除标签（链接在标签里）
            body_content = msg.get('body', {}).get('content', '')
            body_type = msg.get('body', {}).get('contentType', 'text')
            
            # 如果是HTML，保留原始HTML（包含链接）
            if body_type == 'html':
                body = body_content  # 保留HTML
                # 同时生成一个纯文本版本（用于兼容）
                text_only = re.sub(r'<[^>]+>', ' ', body_content)
            else:
                body = body_content
                text_only = body_content
            
            return {
                'id': msg.get('id'),
                'from_address': msg.get('from', {}).get('emailAddress', {}).get('address', ''),
                'from': msg.get('from', {}).get('emailAddress', {}).get('address', ''),
                'subject': msg.get('subject', ''),
                'received_at': msg.get('receivedDateTime', ''),
                'body': body,  # 原始内容（HTML或文本）
                'text': text_only,  # 纯文本（无标签）
                'html': body_content if body_type == 'html' else '',  # HTML原文
            }
        except Exception as e:
            raise RuntimeError(f"获取邮件失败: {e}")
    
    def wait_for_message(self, sender_contains=None, timeout=120, interval=5):
        """等待邮件到达"""
        deadline = time.time() + timeout
        seen = set()
        
        code_pattern = re.compile(
            r'(?i)(?:验证码|code|OTP|security code is)[：:\s]*([A-Z0-9]{6,8})'
        )
        
        while time.time() < deadline:
            try:
                messages = self.list_messages(limit=10)
                
                for msg in messages:
                    mid = msg['id']
                    if mid in seen:
                        continue
                    seen.add(mid)
                    
                    frm = msg.get('from_address', '')
                    if sender_contains and sender_contains.lower() not in frm.lower():
                        continue
                    
                    # 获取完整邮件
                    full_msg = self.get_message(mid)
                    
                    # 提取验证码
                    for text in [full_msg.get('subject', ''), full_msg.get('body', '')]:
                        match = code_pattern.search(text)
                        if match:
                            full_msg['_extracted_code'] = match.group(1)
                            break
                    
                    return full_msg
            except:
                pass
            
            time.sleep(interval)
        
        raise TimeoutError(f"{timeout}s 内未等到邮件")

class OutlookClient:
    """Outlook邮箱IMAP客户端"""
    
    def __init__(self, email_address, password):
        """
        初始化Outlook客户端
        
        Args:
            email_address: 邮箱地址
            password: 邮箱密码(或应用专用密码)
        """
        self.email_address = email_address
        self.password = password
        
        # Outlook IMAP配置
        self.imap_host = "outlook.office365.com"
        self.imap_port = 993
        
        self.mail = None
    
    def connect(self):
        """连接到IMAP服务器"""
        try:
            self.mail = imaplib.IMAP4_SSL(self.imap_host, self.imap_port)
            # 使用邮箱密码登录
            self.mail.login(self.email_address, self.password)
            return True
        except Exception as e:
            raise ConnectionError(f"IMAP连接失败: {e}")
    
    def disconnect(self):
        """断开IMAP连接"""
        try:
            if self.mail:
                self.mail.logout()
        except:
            pass
    
    def _decode_str(self, s):
        """解码邮件头部字符串"""
        if not s:
            return ""
        
        if isinstance(s, bytes):
            s = s.decode('utf-8', errors='ignore')
        
        # 处理MIME编码
        try:
            decoded_parts = decode_header(s)
            result = ""
            for content, encoding in decoded_parts:
                if isinstance(content, bytes):
                    result += content.decode(encoding or 'utf-8', errors='ignore')
                else:
                    result += content
            return result
        except:
            return str(s)
    
    def _get_body(self, msg):
        """提取邮件正文，返回(text_body, html_body)元组"""
        text_body = ""
        html_body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                
                if "attachment" in disposition:
                    continue
                
                if content_type == "text/plain":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            text_body += payload.decode(charset, errors='ignore')
                    except:
                        pass
                elif content_type == "text/html":
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or 'utf-8'
                            html_body += payload.decode(charset, errors='ignore')
                    except:
                        pass
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or 'utf-8'
                    content = payload.decode(charset, errors='ignore')
                    # 判断是HTML还是文本
                    if msg.get_content_type() == "text/html":
                        html_body = content
                    else:
                        text_body = content
            except:
                text_body = str(msg.get_payload())
        
        # 如果有HTML但没有文本，从HTML生成文本
        if html_body and not text_body:
            text_body = re.sub(r'<[^>]+>', ' ', html_body)
        
        # 如果有HTML，优先返回HTML（包含链接）
        return html_body if html_body else text_body, html_body
    
    def list_messages(self, folder="INBOX", limit=10):
        """
        获取邮件列表
        
        Args:
            folder: 邮箱文件夹 (默认INBOX)
            limit: 最多返回邮件数
            
        Returns:
            list: 邮件列表
        """
        if not self.mail:
            self.connect()
        
        try:
            # 选择文件夹
            self.mail.select(folder)
            
            # 搜索所有邮件
            status, messages = self.mail.search(None, "ALL")
            if status != "OK":
                return []
            
            # 获取邮件ID列表
            msg_ids = messages[0].split()
            msg_ids = msg_ids[-limit:]  # 只取最新的N封
            
            result = []
            for msg_id in reversed(msg_ids):  # 倒序,最新的在前
                try:
                    # 获取邮件
                    status, data = self.mail.fetch(msg_id, "(RFC822)")
                    if status != "OK":
                        continue
                    
                    # 解析邮件
                    msg = email.message_from_bytes(data[0][1])
                    
                    # 提取信息
                    from_addr = self._decode_str(msg.get("From", ""))
                    subject = self._decode_str(msg.get("Subject", ""))
                    date = msg.get("Date", "")
                    
                    result.append({
                        "id": msg_id.decode(),
                        "from_address": from_addr,
                        "from": from_addr,
                        "subject": subject,
                        "received_at": date,
                        "_raw_msg": msg
                    })
                except:
                    continue
            
            return result
        except Exception as e:
            raise RuntimeError(f"获取邮件列表失败: {e}")
    
    def get_message(self, message_id):
        """
        获取单个邮件详情
        
        Args:
            message_id: 邮件ID
            
        Returns:
            dict: 邮件详情
        """
        if not self.mail:
            self.connect()
        
        try:
            # 获取邮件
            status, data = self.mail.fetch(message_id, "(RFC822)")
            if status != "OK":
                raise ValueError(f"邮件不存在: {message_id}")
            
            # 解析邮件
            msg = email.message_from_bytes(data[0][1])
            
            # 提取信息
            from_addr = self._decode_str(msg.get("From", ""))
            subject = self._decode_str(msg.get("Subject", ""))
            date = msg.get("Date", "")
            body, html_body = self._get_body(msg)  # 获取body和html
            
            return {
                "id": message_id,
                "from_address": from_addr,
                "from": from_addr,
                "subject": subject,
                "received_at": date,
                "body": body,  # 优先HTML（包含链接）
                "text": re.sub(r'<[^>]+>', ' ', body) if html_body else body,  # 纯文本
                "html": html_body,  # HTML原文
            }
        except Exception as e:
            raise RuntimeError(f"获取邮件失败: {e}")
    
    def wait_for_message(self, sender_contains=None, timeout=120, interval=5):
        """
        等待邮件到达
        
        Args:
            sender_contains: 发件人包含的字符串(不区分大小写)
            timeout: 超时时间(秒)
            interval: 轮询间隔(秒)
            
        Returns:
            dict: 邮件详情
        """
        if not self.mail:
            self.connect()
        
        deadline = time.time() + timeout
        seen = set()
        
        # 验证码提取正则
        code_pattern = re.compile(
            r'(?i)(?:验证码|code|OTP|security code is)[：:\s]*([A-Z0-9]{6,8})'
        )
        
        while time.time() < deadline:
            try:
                # 选择收件箱
                self.mail.select("INBOX")
                
                # 搜索最近的邮件
                status, messages = self.mail.search(None, "ALL")
                if status != "OK":
                    time.sleep(interval)
                    continue
                
                msg_ids = messages[0].split()
                # 只检查最新的10封邮件
                msg_ids = msg_ids[-10:]
                
                for msg_id in reversed(msg_ids):
                    mid = msg_id.decode()
                    if mid in seen:
                        continue
                    seen.add(mid)
                    
                    try:
                        # 获取邮件
                        status, data = self.mail.fetch(msg_id, "(RFC822)")
                        if status != "OK":
                            continue
                        
                        msg = email.message_from_bytes(data[0][1])
                        from_addr = self._decode_str(msg.get("From", ""))
                        
                        # 检查发件人
                        if sender_contains and sender_contains.lower() not in from_addr.lower():
                            continue
                        
                        # 找到匹配的邮件,获取完整信息
                        subject = self._decode_str(msg.get("Subject", ""))
                        date = msg.get("Date", "")
                        body, html_body = self._get_body(msg)  # 获取body和html
                        
                        full_msg = {
                            "id": mid,
                            "from_address": from_addr,
                            "from": from_addr,
                            "subject": subject,
                            "received_at": date,
                            "body": body,  # 优先HTML（包含链接）
                            "text": re.sub(r'<[^>]+>', ' ', body) if html_body else body,  # 纯文本
                            "html": html_body,  # HTML原文
                        }
                        
                        # 尝试提取验证码
                        for text in [subject, body]:
                            match = code_pattern.search(text)
                            if match:
                                full_msg["_extracted_code"] = match.group(1)
                                break
                        
                        return full_msg
                    except:
                        continue
                
            except Exception as e:
                # 连接断开时重连
                try:
                    self.disconnect()
                    self.connect()
                except:
                    pass
            
            time.sleep(interval)
        
        raise TimeoutError(f"{timeout}s 内未等到邮件")
    
    def __enter__(self):
        """支持with语句"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """支持with语句"""
        self.disconnect()


def parse_outlook_line(line):
    """
    解析Outlook邮箱配置行
    
    格式1(推荐): 邮箱----密码----ClientID----RefreshToken
    格式2(简化): 邮箱----密码 (只用IMAP)
    
    智能模式: 自动尝试Graph API → IMAP,使用第一个成功的方式
    
    Args:
        line: 配置行字符串
        
    Returns:
        dict: 包含email, password, client_id, refresh_token的字典
        
    Raises:
        ValueError: 格式错误时抛出
    """
    parts = line.strip().split("----")
    
    if len(parts) < 2:
        raise ValueError(
            f"格式错误,至少需要2部分:\n"
            f"邮箱----密码----ClientID----RefreshToken (推荐)\n"
            f"或 邮箱----密码 (仅IMAP)\n"
            f"实际{len(parts)}部分"
        )
    
    email_addr = parts[0].strip()
    password = parts[1].strip() if len(parts) > 1 else ""
    client_id = parts[2].strip() if len(parts) > 2 else ""
    refresh_token = parts[3].strip() if len(parts) > 3 else ""
    
    if not email_addr or "@" not in email_addr:
        raise ValueError("邮箱地址无效")
    
    # 至少需要密码或token
    if not password and not (client_id and refresh_token):
        raise ValueError("必须提供密码或ClientID+RefreshToken")
    
    return {
        "email": email_addr,
        "password": password,
        "client_id": client_id,
        "refresh_token": refresh_token
    }
