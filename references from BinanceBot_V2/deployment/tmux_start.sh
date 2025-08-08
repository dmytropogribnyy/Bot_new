#!/bin/bash

# BinanceBot V2 Tmux Startup Script
# Usage: ./tmux_start.sh

BOT_DIR="/home/ubuntu/BinanceBot_V2"
SESSION_NAME="binance_bot"
VENV_PATH="$BOT_DIR/venv/bin/activate"

echo "🚀 Starting BinanceBot V2 in tmux session..."

# Check if tmux session already exists
if tmux has-session -t $SESSION_NAME 2>/dev/null; then
    echo "⚠️  Session $SESSION_NAME already exists. Attaching..."
    tmux attach-session -t $SESSION_NAME
    exit 0
fi

# Create new tmux session
tmux new-session -d -s $SESSION_NAME -c $BOT_DIR

# Activate virtual environment and start bot
tmux send-keys -t $SESSION_NAME "source $VENV_PATH" C-m
tmux send-keys -t $SESSION_NAME "python main.py" C-m

echo "✅ Bot started in tmux session: $SESSION_NAME"
echo "📋 Commands:"
echo "  - Attach: tmux attach-session -t $SESSION_NAME"
echo "  - Detach: Ctrl+B, then D"
echo "  - Kill session: tmux kill-session -t $SESSION_NAME"
echo "  - List sessions: tmux list-sessions"

# Attach to session
tmux attach-session -t $SESSION_NAME
