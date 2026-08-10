# -*- coding: utf-8 -*-
"""
反检测环境配置
Author: 海鸥
"""

import random
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
import undetected_chromedriver as uc

class AntiDetectionBrowser:
    """反检测浏览器环境"""
    
    def __init__(self, proxy=None):
        self.proxy = proxy
        self.driver = None
    
    def create_realistic_browser(self):
        """创建真实的浏览器环境"""
        options = uc.ChromeOptions()
        
        # 随机User-Agent
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        ]
        options.add_argument(f'--user-agent={random.choice(user_agents)}')
        
        # 代理设置
        if self.proxy:
            options.add_argument(f'--proxy-server={self.proxy}')
        
        # 反检测参数
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--no-sandbox')
        
        # 随机窗口大小 (模拟真实用户)
        window_sizes = [
            (1920, 1080),
            (1366, 768),
            (1536, 864),
            (1440, 900),
        ]
        width, height = random.choice(window_sizes)
        options.add_argument(f'--window-size={width},{height}')
        
        # 语言设置 (根据IP地理位置)
        options.add_argument('--lang=zh-CN,zh;q=0.9,en;q=0.8')
        
        # 禁用webdriver检测
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # 创建driver
        self.driver = uc.Chrome(options=options)
        
        # 修改navigator.webdriver
        self.driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
            'source': '''
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // 修改plugin数组
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                // 修改language
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['zh-CN', 'zh', 'en']
                });
                
                // Chrome runtime
                window.chrome = {
                    runtime: {}
                };
                
                // Permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({state: Notification.permission}) :
                        originalQuery(parameters)
                );
            '''
        })
        
        return self.driver
    
    def human_like_mouse_move(self, element):
        """模拟真人鼠标移动"""
        actions = ActionChains(self.driver)
        
        # 获取元素位置
        location = element.location
        size = element.size
        
        # 随机目标点
        x_offset = random.randint(5, size['width'] - 5)
        y_offset = random.randint(5, size['height'] - 5)
        
        # 分段移动 (更真实)
        steps = random.randint(10, 20)
        for i in range(steps):
            intermediate_x = (x_offset / steps) * i
            intermediate_y = (y_offset / steps) * i
            actions.move_to_element_with_offset(element, intermediate_x, intermediate_y)
            actions.pause(random.uniform(0.01, 0.05))
        
        actions.perform()
        time.sleep(random.uniform(0.2, 0.5))
    
    def human_like_typing(self, element, text):
        """模拟真人打字"""
        element.click()
        time.sleep(random.uniform(0.1, 0.3))
        
        for char in text:
            element.send_keys(char)
            # 随机打字速度
            delay = random.uniform(0.05, 0.2)
            # 偶尔停顿 (模拟思考)
            if random.random() < 0.1:
                delay += random.uniform(0.3, 0.8)
            time.sleep(delay)
    
    def random_scroll(self):
        """随机滚动页面"""
        scroll_amount = random.randint(100, 500)
        self.driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        time.sleep(random.uniform(0.5, 1.5))
    
    def random_page_interaction(self):
        """随机页面交互"""
        # 随机停留
        time.sleep(random.uniform(2, 5))
        
        # 随机滚动
        if random.random() < 0.7:
            self.random_scroll()
        
        # 随机移动鼠标
        if random.random() < 0.5:
            x = random.randint(100, 800)
            y = random.randint(100, 600)
            ActionChains(self.driver).move_by_offset(x, y).perform()


