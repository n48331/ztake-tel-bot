import re
import requests
import json
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
API_ENDPOINT = os.getenv('API_ENDPOINT', 'https://httpbin.org/post')  # Using httpbin for testing
API_KEY = os.getenv('API_KEY', 'test-key')
VENDOR_ID = os.getenv('VENDOR_ID', '3')
def extract_utr_numbers(text):
    """Extract UTR numbers from text"""
    # Pattern matches UTR followed by 9-12 digits
    pattern = r'UTR\d{9,12}'
    matches = re.findall(pattern, text, re.IGNORECASE)
    return matches

def extract_money_amounts(text):
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
                # Remove commas and convert to float
                clean_amount = float(match.replace(',', ''))
                amounts.append(clean_amount)
            except ValueError:
                continue
    
    return amounts

def call_external_api(utr_numbers, amounts, VENDOR_ID, user_info=None):
    """Call external API with extracted data"""
    # Convert arrays to single values as expected by API
    utr_value = utr_numbers[0] if utr_numbers else ""
    amount_value = amounts[0] if amounts else 0.0
    vendor_id_value = int(VENDOR_ID) if VENDOR_ID else 3
    
    payload = {
        'utr': utr_value,
        'amount': amount_value,
        'vendor_id': vendor_id_value
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {API_KEY}',
        'User-Agent': 'TelegramBot/1.0'
    }
    
    try:
        response = requests.post(
            API_ENDPOINT, 
            json=payload, 
            headers=headers, 
            timeout=10
        )
        
        if response.status_code == 200:
            return {'success': True, 'data': response.json()}
        else:
            return {
                'success': False, 
                'error': f'API returned status {response.status_code}',
                'response': response.text[:200]
            }
            
    except requests.exceptions.Timeout:
        return {'success': False, 'error': 'API request timed out'}
    except requests.exceptions.RequestException as e:
        return {'success': False, 'error': f'Network error: {str(e)}'}

async def start(update: Update, context):
    """Handle /start command"""
    message = """
🤖 **Transaction Bot Started!**

**What I can do:**
• Extract UTR numbers (like UTR123456789)
• Extract money amounts in various formats
• Send extracted data to your API endpoint

**Supported formats:**
• UTR numbers: UTR123456789
• Money: ₹1,234.56, Rs 500, INR 1000, $100, amount: 2500

**Example message:**
"Payment of ₹15,000 completed via UTR123456789"

Just send me any message with transaction details and I'll process it automatically!
    """
    await update.message.reply_text(message, parse_mode='Markdown')

async def help_command(update: Update, context):
    """Handle /help command"""
    help_text = """
📖 **Help - Transaction Bot**

**Commands:**
/start - Start the bot and get welcome message
/help - Show this help message
/test - Send a test message to verify extraction

```
    """
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def test_command(update: Update, context):
    """Handle /test command"""
    test_message = "Test payment of ₹12,345.67 completed via UTR987654321012"
    
    utr_numbers = extract_utr_numbers(test_message)
    amounts = extract_money_amounts(test_message)
    
    response = f"""
🧪 **Test Extraction Results:**

**Test Message:** `{test_message}`

**Extracted Data:**
• UTR Numbers: {utr_numbers if utr_numbers else 'None found'}
• Amounts: {[f'₹{a:,.2f}' for a in amounts] if amounts else 'None found'}

This is a test - no API call was made.
    """
    await update.message.reply_text(response, parse_mode='Markdown')

async def process_message(update: Update, context):
    """Process text messages to extract UTR and amounts"""
    text = update.message.text
    user = update.effective_user
    
    # Extract data
    utr_numbers = extract_utr_numbers(text)
    amounts = extract_money_amounts(text)
    
    if not utr_numbers and not amounts:
        await update.message.reply_text(
            "❌ No UTR numbers or amounts found in your message.\n\n"
            "Make sure to include:\n"
            "• UTR numbers like: UTR123456789\n"
            "• Money amounts like: ₹1,234.56, Rs 500, INR 1000\n\n"
            "Send /help for more examples."
        )
        return
    
    # Create response message
    response_parts = ["🔍 **Extracted Data:**\n"]
    
    if utr_numbers:
        response_parts.append(f"📝 **UTR Numbers:** {', '.join(utr_numbers)}")
    
    if amounts:
        amounts_formatted = [f"₹{amount:,.2f}" for amount in amounts]
        response_parts.append(f"💰 **Amounts:** {', '.join(amounts_formatted)}")
    
    response_parts.append("\n📤 Sending to API...")
    
    await update.message.reply_text(
        '\n'.join(response_parts), 
        parse_mode='Markdown'
    )
    
    # Prepare user info
    user_info = {
        'user_id': user.id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    
    # Call API
    api_result = call_external_api(utr_numbers, amounts, VENDOR_ID, user_info)
    
    if api_result['success']:
        success_msg = "✅ **Successfully sent to API!**"
        
        # Show API response if available
        if 'data' in api_result and api_result['data']:
            # Truncate long responses
            response_str = json.dumps(api_result['data'], indent=2)
            if len(response_str) > 500:
                response_str = response_str[:500] + "..."
            success_msg += f"\n\n📋 **API Response:**\n```json\n{response_str}\n```"
        
        await update.message.reply_text(success_msg, parse_mode='Markdown')
    else:
        error_msg = f"❌ **API call failed:** {api_result['error']}"
        if 'response' in api_result:
            error_msg += f"\n\n**Response:** {api_result['response']}"
        await update.message.reply_text(error_msg, parse_mode='Markdown')

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found! Please set it in .env file")
        print("Create a .env file with: BOT_TOKEN=your_bot_token_here")
        return
    
    print(f"🤖 Starting bot...")
    print(f"📡 API Endpoint: {API_ENDPOINT}")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("test", test_command))
    
    # Add message handler for text processing
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, process_message))
    
    print("🚀 Bot is running... Press Ctrl+C to stop")
    
    # Start polling
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()