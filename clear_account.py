import redis
import yaml
from redis import ConnectionPool, RedisError

def clear_all_accounts():
    try:
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

        redis_client.ping()
        print("Redis连接成功")
        
        user_keys = redis_client.keys("user:*")
        verification_keys = redis_client.keys("verification_code:*")
        
        print(f"找到 {len(user_keys)} 个用户账户")
        print(f"找到 {len(verification_keys)} 个验证码记录")
        
        if user_keys:
            redis_client.delete(*user_keys)
            print("用户账户已删除")
            
        if verification_keys:
            redis_client.delete(*verification_keys)
            print("验证码记录已删除")

        redis_client.delete("user_counter")
        print("用户计数器已重置")
        
        print("所有账户数据已清除完成")
        
    except RedisError as e:
        print(f"Redis错误: {str(e)}")
    except FileNotFoundError:
        print("配置文件 config.yml 未找到")
    except Exception as e:
        print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    confirmation = input("确定要清除所有账户数据吗？此操作不可恢复！(输入 'YES' 确认): ")
    if confirmation == 'YES':
        clear_all_accounts()
    else:
        print("操作已取消")