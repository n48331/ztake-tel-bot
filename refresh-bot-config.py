#!/usr/bin/env python3
"""
Script to refresh the bot configuration and check current settings
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def refresh_bot_config():
    """Refresh bot configuration via API"""
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    
    if not WEBHOOK_URL:
        print("❌ WEBHOOK_URL not found in environment variables")
        return False
    
    refresh_url = f"{WEBHOOK_URL}/refresh_config"
    
    print(f"🔄 Refreshing bot configuration at: {refresh_url}")
    
    try:
        response = requests.post(refresh_url, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("✅ Bot configuration refreshed successfully!")
                print(f"   Authorized Chat ID: {result.get('authorized_chat_id')}")
                print(f"   Bot Token Configured: {result.get('bot_token_configured')}")
                return True
            else:
                print(f"❌ Failed to refresh: {result.get('message')}")
                return False
        else:
            print(f"❌ HTTP Error: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error refreshing configuration: {e}")
        return False

def check_bot_config():
    """Check current bot configuration"""
    WEBHOOK_URL = os.getenv('WEBHOOK_URL')
    
    if not WEBHOOK_URL:
        print("❌ WEBHOOK_URL not found in environment variables")
        return
    
    config_url = f"{WEBHOOK_URL}/bot_config"
    
    print(f"📋 Checking bot configuration at: {config_url}")
    
    try:
        response = requests.get(config_url, timeout=10)
        
        if response.status_code == 200:
            config = response.json()
            print("📊 Current Bot Configuration:")
            print(f"   Bot Token Configured: {config.get('bot_token_configured')}")
            print(f"   Authorized Chat ID: {config.get('authorized_chat_id')}")
            print(f"   Vendor ID: {config.get('vendor_id')}")
            print(f"   API Endpoint: {config.get('api_endpoint')}")
            print(f"   Last Config Fetch: {config.get('last_config_fetch')}")
            print(f"   Seconds Since Last Fetch: {config.get('seconds_since_last_fetch')}")
            print(f"   Cache Duration: {config.get('cache_duration')} seconds")
        else:
            print(f"❌ HTTP Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Error checking configuration: {e}")

def test_api_directly():
    """Test the API directly to see current chat ID"""
    VENDOR_ID = os.getenv('VENDOR_ID', '3')
    API_KEY = os.getenv('API_KEY')
    BOT_CONFIG_ENDPOINT = os.getenv('BOT_CONFIG_ENDPOINT', 'https://ztake.vercel.app/api/vendor/bot-token-secure')
    
    if not API_KEY:
        print("❌ API_KEY not found in environment variables")
        return
    
    print(f"🔍 Testing API directly for vendor_id={VENDOR_ID}")
    
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
            print("✅ API Response:")
            print(f"   Vendor ID: {config_data.get('vendor_id')}")
            print(f"   Business Name: {config_data.get('business_name')}")
            print(f"   Bot Token: {config_data.get('bot_token', '')[:20]}...")
            print(f"   Chat ID: {config_data.get('chat_id')}")
        else:
            print(f"❌ API Error: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"❌ Error testing API: {e}")

if __name__ == "__main__":
    print("🚀 Bot Configuration Refresh Tool\n")
    
    # Test API directly first
    print("="*50)
    test_api_directly()
    
    # Check current bot config
    print("\n" + "="*50)
    check_bot_config()
    
    # Refresh bot config
    print("\n" + "="*50)
    refresh_bot_config()
    
    # Check config again after refresh
    print("\n" + "="*50)
    check_bot_config()
    
    print("\n✅ Configuration refresh completed!")
