# Outlook 取件功能 - 快速开始

## 1 分钟快速上手

### 步骤 1: 添加账号

创建文件 `outlook_test.txt`:

```text
your-email@outlook.com----your-password----client-id----refresh-token----imap
```

运行命令:

```bash
python test_outlook_otp.py add < outlook_test.txt
```

### 步骤 2: 列出账号

```bash
python test_outlook_otp.py list
```

输出:

```text
[列表] 共 1 个账号:

  1. your-email@outlook.com
     模式: imap
     状态: active
     添加时间: 2026-08-12 21:17:54
```

### 步骤 3: 测试 Token 刷新 (可选)

```bash
python -c "from registration.outlook_otp import refresh_outlook_token; token = refresh_outlook_token('your-email@outlook.com', 'client-id', 'refresh-token', 'imap'); print('Token:', token[:10] + '...')"
```

### 步骤 4: 等待验证码

```bash
python test_outlook_otp.py wait your-email@outlook.com
```

**此时:**

1. 向该邮箱发送一封包含 6 位数字的测试邮件
2. 脚本会自动检测并提取验证码

输出:

```text
[Outlook IMAP] 开始等待验证码 (超时120s,间隔5s)
[Outlook IMAP] 找到验证码: 123456
[测试] 成功收到验证码: 123456
```

---

## 模式对比

### IMAP 模式 (默认)

```bash
python test_outlook_otp.py wait user@outlook.com --mode imap
```

**优点:**

- 兼容性好
- 不需要额外 API 权限

**缺点:**

- 速度较慢 (~5 秒/轮询)
- 需要建立 TLS 连接

### Graph API 模式 (推荐)

```bash
python test_outlook_otp.py wait user@outlook.com --mode graph
```

**优点:**

- 速度快 (~1 秒/轮询)
- 服务器端过滤
- 不需要维护长连接

**缺点:**

- 需要 Graph API 权限 (`Mail.Read`)

---

## Web API 使用

### 启动服务器

```bash
python web_server.py
```

### 添加账号

```bash
curl -X POST http://localhost:5000/api/outlook/add \
  -H "Content-Type: application/json" \
  -d '{
    "lines": [
      "user@outlook.com----password----client-id----refresh-token----imap"
    ]
  }'
```

### 等待验证码

```bash
curl -X POST http://localhost:5000/api/outlook/wait-otp \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@outlook.com",
    "client_id": "your-client-id",
    "refresh_token": "your-refresh-token",
    "mode": "graph",
    "timeout": 120,
    "interval": 5
  }'
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

---

## 常见错误

### 错误 1: "not connected"

```text
OutlookNotConnectedError: not connected
```

**解决方法:** 等待 5-10 秒后重试,或网页登录激活邮箱

### 错误 2: "认证失败"

```text
OutlookOTPError: XOAUTH2认证失败: authentication failure
```

**解决方法:** 检查 ClientID 和 RefreshToken 是否正确

### 错误 3: "超时未收到验证码"

```text
TimeoutError: 120s内未收到验证码
```

**解决方法:**

1. 增加 `--timeout 300` 参数
2. 检查邮件是否真的发送了
3. 检查垃圾邮件文件夹

---

## 集成到你的项目

### Python 代码

```python
from registration.outlook_otp import wait_for_outlook_otp

# 等待验证码
code = wait_for_outlook_otp(
    email="user@outlook.com",
    client_id="your-client-id",
    refresh_token="your-refresh-token",
    mode="graph",  # 推荐
    timeout=120,
    interval=5
)

print(f"验证码: {code}")
```

### JavaScript 调用 Web API

```javascript
async function waitForOTP(email, clientId, refreshToken) {
  const response = await fetch('http://localhost:5000/api/outlook/wait-otp', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      email: email,
      client_id: clientId,
      refresh_token: refreshToken,
      mode: 'graph',
      timeout: 120,
      interval: 5
    })
  });
  
  const result = await response.json();
  
  if (result.success) {
    console.log('验证码:', result.data.code);
    return result.data.code;
  } else {
    console.error('错误:', result.error);
    throw new Error(result.error);
  }
}
```

---

## 性能优化建议

### 1. 使用 Graph 模式

Graph 模式比 IMAP 快 50%:

```bash
python test_outlook_otp.py wait user@outlook.com --mode graph
```

### 2. 合理设置轮询间隔

```bash
# 快速响应 (1 秒轮询)
python test_outlook_otp.py wait user@outlook.com --interval 1

# 省资源 (10 秒轮询)
python test_outlook_otp.py wait user@outlook.com --interval 10
```

### 3. 使用代理池

在 `proxy.text` 中配置多个代理,自动轮询使用。

---

## 完整示例

```python
from registration.outlook_otp import (
    wait_for_outlook_otp,
    get_outlook_inbox_count,
    OutlookOTPError,
    OutlookNotConnectedError
)
from account.storage import get_outlook_account

# 从配置文件加载账号
account = get_outlook_account("user@outlook.com")

if not account:
    print("账号不存在")
    exit(1)

try:
    # 获取注册前的邮件数
    before_count = get_outlook_inbox_count(
        email=account["email"],
        client_id=account["client_id"],
        refresh_token=account["refresh_token"]
    )
    
    print(f"当前收件箱: {before_count} 封邮件")
    
    # 发起注册请求 (你的业务逻辑)
    send_registration_request(account["email"])
    
    # 等待验证码
    code = wait_for_outlook_otp(
        email=account["email"],
        client_id=account["client_id"],
        refresh_token=account["refresh_token"],
        mode=account.get("mode", "imap"),
        timeout=120,
        interval=5,
        before_count=before_count
    )
    
    print(f"收到验证码: {code}")
    
    # 提交验证码 (你的业务逻辑)
    submit_verification_code(code)
    
    print("注册成功!")

except OutlookNotConnectedError as e:
    print(f"Outlook 后端未就绪: {e}")
    print("建议: 等待 10 分钟后重试,或网页登录激活邮箱")

except TimeoutError as e:
    print(f"超时: {e}")
    print("建议: 检查邮件是否发送,或增加 timeout 参数")

except OutlookOTPError as e:
    print(f"取件失败: {e}")

except Exception as e:
    print(f"未知错误: {e}")
    import traceback
    traceback.print_exc()
```

---

## 下一步

- 查看完整文档: `OUTLOOK_INTEGRATION.md`
- 了解 API 详情: Web Server 路由 `/api/outlook/*`
- 查看源码: `registration/outlook_otp.py`

---

**开始使用吧!如果遇到问题,先看 `OUTLOOK_INTEGRATION.md` 的错误处理章节。**
