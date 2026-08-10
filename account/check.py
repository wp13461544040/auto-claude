import json
import os
import tempfile
import time
from requests.exceptions import SSLError, HTTPError

from core.config import ACCOUNTS_FILE, BASE_URL
from core.console import print_log
from core.session import make_session

from .storage import load_accounts


def _save_accounts(accounts, filepath):
    """原子写回账号列表到文件。"""
    directory = os.path.dirname(os.path.abspath(filepath))
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=directory, delete=False
        ) as f:
            json.dump(accounts, f, ensure_ascii=False, indent=2)
            f.write("\n")
            temp_path = f.name
        os.replace(temp_path, filepath)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


def _make_direct_session(cookies=None, seed=None):
    """Check 命令使用与注册相同的 session（含代理配置）。"""
    return make_session(cookies=cookies, seed=seed)


def _fetch_with_retry(s, url, params=None, max_retries=3):
    """发起请求，SSL 错误时重试。"""
    for attempt in range(max_retries):
        try:
            r = s.get(url, params=params, timeout=15)
            r.raise_for_status()
            # 返回 HTML 说明 session 失效（302 重定向到登录页后返回 200 HTML）
            ct = r.headers.get("content-type", "")
            if "json" not in ct:
                e = HTTPError(response=r)
                e.response.status_code = 401  # 标记为未认证
                raise e
            return r.json()
        except SSLError:
            if attempt < max_retries - 1:
                time.sleep(1 * (attempt + 1))
                continue
            raise
        except HTTPError:
            raise


def _fetch_account(s):
    return _fetch_with_retry(s, f"{BASE_URL}/api/account",
                             params={"statsig_hashing_algorithm": "djb2"})


def _fetch_user_access(s, org_uuid):
    return _fetch_with_retry(s, f"{BASE_URL}/api/bootstrap/{org_uuid}/current_user_access")


def _parse_plan(org):
    tier = org.get("rate_limit_tier", "")
    if tier == "default_claude_ai":
        return "Free"
    if "pro" in tier.lower():
        return "Pro"
    if "team" in tier.lower():
        return "Team"
    return tier or "Unknown"


def _parse_model_limits(acct_data):
    mems = acct_data.get("memberships", [])
    if not mems:
        return []
    cfg = mems[0]["organization"].get("claude_ai_bootstrap_models_config", [])
    return [{"model": m.get("model"), "hard_limit": m.get("hard_limit")} for m in cfg]


def _parse_features(access_data):
    return {f["feature"]: f["status"] for f in access_data.get("features", [])}


def check_usage(accounts_file=ACCOUNTS_FILE):
    """查询并打印账号文件中所有账号的用量状态，自动移除有问题的账号。"""
    accounts = load_accounts(accounts_file)
    if not accounts:
        print_log("未找到账号，请先运行: python main.py register")
        return

    print_log(f"共找到 {len(accounts)} 个账号\n")

    stats = {"ok": 0, "expired": 0, "error": 0}
    good_accounts = []  # 检查通过的账号

    for i, record in enumerate(accounts, 1):
        email    = record["email"]
        org_uuid = record.get("org_uuid", "")
        cookies  = record.get("cookies", {})

        print_log(f"[{i}/{len(accounts)}] {email}")
        try:
            s    = _make_direct_session(cookies, seed=email)
            acct = _fetch_account(s)
            mems = acct.get("memberships", [])

            plan   = _parse_plan(mems[0]["organization"]) if mems else "Unknown"
            limits = _parse_model_limits(acct)

            features   = {}
            if org_uuid:
                access   = _fetch_user_access(s, org_uuid)
                features = _parse_features(access)

            chat_status = features.get("chat", "unknown")
            status      = "active" if chat_status == "available" else chat_status
            icon        = "[OK]" if status == "active" else "[ERR]"

            print_log(f"  {icon} 状态: {status}  套餐: {plan}")
            for m in limits[:3]:  # 仅显示前 3 个模型
                limit_str = f"{m['hard_limit']:,}" if m["hard_limit"] else "unlimited"
                print_log(f"    {m['model']:<34} {limit_str}")
            if len(limits) > 3:
                print_log(f"    ... (共 {len(limits)} 个模型)")
            stats["ok"] += 1
            good_accounts.append(record)

        except HTTPError as e:
            code = getattr(e.response, 'status_code', 0)
            if code in (401, 403):
                print_log(f"  [EXPIRED] 会话已失效 ({code})，已移除")
                stats["expired"] += 1
            else:
                print_log(f"  [ERR] HTTP {code}，已移除")
                stats["error"] += 1
        except Exception as e:
            err_msg = str(e)
            if "SSLEOFError" in err_msg or "SSL" in err_msg:
                print_log("  [ERR] SSL 连接失败（代理问题），已移除")
            else:
                print_log(f"  [ERR] {err_msg[:80]}，已移除")
            stats["error"] += 1

        print_log()

    removed = len(accounts) - len(good_accounts)
    print_log(
        f"汇总: {stats['ok']} 正常, {stats['expired']} 失效, "
        f"{stats['error']} 错误"
    )
    if removed > 0:
        _save_accounts(good_accounts, accounts_file)
        print_log(f"已从 {accounts_file} 移除 {removed} 个有问题的账号，剩余 {len(good_accounts)} 个")
    else:
        print_log("所有账号均正常，无需移除")

    if stats["expired"] > 0:
        print_log("\n提示: 可运行 python main.py register 补充新账号")
