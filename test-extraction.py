#!/usr/bin/env python3
"""
Test script for Telegram Bot UTR and Amount extraction
Run this to test your regex patterns and API integration without starting the bot
"""

import re
import requests
import json
from datetime import datetime

def extract_utr_numbers(text):
    """Extract UTR numbers from text"""
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
                clean_amount = float(match.replace(',', ''))
                amounts.append(clean_amount)
            except ValueError:
                continue
    
    return amounts

def test_extraction():
    """Test the extraction functions with sample data"""
    test_messages = [
        "UTR123456789",
        "₹1,234.56",
        "Payment of ₹15,000 completed via UTR123456789",
        "Received Rs 2500 from UTR987654321",
        "Transfer amount: ₹50,000.00 UTR555666777888",
        "Multiple UTRs: UTR111222333 UTR444555666 ₹5000",
        "amount: 1000 rs 500 INR 750",
        "Transaction of $100.99 via UTR123456789012",
        "Payment 2500 rupees UTR111222333444",
        "Invalid: UTR123 (too short) and regular text",
    ]
    
    print("🧪 TESTING EXTRACTION PATTERNS")
    print("=" * 60)
    
    for i, message in enumerate(test_messages, 1):
        print(f"\n{i}. Test Message:")
        print(f"   '{message}'")
        
        utr_numbers = extract_utr_numbers(message)
        amounts = extract_money_amounts(message)
        
        print(f"   📝 UTR Numbers: {utr_numbers if utr_numbers else 'None'}")
        print(f"   💰 Amounts: {amounts if amounts else 'None'}")
        
        if utr_numbers or amounts:
            print(f"   ✅ MATCHED")
        else:
            print(f"   ❌ NO MATCH")

def test_api_call(endpoint="https://httpbin.org/post", api_key="test-key"):
    """Test API call with sample data"""
    print(f"\n🌐 TESTING API CALL")
    print("=" * 60)
    print(f"Endpoint: {endpoint}")
    
    # Sample extracted data
    sample_data = {
        'utr_numbers': ['UTR123456789'],
        'amounts': [15000.0],
        'original_message': 'Test payment of ₹15,000 via UTR123456789',
        'user_info': {
            'user_id': 12345,
            'username': 'test_user',
            'first_name': 'Test',
            'last_name': 'User'
        },
        'timestamp': datetime.now().isoformat(),
        'source': 'telegram_bot_test'
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}',
        'User-Agent': 'TelegramBot-Test/1.0'
    }
    
    print(f"📤 Sending payload:")
    print(json.dumps(sample_data, indent=2))
    
    try:
        response = requests.post(
            endpoint,
            json=sample_data,
            headers=headers,
            timeout=10
        )
        
        print(f"\n📥 Response:")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("✅ SUCCESS!")
            try:
                response_data = response.json()
                print("Response Data:")
                print(json.dumps(response_data, indent=2))
            except json.JSONDecodeError:
                print("Response Text:", response.text[:500])
        else:
            print(f"❌ FAILED - Status {response.status_code}")
            print("Response:", response.text[:200])
            
    except requests.exceptions.Timeout:
        print("❌ FAILED - Request timed out")
    except requests.exceptions.RequestException as e:
        print(f"❌ FAILED - Network error: {e}")

def interactive_test():
    """Interactive test mode"""
    print("\n🔧 INTERACTIVE TEST MODE")
    print("=" * 60)
    print("Enter test messages (or 'quit' to exit):")
    
    while True:
        try:
            message = input("\n> ").strip()
            if message.lower() in ['quit', 'exit', 'q']:
                break
            
            if not message:
                continue
                
            utr_numbers = extract_utr_numbers(message)
            amounts = extract_money_amounts(message)
            
            print(f"📝 UTR Numbers: {utr_numbers if utr_numbers else 'None'}")
            print(f"💰 Amounts: {amounts if amounts else 'None'}")
            
            if utr_numbers or amounts:
                print("✅ Data extracted successfully!")
            else:
                print("❌ No data extracted")
                
        except KeyboardInterrupt:
            break
    
    print("\n👋 Goodbye!")

def main():
    """Main test function"""
    print("🤖 TELEGRAM BOT EXTRACTION TESTER")
    print("=" * 60)
    
    while True:
        print("\nChoose test option:")
        print("1. Test extraction patterns")
        print("2. Test API call")
        print("3. Interactive test mode")
        print("4. Run all tests")
        print("5. Exit")
        
        try:
            choice = input("\nEnter choice (1-5): ").strip()
            
            if choice == '1':
                test_extraction()
            elif choice == '2':
                endpoint = input("API endpoint (default: https://httpbin.org/post): ").strip()
                if not endpoint:
                    endpoint = "https://httpbin.org/post"
                api_key = input("API key (default: test-key): ").strip()
                if not api_key:
                    api_key = "test-key"
                test_api_call(endpoint, api_key)
            elif choice == '3':
                interactive_test()
            elif choice == '4':
                test_extraction()
                test_api_call()
            elif choice == '5':
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1-5.")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break

if __name__ == "__main__":
    main()