# -*- coding: utf-8 -*-
"""
账号养护策略
Author: 海鸥
"""

import time
import random
import json
from datetime import datetime, timedelta

class AccountWarmup:
    """账号养护系统"""
    
    def __init__(self):
        self.accounts = []
        self.warmup_schedule = []
    
    def create_warmup_schedule(self, account):
        """创建养护计划"""
        schedule = {
            'account': account,
            'created_at': datetime.now(),
            'stages': [
                {
                    'name': '初始化阶段',
                    'duration': timedelta(hours=2),
                    'actions': [
                        '完善个人资料',
                        '上传头像',
                        '设置偏好'
                    ]
                },
                {
                    'name': '低频使用阶段',
                    'duration': timedelta(days=3),
                    'actions': [
                        '每天登录1-2次',
                        '浏览内容5-10分钟',
                        '随机点击/互动'
                    ]
                },
                {
                    'name': '正常使用阶段',
                    'duration': timedelta(days=7),
                    'actions': [
                        '每天登录2-4次',
                        '发布内容',
                        '关注其他用户',
                        '评论互动'
                    ]
                },
                {
                    'name': '成熟账号',
                    'duration': None,  # 持续
                    'actions': [
                        '正常频率使用',
                        '保持活跃'
                    ]
                }
            ]
        }
        return schedule
    
    def warmup_action_login(self, account, driver):
        """养护动作: 登录"""
        print(f"[*] 账号 {account['email']} 执行登录...")
        
        # 访问登录页
        driver.get("https://目标网站.com/login")
        time.sleep(random.uniform(2, 4))
        
        # 输入凭证 (使用真人模拟)
        # ... 省略具体实现
        
        # 停留一段时间
        time.sleep(random.uniform(30, 60))
    
    def warmup_action_browse(self, driver):
        """养护动作: 浏览内容"""
        print("[*] 浏览内容...")
        
        # 随机浏览3-5个页面
        for _ in range(random.randint(3, 5)):
            # 滚动页面
            scroll_count = random.randint(2, 5)
            for _ in range(scroll_count):
                driver.execute_script(f"window.scrollBy(0, {random.randint(200, 500)});")
                time.sleep(random.uniform(1, 3))
            
            # 随机停留
            time.sleep(random.uniform(10, 30))
            
            # 随机点击链接
            if random.random() < 0.5:
                # ... 点击逻辑
                pass
    
    def warmup_action_interact(self, driver):
        """养护动作: 互动"""
        print("[*] 执行互动...")
        
        # 随机点赞/关注/评论
        actions = ['like', 'follow', 'comment']
        action = random.choice(actions)
        
        if action == 'like':
            # 点赞逻辑
            pass
        elif action == 'follow':
            # 关注逻辑
            pass
        elif action == 'comment':
            # 评论逻辑 (使用预设评论模板)
            pass
    
    def execute_warmup_schedule(self, account):
        """执行养护计划"""
        print(f"[*] 开始养护账号: {account['email']}")
        
        schedule = self.create_warmup_schedule(account)
        
        for stage in schedule['stages']:
            print(f"\n[*] 进入阶段: {stage['name']}")
            print(f"[*] 计划时长: {stage['duration']}")
            print(f"[*] 行动列表: {', '.join(stage['actions'])}")
            
            # 这里应该是异步执行,按时间表定期操作
            # 简化示例
            if stage['duration']:
                print(f"[*] 该阶段将持续 {stage['duration']}")
            else:
                print("[*] 该阶段持续进行")


class ProxyIPRotation:
    """代理IP轮换策略"""
    
    def __init__(self):
        self.ip_usage_limit = {
            'datacenter': 1,      # 数据中心IP: 1个账号
            'residential': 5,     # 住宅IP: 5个账号
            'mobile': 10,         # 移动IP: 10个账号
        }
        self.ip_cooldown = {
            'datacenter': 24 * 60 * 60,    # 24小时
            'residential': 6 * 60 * 60,     # 6小时
            'mobile': 2 * 60 * 60,          # 2小时
        }
    
    def should_rotate_ip(self, ip_info):
        """判断是否需要轮换IP"""
        # 检查IP使用次数
        if ip_info['usage_count'] >= self.ip_usage_limit[ip_info['type']]:
            return True
        
        # 检查冷却时间
        last_used = ip_info['last_used']
        cooldown = self.ip_cooldown[ip_info['type']]
        if (time.time() - last_used) < cooldown:
            return True
        
        return False


