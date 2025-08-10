#!/bin/bash
# Quick Fix Script for BinanceBot v2.1 Critical Issues
# Run this after audit to fix critical problems

echo "🔧 BinanceBot v2.1 - Quick Fix Script"
echo "======================================"

# 1. Remove corrupted database file (if exists)
if [ -f "data/trading_bot.db" ]; then
    echo "📁 Removing corrupted database file..."
    rm -f data/trading_bot.db
    echo "✅ Database file removed (will be recreated on next run)"
else
    echo "✅ Database file already clean"
fi

# 2. Backup current .env
if [ -f ".env" ]; then
    BACKUP_NAME=".env.backup.$(date +%Y%m%d_%H%M%S)"
    cp .env "$BACKUP_NAME"
    echo "✅ Created backup: $BACKUP_NAME"
fi

# 3. Clean up .env inline comments (removes everything after #)
if [ -f ".env" ]; then
    echo "🧹 Cleaning .env file comments..."
    # Remove inline comments and trailing spaces
    sed -i.tmp 's/\(^[A-Z_]*=[^#]*\)#.*/\1/' .env
    sed -i 's/[[:space:]]*$//' .env
    rm -f .env.tmp
    echo "✅ .env file cleaned"
fi

# 4. Create logs directory if missing
if [ ! -d "logs" ]; then
    mkdir -p logs
    echo "✅ Created logs directory"
fi

# 5. Create data/runtime directory if missing
if [ ! -d "data/runtime" ]; then
    mkdir -p data/runtime
    echo "✅ Created data/runtime directory"
fi

# 6. Check Python dependencies
echo ""
echo "📦 Checking Python dependencies..."
python3 -c "import ccxt, pydantic, pandas, ta" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Core dependencies installed"
else
    echo "⚠️  Missing dependencies. Run: pip3 install -r requirements.txt"
fi

# 7. Test configuration loading
echo ""
echo "🔍 Testing configuration..."
python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from core.config import TradingConfig
    config = TradingConfig.from_env()
    print('✅ Configuration loads successfully')
    print(f'   - Mode: {\"TESTNET\" if config.testnet else \"PRODUCTION\"}')
    print(f'   - Dry Run: {config.dry_run}')
    print(f'   - Stage D: working_type={config.working_type}')
    print(f'   - Stage F: enabled={config.enable_stage_f_guard}')
except Exception as e:
    print(f'❌ Configuration error: {e}')
" 2>&1

echo ""
echo "======================================"
echo "✨ Quick fixes complete!"
echo ""
echo "Next steps:"
echo "1. Review AUDIT_REPORT.md for detailed findings"
echo "2. Test with: python3 main.py --dry-run"
echo "3. Check logs in ./logs/ directory"
echo ""
echo "⚠️  Remember: Always test on TESTNET first!"
