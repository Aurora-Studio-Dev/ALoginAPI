import smtplib
import random
import ssl
import string
import os
import traceback
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

class EmailVerificationService:
    def __init__(self, smtp_config, redis_client):
        self.smtp_server = smtp_config['server']
        self.smtp_port = smtp_config['port']
        self.username = smtp_config['username']
        self.password = smtp_config['password']
        self.template_path = os.path.join(os.path.dirname(__file__), './templates/email_template.html')
        self.welcome_template_path = os.path.join(os.path.dirname(__file__), './templates/welcome_template.html')
        self.redis_client = redis_client
    
    def generate_verification_code(self, length=6):
        return ''.join(random.choices(string.digits, k=length))

    def send_verification_email(self, to_email, code):
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = to_email
            msg['Subject'] = "AuroraID 动态密码"

            with open(self.template_path, 'r', encoding='utf-8') as f:
                html_template = f.read()

            html_body = html_template.replace('{code}', code)

            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.options |= 0x4
            context.options |= 0x8
            context.options |= 0x10

            print(f"连接到SMTP服务器: {self.smtp_server}:{self.smtp_port}")
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.set_debuglevel(1) 
            print("启动TLS加密")
            server.starttls(context=context)
            print(f"尝试使用用户名 {self.username} 进行身份验证")
            server.login(self.username, self.password)
            print("发送邮件")
            server.send_message(msg)
            print("关闭SMTP连接")
            server.quit()
            
            print("邮件发送成功")
            return True
        except smtplib.SMTPAuthenticationError as e:
            print(f"SMTP认证失败: {e}")
            traceback.print_exc()
            return False
        except smtplib.SMTPException as e:
            print(f"SMTP错误: {e}")
            traceback.print_exc()
            return False
        except FileNotFoundError as e:
            print(f"找不到HTML模板文件: {e}")
            traceback.print_exc()
            return False
        except Exception as e:
            print(f"发送邮件失败: {e}")
            traceback.print_exc()
            return False
    
    def store_verification_code(self, email, code, expire_time=300):
        try:
            key = f"verification_code:{email}"
            self.redis_client.setex(key, expire_time, code)
            print(f"验证码 {code} 已存储到Redis，key为 {key}")
            return True
        except Exception as e:
            print(f"存储验证码到Redis失败: {e}")
            traceback.print_exc()
            return False
    
    def verify_code(self, email, code):
        try:
            key = f"verification_code:{email}"
            stored_code = self.redis_client.get(key)
            print(f"从Redis获取key {key} 的值: {stored_code}")
            
            if not stored_code:
                return False, "验证码已过期或不存在"
            
            if stored_code == code:
                self.redis_client.delete(key)
                return True, "验证成功"
            else:
                return False, "验证码错误"
        except Exception as e:
            print(f"验证验证码时出错: {e}")
            traceback.print_exc()
            return False, "服务器内部错误"
        
    def send_welcome_email(self, to_email, password):
        try:
            msg = MIMEMultipart()
            msg['From'] = self.username
            msg['To'] = to_email
            msg['Subject'] = "感谢您注册 AuroraID ！"

            with open(self.welcome_template_path, 'r', encoding='utf-8') as f:
                welcomehtml_template = f.read()

            html_body = welcomehtml_template.replace('{password}', password)

            msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            context = ssl.create_default_context()
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.options |= 0x4
            context.options |= 0x8
            context.options |= 0x10

            print(f"连接到SMTP服务器: {self.smtp_server}:{self.smtp_port}")
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.set_debuglevel(1) 
            print("启动TLS加密")
            server.starttls(context=context)
            print(f"尝试使用用户名 {self.username} 进行身份验证")
            server.login(self.username, self.password)
            print("发送邮件")
            server.send_message(msg)
            print("关闭SMTP连接")
            server.quit()
            
            print("邮件发送成功")
            return True
        except smtplib.SMTPAuthenticationError as e:
            print(f"SMTP认证失败: {e}")
            traceback.print_exc()
            return False
        except smtplib.SMTPException as e:
            print(f"SMTP错误: {e}")
            traceback.print_exc()
            return False
        except FileNotFoundError as e:
            print(f"找不到HTML模板文件: {e}")
            traceback.print_exc()
            return False
        except Exception as e:
            print(f"发送邮件失败: {e}")
            traceback.print_exc()
            return False