class EmailProvider:
    """邮箱提供商建议"""
    
    @staticmethod
    def get_recommended_providers():
        """推荐的邮箱服务"""
        return {
            'temporary': [
                'guerrillamail.com',
                'temp-mail.org',
                '10minutemail.com',
                'mohmal.com',  # 阿拉伯临时邮箱,检测少
            ],
            'permanent': [
                'gmail.com',    # 需要手机号
                'outlook.com',  # 相对容易
                'protonmail.com',  # 注重隐私
                'yandex.com',   # 俄罗斯服务,限制少
            ],
            'catch_all': [
                '自建域名 + catch-all',  # 最灵活
            ]
        }
    
    @staticmethod
    def create_catch_all_email(domain, unique_id):
        """创建catch-all邮箱"""
        # 格式: user+uniqueid@yourdomain.com
        # 或: uniqueid@yourdomain.com
        return f"reg_{unique_id}@{domain}"


class RegistrationTiming:
    """注册时机控制"""
    
    @staticmethod
    def get_safe_registration_time():
        """获取安全的注册时间"""
        # 避开高峰期 (更容易被检测)
        # 模拟当地时间的正常作息
        
        current_hour = datetime.now().hour
        
        # 凌晨2-6点: 高风险
        if 2 <= current_hour < 6:
            print("[!] 警告: 当前时间段注册风险较高")
            return False
        
        # 工作日白天9-18点: 正常
        # 晚上19-23点: 正常
        return True
    
    @staticmethod
    def calculate_next_registration_time(last_reg_time, account_count):
        """计算下次注册时间"""
        # 基础间隔: 10-30分钟
        base_interval = random.randint(10 * 60, 30 * 60)
        
        # 如果已注册多个账号,增加间隔
        if account_count > 5:
            base_interval *= 2
        if account_count > 10:
            base_interval *= 3
        
        # 添加随机波动
        jitter = random.randint(-300, 300)
        
        next_time = last_reg_time + timedelta(seconds=base_interval + jitter)
        return next_time


class AntiDetectionTips:
    """反检测建议"""
    
    @staticmethod
    def print_checklist():
        """打印检查清单"""
        checklist = """
        ========================================
                 反检测检查清单
        ========================================
        
        [ ] IP质量
            [ ] 使用住宅/移动IP (不用数据中心IP)
            [ ] IP信誉良好 (未被标记)
            [ ] IP地理位置匹配注册信息
            [ ] 每个IP注册数量限制 (1-5个)
            [ ] IP轮换间隔 (至少2小时)
        
        [ ] 浏览器指纹
            [ ] 使用undetected-chromedriver
            [ ] 随机User-Agent
            [ ] 随机屏幕分辨率
            [ ] 语言/时区匹配IP位置
            [ ] Canvas/WebGL指纹随机化
            [ ] 禁用WebRTC (防止IP泄露)
        
        [ ] 行为模式
            [ ] 注册前浏览2-5个页面 (预热)
            [ ] 模拟真人鼠标移动
            [ ] 模拟真人打字速度
            [ ] 随机停顿/滚动
            [ ] 注册后继续浏览 (不要秒跑)
        
        [ ] 注册信息
            [ ] 邮箱多样化 (不要都是Gmail)
            [ ] 用户名随机化 (不要有规律)
            [ ] 密码强度适中
            [ ] 头像/资料准备
        
        [ ] 时机控制
            [ ] 避开凌晨注册
            [ ] 注册间隔随机 (10-30分钟)
            [ ] 批量上限 (每天不超过20个)
        
        [ ] 账号养护
            [ ] 注册后2小时内完善资料
            [ ] 前3天低频使用
            [ ] 7天后逐渐正常使用
            [ ] 保持长期活跃
        
        [ ] 邮箱验证
            [ ] 及时验证邮箱 (不要拖延)
            [ ] 用真实邮箱服务
            [ ] 避免使用已知临时邮箱域名
        
        [ ] Cookie/Session
            [ ] 每个账号独立Cookie
            [ ] 模拟正常Session时长
            [ ] 定期登录保持活跃
        
        ========================================
        """
        print(checklist)


# 使用示例
if __name__ == '__main__':
    # 打印检查清单
    AntiDetectionTips.print_checklist()
    
    # 检查注册时机
    if RegistrationTiming.get_safe_registration_time():
        print("[+] 当前时间适合注册")
    
    # 推荐邮箱服务
    providers = EmailProvider.get_recommended_providers()
    print(f"\n[*] 推荐邮箱服务:")
    for category, services in providers.items():
        print(f"  {category}: {', '.join(services)}")
    
    # 创建养护计划
    warmup = AccountWarmup()
    test_account = {
        'email': 'test@example.com',
        'password': 'SecurePass123!',
        'created_at': datetime.now()
    }
    
    schedule = warmup.create_warmup_schedule(test_account)
    print(f"\n[*] 账号养护计划:")
    for stage in schedule['stages']:
        print(f"  阶段: {stage['name']}")
        print(f"    时长: {stage['duration']}")
        print(f"    行动: {', '.join(stage['actions'])}")
