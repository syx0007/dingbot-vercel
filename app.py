import json
import requests
import hashlib
import hmac
import base64
import urllib.parse
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# 钉钉机器人配置
DINGTALK_SECRET = "SECc152bf75a424a08ff836e76b5d68c3a9eed16b3c479b259e9a9de5cb5f47d1e9"
DINGTALK_WEBHOOK = "https://oapi.dingtalk.com/robot/send?access_token=430e50466d5efaa9130747f6e6d2139f95b7171390c45774342b68d0ce32abac"

# 音乐API配置
MUSIC_API_URL = "https://api.ikunshare.com:8000/url"
MUSIC_API_HEADERS = {
    'User-Agent': 'lx-music-mobile/2.0.0',
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'X-Request-Key': 'WIN_bbf2e273-FW3YIR92N8HQY4YQ',
    'Host': 'api.ikunshare.com:8000',
    'Connection': 'Keep-Alive',
    'Accept-Encoding': 'gzip'
}

def verify_dingtalk_signature(timestamp, sign):
    """
    验证钉钉机器人签名
    """
    secret_enc = DINGTALK_SECRET.encode('utf-8')
    string_to_sign = f"{timestamp}\n{DINGTALK_SECRET}"
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    my_sign = base64.b64encode(hmac_code).decode('utf-8')
    return my_sign == sign

def send_dingtalk_message(content, at_user_ids=None):
    """
    发送钉钉机器人消息
    """
    timestamp = str(round(datetime.now().timestamp() * 1000))
    sign = generate_dingtalk_signature(timestamp)
    
    params = {
        "access_token": DINGTALK_WEBHOOK.split('=')[-1],
        "timestamp": timestamp,
        "sign": sign
    }
    
    data = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }
    
    if at_user_ids:
        data["at"] = {
            "atUserIds": at_user_ids
        }
    
    response = requests.post(DINGTALK_WEBHOOK, params=params, json=data)
    return response.json()

def generate_dingtalk_signature(timestamp):
    """
    生成钉钉机器人签名
    """
    secret = DINGTALK_SECRET
    secret_enc = secret.encode('utf-8')
    string_to_sign = f"{timestamp}\n{secret}"
    string_to_sign_enc = string_to_sign.encode('utf-8')
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    return base64.b64encode(hmac_code).decode('utf-8')

def get_music_info(song_id, source, quality='128k'):
    """
    从音乐API获取音乐信息
    """
    params = {
        'source': source,
        'songId': song_id,
        'quality': quality
    }
    
    try:
        response = requests.get(
            MUSIC_API_URL,
            headers=MUSIC_API_HEADERS,
            params=params,
            timeout=8
        )
        response.raise_for_status()
        
        data = response.json()
        return {
            'success': True,
            'url': data.get('url'),
            'info': data.get('info'),
            'quality': data.get('quality'),
            'expire': data.get('expire')
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def parse_music_command(text):
    """
    解析音乐命令
    格式: @机器人 getmusic id=xxx s=xxx p=xxx
    """
    parts = text.split()
    if len(parts) < 2 or parts[0].lower() != 'getmusic':
        return None
    
    params = {}
    for part in parts[1:]:
        if '=' in part:
            key, value = part.split('=', 1)
            params[key.lower()] = value
    
    return params

@app.route('/dingtalk', methods=['POST'])
def handle_dingtalk():
    """
    处理钉钉机器人回调
    """
    data = request.json
    
    # 验证签名
    timestamp = request.headers.get('timestamp')
    sign = request.headers.get('sign')
    if not verify_dingtalk_signature(timestamp, sign):
        return jsonify({'error': 'Invalid signature'}), 403
    
    # 检查是否被@
    if not data.get('isAt', False):
        return jsonify({'msg': 'Not @ message, ignore'})
    
    # 获取消息内容
    text = data.get('text', {}).get('content', '').strip()
    sender_id = data.get('senderStaffId')
    
    # 解析音乐命令
    params = parse_music_command(text)
    if not params:
        return jsonify({'msg': 'Invalid command format'})
    
    # 获取音乐信息
    song_id = params.get('id')
    source = params.get('s')
    quality = params.get('p', '128k')
    
    if not song_id or not source:
        send_dingtalk_message(
            "❌ 参数错误，请使用格式: @机器人 getmusic id=歌曲ID s=来源 [p=音质]",
            at_user_ids=[sender_id]
        )
        return jsonify({'msg': 'Missing parameters'})
    
    music_info = get_music_info(song_id, source, quality)
    
    # 发送结果到钉钉
    if music_info.get('success'):
        message = f"""
        🎵 音乐信息:
        - 来源: {source}
        - 歌曲ID: {song_id}
        - 音质: {quality}
        - 播放地址: {music_info['url']}
        - 信息: {music_info['info']}
        - 过期时间: {music_info['expire']}
        """
    else:
        message = f"""
        ❌ 获取音乐信息失败:
        - 错误: {music_info.get('error', '未知错误')}
        - 请检查参数是否正确
        """
    
    send_dingtalk_message(message, at_user_ids=[sender_id])
    
    return jsonify({'msg': 'Message processed'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
