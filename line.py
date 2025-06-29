import requests
import json

# ファイルからトークンとユーザーIDを読み込み
with open("token.txt", 'r') as f:
    channel_access_token = f.read().strip()

with open("user_id.txt", 'r') as f:
    user_id = f.read().strip()

# 送信するメッセージの内容
items = ['apple', 'orange', 'pineapple']
message_text = '\n'.join(items)

# LINE Messaging APIのエンドポイント
endpoint = 'https://api.line.me/v2/bot/message/push'

# リクエストヘッダー
headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {channel_access_token}'
}

# リクエストボディ
payload = {
    'to': user_id,
    'messages': [
        {
            'type': 'text',
            'text': message_text
        }
    ]
}

# リクエストを送信
response = requests.post(endpoint, headers=headers, data=json.dumps(payload))

# 結果を表示
print(f'Status code: {response.status_code}')
print(f'Response: {response.text}')