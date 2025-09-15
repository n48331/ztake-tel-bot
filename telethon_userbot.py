import os
import re
import json
import asyncio
import logging
from typing import List, Tuple, Optional

from dotenv import load_dotenv
import httpx
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import PeerChannel


# Setup logging consistent with existing bot
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env
load_dotenv()

# Configuration from environment variables (re-using names where applicable)
API_ENDPOINT = os.getenv('API_ENDPOINT', 'https://httpbin.org/post')
API_KEY = os.getenv('API_KEY', 'test-key')
VENDOR_ID = int(os.getenv('VENDOR_ID', '3'))
BOT_CONFIG_ENDPOINT = os.getenv('BOT_CONFIG_ENDPOINT', 'https://ztakepayments.vercel.app/api/vendor/bot-token-secure')

# Telethon credentials
API_ID_ENV = os.getenv('API_ID')
API_HASH_ENV = os.getenv('API_HASH')
SESSION_NAME = os.getenv('SESSION_NAME', 'ztake_userbot')
TELETHON_STRING_SESSION_ENV = os.getenv('TELETHON_STRING_SESSION', '')
BOT_TOKEN_ENV = os.getenv('BOT_TOKEN', '')

# Target chat and source bot filter
AUTHORIZED_CHAT_ID_ENV = os.getenv('AUTHORIZED_CHAT_ID')  # may be numeric id or @username
SOURCE_BOT_USERNAME_ENV = os.getenv('SOURCE_BOT_USERNAME', '')  # username of the first bot in the group to process


async def fetch_runtime_config() -> dict:
    """Fetch credentials and chat config from central API, with env as override."""
    params = {'vendor_id': VENDOR_ID}
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json',
        'User-Agent': 'TelegramUserbot/1.0'
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(BOT_CONFIG_ENDPOINT, params=params, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
        else:
            logger.warning(f"Config fetch failed {resp.status_code}: {resp.text[:200]}")
            data = {}
    except Exception as e:
        logger.error(f"Error fetching config: {e}")
        data = {}

    # Normalize keys we care about
    api_id = data.get('api_id') or data.get('API_ID') or API_ID_ENV
    api_hash = data.get('api_hash') or data.get('API_HASH') or API_HASH_ENV
    chat_id = data.get('chat_id') or data.get('AUTHORIZED_CHAT_ID') or AUTHORIZED_CHAT_ID_ENV
    source_bot = data.get('source_bot_username') or data.get('SOURCE_BOT_USERNAME') or SOURCE_BOT_USERNAME_ENV
    string_session = data.get('telethon_string_session') or data.get('TELETHON_STRING_SESSION') or TELETHON_STRING_SESSION_ENV

    # Types
    api_id_int = int(api_id) if api_id is not None and str(api_id).isdigit() else 0

    return {
        'api_id': api_id_int,
        'api_hash': api_hash or '',
        'authorized_chat_id': str(chat_id) if chat_id is not None else None,
        'source_bot_username': source_bot or '',
        'telethon_string_session': string_session or '',
    }


class TransactionUserbot:
    def __init__(self, client: TelegramClient):
        self.client = client

    # ---- Extraction logic ported from webhook bot ----
    def extract_reference_numbers(self, text: str) -> List[str]:
        patterns = [
            r'UPI\s*Ref(?:erence)?\s*(?:no\.?|number)?\s*[:\-]?\s*(\d{8,20})',
            r'Ref(?:erence)?\s*(?:no\.?|number)?\s*[:\-]?\s*(\d{8,20})',
            r'Transaction\s*ID[:\-]?\s*(\d{8,20})',
            r'Txn\s*ID[:\-]?\s*(\d{8,20})',
        ]

        matches: List[str] = []
        for pattern in patterns:
            found = re.findall(pattern, text, re.IGNORECASE)
            matches.extend(found)

        # Deduplicate preserving order
        seen = set()
        unique_matches: List[str] = []
        for match in matches:
            if match not in seen:
                seen.add(match)
                unique_matches.append(match)
        return unique_matches

    def extract_money_amounts(self, text: str) -> List[float]:
        patterns = [
            r'₹\s*([\d,]+(?:\.\d{2})?)',
            r'Rs\.?\s*([\d,]+(?:\.\d{2})?)',
            r'INR\s*([\d,]+(?:\.\d{2})?)',
            r'\$\s*([\d,]+(?:\.\d{2})?)',
            r'amount\s*:?\s*([\d,]+(?:\.\d{2})?)',
            r'([\d,]+(?:\.\d{2})?)\s*(?:rupees|rs)',
            r'credited\s+for\s+Rs\.?\s*([\d,]+(?:\.\d{2})?)',
            r'debited\s+for\s+Rs\.?\s*([\d,]+(?:\.\d{2})?)',
        ]

        amounts: List[float] = []
        for pattern in patterns:
            for match in re.findall(pattern, text, re.IGNORECASE):
                try:
                    amounts.append(float(match.replace(',', '')))
                except ValueError:
                    continue

        # Deduplicate preserving order
        seen = set()
        unique_amounts: List[float] = []
        for amount in amounts:
            if amount not in seen:
                seen.add(amount)
                unique_amounts.append(amount)
        return unique_amounts

    # ---- API call logic, converted to async httpx ----
    async def call_external_api(self, reference_numbers: List[str], amounts: List[float], original_text: str, user_info: Optional[dict] = None) -> dict:
        ref_value = reference_numbers[0] if reference_numbers else ''
        amount_value = amounts[0] if amounts else 0.0
        payload = {
            'utr': ref_value,
            'amount': amount_value,
            'vendor_id': VENDOR_ID,
        }
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}',
            'User-Agent': 'TelegramUserbot/1.0'
        }

        try:
            logger.info(f"Sending payload to API: {payload}")
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(API_ENDPOINT, json=payload, headers=headers)
            logger.info(f"API response status: {response.status_code}")
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            else:
                return {
                    'success': False,
                    'error': f'API returned status {response.status_code}',
                    'response': response.text[:500],
                    'status_code': response.status_code,
                    'headers': dict(response.headers),
                }
        except httpx.TimeoutException:
            return {'success': False, 'error': 'API request timed out'}
        except httpx.RequestError as e:
            return {'success': False, 'error': f'Network error: {str(e)}'}

    # ---- Messaging helpers ----
    async def send_markdown(self, chat, text: str) -> None:
        await self.client.send_message(chat, text, parse_mode='md')

    # ---- Core processing ----
    async def process_text(self, chat, text: str, from_user) -> None:
        reference_numbers = self.extract_reference_numbers(text)
        amounts = self.extract_money_amounts(text)

        if not reference_numbers and not amounts:
            response_text = (
                "❌ No reference numbers or amounts found.\n\n"
                # "**Examples:**\n"
                # "• UPI Ref no 690518190930\n"
                # "• Rs.2.00\n"
                # "• credited for Rs.2.00 on 12-09-25 and debited from a/c no. XX0076 (UPI Ref no 690518190930)"
            )
            await self.send_markdown(chat, response_text)
            return

        response_parts = ["🔍 **Extracted Data:**"]
        if reference_numbers:
            response_parts.append(f"📝 Reference No: {', '.join(reference_numbers)}")
        if amounts:
            amounts_str = ', '.join([f"₹{amount:,.2f}" for amount in amounts])
            response_parts.append(f"💰 Amounts: {amounts_str}")
        response_parts.append("📤 Sending to API...")
        await self.send_markdown(chat, "\n".join(response_parts))

        user_info = {
            'user_id': getattr(from_user, 'id', None),
            'username': getattr(from_user, 'username', None),
            'first_name': getattr(from_user, 'first_name', None),
            'last_name': getattr(from_user, 'last_name', None),
        }

        api_result = await self.call_external_api(reference_numbers, amounts, text, user_info)

        if api_result.get('success'):
            final_msg = "✅ **Successfully sent to API!**"
        else:
            error_msg = f"❌ **API call failed:** {api_result.get('error')}"
            if api_result.get('response'):
                error_msg += f"\n\n**Server Response:**\n```\n{api_result['response'][:300]}\n```"
            if api_result.get('status_code') is not None:
                error_msg += f"\n**Status Code:** {api_result['status_code']}"
            final_msg = error_msg

        await self.send_markdown(chat, final_msg)


