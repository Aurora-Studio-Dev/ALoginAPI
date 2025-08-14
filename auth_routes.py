import traceback
from flask import Blueprint, request, jsonify
from email_service import EmailVerificationService

auth_bp = Blueprint('auth', __name__)

email_service = None

def init_email_service(service):
    global email_service
    email_service = service

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

@auth_bp.route('/verify_code', methods=['POST'])
def verify_code():
    try:
        # 检查email_service是否已初始化
        if email_service is None:
            return jsonify({'success': False, 'message': '邮件服务未初始化'}), 500
            
        print("收到验证验证码请求")
        data = request.get_json(force=True)
        print(f"请求数据: {data}")
        
        if data is None:
            return jsonify({'success': False, 'message': '请求体为空或不是有效的 JSON'}), 400
            
        email = data.get('email')
        code = data.get('code')
        print(f"验证信息 - 邮箱: {email}, 验证码: {code}")
        
        if not email or not code:
            return jsonify({'success': False, 'message': '邮箱和验证码不能为空'}), 400
        
        is_valid, message = email_service.verify_code(email, code)
        print(f"验证结果: 有效={is_valid}, 消息={message}")
        
        return jsonify({'success': is_valid, 'message': message}), 200 if is_valid else 400
        
    except Exception as e:
        print(f"处理验证验证码请求时发生未预期的错误: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        # 检查email_service是否已初始化
        if email_service is None:
            return jsonify({'success': False, 'message': '邮件服务未初始化'}), 500
            
        print("收到登录请求")
        data = request.get_json(force=True)
        print(f"请求数据: {data}")
        
        if data is None:
            return jsonify({'success': False, 'message': '请求体为空或不是有效的 JSON'}), 400
            
        email = data.get('email')
        code = data.get('code')
        print(f"登录信息 - 邮箱: {email}, 验证码: {code}")
        
        if not email or not code:
            return jsonify({'success': False, 'message': '邮箱和验证码不能为空'}), 400
        
        is_valid, message = email_service.verify_code(email, code)
        print(f"验证结果: 有效={is_valid}, 消息={message}")
        
        if not is_valid:
            return jsonify({'success': False, 'message': message}), 400
        
        return jsonify({
            'success': True, 
            'message': '登录成功',
            'user': {
                'email': email
            }
        }), 200
        
    except Exception as e:
        print(f"处理登录请求时发生未预期的错误: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': f'服务器错误: {str(e)}'}), 500