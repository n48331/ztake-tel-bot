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
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ENDPOINT = os.getenv('API_ENDPOINT', 'https://httpbin.org/post')
API_KEY = os.getenv('API_KEY', 'test-key')
VENDOR_ID = os.getenv('VENDOR_ID', '3')
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')

# Create Flask app
app = Flask(__name__)

class TransactionBot:
    def __init__(self, token, api_endpoint, api_key, vendor_id):
        self.token = token
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.vendor_id = vendor_id
        
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

# Initialize bot
bot = TransactionBot(BOT_TOKEN, API_ENDPOINT, API_KEY, VENDOR_ID)

# Flask routes
@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'service': 'telegram-utr-bot',
        'message': 'Bot is running with webhooks on Render',
        'webhook_path': f'/{BOT_TOKEN}' if BOT_TOKEN else '/webhook'
    })

@app.route('/health')
def health():
    """Health check for Render"""
    return jsonify({'status': 'healthy'}), 200

@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    """Handle webhook requests from Telegram"""
    if not BOT_TOKEN:
        return jsonify({'error': 'Bot token not configured'}), 500
    
    try:
        update = request.get_json()
        
        if not update:
            return jsonify({'error': 'No data received'}), 400
        
        logger.info(f"Received update: {update}")
        
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
    if not BOT_TOKEN:
        return jsonify({'error': 'BOT_TOKEN not configured'}), 400
    
    if not WEBHOOK_URL:
        return jsonify({'error': 'WEBHOOK_URL not configured'}), 400
    
    webhook_url = f"{WEBHOOK_URL}/{BOT_TOKEN}"
    
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
    if not BOT_TOKEN:
        return jsonify({'error': 'BOT_TOKEN not configured'}), 400
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()
        else:
            return jsonify({'error': 'Failed to get webhook info'}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is required!")
        exit(1)
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)