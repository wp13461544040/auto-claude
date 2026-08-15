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
from registration.register import register_batch, register_batch_outlook
from core.config import ACCOUNTS_FILE, OUTLOOK_ACCOUNTS_FILE, REGISTER_COUNT, REGISTER_CONCURRENT

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


@app.route('/api/accounts/outlook', methods=['GET'])
def get_outlook_accounts():
    """获取Outlook账号列表"""
    try:
        # 使用统一的加载函数
        from account.storage import load_outlook_accounts
        
        accounts = load_outlook_accounts(OUTLOOK_ACCOUNTS_FILE)
        
        return jsonify({
            "success": True,
            "data": accounts,
            "total": len(accounts),
            "file": OUTLOOK_ACCOUNTS_FILE
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/outlook/<int:index>/check', methods=['POST'])
def check_outlook_account(index):
    """检查Outlook账号状态"""
    try:
        from account.storage import load_outlook_accounts, save_outlook_accounts
        
        accounts = load_outlook_accounts(OUTLOOK_ACCOUNTS_FILE)
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
            
            save_outlook_accounts(accounts, OUTLOOK_ACCOUNTS_FILE)
            return jsonify({"success": True, "data": result})
            
        except Exception as e:
            account["health"] = "error"
            account["checked_at"] = datetime.now().isoformat()
            save_outlook_accounts(accounts, OUTLOOK_ACCOUNTS_FILE)
            return jsonify({"success": False, "error": str(e)[:100]}), 500
            
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/outlook/<int:index>/mark', methods=['POST'])
def mark_outlook_account(index):
    """标记Outlook账号为已使用"""
    try:
        from account.storage import load_outlook_accounts, save_outlook_accounts
        
        accounts = load_outlook_accounts(OUTLOOK_ACCOUNTS_FILE)
        if index < 0 or index >= len(accounts):
            return jsonify({"success": False, "error": "账号不存在"}), 404
        
        # 添加或更新 used 字段
        accounts[index]["used"] = True
        accounts[index]["used_at"] = datetime.now().isoformat()
        
        save_outlook_accounts(accounts, OUTLOOK_ACCOUNTS_FILE)
        return jsonify({"success": True, "message": "标记成功"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/outlook/<int:index>/unmark', methods=['POST'])
def unmark_outlook_account(index):
    """取消标记Outlook账号"""
    try:
        from account.storage import load_outlook_accounts, save_outlook_accounts
        
        accounts = load_outlook_accounts(OUTLOOK_ACCOUNTS_FILE)
        if index < 0 or index >= len(accounts):
            return jsonify({"success": False, "error": "账号不存在"}), 404
        
        # 移除 used 字段
        if "used" in accounts[index]:
            del accounts[index]["used"]
        if "used_at" in accounts[index]:
            del accounts[index]["used_at"]
        
        save_outlook_accounts(accounts, OUTLOOK_ACCOUNTS_FILE)
        return jsonify({"success": True, "message": "取消标记成功"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/outlook/<int:index>', methods=['DELETE'])
def delete_outlook_account(index):
    """删除Outlook账号"""
    try:
        from account.storage import load_outlook_accounts, save_outlook_accounts
        
        accounts = load_outlook_accounts(OUTLOOK_ACCOUNTS_FILE)
        if index < 0 or index >= len(accounts):
            return jsonify({"success": False, "error": "账号不存在"}), 404
        
        deleted = accounts.pop(index)
        save_outlook_accounts(accounts, OUTLOOK_ACCOUNTS_FILE)
        return jsonify({
            "success": True,
            "message": f"已删除账号 {deleted.get('email', 'N/A')}"
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


@app.route('/api/accounts/delete-expired', methods=['POST'])
def delete_expired_accounts():
    """删除失效账号"""
    try:
        accounts = load_accounts()
        original_count = len(accounts)
        
        # 只保留非失效的账号（health != 'expired'）
        accounts = [acc for acc in accounts if acc.get('health') != 'expired']
        
        deleted_count = original_count - len(accounts)
        save_accounts(accounts)
        
        return jsonify({
            "success": True,
            "count": deleted_count,
            "message": f"已删除 {deleted_count} 个失效账号"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/delete-used', methods=['POST'])
def delete_used_accounts():
    """删除已使用账号"""
    try:
        accounts = load_accounts()
        original_count = len(accounts)
        
        # 统计used=true的账号数量
        used_count = len([acc for acc in accounts if acc.get('used', False)])
        print(f"[DEBUG] 总账号数: {original_count}, 已使用账号数: {used_count}")
        
        # 只保留未使用的账号（used != true）
        accounts = [acc for acc in accounts if not acc.get('used', False)]
        
        deleted_count = original_count - len(accounts)
        save_accounts(accounts)
        
        print(f"[DEBUG] 删除后剩余: {len(accounts)}, 实际删除: {deleted_count}")
        
        return jsonify({
            "success": True,
            "count": deleted_count,
            "message": f"已删除 {deleted_count} 个已使用账号"
        })
    except Exception as e:
        print(f"[ERROR] 删除已使用账号失败: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/delete-all', methods=['POST'])
def delete_all_accounts():
    """批量删除所有账号"""
    try:
        accounts = load_accounts()
        count = len(accounts)
        
        # 清空账号列表
        save_accounts([])
        
        log_message(f"批量删除所有账号: 删除{count}个")
        
        return jsonify({
            "success": True,
            "count": count,
            "message": f"已删除 {count} 个账号"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/outlook/delete-expired', methods=['POST'])
def delete_expired_outlook_accounts():
    """批量删除失效的Outlook账号"""
    try:
        from account.storage import load_outlook_accounts, save_outlook_accounts
        
        accounts = load_outlook_accounts(OUTLOOK_ACCOUNTS_FILE)
        original_count = len(accounts)
        
        # 只保留非失效的账号（health != 'expired'）
        accounts = [acc for acc in accounts if acc.get('health') != 'expired']
        
        deleted_count = original_count - len(accounts)
        save_outlook_accounts(accounts, OUTLOOK_ACCOUNTS_FILE)
        
        log_message(f"批量删除Outlook失效账号: 删除{deleted_count}个, 剩余{len(accounts)}个")
        
        return jsonify({
            "success": True,
            "count": deleted_count,
            "message": f"已删除 {deleted_count} 个失效的Outlook账号"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/outlook/delete-all', methods=['POST'])
def delete_all_outlook_accounts():
    """批量删除所有Outlook账号"""
    try:
        from account.storage import load_outlook_accounts, save_outlook_accounts
        
        accounts = load_outlook_accounts(OUTLOOK_ACCOUNTS_FILE)
        count = len(accounts)
        
        # 清空账号列表
        save_outlook_accounts([], OUTLOOK_ACCOUNTS_FILE)
        
        log_message(f"批量删除所有Outlook账号: 删除{count}个")
        
        return jsonify({
            "success": True,
            "count": count,
            "message": f"已删除 {count} 个Outlook账号"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/accounts/outlook/export', methods=['GET'])
def export_outlook_accounts():
    """导出Outlook账号的email、password、sessionKey"""
    try:
        from account.storage import load_outlook_accounts
        
        accounts = load_outlook_accounts(OUTLOOK_ACCOUNTS_FILE)
        
        # 提取需要的字段
        exported_data = []
        for account in accounts:
            exported_data.append({
                'email': account.get('email', ''),
                'password': account.get('password', ''),
                'sessionKey': account.get('cookies', {}).get('sessionKey', '')
            })
        
        return jsonify({
            "success": True,
            "data": exported_data,
            "count": len(exported_data)
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
            # 重新加载配置（确保使用最新的邮箱服务配置）
            import importlib
            import core.config
            from registration import register as reg_module
            
            importlib.reload(core.config)
            importlib.reload(reg_module)
            
            # 重新导入register_batch（使用新配置）
            from registration.register import register_batch as fresh_register_batch
            
            log_message(f"开始注册 {count} 个账号，并发数 {concurrent}")
            log_message(f"当前邮箱服务: {core.config.EMAIL_SERVICE}")
            
            # 自定义回调统计成功数
            def on_success(account):
                task_status["success_count"] += 1
                task_status["progress"] += 1
                log_message(f"✓ 注册成功: {account.get('email', 'N/A')}")
            
            # 使用重新加载的register_batch
            fresh_register_batch(
                count=count,
                concurrent=concurrent,
                accounts_file=ACCOUNTS_FILE,
                on_success=on_success,
            )
            
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


@app.route('/api/register/outlook', methods=['POST'])
def start_register_outlook():
    """开始Outlook批量注册(保存到单独文件)"""
    global task_status
    
    if task_status["running"]:
        return jsonify({"success": False, "error": "已有任务正在运行"}), 400
    
    data = request.json or {}
    outlook_lines = data.get("outlook_lines", [])
    concurrent = data.get("concurrent", 1)  # 忽略此参数，强制单线程
    
    if not outlook_lines:
        return jsonify({"success": False, "error": "Outlook配置列表不能为空"}), 400
    
    # 忽略并发参数提示
    if concurrent > 1:
        print(f"[警告] Outlook注册忽略并发参数 {concurrent}，强制使用单线程")
    
    # 验证格式
    try:
        from registration.outlook import parse_outlook_line
        for line in outlook_lines:
            parse_outlook_line(line)
    except Exception as e:
        return jsonify({"success": False, "error": f"配置格式错误: {e}"}), 400
    
    # 重置任务状态
    task_status = {
        "running": True,
        "progress": 0,
        "total": len(outlook_lines),
        "logs": [],
        "success_count": 0,
        "fail_count": 0,
    }
    
    def run_register():
        """后台运行Outlook注册任务"""
        try:
            log_message(f"开始Outlook注册 {len(outlook_lines)} 个账号（单线程执行）")
            log_message(f"保存到文件: {OUTLOOK_ACCOUNTS_FILE}")
            log_message(f"⚠️  Outlook注册强制单线程，避免IMAP/Graph频率限制")
            
            # 自定义回调统计成功数
            def on_success(account):
                task_status["success_count"] += 1
                task_status["progress"] += 1
                log_message(f"✓ 注册成功: {account.get('email', 'N/A')}")
            
            register_batch_outlook(
                outlook_lines=outlook_lines,
                accounts_file=OUTLOOK_ACCOUNTS_FILE,  # 使用单独的文件
                on_success=on_success,
            )
            
            # 计算失败数
            task_status["fail_count"] = len(outlook_lines) - task_status["success_count"]
            log_message(f"Outlook注册完成！成功: {task_status['success_count']}, 失败: {task_status['fail_count']}")
            log_message(f"账号已保存到: {OUTLOOK_ACCOUNTS_FILE}")
            
        except Exception as e:
            log_message(f"✗ Outlook注册任务异常: {e}")
        finally:
            task_status["running"] = False
            task_status["progress"] = task_status["total"]
    
    # 启动后台线程
    thread = threading.Thread(target=run_register, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": "Outlook注册任务已启动"})


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


@app.route('/api/check/outlook', methods=['POST'])
def start_check_outlook():
    """批量检查Outlook账号状态"""
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
        """后台运行Outlook账号检查任务"""
        try:
            from account.storage import load_outlook_accounts, save_outlook_accounts
            
            accounts = load_outlook_accounts(OUTLOOK_ACCOUNTS_FILE)
            task_status["total"] = len(accounts)
            log_message(f"开始检查 {len(accounts)} 个Outlook账号状态")
            
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
            save_outlook_accounts(accounts, OUTLOOK_ACCOUNTS_FILE)
            log_message(f"Outlook账号检查完成！健康: {task_status['success_count']}, 异常: {task_status['fail_count']}")
            
        except Exception as e:
            log_message(f"✗ Outlook检查任务异常: {e}")
        finally:
            task_status["running"] = False
            task_status["progress"] = task_status["total"]
    
    # 启动后台线程
    thread = threading.Thread(target=run_check, daemon=True)
    thread.start()
    
    return jsonify({"success": True, "message": "Outlook检查任务已启动"})


@app.route('/api/config', methods=['GET'])
def get_config():
    """获取配置信息"""
    from core.config import (
        PROXY_LIST, EMAIL_SERVICE,
        MOEMAIL_API_KEY, MOEMAIL_BASE_URL,
        REMAIL_API_KEY, REMAIL_API_URL, REMAIL_PROJECT_ID,
        REMAIL_PRODUCT_ID, REMAIL_MODE, REMAIL_SUFFIX
    )
    return jsonify({
        "success": True,
        "data": {
            "accounts_file": ACCOUNTS_FILE,
            "default_count": REGISTER_COUNT,
            "default_concurrent": REGISTER_CONCURRENT,
            "proxy_count": len(PROXY_LIST),
            "email_service": EMAIL_SERVICE,
            "moemail": {
                "api_key": MOEMAIL_API_KEY,  # 返回完整API Key
                "base_url": MOEMAIL_BASE_URL,
                "configured": bool(MOEMAIL_API_KEY and MOEMAIL_BASE_URL)
            },
            "remail": {
                "api_key": REMAIL_API_KEY,  # 返回完整API Key
                "api_url": REMAIL_API_URL,
                "project_id": REMAIL_PROJECT_ID,
                "product_id": REMAIL_PRODUCT_ID,
                "mode": REMAIL_MODE,
                "suffix": REMAIL_SUFFIX,
                "configured": bool(REMAIL_API_KEY and REMAIL_PROJECT_ID and REMAIL_PRODUCT_ID)
            }
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
        
        # 处理并规范化代理格式
        normalized_proxies = []
        for proxy in proxies:
            proxy = proxy.strip()
            if not proxy or proxy.startswith('#'):
                continue
            
            # 自动补全协议前缀
            if '://' not in proxy:
                # 如果没有协议前缀，自动添加socks5h://
                proxy = f'socks5h://{proxy}'
            
            normalized_proxies.append(proxy)
        
        # 写入文件
        with open(proxy_file, 'w', encoding='utf-8') as f:
            f.write("# 代理列表\n")
            f.write("# \n")
            f.write("# 格式: socks5h://用户名:密码@主机:端口\n")
            f.write("# 示例: socks5h://user:pass@proxy.example.com:1080\n")
            f.write("#\n")
            f.write("# 留空或注释所有行 = 直连(不使用代理)\n\n")
            
            for proxy in normalized_proxies:
                f.write(proxy + '\n')
        
        return jsonify({
            "success": True,
            "message": f"已上传 {len(normalized_proxies)} 个代理",
            "count": len(normalized_proxies)
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


@app.route('/api/proxies/delete', methods=['POST'])
def delete_proxy():
    """删除代理"""
    try:
        import os
        
        data = request.json or {}
        proxy_line = data.get('proxy', '')
        
        if not proxy_line:
            return jsonify({"success": False, "error": "代理不能为空"}), 400
        
        proxy_file = os.path.join(os.path.dirname(__file__), "proxy.text")
        
        if not os.path.exists(proxy_file):
            return jsonify({"success": False, "error": "代理文件不存在"}), 404
        
        # 读取文件
        with open(proxy_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 过滤掉要删除的行
        new_lines = []
        deleted = False
        for line in lines:
            stripped = line.strip()
            # 匹配代理行（无论是否注释）
            if stripped == proxy_line or stripped == f"# {proxy_line}":
                deleted = True
                continue
            new_lines.append(line)
        
        if not deleted:
            return jsonify({"success": False, "error": "未找到该代理"}), 404
        
        # 写回文件
        with open(proxy_file, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        return jsonify({
            "success": True,
            "message": "代理已删除"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/email-config', methods=['POST'])
def update_email_config():
    """更新邮箱服务配置(动态生效,无需重启)"""
    try:
        import os
        
        data = request.json or {}
        service = data.get('service', 'moemail')
        config = data.get('config', {})
        
        # 读取.env文件
        env_file = os.path.join(os.path.dirname(__file__), ".env")
        env_lines = []
        
        if os.path.exists(env_file):
            with open(env_file, 'r', encoding='utf-8') as f:
                env_lines = f.readlines()
        
        # 更新EMAIL_SERVICE
        updated = False
        for i, line in enumerate(env_lines):
            if line.strip().startswith('EMAIL_SERVICE='):
                env_lines[i] = f'EMAIL_SERVICE={service}\n'
                updated = True
                break
        
        if not updated:
            env_lines.append(f'EMAIL_SERVICE={service}\n')
        
        # 如果是moemail，更新moemail配置
        if service == 'moemail':
            moemail_keys = {}
            
            # 只更新非空的值
            if config.get('api_key'):
                moemail_keys['MOEMAIL_API_KEY'] = config['api_key']
            if 'base_url' in config:  # 允许空字符串
                moemail_keys['MOEMAIL_BASE_URL'] = config['base_url']
            
            for key, value in moemail_keys.items():
                updated = False
                for i, line in enumerate(env_lines):
                    if line.strip().startswith(f'{key}='):
                        env_lines[i] = f'{key}={value}\n'
                        updated = True
                        break
                
                if not updated:
                    env_lines.append(f'{key}={value}\n')
        
        # 如果是remail，更新remail配置
        if service == 'remail':
            remail_keys = {}
            
            # 只更新非空的值
            if config.get('api_key'):
                remail_keys['REMAIL_API_KEY'] = config['api_key']
            if 'api_url' in config:
                remail_keys['REMAIL_API_URL'] = config.get('api_url', 'https://remail.aishop6.com')
            if 'project_id' in config:
                remail_keys['REMAIL_PROJECT_ID'] = str(config['project_id'])
            if 'product_id' in config:
                remail_keys['REMAIL_PRODUCT_ID'] = str(config['product_id'])
            if 'mode' in config:
                remail_keys['REMAIL_MODE'] = config.get('mode', 'package')
            if 'suffix' in config:
                remail_keys['REMAIL_SUFFIX'] = config.get('suffix', '')
            
            for key, value in remail_keys.items():
                updated = False
                for i, line in enumerate(env_lines):
                    if line.strip().startswith(f'{key}='):
                        env_lines[i] = f'{key}={value}\n'
                        updated = True
                        break
                
                if not updated:
                    env_lines.append(f'{key}={value}\n')
        
        # 写回文件
        with open(env_file, 'w', encoding='utf-8') as f:
            f.writelines(env_lines)
        
        # ========== 关键:动态重载配置 ==========
        # 1. 重新加载环境变量到os.environ
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
        
        # 2. 重新加载所有相关模块(确保用新配置)
        import importlib
        import sys
        
        # 重载配置模块
        import core.config
        importlib.reload(core.config)
        
        # 重载邮箱服务模块
        import registration.moemail
        import registration.remail
        import registration.register
        importlib.reload(registration.moemail)
        importlib.reload(registration.remail)
        importlib.reload(registration.register)
        
        # 清除模块缓存,确保下次import用新的
        for module_name in list(sys.modules.keys()):
            if module_name.startswith('registration.') or module_name.startswith('core.config'):
                pass  # 已经reload了,不需要删除
        
        log_message(f"✓ 邮箱服务已切换到 {service}")
        log_message(f"✓ 配置已动态生效,无需重启服务")
        
        return jsonify({
            "success": True,
            "message": f"已切换到 {service} 邮箱服务,配置已动态生效(无需重启)"
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/remail/projects', methods=['POST'])
def get_remail_projects():
    """获取Remail项目列表"""
    try:
        data = request.json or {}
        api_key = data.get('api_key', '')
        api_url = data.get('api_url', 'https://remail.aishop6.com')
        
        if not api_key:
            return jsonify({
                "success": False,
                "error": "缺少API Key"
            }), 400
        
        # 创建临时客户端(不需要project_id和product_id)
        import requests
        s = requests.Session()
        s.trust_env = False
        s.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Python-ClaudeX/1.0"
        })
        
        url = f"{api_url.rstrip('/')}/v1/open/projects"
        params = {"offset": 0, "limit": 100}
        
        print(f"[DEBUG] 请求URL: {url}")
        print(f"[DEBUG] 请求参数: {params}")
        print(f"[DEBUG] 请求头: Authorization=Bearer {api_key[:10]}...")
        
        r = s.get(url, params=params, timeout=15)
        
        print(f"[DEBUG] 响应状态码: {r.status_code}")
        print(f"[DEBUG] 响应内容: {r.text[:500]}")
        
        r.raise_for_status()
        result = r.json()
        
        projects = result.get("items", [])
        
        print(f"[DEBUG] 获取到 {len(projects)} 个项目")
        
        return jsonify({
            "success": True,
            "data": {
                "projects": [
                    {
                        "id": p.get("id"),
                        "name": p.get("name", "未命名"),
                        "description": p.get("description", ""),
                        "products": p.get("products", [])
                    }
                    for p in projects
                ]
            }
        })
    except requests.exceptions.HTTPError as e:
        error_msg = f"HTTP错误 {e.response.status_code}: {e.response.text[:200]}"
        print(f"[ERROR] {error_msg}")
        return jsonify({
            "success": False,
            "error": error_msg
        }), 500
    except requests.exceptions.RequestException as e:
        error_msg = f"请求失败: {str(e)[:200]}"
        print(f"[ERROR] {error_msg}")
        return jsonify({
            "success": False,
            "error": error_msg
        }), 500
    except Exception as e:
        import traceback
        error_msg = f"异常: {str(e)[:200]}"
        print(f"[ERROR] {error_msg}")
        traceback.print_exc()
        return jsonify({
            "success": False,
            "error": error_msg
        }), 500


@app.route('/api/remail/test', methods=['POST'])
def test_remail():
    """测试Remail连接(创建临时邮箱)"""
    try:
        data = request.json or {}
        api_key = data.get('api_key', '')
        project_id = int(data.get('project_id', 0))
        product_id = int(data.get('product_id', 0))
        api_url = data.get('api_url', 'https://remail.aishop6.com')
        mode = data.get('mode', 'package')
        suffix = data.get('suffix', '')
        
        if not api_key or not project_id or not product_id:
            return jsonify({
                "success": False,
                "error": "缺少必需参数"
            }), 400
        
        from registration.remail import RemailClient
        
        # 创建客户端并尝试创建邮箱
        client = RemailClient(
            api_key=api_key,
            project_id=project_id,
            product_id=product_id,
            api_url=api_url,
            mode=mode,
            suffix=suffix
        )
        
        # 尝试创建邮箱测试
        box = client.create_mailbox(name="test")
        
        return jsonify({
            "success": True,
            "message": "连接成功，已创建测试邮箱",
            "data": {
                "email": box["email"],
                "order_no": box["orderNo"]
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)[:200]
        }), 500


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


# ============ Outlook 取件 API ============

@app.route('/api/outlook/add', methods=['POST'])
def add_outlook_accounts_api():
    """批量添加 Outlook 账号"""
    try:
        from account.storage import add_outlook_accounts
        
        data = request.json or {}
        lines = data.get('lines', [])
        
        if not lines:
            return jsonify({"success": False, "error": "账号列表不能为空"}), 400
        
        # 拼接成多行文本
        text = "\n".join(lines)
        result = add_outlook_accounts(text)
        
        log_message(f"添加 Outlook 账号: 新增{result['added']}个, 总计{result['total']}个")
        
        return jsonify({
            "success": True,
            "data": result,
            "message": f"添加成功: 新增{result['added']}个"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/outlook/wait-otp', methods=['POST'])
def wait_outlook_otp_api():
    """等待 Outlook 验证码"""
    try:
        from registration.outlook_otp import wait_for_outlook_otp, OutlookOTPError
        from core.config import get_next_proxy
        
        data = request.json or {}
        email = data.get('email', '')
        client_id = data.get('client_id', '')
        refresh_token = data.get('refresh_token', '')
        mode = data.get('mode', 'imap')
        timeout = data.get('timeout', 120)
        interval = data.get('interval', 5)
        before_count = data.get('before_count')
        
        if not email or not client_id or not refresh_token:
            return jsonify({
                "success": False,
                "error": "缺少必需参数: email, client_id, refresh_token"
            }), 400
        
        proxy = get_next_proxy()
        
        log_message(f"[Outlook] 开始等待验证码: {email} (模式:{mode})")
        
        code = wait_for_outlook_otp(
            email=email,
            client_id=client_id,
            refresh_token=refresh_token,
            mode=mode,
            timeout=timeout,
            interval=interval,
            before_count=before_count,
            proxy=proxy
        )
        
        log_message(f"[Outlook] 成功收到验证码: {code}")
        
        return jsonify({
            "success": True,
            "data": {"code": code},
            "message": f"验证码: {code}"
        })
    
    except TimeoutError as e:
        log_message(f"[Outlook] 等待超时: {e}")
        return jsonify({"success": False, "error": str(e)}), 408
    
    except OutlookOTPError as e:
        log_message(f"[Outlook] 取件失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    
    except Exception as e:
        log_message(f"[Outlook] 未知错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/outlook/inbox-count', methods=['POST'])
def get_outlook_inbox_count_api():
    """获取 Outlook 收件箱邮件数量"""
    try:
        from registration.outlook_otp import get_outlook_inbox_count, OutlookOTPError
        from core.config import get_next_proxy
        
        data = request.json or {}
        email = data.get('email', '')
        client_id = data.get('client_id', '')
        refresh_token = data.get('refresh_token', '')
        
        if not email or not client_id or not refresh_token:
            return jsonify({
                "success": False,
                "error": "缺少必需参数: email, client_id, refresh_token"
            }), 400
        
        proxy = get_next_proxy()
        
        count = get_outlook_inbox_count(
            email=email,
            client_id=client_id,
            refresh_token=refresh_token,
            proxy=proxy
        )
        
        return jsonify({
            "success": True,
            "data": {"count": count},
            "message": f"收件箱邮件数: {count}"
        })
    
    except OutlookOTPError as e:
        return jsonify({"success": False, "error": str(e)}), 500
    
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/outlook/test-token', methods=['POST'])
def test_outlook_token_api():
    """测试 Outlook Token 刷新"""
    try:
        from registration.outlook_otp import refresh_outlook_token, OutlookOTPError
        from core.config import get_next_proxy
        
        data = request.json or {}
        email = data.get('email', '')
        client_id = data.get('client_id', '')
        refresh_token = data.get('refresh_token', '')
        mode = data.get('mode', 'imap')
        
        if not email or not client_id or not refresh_token:
            return jsonify({
                "success": False,
                "error": "缺少必需参数: email, client_id, refresh_token"
            }), 400
        
        proxy = get_next_proxy()
        
        log_message(f"[Outlook] 测试 Token 刷新: {email} (模式:{mode})")
        
        access_token = refresh_outlook_token(
            email=email,
            client_id=client_id,
            refresh_token=refresh_token,
            mode=mode,
            proxy=proxy
        )
        
        # 只返回前 10 个字符 (安全考虑)
        token_preview = access_token[:10] + "..." if len(access_token) > 10 else access_token
        
        log_message(f"[Outlook] Token 刷新成功: {token_preview}")
        
        return jsonify({
            "success": True,
            "data": {"token_preview": token_preview},
            "message": "Token 刷新成功"
        })
    
    except OutlookOTPError as e:
        log_message(f"[Outlook] Token 刷新失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    
    except Exception as e:
        log_message(f"[Outlook] 未知错误: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/reload-modules', methods=['POST'])
def reload_modules():
    """热重载模块 (调试用)"""
    try:
        import importlib
        import sys
        
        # 重载 outlook_otp 模块
        if 'registration.outlook_otp' in sys.modules:
            import registration.outlook_otp
            importlib.reload(registration.outlook_otp)
            log_message("[系统] outlook_otp 模块已重载")
        
        # 重载 account.storage 模块
        if 'account.storage' in sys.modules:
            import account.storage
            importlib.reload(account.storage)
            log_message("[系统] account.storage 模块已重载")
        
        return jsonify({
            "success": True,
            "message": "模块热重载成功"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
