#!/usr/bin/env python3
"""Remail 集成测试脚本 - 测试完成后自动删除"""

import sys
import time
from registration.remail import RemailClient
from core.config import (
    REMAIL_API_KEY, REMAIL_API_URL, REMAIL_PROJECT_ID,
    REMAIL_PRODUCT_ID, REMAIL_MODE, REMAIL_SUFFIX
)


def test_remail_config():
    """测试1: 配置检查"""
    print("\n[测试 1/3] 检查 Remail 配置...")
    
    if not REMAIL_API_KEY:
        print("  ❌ REMAIL_API_KEY 未配置")
        return False
    print(f"  ✓ API Key: {REMAIL_API_KEY[:10]}...")
    
    if not REMAIL_PROJECT_ID or REMAIL_PROJECT_ID == 0:
        print("  ❌ REMAIL_PROJECT_ID 未配置或无效")
        return False
    print(f"  ✓ Project ID: {REMAIL_PROJECT_ID}")
    
    if not REMAIL_PRODUCT_ID or REMAIL_PRODUCT_ID == 0:
        print("  ❌ REMAIL_PRODUCT_ID 未配置或无效")
        return False
    print(f"  ✓ Product ID: {REMAIL_PRODUCT_ID}")
    
    print(f"  ✓ API URL: {REMAIL_API_URL}")
    print(f"  ✓ Mode: {REMAIL_MODE}")
    print(f"  ✓ Suffix: {REMAIL_SUFFIX or '(无)'}")
    
    return True


def test_remail_connection():
    """测试2: API连接和项目列表"""
    print("\n[测试 2/3] 测试 API 连接...")
    
    try:
        client = RemailClient(
            api_key=REMAIL_API_KEY,
            project_id=REMAIL_PROJECT_ID,
            product_id=REMAIL_PRODUCT_ID,
            api_url=REMAIL_API_URL,
            mode=REMAIL_MODE,
            suffix=REMAIL_SUFFIX
        )
        
        # 尝试获取项目列表
        print("  → 查询项目列表...")
        projects = client.get_projects(limit=5)
        
        items = projects.get("items", [])
        if items:
            print(f"  ✓ 成功获取 {len(items)} 个项目")
            for p in items[:3]:
                print(f"    - {p.get('name', '未命名')} (ID: {p.get('id')})")
        else:
            print("  ⚠ 未获取到项目列表(可能是权限问题)")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 连接失败: {e}")
        return False


def test_remail_mailbox():
    """测试3: 创建邮箱和接收邮件"""
    print("\n[测试 3/3] 测试创建邮箱...")
    
    try:
        client = RemailClient(
            api_key=REMAIL_API_KEY,
            project_id=REMAIL_PROJECT_ID,
            product_id=REMAIL_PRODUCT_ID,
            api_url=REMAIL_API_URL,
            mode=REMAIL_MODE,
            suffix=REMAIL_SUFFIX
        )
        
        # 创建邮箱
        print("  → 创建临时邮箱...")
        box = client.create_mailbox(name="test")
        
        email = box["email"]
        token = box["token"]
        order_no = box["orderNo"]
        
        print(f"  ✓ 邮箱创建成功!")
        print(f"    邮箱地址: {email}")
        print(f"    订单号: {order_no}")
        print(f"    Token: {token[:20]}...")
        
        # 测试查询邮件(应该是空的)
        print("\n  → 测试查询邮件...")
        result = client.list_messages()
        messages = result.get("messages", [])
        print(f"  ✓ 邮箱当前有 {len(messages)} 封邮件")
        
        if messages:
            print("    最近的邮件:")
            for msg in messages[:3]:
                print(f"    - 来自: {msg.get('from_address', '?')}")
                print(f"      主题: {msg.get('subject', '(无主题)')}")
        
        print("\n  提示: 你可以向该邮箱发送测试邮件来验证接收功能")
        print(f"  邮箱: {email}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("Remail 集成测试")
    print("=" * 60)
    
    # 测试1: 配置检查
    if not test_remail_config():
        print("\n❌ 配置检查失败! 请在 .env 中配置 Remail 参数")
        print("\n配置示例:")
        print("  EMAIL_SERVICE=remail")
        print("  REMAIL_API_KEY=your_api_key")
        print("  REMAIL_PROJECT_ID=123")
        print("  REMAIL_PRODUCT_ID=456")
        return 1
    
    # 测试2: API连接
    if not test_remail_connection():
        print("\n❌ API 连接失败! 请检查 API Key 和网络")
        return 1
    
    # 测试3: 创建邮箱
    if not test_remail_mailbox():
        print("\n❌ 邮箱创建失败! 请检查项目ID和产品ID")
        return 1
    
    print("\n" + "=" * 60)
    print("✓ 所有测试通过! Remail 集成成功")
    print("=" * 60)
    print("\n你现在可以在 .env 中设置 EMAIL_SERVICE=remail 来使用 Remail")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
