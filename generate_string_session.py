import os
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.sessions import StringSession


def main():
    load_dotenv()
    api_id = int(os.getenv('API_ID', '0'))
    api_hash = os.getenv('API_HASH', '')
    if not api_id or not api_hash:
        print('Please set API_ID and API_HASH in environment or .env')
        return

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session = client.session.save()
        print('\nYour TELETHON_STRING_SESSION (store securely as env var):')
        print(session)


if __name__ == '__main__':
    main()


