#!/bin/bash
#
# Quick script to set Anthropic API key and configure Claude
#

set -e

echo "════════════════════════════════════════════════════════════════"
echo "   Claude/Anthropic API Key Configuration"
echo "════════════════════════════════════════════════════════════════"
echo ""

# Get API key from user
read -p "Enter your Anthropic API key (starts with sk-ant-api03-): " ANTHROPIC_KEY

if [ -z "$ANTHROPIC_KEY" ]; then
    echo "❌ Error: API key cannot be empty"
    exit 1
fi

# Validate key format
if [[ ! $ANTHROPIC_KEY =~ ^sk-ant- ]]; then
    echo "⚠️  Warning: API key doesn't start with 'sk-ant-', but continuing..."
fi

# Ask for model preference
echo ""
echo "Select Claude model:"
echo "  1) claude-3-5-sonnet-20241022 (Recommended - Best balance)"
echo "  2) claude-3-5-haiku-20241022 (Fast and cheap)"
echo "  3) claude-3-opus-20240229 (Most powerful, expensive)"
echo ""
read -p "Enter choice [1-3, default: 1]: " MODEL_CHOICE

case "$MODEL_CHOICE" in
    2)
        MODEL="claude-3-5-haiku-20241022"
        ;;
    3)
        MODEL="claude-3-opus-20240229"
        ;;
    *)
        MODEL="claude-3-5-sonnet-20241022"
        ;;
esac

echo ""
echo "Configuration:"
echo "  Model: $MODEL"
echo "  API Key: ${ANTHROPIC_KEY:0:20}..."
echo ""

# Update or create .env file
ENV_FILE=".env"

# Backup existing .env if it exists
if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✅ Backed up existing .env file"
fi

# Remove old ANTHROPIC_API_KEY and DEFAULT_LLM_MODEL if they exist
if [ -f "$ENV_FILE" ]; then
    sed -i.tmp '/^ANTHROPIC_API_KEY=/d' "$ENV_FILE"
    sed -i.tmp '/^DEFAULT_LLM_MODEL=/d' "$ENV_FILE"
    rm -f "${ENV_FILE}.tmp"
fi

# Add new values
echo "ANTHROPIC_API_KEY=$ANTHROPIC_KEY" >> "$ENV_FILE"
echo "DEFAULT_LLM_MODEL=$MODEL" >> "$ENV_FILE"

echo "✅ Updated .env file"
echo ""

# Ask about docker restart
read -p "Restart Docker containers to apply changes? [y/N]: " RESTART

if [[ $RESTART =~ ^[Yy]$ ]]; then
    echo ""
    echo "🔄 Restarting Docker containers..."
    docker compose -f docker/docker-compose.yml down
    docker compose -f docker/docker-compose.yml up -d
    
    echo ""
    echo "⏳ Waiting for services to be healthy..."
    sleep 10
    
    echo ""
    echo "✅ Containers restarted!"
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "   Configuration Complete! 🎉"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    echo "Next steps:"
    echo "  1. Verify configuration:"
    echo "     docker exec docker-app-1 python -c 'from src.core.config import get_settings; s=get_settings(); print(f\"Model: {s.DEFAULT_LLM_MODEL}\")'"
    echo ""
    echo "  2. Run production test:"
    echo "     docker exec docker-app-1 python test_crewai_data_analysis_production.py"
    echo ""
else
    echo ""
    echo "════════════════════════════════════════════════════════════════"
    echo "   Configuration Saved (Restart Required)"
    echo "════════════════════════════════════════════════════════════════"
    echo ""
    echo "To apply changes, restart containers:"
    echo "  cd /Users/scottgay/Documents/Eliza/eliza-platform"
    echo "  docker compose -f docker/docker-compose.yml restart"
    echo ""
fi