async def resolve_authorized_chat(client: TelegramClient, target: Optional[str]):
    if not target:
        raise RuntimeError('AUTHORIZED_CHAT_ID is not set')
    # If numeric id
    try:
        return int(target)
    except ValueError:
        pass
    # Otherwise treat as username/link
    return target


async def main() -> None:
    cfg = await fetch_runtime_config()
    api_id = cfg['api_id']
    api_hash = cfg['api_hash']
    if not api_id or not api_hash:
        raise RuntimeError('api_id/api_hash missing; provide via config API or environment')

    # Prefer headless session if provided (for hosting). If BOT_TOKEN is set, we'll start as a bot.
    if BOT_TOKEN_ENV:
        client = TelegramClient(SESSION_NAME, api_id, api_hash)
        await client.start(bot_token=BOT_TOKEN_ENV)
        logger.info('Telethon bot client started (testing mode)')
    else:
        if cfg['telethon_string_session']:
            client = TelegramClient(StringSession(cfg['telethon_string_session']), api_id, api_hash)
        else:
            client = TelegramClient(SESSION_NAME, api_id, api_hash)
        await client.start()
        logger.info('Telethon user client started')

    authorized_chat = await resolve_authorized_chat(client, cfg['authorized_chat_id'])
    userbot = TransactionUserbot(client)

    # Resolve source bot peer if username provided (optional optimization)
    source_bot_username = cfg['source_bot_username'].lstrip('@') if cfg['source_bot_username'] else ''

    me = await client.get_me()
    running_as_bot = bool(getattr(me, 'bot', False))

    @client.on(events.NewMessage(chats=authorized_chat))
    async def handler(event):
        try:
            sender = await event.get_sender()
            # Filtering rules:
            # - If running as a bot (testing), accept all senders to allow smoke-tests
            # - If running as a user, enforce bot-only sender and optional username match
            if not running_as_bot:
                if source_bot_username:
                    if not getattr(sender, 'bot', False):
                        return
                    if sender.username and sender.username.lower() != source_bot_username.lower():
                        return
                else:
                    if not getattr(sender, 'bot', False):
                        return

            text = event.message.message or ''
            await userbot.process_text(event.chat_id, text, sender)
        except Exception as e:
            logger.exception(f"Error in handler: {e}")

    logger.info('Listening for new messages...')
    await client.run_until_disconnected()


if __name__ == '__main__':
    asyncio.run(main())


