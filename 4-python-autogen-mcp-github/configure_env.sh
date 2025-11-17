#!/bin/bash

# Script to configure environment variables for the AI monitoring project
# This script prompts for New Relic license key and OpenAI API key,
# then updates both server/.env and tools/.env files

set -e  # Exit on error

echo "=========================================="
echo "AI Monitoring Project Configuration"
echo "=========================================="
echo ""

# Check if .env.example exists
if [ ! -f ".env.example" ]; then
    echo "Error: .env.example not found!"
    exit 1
fi

# Create server/.env from .env.example if it doesn't exist
if [ ! -f "server/.env" ]; then
    echo "Creating server/.env from .env.example..."
    cp .env.example server/.env
    # Uncomment the agent app name for server
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' 's|^#NEW_RELIC_APP_NAME=autogen-agent-app|NEW_RELIC_APP_NAME=autogen-agent-app|' server/.env
    else
        sed -i 's|^#NEW_RELIC_APP_NAME=autogen-agent-app|NEW_RELIC_APP_NAME=autogen-agent-app|' server/.env
    fi
    echo "✓ Created server/.env"
else
    echo "✓ server/.env already exists"
    echo "Creating backup: server/.env.backup"
    cp server/.env server/.env.backup
fi

# Create tools/.env from .env.example if it doesn't exist
if [ ! -f "tools/.env" ]; then
    echo "Creating tools/.env from .env.example..."
    cp .env.example tools/.env
    # Uncomment the tools app name for tools
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' 's|^#NEW_RELIC_APP_NAME=agent-mcp-tools|NEW_RELIC_APP_NAME=agent-mcp-tools|' tools/.env
    else
        sed -i 's|^#NEW_RELIC_APP_NAME=agent-mcp-tools|NEW_RELIC_APP_NAME=agent-mcp-tools|' tools/.env
    fi
    echo "✓ Created tools/.env"
else
    echo "✓ tools/.env already exists"
    echo "Creating backup: tools/.env.backup"
    cp tools/.env tools/.env.backup
fi

echo ""

# Check for New Relic License Key
if [ -n "$NEW_RELIC_LICENSE_KEY" ]; then
    echo "✓ Using NEW_RELIC_LICENSE_KEY from environment"
    nr_license_key="$NEW_RELIC_LICENSE_KEY"
else
    echo "Enter your New Relic License Key:"
    echo "(Find it at: https://one.newrelic.com/launcher/api-keys-ui.api-keys-launcher)"
    read -p "License Key: " nr_license_key
    
    if [ -z "$nr_license_key" ]; then
        echo "Error: New Relic License Key cannot be empty"
        exit 1
    fi
fi

# Check for GitHub Token / OpenAI API Key
if [ -n "$GITHUB_TOKEN" ]; then
    echo "✓ Using GITHUB_TOKEN from environment"
    openai_api_key="$GITHUB_TOKEN"
else
    echo ""
    echo "Enter your OpenAI API Key (or GitHub Models token):"
    echo "(For GitHub Models: https://github.com/marketplace/models)"
    read -p "API Key: " openai_api_key
    
    if [ -z "$openai_api_key" ]; then
        echo "Error: OpenAI API Key cannot be empty"
        exit 1
    fi
fi

# Prompt for OpenWeather API Key (optional)
echo ""
echo "Enter your OpenWeather API Key (optional - press Enter to skip):"
echo "(Sign up at: https://home.openweathermap.org/api_keys)"
read -p "OpenWeather API Key: " openweather_api_key

echo ""
echo "Updating configuration files..."

# Update server/.env
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|^NEW_RELIC_LICENSE_KEY=.*|NEW_RELIC_LICENSE_KEY=$nr_license_key|" server/.env
    sed -i '' "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$openai_api_key|" server/.env
    if [ -n "$openweather_api_key" ]; then
        sed -i '' "s|^OPENWEATHER_API_KEY=.*|OPENWEATHER_API_KEY=$openweather_api_key|" server/.env
    fi
else
    # Linux
    sed -i "s|^NEW_RELIC_LICENSE_KEY=.*|NEW_RELIC_LICENSE_KEY=$nr_license_key|" server/.env
    sed -i "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$openai_api_key|" server/.env
    if [ -n "$openweather_api_key" ]; then
        sed -i "s|^OPENWEATHER_API_KEY=.*|OPENWEATHER_API_KEY=$openweather_api_key|" server/.env
    fi
fi

# Update tools/.env
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s|^NEW_RELIC_LICENSE_KEY=.*|NEW_RELIC_LICENSE_KEY=$nr_license_key|" tools/.env
    if [ -n "$openweather_api_key" ]; then
        sed -i '' "s|^OPENWEATHER_API_KEY=.*|OPENWEATHER_API_KEY=$openweather_api_key|" tools/.env
    fi
else
    # Linux
    sed -i "s|^NEW_RELIC_LICENSE_KEY=.*|NEW_RELIC_LICENSE_KEY=$nr_license_key|" tools/.env
    if [ -n "$openweather_api_key" ]; then
        sed -i "s|^OPENWEATHER_API_KEY=.*|OPENWEATHER_API_KEY=$openweather_api_key|" tools/.env
    fi
fi

echo "✓ Updated server/.env"
echo "✓ Updated tools/.env"
echo ""
echo "=========================================="
echo "Configuration completed successfully!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Review the updated .env files"
echo "2. Run ./start_all.sh to start the services"
echo ""
echo "Note: Backups are saved as .env.backup in case you need to restore"
