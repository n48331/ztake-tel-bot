import os
import re
import json
import requests
import logging
from flask import Flask, request, jsonify

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration from environment variables
API_ENDPOINT = os.getenv('API_ENDPOINT', 'https://httpbin.org/post')
API_KEY = os.getenv('API_KEY', 'test-key')
VENDOR_ID = os.getenv('VENDOR_ID', '3')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
BOT_CONFIG_ENDPOINT = os.getenv('BOT_CONFIG_ENDPOINT', 'https://ztake.vercel.app/api/vendor/bot-token-secure')

# Global variables for bot configuration
BOT_TOKEN = None
AUTHORIZED_CHAT_ID = None
LAST_CONFIG_FETCH = None
CONFIG_CACHE_DURATION = 300  # 5 minutes in seconds

# Create Flask app
app = Flask(__name__)

def fetch_bot_configuration(vendor_id, force_refresh=False):
    """Fetch bot token and chat ID from API endpoint"""
    global BOT_TOKEN, AUTHORIZED_CHAT_ID, LAST_CONFIG_FETCH
    
    import time
    
    # Check if we need to refresh the configuration
    current_time = time.time()
    if not force_refresh and LAST_CONFIG_FETCH and (current_time - LAST_CONFIG_FETCH) < CONFIG_CACHE_DURATION:
        logger.info("Using cached bot configuration")
        return True
    
    try:
        url = f"{BOT_CONFIG_ENDPOINT}?vendor_id={vendor_id}"
        logger.info(f"Fetching bot configuration from: {url}")
        
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json',
            'User-Agent': 'TelegramBot-Webhook/1.0'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            config_data = response.json()
            old_chat_id = AUTHORIZED_CHAT_ID
            BOT_TOKEN = config_data.get('bot_token')
            AUTHORIZED_CHAT_ID = config_data.get('chat_id')
            LAST_CONFIG_FETCH = current_time
            
            logger.info(f"Bot configuration loaded: vendor_id={config_data.get('vendor_id')}, business_name={config_data.get('business_name')}")
            
            # Log if chat ID changed
            if old_chat_id and old_chat_id != AUTHORIZED_CHAT_ID:
                logger.warning(f"Chat ID changed from {old_chat_id} to {AUTHORIZED_CHAT_ID}")
            
            return True
        else:
            logger.error(f"Failed to fetch bot configuration: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"Error fetching bot configuration: {e}")
        return False

def refresh_bot_configuration():
    """Force refresh bot configuration"""
    global bot
    logger.info("Force refreshing bot configuration...")
    
    if fetch_bot_configuration(VENDOR_ID, force_refresh=True):
        # Reinitialize bot with new configuration
        bot = TransactionBot(BOT_TOKEN, API_ENDPOINT, API_KEY, VENDOR_ID, AUTHORIZED_CHAT_ID)
        logger.info("Bot reinitialized with updated configuration")
        return True
    return False

class TransactionBot:
    def __init__(self, token, api_endpoint, api_key, vendor_id, authorized_chat_id=None):
        self.token = token
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.vendor_id = vendor_id
        self.authorized_chat_id = authorized_chat_id
        
    def extract_utr_numbers(self, text):
        """Extract UTR numbers from text"""
        pattern = r'UTR\d{9,12}'
        matches = re.findall(pattern, text, re.IGNORECASE)
        return matches
    
    def extract_money_amounts(self, text):
        """Extract money amounts from text in various formats"""
        patterns = [
            r'₹\s*([\d,]+(?:\.\d{2})?)',           # ₹1,234.56
            r'Rs\.?\s*([\d,]+(?:\.\d{2})?)',      # Rs.1234.56 or Rs 1234
            r'INR\s*([\d,]+(?:\.\d{2})?)',        # INR 1234.56
            r'\$\s*([\d,]+(?:\.\d{2})?)',         # $1234.56
            r'amount\s*:?\s*([\d,]+(?:\.\d{2})?)', # amount: 1234.56
            r'([\d,]+(?:\.\d{2})?)\s*(?:rupees|rs)', # 1234.56 rupees
        ]
        
        amounts = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                try:
                    clean_amount = float(match.replace(',', ''))
                    amounts.append(clean_amount)
                except ValueError:
                    continue
        
        return amounts
    
    def is_authorized_chat(self, chat_id):
        """Check if the chat ID is authorized"""
        if not self.authorized_chat_id:
            logger.warning("No authorized chat ID configured")
            return False
        
        # Convert both to string for comparison
        return str(chat_id) == str(self.authorized_chat_id)
    
    def call_external_api(self, utr_numbers, amounts, original_text, user_info=None):
        """Call external API with extracted data"""
        # Convert arrays to single values as expected by API
        utr_value = utr_numbers[0] if utr_numbers else ""
        amount_value = amounts[0] if amounts else 0.0
        vendor_id_value = int(self.vendor_id) if self.vendor_id else 3
        
        payload = {
            'utr': utr_value,
            'amount': amount_value,
            'vendor_id': vendor_id_value
        }
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}',
            'User-Agent': 'TelegramBot-Webhook/1.0'
        }
        
        try:
            logger.info(f"Sending payload to API: {payload}")
            response = requests.post(
                self.api_endpoint, 
                json=payload, 
                headers=headers, 
                timeout=10
            )
            
            logger.info(f"API response status: {response.status_code}")
            logger.info(f"API response headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                return {'success': True, 'data': response.json()}
            else:
                error_details = {
                    'success': False, 
                    'error': f'API returned status {response.status_code}',
                    'response': response.text[:500],
                    'status_code': response.status_code,
                    'headers': dict(response.headers)
                }
                logger.error(f"API call failed: {error_details}")
                return error_details
                
        except requests.exceptions.Timeout:
            return {'success': False, 'error': 'API request timed out'}
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': f'Network error: {str(e)}'}
    
    def send_message(self, chat_id, text, parse_mode='Markdown'):
        """Send message via Telegram Bot API"""
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': text,
            'parse_mode': parse_mode
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False
    
    def process_message(self, message):
        """Process incoming message and extract data"""
        text = message.get('text', '')
        chat_id = message['chat']['id']
        user = message.get('from', {})
        
        # Check if chat is authorized
        if not self.is_authorized_chat(chat_id):
            logger.warning(f"Unauthorized chat ID: {chat_id}. Authorized: {self.authorized_chat_id}")
            self.send_message(chat_id, "❌ Unauthorized access. This bot is not configured for this chat.")
            return
        
        # Extract data
        utr_numbers = self.extract_utr_numbers(text)
        amounts = self.extract_money_amounts(text)
        
        if not utr_numbers and not amounts:
            response_text = (
                "❌ No UTR numbers or amounts found.\n\n"
                "**Examples:**\n"
                "• UTR123456789\n"
                "• ₹1,234.56\n"
                "• Payment of ₹5000 via UTR987654321"
            )
            self.send_message(chat_id, response_text)
            return
        
        # Create response message
        response_parts = ["🔍 **Extracted Data:**"]
        
        if utr_numbers:
            response_parts.append(f"📝 UTR: {', '.join(utr_numbers)}")
        
        if amounts:
            amounts_str = ', '.join([f"₹{amount:,.2f}" for amount in amounts])
            response_parts.append(f"💰 Amounts: {amounts_str}")
        
        response_parts.append("📤 Sending to API...")
        
        # Send initial response
        self.send_message(chat_id, '\n'.join(response_parts))
        
        # Prepare user info
        user_info = {
            'user_id': user.get('id'),
            'username': user.get('username'),
            'first_name': user.get('first_name'),
            'last_name': user.get('last_name')
        }
        
        # Call external API
        api_result = self.call_external_api(utr_numbers, amounts, text, user_info)
        
        # Send final response
        if api_result['success']:
            final_msg = "✅ **Successfully sent to API!**"
        else:
            error_msg = f"❌ **API call failed:** {api_result['error']}"
            
            # Add more details for debugging
            if 'response' in api_result and api_result['response']:
                error_msg += f"\n\n**Server Response:**\n```\n{api_result['response'][:300]}\n```"
            
            if 'status_code' in api_result:
                error_msg += f"\n**Status Code:** {api_result['status_code']}"
            
            final_msg = error_msg
        
        self.send_message(chat_id, final_msg)
    
    def process_start_command(self, message):
        """Handle /start command"""
        chat_id = message['chat']['id']
        
        # Check if chat is authorized
        if not self.is_authorized_chat(chat_id):
            logger.warning(f"Unauthorized chat ID for /start: {chat_id}. Authorized: {self.authorized_chat_id}")
            self.send_message(chat_id, "❌ Unauthorized access. This bot is not configured for this chat.")
            return
        
        welcome_text = """
🤖 **Transaction Bot Started!**

**What I can extract:**
• UTR numbers (UTR123456789)
• Money amounts (₹1,234.56, Rs 500, INR 1000)

**Example:**
"Payment of ₹15,000 via UTR123456789"

Just send me any message with transaction details!
        """
        self.send_message(chat_id, welcome_text.strip())

# Initialize bot (will be configured dynamically)
bot = None

# Flask routes
@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'service': 'telegram-utr-bot',
        'message': 'Bot is running with webhooks on Render',
        'webhook_path': '/webhook',
        'vendor_id': VENDOR_ID,
        'bot_config_endpoint': BOT_CONFIG_ENDPOINT
    })

