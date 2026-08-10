# -*- coding: utf-8 -*-
"""
最优注册流程
Author: 海鸥
"""

import time
import random
from datetime import datetime, timedelta
import json

class OptimalRegistrationFlow:
    """最优注册流程"""
    
    def __init__(self, config):
        self.config = config
        self.registration_log = []
    
    def step1_ip_selection(self):
        """步骤1: 选择高质量IP"""
        print("\n=== 步骤1: IP选择 ===")
        
        ip_priorities = [
            ('移动4G/5G', '最高质量,最贵'),
            ('住宅宽带', '高质量,推荐'),
            ('商业宽带', '中等质量'),
            ('数据中心', '低质量,不推荐'),
        ]
        
        print("[*] IP质量优先级:")
        for ip_type, quality in ip_priorities:
            print(f"  {ip_type}: {quality}")
        
        # 选择住宅代理
        selected_proxy = self.select_residential_proxy()
        print(f"[+] 已选择代理: {selected_proxy}")
        
        return selected_proxy
    
    def step2_environment_preparation(self, proxy):
        """步骤2: 环境准备"""
        print("\n=== 步骤2: 环境准备 ===")
        
        # 创建独立浏览器环境
        print("[*] 创建独立浏览器配置...")
        browser_config = {
            'user_agent': self.generate_random_ua(),
            'screen_resolution': random.choice(['1920x1080', '1366x768', '1536x864']),
            'timezone': self.get_timezone_from_ip(proxy),
            'language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'webgl_vendor': random.choice(['Google Inc.', 'Intel Inc.']),
            'canvas_fingerprint': self.generate_canvas_fingerprint(),
        }
        
        print(f"[+] 浏览器配置:")
        for key, value in browser_config.items():
            print(f"  {key}: {value}")
        
        return browser_config
    
    def step3_pre_registration_browsing(self, driver):
        """步骤3: 注册前浏览 (关键!)"""
        print("\n=== 步骤3: 注册前预热 ===")
        
        # 模拟真实用户浏览路径
        browsing_path = [
            ('首页', '/', random.randint(5, 10)),
            ('关于页面', '/about', random.randint(3, 6)),
            ('功能页面', '/features', random.randint(4, 8)),
            ('定价页面', '/pricing', random.randint(3, 5)),
            ('博客', '/blog', random.randint(5, 10)),
        ]
        
        # 随机选择2-4个页面
        selected_pages = random.sample(browsing_path, random.randint(2, 4))
        
        for page_name, url, stay_seconds in selected_pages:
            print(f"[*] 浏览 {page_name}...")
            driver.get(f"https://目标网站.com{url}")
            
            # 随机滚动
            self.random_scroll_page(driver)
            
            # 停留
            print(f"  停留 {stay_seconds} 秒")
            time.sleep(stay_seconds)
        
        print("[+] 预热完成")
    
    def step4_registration(self, driver, account_info):
        """步骤4: 注册"""
        print("\n=== 步骤4: 执行注册 ===")
        
        # 访问注册页面
        print("[*] 访问注册页面...")
        driver.get("https://目标网站.com/register")
        time.sleep(random.uniform(2, 4))
        
        # 随机看看页面
        self.random_scroll_page(driver)
        time.sleep(random.uniform(2, 3))
        
        # 填写表单 (模拟真人)
        print("[*] 填写注册信息...")
        self.fill_registration_form(driver, account_info)
        
        # 等待一下再提交
        time.sleep(random.uniform(1, 2))
        
        # 提交注册
        print("[*] 提交注册...")
        submit_button = driver.find_element("xpath", "//button[@type='submit']")
        submit_button.click()
        
        # 等待结果
        time.sleep(random.uniform(3, 5))
        
        # 检查是否成功
        success = self.check_registration_success(driver)
        
        if success:
            print("[+] 注册成功!")
        else:
            print("[-] 注册失败,检查错误信息...")
        
        return success
    
    def step5_post_registration_activity(self, driver):
        """步骤5: 注册后行为 (非常重要!)"""
        print("\n=== 步骤5: 注册后行为 ===")
        
        # 不要立即离开!
        print("[*] 继续浏览...")
        
        # 完善个人资料
        if random.random() < 0.8:
            print("[*] 完善个人资料...")
            self.complete_profile(driver)
        
        # 浏览2-3个页面
        for i in range(random.randint(2, 3)):
            print(f"[*] 浏览页面 {i+1}...")
            self.random_browse_page(driver)
            time.sleep(random.uniform(10, 20))
        
        # 总停留时间: 至少5分钟
        print("[*] 保持活跃...")
        time.sleep(random.uniform(300, 600))
        
        print("[+] 注册后行为完成")
    
    def step6_initial_warmup(self, account_info):
        """步骤6: 初始养护 (注册后24小时内)"""
        print("\n=== 步骤6: 初始养护计划 ===")
        
        warmup_schedule = [
            {
                'time': '注册后2小时',
                'action': '登录 + 浏览5分钟',
                'delay': timedelta(hours=2)
            },
            {
                'time': '注册后6小时',
                'action': '登录 + 完善资料',
                'delay': timedelta(hours=6)
            },
            {
                'time': '注册后12小时',
                'action': '登录 + 浏览10分钟',
                'delay': timedelta(hours=12)
            },
            {
                'time': '注册后24小时',
                'action': '登录 + 进行互动',
                'delay': timedelta(hours=24)
            },
        ]
        
        print("[*] 养护计划:")
        for schedule in warmup_schedule:
            target_time = datetime.now() + schedule['delay']
            print(f"  {schedule['time']} ({target_time.strftime('%Y-%m-%d %H:%M')})")
            print(f"    行动: {schedule['action']}")
        
        # 保存计划到数据库/文件
        self.save_warmup_schedule(account_info, warmup_schedule)
        
        return warmup_schedule
    
    def step7_long_term_maintenance(self, account_info):
        """步骤7: 长期维护"""
        print("\n=== 步骤7: 长期维护策略 ===")
        
        maintenance_plan = {
            'week_1': {
                'frequency': '每天1-2次登录',
                'duration': '每次5-10分钟',
                'activities': ['浏览', '偶尔点赞']
            },
            'week_2-4': {
                'frequency': '每天2-3次登录',
                'duration': '每次10-15分钟',
                'activities': ['浏览', '点赞', '关注', '评论']
            },
            'month_2+': {
                'frequency': '正常使用',
                'duration': '根据需求',
                'activities': ['所有功能']
            }
        }
        
        print("[*] 维护计划:")
        for period, plan in maintenance_plan.items():
            print(f"\n  {period}:")
            print(f"    频率: {plan['frequency']}")
            print(f"    时长: {plan['duration']}")
            print(f"    活动: {', '.join(plan['activities'])}")
        
        return maintenance_plan
    
    # ===== 辅助方法 =====
    
    def select_residential_proxy(self):
        """选择住宅代理"""
        # 从代理池选择
        proxies = self.config.get('proxy_pool', [])
        if proxies:
            return random.choice(proxies)
        return None
    
    def generate_random_ua(self):
        """生成随机UA"""
        return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    
    def get_timezone_from_ip(self, proxy):
        """从IP获取时区"""
        # 简化实现
        return 'Asia/Shanghai'
    
    def generate_canvas_fingerprint(self):
        """生成Canvas指纹"""
        return f"canvas_{random.randint(1000000, 9999999)}"
    
    def random_scroll_page(self, driver):
        """随机滚动页面"""
        for _ in range(random.randint(2, 5)):
            scroll_amount = random.randint(200, 500)
            driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
            time.sleep(random.uniform(0.5, 1.5))
    
    def fill_registration_form(self, driver, account_info):
        """填写注册表单"""
        # 实现真人打字逻辑
        pass
    
    def check_registration_success(self, driver):
        """检查注册是否成功"""
        # 检查页面元素或URL变化
        return True
    
    def complete_profile(self, driver):
        """完善个人资料"""
        print("  - 设置用户名")
        time.sleep(random.uniform(1, 2))
        print("  - 上传头像")
        time.sleep(random.uniform(2, 3))
        print("  - 填写简介")
        time.sleep(random.uniform(1, 2))
    
    def random_browse_page(self, driver):
        """随机浏览页面"""
        self.random_scroll_page(driver)
    
    def save_warmup_schedule(self, account_info, schedule):
        """保存养护计划"""
        # 保存到数据库或文件
        pass
    
    def execute_complete_flow(self, account_info):
        """执行完整流程"""
        print("\n" + "="*50)
        print("         最优注册流程开始")
        print("="*50)
        
        # 步骤1: IP选择
        proxy = self.step1_ip_selection()
        
        # 步骤2: 环境准备
        browser_config = self.step2_environment_preparation(proxy)
        
        # 创建浏览器 (这里需要实际实现)
        # driver = self.create_browser(proxy, browser_config)
        driver = None  # 占位
        
        if driver:
            # 步骤3: 预热
            self.step3_pre_registration_browsing(driver)
            
            # 步骤4: 注册
            success = self.step4_registration(driver, account_info)
            
            if success:
                # 步骤5: 注册后行为
                self.step5_post_registration_activity(driver)
                
                # 步骤6: 初始养护
                self.step6_initial_warmup(account_info)
                
                # 步骤7: 长期维护
                self.step7_long_term_maintenance(account_info)
            
            # driver.quit()
        
        print("\n" + "="*50)
        print("         流程执行完毕")
        print("="*50)


# 配置
config = {
    'proxy_pool': [
        'socks5://user:pass@residential1.com:1080',
        'socks5://user:pass@residential2.com:1080',
    ],
    'email_domain': 'yourdomain.com',
    'max_accounts_per_day': 20,
    'min_interval_minutes': 15,
}

# 测试账号信息
test_account = {
    'email': 'test123@example.com',
    'password': 'SecurePass123!',
    'username': 'testuser123',
}

# 执行流程
flow = OptimalRegistrationFlow(config)
flow.execute_complete_flow(test_account)
