# Claude 账号检测功能

## 功能说明

Outlook 注册流程现在会自动检测邮箱是否已注册过 Claude 账号:

- ✅ **已注册** - 自动使用 magic link 登录,获取现有账号 session
- ✅ **未注册** - 正常走注册流程,创建新账号

## 工作流程

### 步骤 3/7: 账号状态检测

```
[3/7] 查询 claude.ai 登录方式并检测账号状态…
      可用方式: ['google', 'magic_link']
      
情况 1: 已注册账号
      ⚠️  邮箱已注册过 Claude 账号
      策略: 使用 magic link 登录获取现有账号 session
      
情况 2: 新账号
      ✓ 邮箱未注册,将创建新账号
```

### 检测逻辑

通过查询 `/api/auth/login_methods` 接口:

```python
methods = _get_login_methods(s, email)
available_methods = methods.get('methods', [])

if available_methods and len(available_methods) > 0:
    # 有登录方式 = 账号已存在
    is_new_account = False
else:
    # 无登录方式 = 新账号
    is_new_account = True
```

## 数据标记

账号记录会添加 `account_status` 字段:

```json
{
  "email": "user@outlook.com",
  "uuid": "xxx",
  "account_status": "existing",  // "existing" 或 "new"
  "registration_mode": "outlook",
  "outlook_mode": "graph"
}
```

## 日志示例

### 已注册账号 (登录)

```
[1/7] 检查出口 IP…
      出口 IP: 1.2.3.4
[2/7] 初始化Outlook客户端(智能模式)…
      ✓ Graph API连接成功
[3/7] 查询 claude.ai 登录方式并检测账号状态…
      可用方式: ['google', 'magic_link']
      ⚠️  邮箱已注册过 Claude 账号
      策略: 使用 magic link 登录获取现有账号 session
[4/7] 发送 magic link 邮件 (登录)…
      已发送，等待邮件到达…
[5/7] 轮询Outlook邮箱(GRAPH模式)，等待 Anthropic 验证邮件…
      收到验证邮件，提取 nonce…
[6/7] 用 nonce 换取登录会话…
      账号 UUID: xxx
      账号类型: 现有账号(登录)
[7/7] 验证账号额度和订阅状态…
      订阅: FREE
      额度: 0/100
[成功] Outlook 登录完成: user@outlook.com
```

### 新账号 (注册)

```
[1/7] 检查出口 IP…
[2/7] 初始化Outlook客户端(智能模式)…
      ✓ Graph API连接成功
[3/7] 查询 claude.ai 登录方式并检测账号状态…
      可用方式: []
      ✓ 邮箱未注册,将创建新账号
[4/7] 发送 magic link 邮件 (注册)…
      已发送，等待邮件到达…
[5/7] 轮询Outlook邮箱(GRAPH模式)，等待 Anthropic 验证邮件…
      收到验证邮件，提取 nonce…
[6/7] 用 nonce 换取注册会话…
      账号 UUID: xxx
      账号类型: 新账号(注册)
[7/7] 验证账号额度和订阅状态…
      订阅: FREE
      额度: 0/100
[成功] Outlook 注册完成: user@outlook.com
```

## 优势

### 1. 防止重复注册

- 避免浪费 Outlook 邮箱资源
- 自动跳过已注册的邮箱

### 2. 自动登录现有账号

- 如果邮箱已注册,直接获取 session
- 可用于批量登录 + 更新 cookies

### 3. 清晰的状态标记

- `account_status` 字段区分新老账号
- 方便后续统计和管理

## API 调用

检测 API:

```http
GET /api/auth/login_methods?email=user@outlook.com&source=claude
Host: claude.ai
```

响应示例:

```json
// 已注册
{
  "methods": ["google", "magic_link"]
}

// 未注册
{
  "methods": []
}
```

## 注意事项

1. **已注册不代表失败** - 登录也能获取有效 session
2. **检测耗时极短** - 只增加 1 次 HTTP 请求 (~1 秒)
3. **兼容所有模式** - IMAP 和 Graph 模式都支持

---

**版本:** 1.0  
**更新日期:** 2026-08-12