@app.route('/health')
def health():
    """Health check for Render"""
    return jsonify({'status': 'healthy'}), 200

@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle webhook requests from Telegram"""
    global bot
    
    try:
        update = request.get_json()
        
        if not update:
            return jsonify({'error': 'No data received'}), 400
        
        logger.info(f"Received update: {update}")
        
        # Always fetch fresh bot configuration to ensure we have the latest chat ID
        if not fetch_bot_configuration(VENDOR_ID, force_refresh=True):
            logger.error("Failed to fetch bot configuration")
            return jsonify({'error': 'Failed to fetch bot configuration'}), 500
        
        # Initialize or reinitialize bot with fresh configuration
        bot = TransactionBot(BOT_TOKEN, API_ENDPOINT, API_KEY, VENDOR_ID, AUTHORIZED_CHAT_ID)
        logger.info(f"Bot initialized with fresh configuration - Chat ID: {AUTHORIZED_CHAT_ID}")
        
        # Log the incoming chat ID for debugging
        if 'message' in update:
            incoming_chat_id = update['message']['chat']['id']
            logger.info(f"Incoming message from chat ID: {incoming_chat_id}, Authorized: {AUTHORIZED_CHAT_ID}")
        
        # Handle different update types
        if 'message' in update:
            message = update['message']
            
            # Handle commands
            if 'text' in message and message['text'].startswith('/'):
                command = message['text'].split()[0]
                
                if command == '/start':
                    bot.process_start_command(message)
                else:
                    # Unknown command
                    chat_id = message['chat']['id']
                    bot.send_message(chat_id, "Unknown command. Send /start to begin.")
            
            # Handle regular messages
            elif 'text' in message:
                bot.process_message(message)
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/set_webhook', methods=['POST'])
def set_webhook():
    """Set webhook URL for the bot (for manual setup)"""
    global bot
    
    # Fetch bot configuration if not already done
    if not BOT_TOKEN or not bot:
        if not fetch_bot_configuration(VENDOR_ID):
            return jsonify({'error': 'Failed to fetch bot configuration'}), 500
        
        # Initialize bot with fetched configuration
        bot = TransactionBot(BOT_TOKEN, API_ENDPOINT, API_KEY, VENDOR_ID, AUTHORIZED_CHAT_ID)
    
    if not WEBHOOK_URL:
        return jsonify({'error': 'WEBHOOK_URL not configured'}), 400
    
    webhook_url = f"{WEBHOOK_URL}/webhook"
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        response = requests.post(url, json={'url': webhook_url})
        
        if response.status_code == 200:
            return jsonify({
                'success': True, 
                'webhook_url': webhook_url,
                'telegram_response': response.json()
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Failed to set webhook: {response.text}'
            }), 400
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/webhook_info')
def webhook_info():
    """Get current webhook information"""
    global bot
    
    # Fetch bot configuration if not already done
    if not BOT_TOKEN or not bot:
        if not fetch_bot_configuration(VENDOR_ID):
            return jsonify({'error': 'Failed to fetch bot configuration'}), 500
        
        # Initialize bot with fetched configuration
        bot = TransactionBot(BOT_TOKEN, API_ENDPOINT, API_KEY, VENDOR_ID, AUTHORIZED_CHAT_ID)
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()
        else:
            return jsonify({'error': 'Failed to get webhook info'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/bot_config')
def bot_config():
    """Get current bot configuration"""
    global BOT_TOKEN, AUTHORIZED_CHAT_ID, LAST_CONFIG_FETCH
    
    import time
    current_time = time.time()
    last_fetch_ago = current_time - LAST_CONFIG_FETCH if LAST_CONFIG_FETCH else None
    
    return jsonify({
        'bot_token_configured': bool(BOT_TOKEN),
        'authorized_chat_id': AUTHORIZED_CHAT_ID,
        'vendor_id': VENDOR_ID,
        'api_endpoint': API_ENDPOINT,
        'last_config_fetch': LAST_CONFIG_FETCH,
        'seconds_since_last_fetch': last_fetch_ago,
        'cache_duration': CONFIG_CACHE_DURATION
    })

@app.route('/refresh_config', methods=['POST'])
def refresh_config():
    """Force refresh bot configuration"""
    if refresh_bot_configuration():
        return jsonify({
            'success': True,
            'message': 'Bot configuration refreshed successfully',
            'authorized_chat_id': AUTHORIZED_CHAT_ID,
            'bot_token_configured': bool(BOT_TOKEN)
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Failed to refresh bot configuration'
        }), 500


if __name__ == '__main__':
    # Try to fetch initial configuration
    if not fetch_bot_configuration(VENDOR_ID):
        logger.error("Failed to fetch initial bot configuration!")
        exit(1)
    
    # Initialize bot
    bot = TransactionBot(BOT_TOKEN, API_ENDPOINT, API_KEY, VENDOR_ID, AUTHORIZED_CHAT_ID)
    logger.info("Bot initialized successfully")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)