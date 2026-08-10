#!/usr/bin/env python3
"""
ClaudeX Web 管理界面
"""
import json
import os
import threading
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from account.check import check_usage
from account.storage import load_accounts, save_accounts
from registration.register import register_batch
from core.config import ACCOUNTS_FILE, REGISTER_COUNT, REGISTER_CONCURRENT

app = Flask(__name__, static_folder='web_static', static_url_path='')
CORS(app)

# 全局任务状态
task_status = {
    "running": False,
    "progress": 0,
    "total": 0,
    "logs": [],
    "success_count": 0,
    "fail_count": 0,
}


def log_message(msg):
    """记录日志到任务状态"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    task_status["logs"].append(f"[{timestamp}] {msg}")
    # 只保留最近100条日志
    if len(task_status["logs"]) > 100:
        task_status["logs"] = task_status["logs"][-100:]


@app.route('/')
def index():
    """主页"""
    return send_from_directory('web_static', 'index.html')


@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """获取账号列表"""
    try:
        accounts = load_accounts()
        return jsonify({
            "success": True,
            "data": accounts,
            "total": len(accounts)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/<int:index>/check', methods=['POST'])
def check_single_account(index):
    """检查单个账号状态"""
    try:
        accounts = load_accounts()
        if index < 0 or index >= len(accounts):
            return jsonify({"success": False, "error": "账号不存在"}), 404
        
        account = accounts[index]
        email = account.get("email", "N/A")
        cookies = account.get("cookies", {})
        
        from core.session import make_session
        from core.config import BASE_URL
        
        try:
            s = make_session(cookies, seed=email)
            r = s.get(f"{BASE_URL}/api/account", timeout=15)
            
            if r.status_code == 200:
                account["health"] = "healthy"
                account["checked_at"] = datetime.now().isoformat()
                result = {"health": "healthy", "message": "账号健康"}
            elif r.status_code in (401, 403):
                account["health"] = "expired"
                account["checked_at"] = datetime.now().isoformat()
                result = {"health": "expired", "message": "账号已失效"}
            else:
                account["health"] = "error"
                account["checked_at"] = datetime.now().isoformat()
                result = {"health": "error", "message": f"错误 ({r.status_code})"}
            
            save_accounts(accounts)
            return jsonify({"success": True, "data": result})
            
        except Exception as e:
            account["health"] = "error"
            account["checked_at"] = datetime.now().isoformat()
            save_accounts(accounts)
            return jsonify({"success": False, "error": str(e)[:100]}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/<int:index>/mark', methods=['POST'])
def mark_account(index):
    """标记账号为已使用"""
    try:
        accounts = load_accounts()
        if index < 0 or index >= len(accounts):
            return jsonify({"success": False, "error": "账号不存在"}), 404
        
        # 添加或更新 used 字段
        accounts[index]["used"] = True
        accounts[index]["used_at"] = datetime.now().isoformat()
        
        save_accounts(accounts)
        return jsonify({"success": True, "message": "标记成功"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/<int:index>/unmark', methods=['POST'])
def unmark_account(index):
    """取消标记账号"""
    try:
        accounts = load_accounts()
        if index < 0 or index >= len(accounts):
            return jsonify({"success": False, "error": "账号不存在"}), 404
        
        # 移除 used 字段
        if "used" in accounts[index]:
            del accounts[index]["used"]
        if "used_at" in accounts[index]:
            del accounts[index]["used_at"]
        
        save_accounts(accounts)
        return jsonify({"success": True, "message": "取消标记成功"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/<int:index>', methods=['DELETE'])
def delete_account(index):
    """删除账号"""
    try:
        accounts = load_accounts()
        if index < 0 or index >= len(accounts):
            return jsonify({"success": False, "error": "账号不存在"}), 404
        
        deleted = accounts.pop(index)
        save_accounts(accounts)
        return jsonify({
            "success": True,
            "message": f"已删除账号 {deleted.get('email', 'N/A')}"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/register', methods=['POST'])
def start_register():
    """开始批量注册"""
    global task_status
    
    if task_status["running"]:
        return jsonify({"success": False, "error": "已有任务正在运行"}), 400
    
    data = request.json or {}
    count = data.get("count", REGISTER_COUNT)
    concurrent = data.get("concurrent", REGISTER_CONCURRENT)
    
    # 重置任务状态
    task_status = {
        "running": True,
        "progress": 0,
        "total": count,
        "logs": [],
        "success_count": 0,
        "fail_count": 0,
    }
    
    def run_register():
        """后台运行注册任务"""
        try:
            log_message(f"开始注册 {count} 个账号，并发数 {concurrent}")
            
            # 自定义回调统计成功数
            def on_success(account):
                task_status["success_count"] += 1
                task_status["progress"] += 1
                log_message(f"✓ 注册成功: {account.get('email', 'N/A')}")
            
            # 注册失败回调
            original_batch = register_batch
            
            def wrapped_register():
                try:
                    register_batch(
                        count=count,
                        concurrent=concurrent,
                        accounts_file=ACCOUNTS_FILE,
                        on_success=on_success,
                    )
                except Exception as e:
                    log_message(f"✗ 注册失败: {e}")
                    task_status["fail_count"] += 1
            
            wrapped_register()
            
            # 计算失败数（总数 - 成功数）
            task_status["fail_count"] = count - task_status["success_count"]
            log_message(f"注册完成！成功: {task_status['success_count']}, 失败: {task_status['fail_count']}")
            
        except Exception as e:
            log_message(f"✗ 注册任务异常: {e}")
        finally:
            task_status["running"] = False
            task_status["progress"] = task_status["total"]
    
    # 启动后台线程
    thread = threading.Thread(target=run_register, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": "注册任务已启动"})


@app.route('/api/register/status', methods=['GET'])
def get_register_status():
    """获取注册任务状态"""
    return jsonify({
        "success": True,
        "data": task_status
    })


@app.route('/api/check', methods=['POST'])
def start_check():
    """检查所有账号状态（不删除，只标记健康状态）"""
    global task_status
    
    if task_status["running"]:
        return jsonify({"success": False, "error": "已有任务正在运行"}), 400
    
    # 重置任务状态
    task_status = {
        "running": True,
        "progress": 0,
        "total": 0,
        "logs": [],
        "success_count": 0,
        "fail_count": 0,
    }
    
    def run_check():
        """后台运行检查任务"""
        try:
            accounts = load_accounts()
            task_status["total"] = len(accounts)
            log_message(f"开始检查 {len(accounts)} 个账号状态")
            
            from core.session import make_session
            from core.config import BASE_URL
            
            for i, account in enumerate(accounts):
                email = account.get("email", "N/A")
                cookies = account.get("cookies", {})
                
                try:
                    log_message(f"[{i+1}/{len(accounts)}] 检查 {email}")
                    s = make_session(cookies, seed=email)
                    r = s.get(f"{BASE_URL}/api/account", timeout=15)
                    
                    if r.status_code == 200:
                        account["health"] = "healthy"
                        account["checked_at"] = datetime.now().isoformat()
                        log_message(f"  ✓ 健康")
                        task_status["success_count"] += 1
                    elif r.status_code in (401, 403):
                        account["health"] = "expired"
                        account["checked_at"] = datetime.now().isoformat()
                        log_message(f"  ✗ 已失效")
                        task_status["fail_count"] += 1
                    else:
                        account["health"] = "error"
                        account["checked_at"] = datetime.now().isoformat()
                        log_message(f"  ? 错误 ({r.status_code})")
                        task_status["fail_count"] += 1
                        
                except Exception as e:
                    account["health"] = "error"
                    account["checked_at"] = datetime.now().isoformat()
                    log_message(f"  ✗ 异常: {str(e)[:50]}")
                    task_status["fail_count"] += 1
                
                task_status["progress"] = i + 1
            
            # 保存更新后的健康状态
            save_accounts(accounts)
            log_message(f"检查完成！健康: {task_status['success_count']}, 异常: {task_status['fail_count']}")
            
        except Exception as e:
            log_message(f"✗ 检查任务异常: {e}")
        finally:
            task_status["running"] = False
            task_status["progress"] = task_status["total"]
    
    # 启动后台线程
    thread = threading.Thread(target=run_check, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": "检查任务已启动"})


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置信息"""
    from core.config import PROXY_LIST
    return jsonify({
        "success": True,
        "data": {
            "accounts_file": ACCOUNTS_FILE,
            "default_count": REGISTER_COUNT,
            "default_concurrent": REGISTER_CONCURRENT,
            "proxy_count": len(PROXY_LIST),
        }
    })


