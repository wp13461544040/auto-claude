#!/usr/bin/env python3
"""
Remail API 调试脚本 - 直接测试API连接
用完立即删除！
"""

import sys
import requests
import json

def test_remail_api():
    """直接测试Remail API"""
    
    print("=" * 60)
    print("Remail API 调试工具")
    print("=" * 60)
    
    # 获取用户输入
    api_key = input("\n请输入 API Key: ").strip()
    if not api_key:
        print("❌ API Key 不能为空")
        return
    
    api_url = input("请输入 API URL (直接回车使用默认): ").strip()
    if not api_url:
        api_url = "https://remail.aishop6.com"
    
    print(f"\n使用配置:")
    print(f"  API Key: {api_key[:10]}...")
    print(f"  API URL: {api_url}")
    
    # 测试1: 获取项目列表
    print("\n" + "=" * 60)
    print("测试1: 获取项目列表")
    print("=" * 60)
    
    try:
        s = requests.Session()
        s.trust_env = False
        s.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Python-Debug/1.0"
        })
        
        url = f"{api_url.rstrip('/')}/v1/open/projects"
        params = {"offset": 0, "limit": 10}
        
        print(f"\n→ 请求URL: {url}")
        print(f"→ 请求参数: {params}")
        print(f"→ 请求头: Authorization=Bearer {api_key[:10]}...")
        
        r = s.get(url, params=params, timeout=15)
        
        print(f"\n← 响应状态码: {r.status_code}")
        print(f"← 响应头 Content-Type: {r.headers.get('content-type')}")
        
        if r.status_code == 401:
            print("\n❌ 401 Unauthorized - API Key 无效或已过期")
            print(f"响应内容: {r.text[:500]}")
            return
        
        if r.status_code == 403:
            print("\n❌ 403 Forbidden - 权限不足")
            print(f"响应内容: {r.text[:500]}")
            return
        
        if r.status_code != 200:
            print(f"\n❌ HTTP {r.status_code} 错误")
            print(f"响应内容: {r.text[:500]}")
            return
        
        # 检查响应类型
        content_type = r.headers.get('content-type', '')
        if 'json' not in content_type.lower():
            print(f"\n⚠️  警告: 响应不是JSON格式 (Content-Type: {content_type})")
            print(f"响应内容: {r.text[:500]}")
            return
        
        result = r.json()
        
        print(f"\n✓ 成功获取项目列表!")
        print(f"\n响应数据结构:")
        print(json.dumps(result, indent=2, ensure_ascii=False)[:1000])
        
        projects = result.get("items", [])
        
        if not projects:
            print(f"\n⚠️  项目列表为空")
            return
        
        print(f"\n发现 {len(projects)} 个项目:")
        for i, proj in enumerate(projects[:5], 1):
            proj_id = proj.get("id")
            proj_name = proj.get("name", "未命名")
            products = proj.get("products", [])
            
            print(f"\n  [{i}] {proj_name} (ID: {proj_id})")
            print(f"      产品数量: {len(products)}")
            
            if products:
                print(f"      产品列表:")
                for prod in products[:3]:
                    prod_id = prod.get("id")
                    prod_name = prod.get("name", "未命名")
                    print(f"        - {prod_name} (ID: {prod_id})")
        
        # 测试2: 创建邮箱
        if projects and projects[0].get("products"):
            print("\n" + "=" * 60)
            print("测试2: 创建测试邮箱")
            print("=" * 60)
            
            first_proj = projects[0]
            first_prod = first_proj["products"][0]
            
            test_project_id = first_proj["id"]
            test_product_id = first_prod["id"]
            
            print(f"\n使用:")
            print(f"  项目: {first_proj.get('name')} (ID: {test_project_id})")
            print(f"  产品: {first_prod.get('name')} (ID: {test_product_id})")
            
            confirm = input("\n是否创建测试邮箱? (y/n): ").strip().lower()
            
            if confirm == 'y':
                create_url = f"{api_url.rstrip('/')}/v1/open/orders"
                create_params = {
                    "serviceMode": "code",
                    "supply": "private_first"
                }
                create_data = {
                    "projectId": test_project_id,
                    "productId": test_product_id,
                    "emailSuffix": ""
                }
                
                print(f"\n→ 创建邮箱...")
                print(f"  URL: {create_url}")
                print(f"  参数: {create_params}")
                print(f"  数据: {create_data}")
                
                r2 = s.post(create_url, json=create_data, params=create_params, timeout=15)
                
                print(f"\n← 响应状态码: {r2.status_code}")
                
                if r2.status_code in (200, 201):
                    box = r2.json()
                    email = box.get("deliveryEmail")
                    token = box.get("serviceToken")
                    order_no = box.get("orderNo")
                    
                    print(f"\n✓ 邮箱创建成功!")
                    print(f"  邮箱地址: {email}")
                    print(f"  订单号: {order_no}")
                    print(f"  Token: {token[:20]}...")
                else:
                    print(f"\n❌ 创建失败: HTTP {r2.status_code}")
                    print(f"响应内容: {r2.text[:500]}")
        
        print("\n" + "=" * 60)
        print("测试完成!")
        print("=" * 60)
        
    except requests.exceptions.ConnectTimeout:
        print(f"\n❌ 连接超时 - 无法连接到 {api_url}")
    except requests.exceptions.ReadTimeout:
        print(f"\n❌ 读取超时 - API响应太慢")
    except requests.exceptions.ConnectionError as e:
        print(f"\n❌ 连接错误: {str(e)[:200]}")
    except requests.exceptions.RequestException as e:
        print(f"\n❌ 请求异常: {str(e)[:200]}")
    except Exception as e:
        print(f"\n❌ 未知错误: {str(e)[:200]}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    try:
        test_remail_api()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n致命错误: {e}")
        import traceback
        traceback.print_exc()
    
    input("\n按回车键退出...")
