# Outlook 取件功能集成文档

## 功能概述

Outlook 取件模块支持两种取件协议:

- **IMAP 模式**: 通过 XOAUTH2 认证连接 `outlook.office365.com:993`
- **Graph API 模式**: 通过 Microsoft Graph API `/me/mailFolders/inbox/messages`

### 核心特性

- ✅ OAuth Token 自动刷新 (有效期 1 小时)
- ✅ 时间戳过滤 (只检测最近 2 分钟内的邮件)
- ✅ 验证码自动提取 (正则 `\b(\d{6})\b`)
- ✅ 代理支持 (自动降级直连)
- ✅ "not connected" 错误容错 (Outlook 后端未就绪)
- ✅ 连接重试机制

---

## 数据结构

### Outlook 账号格式

**标准卡密格式 (推荐):**

```text
邮箱----密码----client_id----refresh_token
```

**注意:** 不需要指定模式,代码会自动根据 scope 判断。卡密商家标准:

- **Graph 模式**: `scope = "https://graph.microsoft.com/.default"`
- **IMAP 模式**: `scope = "https://outlook.office.com/.default"`

**示例:**

```text
user@outlook.com----password----client-id-here----refresh-token-here
user2@outlook.com----password----client-id----refresh-token
```

**兼容格式 (可选指定模式):**

```text
邮箱----密码----client_id----refresh_token----imap
邮箱----密码----client_id----refresh_token----graph
```

**字段说明:**

- `邮箱`: Outlook 邮箱地址
- `密码`: 邮箱密码 (可选,目前未使用)
- `client_id`: Azure 应用 Client ID
- `refresh_token`: 永久刷新令牌 (卡密核心)
- `模式`: `imap` 或 `graph` (可选,默认自动检测)

---

## 命令行工具

### 1. 添加账号

```bash
python test_outlook_otp.py add
```

交互式输入格式:

```text
user@outlook.com----password----client-id----refresh-token----imap
user2@outlook.com----password----client-id----refresh-token----graph
```

输入完成后按 `Ctrl+D` (Linux/Mac) 或 `Ctrl+Z` (Windows)

### 2. 列出账号

```bash
python test_outlook_otp.py list
```

输出示例:

```text
[列表] 共 2 个账号:

  1. user@outlook.com
     模式: imap
     状态: active
     添加时间: 2026-08-12 21:17:54

  2. user2@outlook.com
     模式: graph
     状态: active
     添加时间: 2026-08-12 21:18:10
```

### 3. 等待验证码 (IMAP 模式)

```bash
python test_outlook_otp.py wait user@outlook.com
```

可选参数:

```bash
python test_outlook_otp.py wait user@outlook.com \
  --mode imap \
  --timeout 120 \
  --interval 5
```

### 4. 等待验证码 (Graph 模式)

```bash
python test_outlook_otp.py wait user@outlook.com --mode graph
```

### 5. 获取收件箱数量

```bash
python test_outlook_otp.py count user@outlook.com
```

---

## Python API

### 等待验证码 (统一接口)

```python
from registration.outlook_otp import wait_for_outlook_otp

code = wait_for_outlook_otp(
    email="user@outlook.com",
    client_id="your-client-id",
    refresh_token="your-refresh-token",
    mode="imap",  # 或 "graph"
    timeout=120,
    interval=5,
    before_count=None,  # 可选,之前的邮件数量
    proxy=None  # 可选,代理地址
)

print(f"验证码: {code}")
```

### IMAP 模式详细用法

```python
from registration.outlook_otp import OutlookIMAPOTPClient

client = OutlookIMAPOTPClient(
    email="user@outlook.com",
    client_id="your-client-id",
    refresh_token="your-refresh-token",
    proxy="socks5://127.0.0.1:1080"  # 可选
)

# 使用 with 语句自动管理连接
with client:
    # 获取收件箱数量
    count = client.get_inbox_count()
    print(f"收件箱邮件数: {count}")
    
    # 等待验证码
    code = client.wait_for_otp(timeout=120, interval=5)
    print(f"验证码: {code}")
```