@app.route('/api/test-ip', methods=['GET'])
def test_exit_ip():
    """测试出口IP"""
    try:
        import requests
        from core.config import PROXIES, PROXY
        
        result = {
            "proxy_used": PROXY if PROXY else "直连",
            "success": False,
        }
        
        # 测试IP检测
        try:
            proxies = PROXIES if PROXIES else None
            r = requests.get(
                'http://ip-api.com/json',
                params={'fields': 'query,country,city,isp,mobile,proxy,hosting'},
                proxies=proxies,
                timeout=15
            )
            
            if r.status_code == 200:
                d = r.json()
                result["success"] = True
                result["ip"] = d.get("query", "?")
                result["country"] = d.get("country", "?")
                result["city"] = d.get("city", "?")
                result["isp"] = d.get("isp", "?")
                
                # 判断IP类型
                if d.get("proxy"):
                    result["type"] = "代理/VPN"
                    result["quality"] = "低"
                elif d.get("hosting"):
                    result["type"] = "数据中心"
                    result["quality"] = "低"
                elif d.get("mobile"):
                    result["type"] = "移动网络"
                    result["quality"] = "高"
                else:
                    result["type"] = "住宅IP"
                    result["quality"] = "高"
            else:
                result["error"] = f"HTTP {r.status_code}"
                
        except requests.exceptions.ProxyError as e:
            result["error"] = f"代理错误: {str(e)[:100]}"
        except requests.exceptions.ConnectTimeout:
            result["error"] = "连接超时"
        except requests.exceptions.ReadTimeout:
            result["error"] = "读取超时"
        except Exception as e:
            result["error"] = f"{type(e).__name__}: {str(e)[:100]}"
        
        return jsonify({"success": True, "data": result})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/proxies', methods=['GET'])
