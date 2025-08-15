from flask import Blueprint, request, jsonify, current_app
from email_service import *
import redis
import hashlib
import uuid
import re
from redis import ConnectionPool, RedisError
import traceback
import string
import random
import yaml

auth_bp = Blueprint('auth', __name__)

email_service = None

def init_email_service(service):
    global email_service
    email_service = service

with open('./config.yml', 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

redis_config = config.get('redis', {})
redis_pool = ConnectionPool(
    host=redis_config.get('host', 'localhost'),
    port=redis_config.get('port', 6379),
    db=redis_config.get('db', 0),
    username=redis_config.get('username'),
    password=redis_config.get('password'),
    decode_responses=redis_config.get('decode_responses', False)
)
redis_client = redis.Redis(connection_pool=redis_pool)

def generate_complex_password(length=16):
    characters = string.ascii_letters + string.digits + '!@#$%^&*'
    return ''.join(random.choice(characters) for _ in range(length))

def is_valid_email(email):
    return re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email)


@auth_bp.route('/send_verification_code', methods=['POST'])
def send_verification_code():
    try:
        if email_service is None:
            return jsonify({'success': False, 'message': '邮件服务未初始化'}), 500
            
        print("收到发送验证码请求")
        data = request.get_json(force=True)
        print(f"请求数据: {data}")
        
        if data is None:
            return jsonify({'success': False, 'message': '请求体为空或不是有效的 JSON'}), 400
            
        email = data.get('email')
        print(f"目标邮箱: {email}")
        
        if not email:
            return jsonify({'success': False, 'message': '邮箱地址不能为空'}), 400
        
        code = email_service.generate_verification_code()
        print(f"生成的验证码: {code}")
        
        if email_service.send_verification_email(email, code):
            print("邮件发送成功，准备存储验证码")
            if email_service.store_verification_code(email, code):
                print("验证码存储成功")
                return jsonify({'success': True, 'message': '验证码已发送到您的邮箱'}), 200
            else:
                print("验证码存储失败")
                return jsonify({'success': False, 'message': '验证码存储失败'}), 500
        else:
            print("邮件发送失败")
            return jsonify({'success': False, 'message': '验证码发送失败'}), 500
            
    except Exception as e:
        print(f"处理发送验证码请求时发生未预期的错误: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        if not request.is_json:
            return jsonify({
                'success': False, 
                'message': '请求内容必须为JSON格式',
                'content_type': request.content_type
            }), 400

        data = request.get_json(silent=True)
        if not data:
            return jsonify({
                'success': False, 
                'message': '无法解析JSON数据',
                'raw_data': request.data[:200] 
            }), 400

        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        code = data.get('code', '').strip()

        if not email:
            return jsonify({'success': False, 'message': '邮箱不能为空'})
        if not is_valid_email(email):
            return jsonify({'success': False, 'message': '邮箱格式不正确'})

        user_key = f"user:{email}"
        
        try:
            if not redis_client.ping():
                raise RedisError(
                    "Redis连接失败")
                
            user_data = redis_client.hgetall(user_key)
            
            if user_data:
                decoded_data = {}
                for k, v in user_data.items():
                    try:
                        decoded_data[k.decode('utf-8') if isinstance(k, bytes) else k] = \
                            v.decode('utf-8') if isinstance(v, bytes) else v
                    except (UnicodeDecodeError, AttributeError) as e:
                        current_app.logger.warning(f"数据解码警告 ({k}): {str(e)}")
                        decoded_data[k] = v 
                user_data = decoded_data
                
        except (RedisError, ConnectionError) as e:
            current_app.logger.error(f"Redis连接异常: {str(e)}", exc_info=True)
            return jsonify({
                'success': False, 
                'message': '认证服务暂时不可用',
                'error_code': 'REDIS_CONNECTION_FAILED'
            }), 503
        except Exception as e:
            current_app.logger.error(f"Redis操作异常: {str(e)}", exc_info=True)
            return jsonify({
                'success': False, 
                'message': '内部服务器错误',
                'error_code': 'REDIS_OPERATION_FAILED'
            }), 500

        if code:
            try:
                stored_code = redis_client.get(f"verification_code:{email}")
                
                if isinstance(stored_code, bytes):
                    stored_code = stored_code.decode('utf-8')
                if not stored_code or stored_code != code:
                    return jsonify({
                        'success': False, 
                        'message': '验证码错误',
                        'stored_code': stored_code is not None  # 仅用于调试
                    })

                if not user_data:
                    system_password = generate_complex_password(12)

                    email_service.send_welcome_email(email, system_password)
                    current_app.logger.info(f"已为新用户 {email} 生成并发送初始密码")

                    parts = email.split('@')
                    if len(parts) < 2 or not parts[0]:
                        return jsonify({
                            'success': False, 
                            'message': '邮箱格式不正确',
                            'error_code': 'INVALID_EMAIL_FORMAT'
                        }), 400

                    username = parts[0]

                    # 使用数字ID替代UUID，并按注册顺序递增
                    # 获取当前最大用户ID并加1
                    user_counter_key = "user_counter"
                    user_id = redis_client.incr(user_counter_key)
                    
                    new_user_data = {
                        'uuid': str(user_id),  # 使用纯数字ID
                        'username': username,
                        'password': hashlib.md5(system_password.encode()).hexdigest(),
                        'password_type': 'system_generated'
                    }

                    if not redis_client.hmset(user_key, new_user_data):
                        raise RedisError("用户数据写入失败")

                    if not redis_client.delete(f"verification_code:{email}"):
                        current_app.logger.warning(f"动态密码清理失败: {email}")

                    return jsonify({
                        'success': True,
                        'message': '账户注册成功，初始密码已发送至您的邮箱',
                        'data': {
                            'username': username,
                            'uuid': new_user_data['uuid']
                        }
                    }), 200
                else:
                    # 用户已存在，清理验证码并返回登录成功
                    redis_client.delete(f"verification_code:{email}")
                    return jsonify({
                        'success': True,
                        'message': '登录成功',
                        'data': {
                            'username': user_data.get('username'),
                            'uuid': user_data.get('uuid')
                        }
                    })
                    
            except (RedisError, uuid.UUIDError, AttributeError, UnicodeEncodeError) as e:
                current_app.logger.error(f"用户数据初始化异常: {str(e)}", exc_info=True)
                return jsonify({
                    'success': False, 
                    'message': '用户初始化失败',
                    'error_code': 'USER_INITIALIZATION_FAILED'
                }), 500

        # 密码验证逻辑
        if password:
            if not user_data:
                return jsonify({'success': False, 'message': '用户不存在'})
                
            hashed_input = hashlib.md5(password.encode('utf-8')).hexdigest()
            stored_hash = user_data.get('password', '')
            
            if hashed_input != stored_hash:
                return jsonify({
                    'success': False, 
                    'message': '密码错误',
                    'hash_match': False
                })

            return jsonify({
                'success': True,
                'data': {
                    'username': user_data.get('username'),
                    'uuid': user_data.get('uuid')
                }
            })

        return jsonify({
            'success': False, 
            'message': '必须提供密码或验证码',
            'provided_fields': list(data.keys())
        })

    except Exception as e:
        current_app.logger.error(f"未处理的异常: {str(e)}", exc_info=True)
        return jsonify({
            'success': False, 
            'message': '内部服务器错误',
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500

@auth_bp.route('/change_password', methods=['POST'])
def change_password():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': '请求数据无效'}), 400
            
        email = data.get('email')
        old_password = data.get('old_password')
        new_password = data.get('new_password')
        
        if not email or not old_password or not new_password:
            return jsonify({'success': False, 'message': '邮箱、旧密码和新密码不能为空'}), 400
            
        if not is_valid_email(email):
            return jsonify({'success': False, 'message': '邮箱格式不正确'}), 400
            
        user_key = f"user:{email}"
        user_data = redis_client.hgetall(user_key)
        
        if not user_data:
            return jsonify({'success': False, 'message': '用户不存在'}), 404

        decoded_user_data = {}
        for k, v in user_data.items():
            try:
                decoded_user_data[k.decode('utf-8') if isinstance(k, bytes) else k] = \
                    v.decode('utf-8') if isinstance(v, bytes) else v
            except (UnicodeDecodeError, AttributeError):
                decoded_user_data[k] = v
                
        stored_password = decoded_user_data.get('password', '')
        hashed_old_password = hashlib.md5(old_password.encode()).hexdigest()
        
        if stored_password != hashed_old_password:
            return jsonify({'success': False, 'message': '旧密码错误'}), 400
            
        hashed_new_password = hashlib.md5(new_password.encode()).hexdigest()
        result = redis_client.hset(user_key, 'password', hashed_new_password)
        
        if result:
            current_app.logger.info(f"用户 {email} 密码修改成功")
            return jsonify({'success': True, 'message': '密码修改成功'})
        else:
            current_app.logger.error(f"用户 {email} 密码修改失败")
            return jsonify({'success': False, 'message': '密码修改失败'}), 500
            
    except Exception as e:
        current_app.logger.error(f"修改密码时发生错误: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': '服务器内部错误'}), 500