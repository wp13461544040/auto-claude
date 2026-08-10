"""
inject_cookie.py
1. 设置 Windows 系统代理（让 Claude Desktop 也走代理）
2. 将 accounts.json 中指定账号的 sessionKey 注入 Claude Desktop Cookies 数据库

用法: python inject_cookie.py [账号序号，从0开始，默认0]

注意: 运行前必须完全关闭 Claude Desktop（含系统托盘）。
"""
import json
import os
import sqlite3
import sys
import time
import winreg

COOKIES_PATH = (
    r"d:\WpSystem\S-1-5-21-4217227049-1155704670-4225484024-500"
    r"\AppData\Local\Packages\Claude_pzs8sxrjxfjjc"
    r"\LocalCache\Roaming\Claude\Network\Cookies"
)
ACCOUNTS_FILE = "accounts.json"
ENV_FILE = ".env"

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _load_proxy_from_env(env_file=ENV_FILE):
    """从 .env 读取 PROXY 配置，去掉协议头返回 host:port 格式。"""
    if not os.path.exists(env_file):
        return None
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("PROXY="):
                value = line[len("PROXY="):].split("#")[0].strip().strip('"').strip("'")
                if not value:
                    return None
                # 去掉协议头，只保留 host:port（Windows 系统代理格式）
                for scheme in ("socks5h://", "socks5://", "https://", "http://"):
                    if value.startswith(scheme):
                        value = value[len(scheme):]
                        break
                return value
    return None


def set_system_proxy(proxy_str):
    """设置 Windows 系统 HTTP/HTTPS 代理。"""
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, proxy_str)
        winreg.CloseKey(key)
        print(f"[系统代理] 已启用: {proxy_str}")
    except Exception as e:
        print(f"[系统代理] 设置失败: {e}")


def clear_system_proxy():
    """关闭 Windows 系统代理。"""
    reg_path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, reg_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        print("[系统代理] 已关闭")
    except Exception as e:
        print(f"[系统代理] 关闭失败: {e}")


def _encrypt_dpapi(plaintext: str) -> bytes:
    """用 Windows DPAPI 加密，Electron/Chromium 可直接读取。"""
    import win32crypt
    return win32crypt.CryptProtectData(plaintext.encode("utf-8"), None, None, None, None, 0)


# ── 主逻辑 ────────────────────────────────────────────────────────────────────

def inject(account_index: int = 0):
    # 1. 读取账号
    with open(ACCOUNTS_FILE, encoding="utf-8") as f:
        accounts = json.load(f)

    if account_index >= len(accounts):
        print(f"账号序号 {account_index} 超出范围，共 {len(accounts)} 个账号")
        return

    account = accounts[account_index]
    email = account["email"]
    cookies_to_inject = {
        k: v for k, v in {
            "sessionKey":  account["cookies"].get("sessionKey", ""),
            "routingHint": account["cookies"].get("routingHint", ""),
        }.items() if v
    }

    print(f"账号: {email}")
    for name, val in cookies_to_inject.items():
        print(f"  {name}: {val[:40]}...")

    # 2. 设置系统代理
    proxy = _load_proxy_from_env()
    if proxy:
        set_system_proxy(proxy)
    else:
        print("[系统代理] .env 中未配置 PROXY，跳过")

    # 3. 注入 Cookie
    if not os.path.exists(COOKIES_PATH):
        print(f"\n找不到 Cookies 文件: {COOKIES_PATH}")
        return

    conn = sqlite3.connect(COOKIES_PATH)
    now_us = int(time.time() * 1_000_000)
    expires_us = now_us + 365 * 24 * 3600 * 1_000_000  # 1 年后

    print("\n注入 Cookie:")
    for name, value in cookies_to_inject.items():
        encrypted = _encrypt_dpapi(value)

        existing = conn.execute(
            "SELECT rowid FROM cookies WHERE host_key='.claude.ai' AND name=?",
            (name,)
        ).fetchone()

        if existing:
            conn.execute(
                """UPDATE cookies
                   SET value='', encrypted_value=?, expires_utc=?,
                       last_access_utc=?, last_update_utc=?
                   WHERE rowid=?""",
                (encrypted, expires_us, now_us, now_us, existing[0])
            )
            print(f"  [更新] {name}")
        else:
            conn.execute(
                """INSERT INTO cookies
                   (creation_utc, host_key, top_frame_site_key, name, value,
                    encrypted_value, path, expires_utc, is_secure, is_httponly,
                    last_access_utc, has_expires, is_persistent, priority,
                    samesite, source_scheme, source_port, last_update_utc,
                    source_type, has_cross_site_ancestor)
                   VALUES (?,'.claude.ai','',?,'',?,'/',?,1,1,?,1,1,1,-1,2,443,?,2,0)""",
                (now_us, name, encrypted, expires_us, now_us, now_us)
            )
            print(f"  [插入] {name}")

    conn.commit()
    conn.close()

    print("\n完成！请现在重新打开 Claude Desktop。")
    print("登录成功后如需关闭系统代理，运行: python inject_cookie.py --clear-proxy")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--clear-proxy":
        clear_system_proxy()
    else:
        idx = int(sys.argv[1]) if len(sys.argv) > 1 else 0
        inject(idx)