def get_proxies():
    """获取代理列表"""
    try:
        from core.config import PROXY_LIST
        import os
        
        proxy_file = os.path.join(os.path.dirname(__file__), "proxy.text")
        proxies_data = []
        
        if os.path.exists(proxy_file):
            with open(proxy_file, 'r', encoding='utf-8') as f:
                for idx, line in enumerate(f):
                    line = line.strip()
                    # 跳过空行和注释行（但不跳过被注释的代理）
                    if not line or (line.startswith('#') and not line.startswith('# socks') and not line.startswith('# http')):
                        continue
                    
                    # 处理被注释的代理
                    if line.startswith('# '):
                        proxy = line[2:].strip()  # 去掉"# "
                        enabled = False
                    else:
                        proxy = line
                        enabled = True
                    
                    # 只添加有效的代理格式
                    if '://' in proxy:
                        proxies_data.append({
                            'index': idx,
                            'proxy': proxy,
                            'enabled': enabled
                        })
        
        return jsonify({
            "success": True,
            "data": proxies_data,
            "total": len(proxies_data),
            "enabled_count": len(PROXY_LIST)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/proxies', methods=['POST'])
def upload_proxies():
    """上传代理列表（覆盖proxy.text文件）"""
    try:
        import os
        
        data = request.json or {}
        proxies = data.get('proxies', [])
        
        if not proxies:
            return jsonify({"success": False, "error": "代理列表不能为空"}), 400
        
        proxy_file = os.path.join(os.path.dirname(__file__), "proxy.text")
        
        # 写入文件
        with open(proxy_file, 'w', encoding='utf-8') as f:
            f.write("# 代理列表\n")
            f.write("# \n")
            f.write("# 格式: socks5h://用户名:密码@主机:端口\n")
            f.write("# 示例: socks5h://user:pass@proxy.example.com:1080\n")
            f.write("#\n")
            f.write("# 留空或注释所有行 = 直连(不使用代理)\n\n")
            
            for proxy in proxies:
                proxy = proxy.strip()
                if proxy and not proxy.startswith('#'):
                    f.write(proxy + '\n')
        
        return jsonify({
            "success": True,
            "message": f"已上传 {len(proxies)} 个代理",
            "count": len(proxies)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/proxies/toggle', methods=['POST'])
def toggle_proxy():
    """切换代理启用状态（通过注释/取消注释）"""
    try:
        import os
        
        data = request.json or {}
        proxy_line = data.get('proxy', '')
        enable = data.get('enable', True)
        
        if not proxy_line:
            return jsonify({"success": False, "error": "代理不能为空"}), 400
        
        proxy_file = os.path.join(os.path.dirname(__file__), "proxy.text")
        
        if not os.path.exists(proxy_file):
            return jsonify({"success": False, "error": "代理文件不存在"}), 404
        
        # 读取文件
        with open(proxy_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 修改对应行
        modified = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            
            # 匹配代理行（无论是否注释）
            if stripped == proxy_line or stripped == f"# {proxy_line}":
                if enable and stripped.startswith('#'):
                    # 取消注释
                    lines[i] = proxy_line + '\n'
                    modified = True
                elif not enable and not stripped.startswith('#'):
                    # 添加注释
                    lines[i] = f"# {proxy_line}\n"
                    modified = True
                break
        
        if not modified:
            return jsonify({"success": False, "error": "未找到该代理"}), 404
        
        # 写回文件
        with open(proxy_file, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        return jsonify({
            "success": True,
            "message": f"代理已{'启用' if enable else '禁用'}"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/proxies/check', methods=['POST'])
def check_proxies():
    """检查代理可用性（测试所有代理，不只是启用的）"""
    try:
        import requests
        import os
        
        # 读取所有代理（包括被注释的）
        proxy_file = os.path.join(os.path.dirname(__file__), "proxy.text")
        all_proxies = []
        
        if os.path.exists(proxy_file):
            with open(proxy_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和纯注释行
                    if not line or (line.startswith('#') and not line.startswith('# socks') and not line.startswith('# http')):
                        continue
                    
                    # 提取代理地址
                    if line.startswith('# '):
                        proxy = line[2:].strip()
                    else:
                        proxy = line
                    
                    # 只添加有效的代理格式
                    if '://' in proxy:
                        all_proxies.append(proxy)
        
        results = []
        
        for proxy in all_proxies:
            result = {
                'proxy': proxy,
                'available': False,
                'error': None,
                'ip': None,
                'country': None,
                'city': None,
                'isp': None,
                'type': None,
                'latency': None
            }
            
            try:
                import time
                start = time.time()
                
                proxies = {'http': proxy, 'https': proxy}
                r = requests.get(
                    'http://ip-api.com/json?fields=query,country,city,isp,mobile,proxy,hosting',
                    proxies=proxies,
                    timeout=10
                )
                
                latency = int((time.time() - start) * 1000)  # 毫秒
                
                if r.status_code == 200:
                    data = r.json()
                    print(f"[DEBUG] ip-api返回数据: {data}")  # 调试日志
                    
                    result['available'] = True
                    result['ip'] = data.get('query', '?')
                    result['country'] = data.get('country', '?')
                    result['city'] = data.get('city', '?')
                    result['isp'] = data.get('isp', '?')
                    result['latency'] = latency
                    
                    # 判断IP类型
                    if data.get('proxy'):
                        result['type'] = '代理/VPN'
                    elif data.get('hosting'):
                        result['type'] = '数据中心'
                    elif data.get('mobile'):
                        result['type'] = '移动网络'
                    else:
                        result['type'] = '住宅IP'
                    
                    print(f"[DEBUG] result字典: {result}")  # 调试日志
                else:
                    result['error'] = f'HTTP {r.status_code}'
                    
            except requests.exceptions.ProxyError:
                result['error'] = '代理连接失败'
            except requests.exceptions.ConnectTimeout:
                result['error'] = '连接超时'
            except requests.exceptions.ReadTimeout:
                result['error'] = '读取超时'
            except Exception as e:
                result['error'] = str(e)[:50]
            
            results.append(result)
        
        available_count = sum(1 for r in results if r['available'])
        
        return jsonify({
            "success": True,
            "data": results,
            "total": len(results),
            "available": available_count,
            "unavailable": len(results) - available_count
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == '__main__':
    # 确保 web_static 目录存在
    os.makedirs('web_static', exist_ok=True)
    
    print("=" * 60)
    print("ClaudeX Web 管理界面")
    print("=" * 60)
    print(f"访问地址: http://127.0.0.1:5000")
    print(f"账号文件: {ACCOUNTS_FILE}")
    print("=" * 60)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
