#!/usr/bin/env python3
"""
Script to update the Telegram bot webhook URL to use the new /webhook endpoint
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def update_webhook():
    """Update the Telegram bot webhook URL"""
    
    # Get configuration from environment
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    VENDOR_ID = os.getenv('VENDOR_ID', '3')
    API_KEY = os.getenv('API_KEY')
    BOT_CONFIG_ENDPOINT = os.getenv('BOT_CONFIG_ENDPOINT', 'https://ztake.vercel.app/api/vendor/bot-token-secure')
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found in environment variables")
        return False
    
    if not WEBHOOK_URL:
        print("❌ WEBHOOK_URL not found in environment variables")
        return False
    
    # First, try to get the bot token from the API
    print("🔄 Fetching bot configuration from API...")
    try:
        url = f"{BOT_CONFIG_ENDPOINT}?vendor_id={VENDOR_ID}"
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json',
            'User-Agent': 'TelegramBot-Webhook/1.0'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            config_data = response.json()
            api_bot_token = config_data.get('bot_token')
            chat_id = config_data.get('chat_id')
            
            print(f"✅ Fetched bot configuration:")
            print(f"   Bot Token: {api_bot_token[:20]}...")
            print(f"   Chat ID: {chat_id}")
            print(f"   Business: {config_data.get('business_name')}")
            
            # Use the API bot token instead of env token
            BOT_TOKEN = api_bot_token
        else:
            print(f"⚠️  Failed to fetch from API ({response.status_code}), using env token")
            
    except Exception as e:
        print(f"⚠️  Error fetching from API: {e}, using env token")
    
    # Set the new webhook URL
    new_webhook_url = f"{WEBHOOK_URL}/webhook"
    
    print(f"\n🔄 Updating webhook URL to: {new_webhook_url}")
    
    try:
        # First, delete the old webhook
        print("🗑️  Deleting old webhook...")
        delete_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook"
        delete_response = requests.post(delete_url)
        
        if delete_response.status_code == 200:
            print("✅ Old webhook deleted successfully")
        else:
            print(f"⚠️  Failed to delete old webhook: {delete_response.text}")
        
        # Set the new webhook
        print("🔗 Setting new webhook...")
        set_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
        webhook_data = {
            'url': new_webhook_url
        }
        
        set_response = requests.post(set_url, json=webhook_data)
        
        if set_response.status_code == 200:
            result = set_response.json()
            if result.get('ok'):
                print("✅ Webhook updated successfully!")
                print(f"   New URL: {new_webhook_url}")
                return True
            else:
                print(f"❌ Failed to set webhook: {result.get('description')}")
                return False
        else:
            print(f"❌ Failed to set webhook: {set_response.status_code} - {set_response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error updating webhook: {e}")
        return False

def check_webhook_info():
    """Check current webhook information"""
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    
    if not BOT_TOKEN:
        print("❌ BOT_TOKEN not found")
        return
    
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo"
        response = requests.get(url)
        
        if response.status_code == 200:
            info = response.json()
            print("\n📋 Current Webhook Info:")
            print(f"   URL: {info.get('result', {}).get('url', 'Not set')}")
            print(f"   Pending Updates: {info.get('result', {}).get('pending_update_count', 0)}")
            print(f"   Last Error: {info.get('result', {}).get('last_error_message', 'None')}")
        else:
            print(f"❌ Failed to get webhook info: {response.text}")
            
    except Exception as e:
        print(f"❌ Error getting webhook info: {e}")

if __name__ == "__main__":
    print("🚀 Telegram Bot Webhook Updater\n")
    
    # Check current webhook info
    check_webhook_info()
    
    # Update webhook
    print("\n" + "="*50)
    success = update_webhook()
    
    if success:
        print("\n✅ Webhook update completed successfully!")
        print("🤖 Your bot should now respond to messages at the new /webhook endpoint")
    else:
        print("\n❌ Webhook update failed!")
        print("Please check the error messages above and try again")
    
    # Check webhook info again
    print("\n" + "="*50)
    check_webhook_info()