### Graph API 模式详细用法

```python
from registration.outlook_otp import OutlookGraphOTPClient

client = OutlookGraphOTPClient(
    email="user@outlook.com",
    client_id="your-client-id",
    refresh_token="your-refresh-token",
    proxy="socks5://127.0.0.1:1080"  # 可选
)

# 等待验证码
code = client.wait_for_otp(timeout=120, interval=5)
print(f"验证码: {code}")
```

### 获取收件箱数量 (快捷函数)

```python
from registration.outlook_otp import get_outlook_inbox_count

count = get_outlook_inbox_count(
    email="user@outlook.com",
    client_id="your-client-id",
    refresh_token="your-refresh-token",
    proxy=None
)

print(f"收件箱邮件数: {count}")
```

---

## Web API 接口

### 1. 批量添加账号

```http
POST /api/outlook/add
Content-Type: application/json

{
  "lines": [
    "user@outlook.com----password----client-id----refresh-token----imap",
    "user2@outlook.com----password----client-id----refresh-token----graph"
  ]
}
```

响应:

```json
{
  "success": true,
  "data": {
    "added": 2,
    "total": 2
  },
  "message": "添加成功: 新增2个"
}
```

### 2. 获取账号列表

```http
GET /api/outlook/list
```

响应:

```json
{
  "success": true,
  "data": [
    {
      "email": "user@outlook.com",
      "password": "password",
      "client_id": "client-id",
      "refresh_token": "refresh-token",
      "mode": "imap",
      "status": "active",
      "added_at": "2026-08-12 21:17:54"
    }
  ],
  "total": 1
}
```

### 3. 等待验证码

```http
POST /api/outlook/wait-otp
Content-Type: application/json

{
  "email": "user@outlook.com",
  "client_id": "your-client-id",
  "refresh_token": "your-refresh-token",
  "mode": "imap",
  "timeout": 120,
  "interval": 5,
  "before_count": 10
}
```

响应:

```json
{
  "success": true,
  "data": {
    "code": "123456"
  },
  "message": "验证码: 123456"
}
```

超时响应 (HTTP 408):

```json
{
  "success": false,
  "error": "120s内未收到验证码"
}
```

### 4. 获取收件箱数量

```http
POST /api/outlook/inbox-count
Content-Type: application/json

{
  "email": "user@outlook.com",
  "client_id": "your-client-id",
  "refresh_token": "your-refresh-token"
}
```

响应:

```json
{
  "success": true,
  "data": {
    "count": 15
  },
  "message": "收件箱邮件数: 15"
}
```

### 5. 测试 Token 刷新

```http
POST /api/outlook/test-token
Content-Type: application/json

{
  "email": "user@outlook.com",
  "client_id": "your-client-id",
  "refresh_token": "your-refresh-token",
  "mode": "imap"
}
```

响应:

```json
{
  "success": true,
  "data": {
    "token_preview": "eyJhbGciOi..."
  },
  "message": "Token 刷新成功"
}
```

---

## 错误处理

### "not connected" 错误

**原因:** Outlook 邮箱后端尚未就绪 (新账号或长时间未登录)

**解决方法:**

1. 断开当前连接
2. 等待 5-10 秒后重连
3. 不要刷新 token (token 没问题)
4. 可以尝试网页登录激活邮箱

**代码示例:**

```python
from registration.outlook_otp import (
    OutlookIMAPOTPClient,
    OutlookNotConnectedError
)

client = OutlookIMAPOTPClient(email, client_id, refresh_token)

try:
    client.connect()
except OutlookNotConnectedError:
    print("后端未就绪,等待 10 秒后重试...")
    time.sleep(10)
    client.connect()  # 重试
```

### 认证失败错误

**原因:** Access Token 过期或无效

**解决方法:** 自动刷新 token (已内置)

### 超时错误

**原因:** 超时时间内未收到验证码邮件

**解决方法:**

1. 增加 `timeout` 参数
2. 检查邮件是否真的发送到该邮箱
3. 检查垃圾邮件文件夹

