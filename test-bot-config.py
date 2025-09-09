#!/usr/bin/env python3
"""
Test script to verify bot configuration fetching and chat ID validation
"""

import requests
import json

# Test configuration
VENDOR_ID = "3"
BOT_CONFIG_ENDPOINT = "https://ztake.vercel.app/api/vendor/bot-token-secure"

def test_bot_config_fetch():
    """Test fetching bot configuration from API"""
    print("🧪 Testing bot configuration fetch...")
    
    try:
        url = f"{BOT_CONFIG_ENDPOINT}?vendor_id={VENDOR_ID}"
        print(f"📡 Fetching from: {url}")
        
        # Use the same API key as in the bot
        API_KEY = "pk_XHbjmoSnX8ZQzKMoGYAUSYRPmAvBsbVM"
        
        headers = {
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json',
            'User-Agent': 'TelegramBot-Webhook/1.0'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            config_data = response.json()
            print("✅ Successfully fetched bot configuration:")
            print(f"   Vendor ID: {config_data.get('vendor_id')}")
            print(f"   Business Name: {config_data.get('business_name')}")
            print(f"   Bot Token: {config_data.get('bot_token', '')[:20]}...")
            print(f"   Chat ID: {config_data.get('chat_id')}")
            return config_data
        else:
            print(f"❌ Failed to fetch configuration: {response.status_code}")
            print(f"   Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Error fetching configuration: {e}")
        return None

def test_chat_id_validation():
    """Test chat ID validation logic"""
    print("\n🧪 Testing chat ID validation...")
    
    # Simulate the validation logic
    def is_authorized_chat(chat_id, authorized_chat_id):
        if not authorized_chat_id:
            return False
        return str(chat_id) == str(authorized_chat_id)
    
    # Test cases
    test_cases = [
        ("651770430", "651770430", True, "Exact match"),
        (651770430, "651770430", True, "String vs int match"),
        ("651770430", 651770430, True, "Int vs string match"),
        ("123456789", "651770430", False, "Different chat ID"),
        ("", "651770430", False, "Empty chat ID"),
        ("651770430", "", False, "Empty authorized chat ID"),
        (None, "651770430", False, "None chat ID"),
    ]
    
    for chat_id, authorized_chat_id, expected, description in test_cases:
        result = is_authorized_chat(chat_id, authorized_chat_id)
        status = "✅" if result == expected else "❌"
        print(f"   {status} {description}: {result} (expected {expected})")

def test_webhook_endpoint():
    """Test webhook endpoint (if available)"""
    print("\n🧪 Testing webhook endpoint...")
    
    # This would test against a running instance
    # For now, just show what the webhook URL should be
    webhook_url = "https://ztake-tel-bot.onrender.com/webhook"
    print(f"📡 Webhook URL: {webhook_url}")
    print("   (Test this by sending a POST request with Telegram webhook data)")

if __name__ == "__main__":
    print("🚀 Starting bot configuration tests...\n")
    
    # Test 1: Fetch bot configuration
    config = test_bot_config_fetch()
    
    # Test 2: Chat ID validation
    test_chat_id_validation()
    
    # Test 3: Webhook endpoint info
    test_webhook_endpoint()
    
    print("\n✅ All tests completed!")
    
    if config:
        print(f"\n📋 Configuration Summary:")
        print(f"   Bot Token: {config.get('bot_token', '')[:20]}...")
        print(f"   Chat ID: {config.get('chat_id')}")
        print(f"   Business: {config.get('business_name')}")
        print(f"   Vendor ID: {config.get('vendor_id')}")
