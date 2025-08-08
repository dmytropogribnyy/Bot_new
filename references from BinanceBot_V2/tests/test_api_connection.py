#!/usr/bin/env python3
"""
Test API Connection
"""

import asyncio
from core.config import TradingConfig
from core.exchange_client import ExchangeClient
from core.unified_logger import UnifiedLogger

async def test_api_connection():
    """Test API connection to Binance"""
    print("🔧 Testing API connection...")
    
    # Load configuration
    try:
        config = TradingConfig()
        print(f"✅ Configuration loaded")
        print(f"   • Exchange mode: {config.exchange_mode}")
        print(f"   • Is testnet: {config.is_testnet_mode()}")
        
        # Get API credentials
        api_key, api_secret = config.get_api_credentials()
        print(f"   • Has API key: {bool(api_key)}")
        print(f"   • Has API secret: {bool(api_secret)}")
        
        if not api_key or not api_secret:
            print("❌ No API credentials found!")
            print("Please check your configuration file or environment variables")
            return False
            
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        return False
    
    # Test exchange client initialization
    try:
        logger = UnifiedLogger(config)
        exchange_client = ExchangeClient(config, logger)
        print("✅ Exchange client created")
        
        # Test connection
        print("🔄 Testing connection to Binance...")
        success = await exchange_client.initialize()
        
        if success:
            print("✅ Successfully connected to Binance!")
            
            # Test balance retrieval
            try:
                balance = await exchange_client.get_balance()
                if balance is not None:
                    print(f"✅ Balance retrieved: {balance}")
                else:
                    print("⚠️ Balance check disabled (Windows compatibility)")
            except Exception as e:
                print(f"⚠️ Balance check failed: {e}")
                
            return True
        else:
            print("❌ Failed to connect to Binance")
            return False
            
    except Exception as e:
        print(f"❌ Exchange client error: {e}")
        return False

if __name__ == "__main__":
    asyncio.run(test_api_connection()) 