class AccountRegistration:
    """账号注册流程优化"""
    
    def __init__(self, proxy_pool):
        self.proxy_pool = proxy_pool
        self.browser = None
    
    def pre_warm_account(self, proxy):
        """账号预热 - 提升存活率"""
        print("[*] 开始账号预热...")
        
        # 创建浏览器
        self.browser = AntiDetectionBrowser(proxy)
        driver = self.browser.create_realistic_browser()
        
        # 1. 先访问首页
        driver.get("https://目标网站.com")
        time.sleep(random.uniform(3, 6))
        
        # 2. 随机浏览几个页面
        browsing_pages = [
            "/about",
            "/features", 
            "/pricing",
            "/blog"
        ]
        
        for _ in range(random.randint(2, 4)):
            page = random.choice(browsing_pages)
            driver.get(f"https://目标网站.com{page}")
            self.browser.random_page_interaction()
            time.sleep(random.uniform(2, 5))
        
        # 3. 最后才访问注册页面
        driver.get("https://目标网站.com/register")
        time.sleep(random.uniform(3, 5))
        
        print("[+] 预热完成")
        return driver
    
    def register_with_delay(self, driver, email, password):
        """带延迟的注册流程"""
        try:
            # 找到输入框
            email_input = driver.find_element(By.NAME, "email")
            password_input = driver.find_element(By.NAME, "password")
            
            # 模拟真人操作
            self.browser.random_page_interaction()
            
            # 输入邮箱
            self.browser.human_like_mouse_move(email_input)
            self.browser.human_like_typing(email_input, email)
            time.sleep(random.uniform(1, 2))
            
            # 输入密码
            self.browser.human_like_mouse_move(password_input)
            self.browser.human_like_typing(password_input, password)
            time.sleep(random.uniform(1, 2))
            
            # 随机操作
            if random.random() < 0.3:
                self.browser.random_scroll()
            
            # 点击注册按钮
            register_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            self.browser.human_like_mouse_move(register_btn)
            time.sleep(random.uniform(0.5, 1))
            register_btn.click()
            
            # 等待结果
            time.sleep(random.uniform(3, 5))
            
            print("[+] 注册请求已发送")
            return True
            
        except Exception as e:
            print(f"[-] 注册失败: {e}")
            return False
    
    def post_registration_activity(self, driver):
        """注册后行为 - 降低风控概率"""
        print("[*] 执行注册后行为...")
        
        # 停留一段时间
        time.sleep(random.uniform(5, 10))
        
        # 随机访问几个页面
        for _ in range(random.randint(2, 3)):
            self.browser.random_page_interaction()
            time.sleep(random.uniform(3, 6))
        
        print("[+] 注册后行为完成")


class IPQualityChecker:
    """IP质量检测"""
    
    @staticmethod
    def check_ip_quality(ip):
        """检查IP质量"""
        import requests
        
        checks = {
            'is_proxy': False,
            'is_vpn': False,
            'is_tor': False,
            'is_datacenter': False,
            'abuse_score': 0,
            'country': '',
        }
        
        try:
            # 使用IP质量检测API
            # 这里用ipinfo.io举例,实际建议用IPQualityScore或类似服务
            response = requests.get(f'https://ipinfo.io/{ip}/json', timeout=5)
            data = response.json()
            
            checks['country'] = data.get('country', '')
            
            # 检测是否是托管IP (数据中心)
            if 'hosting' in data.get('org', '').lower():
                checks['is_datacenter'] = True
            
            print(f"[*] IP质量检测: {ip}")
            print(f"    国家: {checks['country']}")
            print(f"    运营商: {data.get('org', 'Unknown')}")
            print(f"    数据中心: {checks['is_datacenter']}")
            
            return checks
            
        except Exception as e:
            print(f"[-] IP检测失败: {e}")
            return checks


# 使用示例
if __name__ == '__main__':
    # 代理池 (建议用住宅代理)
    proxy_pool = [
        'socks5://user:pass@residential-proxy1.com:1080',
        'socks5://user:pass@residential-proxy2.com:1080',
    ]
    
    # 检查IP质量
    checker = IPQualityChecker()
    for proxy in proxy_pool:
        # 这里需要先获取代理的出口IP
        # checker.check_ip_quality(exit_ip)
        pass
    
    # 注册流程
    registration = AccountRegistration(proxy_pool)
    
    # 选择一个代理
    proxy = random.choice(proxy_pool)
    
    # 预热
    driver = registration.pre_warm_account(proxy)
    
    # 注册
    email = "test@example.com"  # 替换为真实邮箱
    password = "SecurePass123!"
    
    success = registration.register_with_delay(driver, email, password)
    
    if success:
        # 注册后行为
        registration.post_registration_activity(driver)
    
    # 保持会话活跃一段时间
    time.sleep(random.uniform(60, 120))
    
    driver.quit()
