#!/usr/bin/env python3
"""
Outlook 取件功能测试脚本

测试步骤:
1. 添加 Outlook 账号到 outlook_accounts.json
2. 运行此脚本等待验证码
3. 向该邮箱发送测试邮件(包含6位数字)
"""

import sys
import argparse
from registration.outlook_otp import (
    wait_for_outlook_otp,
    get_outlook_inbox_count,
    OutlookOTPError,
    OutlookNotConnectedError
)
from account.storage import (
    load_outlook_accounts,
    add_outlook_accounts,
    get_outlook_account
)
from core.config import get_next_proxy
from core.console import print_log


def test_wait_otp(email, mode="imap", timeout=120, interval=5):
    """测试等待验证码"""
    print_log(f"[测试] 从 outlook_accounts.json 加载账号: {email}")
    
    # 加载账号
    account = get_outlook_account(email)
    if not account:
        print_log(f"[测试] 账号不存在: {email}")
        print_log("[测试] 使用以下命令添加账号:")
        print_log("  python test_outlook_otp.py add")
        return False
    
    # 覆盖模式
    if mode:
        account["mode"] = mode
    
    # 获取代理
    proxy = get_next_proxy()
    if proxy:
        print_log(f"[测试] 使用代理: {proxy}")
    
    print_log(f"[测试] 开始等待验证码 (模式:{account['mode']}, 超时:{timeout}s)")
    print_log("[测试] 请向该邮箱发送包含6位数字的测试邮件...")
    
    try:
        code = wait_for_outlook_otp(
            email=account["email"],
            client_id=account["client_id"],
            refresh_token=account["refresh_token"],
            mode=account["mode"],
            timeout=timeout,
            interval=interval,
            proxy=proxy
        )
        
        print_log(f"[测试] 成功收到验证码: {code}")
        return True
    
    except TimeoutError:
        print_log(f"[测试] {timeout}s 超时未收到验证码")
        return False
    
    except OutlookNotConnectedError as e:
        print_log(f"[测试] Outlook 后端未就绪: {e}")
        print_log("[测试] 建议: 等待5-10分钟后重试,或使用网页登录激活邮箱")
        return False
    
    except OutlookOTPError as e:
        print_log(f"[测试] 取件失败: {e}")
        return False
    
    except Exception as e:
        print_log(f"[测试] 未知错误: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_inbox_count(email):
    """测试获取收件箱数量"""
    print_log(f"[测试] 从 outlook_accounts.json 加载账号: {email}")
    
    account = get_outlook_account(email)
    if not account:
        print_log(f"[测试] 账号不存在: {email}")
        return False
    
    proxy = get_next_proxy()
    
    print_log(f"[测试] 获取收件箱邮件数量...")
    
    try:
        count = get_outlook_inbox_count(
            email=account["email"],
            client_id=account["client_id"],
            refresh_token=account["refresh_token"],
            proxy=proxy
        )
        
        print_log(f"[测试] 收件箱邮件数: {count}")
        return True
    
    except Exception as e:
        print_log(f"[测试] 获取失败: {e}")
        return False


def add_accounts_interactive():
    """交互式添加账号"""
    print_log("[添加账号] 格式: email----password----client_id----refresh_token----mode")
    print_log("[添加账号] mode: imap 或 graph (默认 imap)")
    print_log("[添加账号] 输入完成后按 Ctrl+D (Linux/Mac) 或 Ctrl+Z (Windows) 结束")
    print_log("")
    
    lines = []
    try:
        while True:
            line = input()
            if line.strip():
                lines.append(line.strip())
    except EOFError:
        pass
    
    if not lines:
        print_log("[添加账号] 未输入任何账号")
        return
    
    data = "\n".join(lines)
    result = add_outlook_accounts(data)
    
    print_log(f"[添加账号] 完成: 新增{result['added']}个, 总计{result['total']}个")


def list_accounts():
    """列出所有账号"""
    accounts = load_outlook_accounts()
    
    if not accounts:
        print_log("[列表] 无账号")
        return
    
    print_log(f"[列表] 共 {len(accounts)} 个账号:")
    print_log("")
    
    for i, acc in enumerate(accounts, 1):
        print_log(f"  {i}. {acc['email']}")
        print_log(f"     模式: {acc.get('mode', 'imap')}")
        print_log(f"     状态: {acc.get('status', 'unknown')}")
        print_log(f"     添加时间: {acc.get('added_at', 'unknown')}")
        print_log("")


def main():
    parser = argparse.ArgumentParser(
        description="Outlook 取件功能测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 添加账号
  python test_outlook_otp.py add
  
  # 列出账号
  python test_outlook_otp.py list
  
  # 测试等待验证码 (IMAP 模式)
  python test_outlook_otp.py wait user@outlook.com
  
  # 测试等待验证码 (Graph 模式)
  python test_outlook_otp.py wait user@outlook.com --mode graph
  
  # 测试获取收件箱数量
  python test_outlook_otp.py count user@outlook.com
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # add 命令
    subparsers.add_parser("add", help="添加账号")
    
    # list 命令
    subparsers.add_parser("list", help="列出账号")
    
    # wait 命令
    wait_parser = subparsers.add_parser("wait", help="等待验证码")
    wait_parser.add_argument("email", help="邮箱地址")
    wait_parser.add_argument("--mode", choices=["imap", "graph"], help="取件模式")
    wait_parser.add_argument("--timeout", type=int, default=120, help="超时时间(秒)")
    wait_parser.add_argument("--interval", type=int, default=5, help="轮询间隔(秒)")
    
    # count 命令
    count_parser = subparsers.add_parser("count", help="获取收件箱数量")
    count_parser.add_argument("email", help="邮箱地址")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "add":
        add_accounts_interactive()
    
    elif args.command == "list":
        list_accounts()
    
    elif args.command == "wait":
        success = test_wait_otp(
            args.email, 
            mode=args.mode, 
            timeout=args.timeout,
            interval=args.interval
        )
        sys.exit(0 if success else 1)
    
    elif args.command == "count":
        success = test_inbox_count(args.email)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
