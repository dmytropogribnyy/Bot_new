#!/bin/bash

# BinanceBot V2 VPS Setup Script
# Usage: ./vps_setup.sh

set -e

echo "🚀 Setting up BinanceBot V2 on VPS..."

# Update system
echo "📦 Updating system packages..."
sudo apt update && sudo apt upgrade -y

# Install required packages
echo "📦 Installing required packages..."
sudo apt install -y python3 python3-pip python3-venv git tmux htop curl wget

# Create bot directory
BOT_DIR="/home/ubuntu/BinanceBot_V2"
echo "📁 Creating bot directory: $BOT_DIR"
mkdir -p $BOT_DIR
cd $BOT_DIR

# Clone repository (if not already done)
if [ ! -d ".git" ]; then
    echo "📥 Cloning repository..."
    git clone https://github.com/your-username/BinanceBot_V2.git .
fi

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating data and logs directories..."
mkdir -p data logs

# Set up systemd service
echo "🔧 Setting up systemd service..."
sudo cp deployment/systemd/binance-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable binance-bot.service

# Set up tmux startup script
echo "🔧 Setting up tmux startup script..."
chmod +x deployment/tmux_start.sh

# Create log rotation
echo "📝 Setting up log rotation..."
sudo tee /etc/logrotate.d/binance-bot > /dev/null <<EOF
$BOT_DIR/logs/*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 644 ubuntu ubuntu
}
EOF

# Set up firewall (optional)
echo "🔥 Setting up firewall..."
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# Optimize system for trading
echo "⚡ Optimizing system for trading..."

# Increase file descriptor limits
echo "* soft nofile 65536" | sudo tee -a /etc/security/limits.conf
echo "* hard nofile 65536" | sudo tee -a /etc/security/limits.conf

# Optimize network settings
echo "net.core.rmem_max = 16777216" | sudo tee -a /etc/sysctl.conf
echo "net.core.wmem_max = 16777216" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_rmem = 4096 87380 16777216" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_wmem = 4096 65536 16777216" | sudo tee -a /etc/sysctl.conf
echo "net.ipv4.tcp_congestion_control = bbr" | sudo tee -a /etc/sysctl.conf

# Apply sysctl changes
sudo sysctl -p

# Set up monitoring
echo "📊 Setting up monitoring..."
sudo apt install -y htop iotop nethogs

# Create monitoring script
cat > $BOT_DIR/monitor.sh << 'EOF'
#!/bin/bash
echo "=== System Resources ==="
echo "CPU Usage:"
top -bn1 | grep "Cpu(s)" | awk '{print $2}' | cut -d'%' -f1
echo "Memory Usage:"
free -h
echo "Disk Usage:"
df -h
echo "Network:"
ss -tuln
echo "=== Bot Status ==="
if systemctl is-active --quiet binance-bot; then
    echo "✅ Bot service is running"
else
    echo "❌ Bot service is not running"
fi
EOF

chmod +x $BOT_DIR/monitor.sh

echo "✅ VPS setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Edit configuration files:"
echo "   - $BOT_DIR/data/runtime_config.json"
echo "   - $BOT_DIR/data/leverage_map.json"
echo ""
echo "2. Start the bot:"
echo "   - Systemd: sudo systemctl start binance-bot"
echo "   - Tmux: ./deployment/tmux_start.sh"
echo ""
echo "3. Monitor the bot:"
echo "   - Logs: sudo journalctl -u binance-bot -f"
echo "   - System: ./monitor.sh"
echo ""
echo "4. Telegram commands:"
echo "   - /status - Check bot status"
echo "   - /positions - View open positions"
echo "   - /balance - Check account balance"
echo "   - /pause - Pause trading"
echo "   - /resume - Resume trading"
