#!/usr/bin/env python3
"""最简单的Remail测试 - 用完删除！"""

# 直接在这里填你的配置
REMAIL_API_KEY = "你的完整API_KEY"  # 在这里填写
REMAIL_API_URL = "https://remail.aishop6.com"
REMAIL_PROJECT_ID = 0  # 从API获取后再填
REMAIL_PRODUCT_ID = 0  # 从API获取后再填

print("=" * 60)
print("Remail 最简测试")
print("=" * 60)

if REMAIL_API_KEY == "你的完整API_KEY":
    print("\n❌ 请先在脚本中填写你的API Key!")
    print("   打开 test_remail_direct.py")
    print("   修改 REMAIL_API_KEY = \"你的完整API_KEY\"")
    input("\n按回车退出...")
    exit(1)

# 测试1: 直接用registration.remail模块
print("\n[测试1] 使用RemailClient获取项目...")
try:
    from registration.remail import RemailClient
    
    # 创建临时客户端获取项目(不需要project_id和product_id)
    import requests
    s = requests.Session()
    s.trust_env = False
    s.headers.update({
        "Authorization": f"Bearer {REMAIL_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Python-Test/1.0"
    })
    
    url = f"{REMAIL_API_URL.rstrip('/')}/v1/open/projects"
    params = {"offset": 0, "limit": 10}
    
    print(f"请求URL: {url}")
    print(f"API Key: {REMAIL_API_KEY[:15]}...")
    
    r = s.get(url, params=params, timeout=15)
    print(f"响应状态: {r.status_code}")
    
    if r.status_code == 401:
        print("\n❌ 401错误 - API Key无效或过期")
        print(f"响应: {r.text[:300]}")
    elif r.status_code == 403:
        print("\n❌ 403错误 - 权限不足")
        print(f"响应: {r.text[:300]}")
    elif r.status_code == 200:
        result = r.json()
        projects = result.get("items", [])
        
        print(f"\n✓ 成功! 获取到 {len(projects)} 个项目\n")
        
        if not projects:
            print("⚠️ 项目列表为空")
        else:
            for i, proj in enumerate(projects[:5], 1):
                proj_id = proj.get("id")
                proj_name = proj.get("name", "未命名")
                products = proj.get("products", [])
                
                print(f"[{i}] {proj_name}")
                print(f"    项目ID: {proj_id}")
                print(f"    产品数: {len(products)}")
                
                if products:
                    for prod in products[:3]:
                        print(f"      - {prod.get('name', '未命名')} (ID: {prod.get('id')})")
                print()
            
            # 提示用户更新配置
            if projects and projects[0].get("products"):
                first_proj = projects[0]
                first_prod = first_proj["products"][0]
                
                print("=" * 60)
                print("🎯 复制下面的配置到你的.env文件:")
                print("=" * 60)
                print(f"EMAIL_SERVICE=remail")
                print(f"REMAIL_API_KEY={REMAIL_API_KEY}")
                print(f"REMAIL_API_URL={REMAIL_API_URL}")
                print(f"REMAIL_PROJECT_ID={first_proj['id']}")
                print(f"REMAIL_PRODUCT_ID={first_prod['id']}")
                print(f"REMAIL_MODE=package")
                print(f"REMAIL_SUFFIX=")
                print("=" * 60)
                
                # 测试创建邮箱
                print("\n[测试2] 创建测试邮箱...")
                
                try:
                    client = RemailClient(
                        api_key=REMAIL_API_KEY,
                        project_id=first_proj['id'],
                        product_id=first_prod['id'],
                        api_url=REMAIL_API_URL,
                        mode="package"
                    )
                    
                    box = client.create_mailbox("test")
                    
                    print(f"\n✓ 邮箱创建成功!")
                    print(f"  邮箱: {box['email']}")
                    print(f"  订单号: {box['orderNo']}")
                    
                except Exception as e2:
                    print(f"\n❌ 创建邮箱失败: {e2}")
                    import traceback
                    traceback.print_exc()
    else:
        print(f"\n❌ HTTP {r.status_code} 错误")
        print(f"响应: {r.text[:300]}")
        
except ImportError as e:
    print(f"\n❌ 导入失败: {e}")
    print("请确保在claudex项目目录运行此脚本")
except Exception as e:
    print(f"\n❌ 错误: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
input("按回车退出...")
