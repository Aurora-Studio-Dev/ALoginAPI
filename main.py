import yaml
import os
import sys
from flask import Flask, render_template
import redis
from flask_cors import CORS
from email_service import EmailVerificationService
from auth_routes import auth_bp
def create_default_config():
    """创建默认配置文件"""
    default_config = {
        'smtp': {
            'server': 'smtp.example.com',
            'port': 587,
            'username': 'your-email@example.com',
            'password': 'your-password'
        },
        'redis': {
            'host（不要携带http和https！）': 'localhost',
            'port': 6379,
            'db': 0,
            'username': 'default',
            'password': '',
            'decode_responses': True
        },
        'app': {
            'host': '0.0.0.0',
            'port': 5002,
            'debug': False
        }
    }
    
    with open('config.yml', 'w', encoding='utf-8') as f:
        yaml.dump(default_config, f, default_flow_style=False, allow_unicode=True)
    print("已创建默认配置文件 config.yml，请修改其中的配置信息后再运行程序。")
    return default_config

def load_config():
    """加载配置文件，如果不存在则创建默认配置"""
    if not os.path.exists('config.yml'):
        print("配置文件 config.yml 不存在，正在创建默认配置文件...")
        print("请修改 config.yml 中的配置信息后再运行程序。")
        return create_default_config()
    
    try:
        with open('config.yml', 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        print(f"读取配置文件时出错: {e}")
        sys.exit(1)

app = Flask(__name__)
CORS(app)

config = load_config()

required_sections = ['redis', 'smtp', 'app']
missing_sections = [section for section in required_sections if section not in config]

if missing_sections:
    print(f"配置文件缺少必要配置项: {', '.join(missing_sections)}")
    sys.exit(1)

REDIS_CONFIG = config['redis']
try:
    redis_client = redis.Redis(**REDIS_CONFIG)
    redis_client.ping()
except Exception as e:
    print(f"无法连接到Redis: {e}")
    sys.exit(1)

SMTP_CONFIG = config['smtp']

email_service = EmailVerificationService(SMTP_CONFIG, redis_client)
from auth_routes import init_email_service
init_email_service(email_service)

app.register_blueprint(auth_bp)
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app_config = config['app']
    app.run(
        host=app_config.get('host', '0.0.0.0'),
        port=app_config.get('port', 5000),
        debug=app_config.get('debug', False)
    )