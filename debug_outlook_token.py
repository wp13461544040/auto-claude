#!/usr/bin/env python3
"""
Outlook Token 刷新调试工具
用于诊断 Token 刷新失败的具体原因
"""

import sys
import requests
import json

def debug_refresh_token(client_id, refresh_token, scope, tenant="consumers"):
    """调试 Token 刷新"""
    
    token_url = f"https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"
    
    data = {
        "client_id": client_id,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
        "scope": scope
    }
    
    print("=" * 60)
    print("Outlook Token 刷新调试")
    print("=" * 60)
    print(f"URL: {token_url}")
    print(f"Client ID: {client_id[:10]}...")
    print(f"Refresh Token: {refresh_token[:20]}...")
    print(f"Scope: {scope}")
    print(f"Tenant: {tenant}")
    print("=" * 60)
    
    try:
        resp = requests.post(token_url, data=data, timeout=15)
        
        print(f"\n✓ HTTP Status: {resp.status_code}")
        
        if resp.status_code == 200:
            result = resp.json()
            
            print("\n✓ Token 刷新成功!")
            print(f"  Access Token: {result.get('access_token', '')[:30]}...")
            print(f"  Token Type: {result.get('token_type', '')}")
            print(f"  Expires In: {result.get('expires_in', '')} 秒")
            print(f"  Scope: {result.get('scope', '')}")
            
            if "refresh_token" in result:
                print(f"  New Refresh Token: {result['refresh_token'][:20]}...")
            
            return result.get("access_token")
        
        else:
            print("\n✗ Token 刷新失败!")
            
            try:
                error = resp.json()
                print(f"  Error: {error.get('error', '')}")
                print(f"  Error Description: {error.get('error_description', '')}")
                print(f"  Error Codes: {error.get('error_codes', [])}")
                print(f"  Timestamp: {error.get('timestamp', '')}")
                print(f"  Trace ID: {error.get('trace_id', '')}")
                print(f"  Correlation ID: {error.get('correlation_id', '')}")
                
                print("\n完整响应:")
                print(json.dumps(error, indent=2, ensure_ascii=False))
            except:
                print(f"  Raw Response: {resp.text}")
            
            return None
    
    except Exception as e:
        print(f"\n✗ 请求异常: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法:")
        print("  # IMAP 模式")
        print("  python debug_outlook_token.py <client_id> <refresh_token> imap")
        print("")
        print("  # Graph 模式 (.default)")
        print("  python debug_outlook_token.py <client_id> <refresh_token> graph")
        print("")
        print("  # Graph 模式 (Mail.Read)")
        print("  python debug_outlook_token.py <client_id> <refresh_token> graph-mailread")
        print("")
        print("  # 自定义 scope")
        print("  python debug_outlook_token.py <client_id> <refresh_token> \"https://graph.microsoft.com/Mail.Read offline_access\"")
        sys.exit(1)
    
    client_id = sys.argv[1]
    refresh_token = sys.argv[2]
    mode = sys.argv[3] if len(sys.argv) > 3 else "imap"
    
    # 根据模式选择 scope
    if mode == "imap":
        scope = "https://outlook.office.com/IMAP.AccessAsUser.All offline_access"
    elif mode == "graph":
        scope = "https://graph.microsoft.com/.default offline_access"
    elif mode == "graph-mailread":
        scope = "https://graph.microsoft.com/Mail.Read offline_access"
    else:
        scope = mode  # 自定义 scope
    
    access_token = debug_refresh_token(client_id, refresh_token, scope)
    
    if access_token:
        print("\n" + "=" * 60)
        print("✓ 调试完成,Token 刷新成功")
        print("=" * 60)
        sys.exit(0)
    else:
        print("\n" + "=" * 60)
        print("✗ 调试完成,Token 刷新失败")
        print("=" * 60)
        sys.exit(1)