---

## 性能对比

| 操作 | IMAP 模式 | Graph 模式 |
|------|----------|-----------|
| Token 刷新 | ~2 秒 | ~2 秒 |
| 连接建立 | ~3 秒 | N/A |
| 单次轮询 | ~5 秒 | ~1 秒 |
| 平均取码时间 | 15-30 秒 | 10-20 秒 |

**结论:** Graph 模式速度快 50%,推荐优先使用

---

## 常见问题

### Q1: IMAP 和 Graph 模式有什么区别?

**IMAP 模式:**

- 需要建立 TLS 连接
- 逐封邮件 FETCH
- 兼容性好

**Graph 模式:**

- 单次 HTTPS 请求
- 服务器端过滤
- 速度更快 (推荐)

### Q2: 为什么时间戳过滤往前推 2 分钟?

邮件投递有延迟,如果用精确的当前时间过滤会遗漏刚发送的邮件。往前推 2 分钟可以覆盖绝大多数投递延迟场景。

### Q3: 如何获取 ClientID 和 RefreshToken?

1. 在 Azure Portal 创建应用注册
2. 配置 OAuth 权限:
   - IMAP: `https://outlook.office.com/IMAP.AccessAsUser.All`
   - Graph: `https://graph.microsoft.com/Mail.Read`
3. 通过 OAuth 授权流程获取 refresh_token

### Q4: 支持代理吗?

支持!会自动使用 `proxy.text` 或环境变量 `PROXY` 中配置的代理。

代理失败时会自动降级直连。

---

## 代码规范建议

### 1. 高频轮询日志优化

```python
if attempt % 5 == 0:  # 每 5 次轮询才打印一次
    print_log(f"[Outlook] 第{attempt}次轮询,剩余{remaining}s")
```

### 2. 连接复用 (可选优化)

如果要进一步提升性能,可以维护一个连接池,但要处理 idle timeout。

### 3. 错误日志

```python
try:
    code = wait_for_outlook_otp(...)
except OutlookNotConnectedError as e:
    print_log(f"[Outlook] 后端未就绪: {e}")
except OutlookOTPError as e:
    print_log(f"[Outlook] 取件失败: {e}")
except TimeoutError as e:
    print_log(f"[Outlook] 超时: {e}")
```

---

## 集成到注册流程

```python
from registration.outlook_otp import wait_for_outlook_otp

# 在注册流程中等待验证码
def register_with_outlook(email, client_id, refresh_token):
    # 1. 发起注册请求
    send_registration_request(email)
    
    # 2. 获取注册前的邮件数量 (可选)
    before_count = get_outlook_inbox_count(email, client_id, refresh_token)
    
    # 3. 等待验证码
    code = wait_for_outlook_otp(
        email=email,
        client_id=client_id,
        refresh_token=refresh_token,
        mode="graph",  # 推荐使用 Graph 模式
        timeout=120,
        interval=5,
        before_count=before_count
    )
    
    # 4. 提交验证码
    submit_verification_code(code)
    
    return True
```

---

## 文件结构

```text
claudex/
├── registration/
│   ├── outlook.py          # 原有的 Outlook IMAP 客户端
│   └── outlook_otp.py      # 新增的取件模块 ⭐
├── account/
│   └── storage.py          # 新增 Outlook 账号管理函数 ⭐
├── test_outlook_otp.py     # 命令行测试工具 ⭐
├── web_server.py           # Web API (新增 Outlook 接口) ⭐
├── outlook_accounts.json   # Outlook 账号数据 ⭐
└── OUTLOOK_INTEGRATION.md  # 本文档 ⭐
```

---

## 依赖

所有依赖已包含在 `requirements.txt` 中:

- `requests` - HTTP 请求
- `imaplib` - IMAP 协议 (Python 标准库)
- `email` - 邮件解析 (Python 标准库)

---

## 许可证

与主项目相同的许可证。

---

**文档版本:** 1.0  
**更新日期:** 2026-08-12  
**作者:** 破甲鸟
