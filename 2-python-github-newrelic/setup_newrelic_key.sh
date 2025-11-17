#!/bin/bash

# Script to configure New Relic License Key
# Prompts for license key and stores it in ~/.zshrc for persistence

set -e  # Exit on error

echo "=========================================="
echo "New Relic License Key Configuration"
echo "=========================================="
echo ""

# Check if NEW_RELIC_LICENSE_KEY is already set
if [ -n "$NEW_RELIC_LICENSE_KEY" ]; then
    echo "✓ NEW_RELIC_LICENSE_KEY is already set in your environment"
    echo "Current value: ${NEW_RELIC_LICENSE_KEY:0:10}..."
    echo ""
    read -p "Do you want to update it? (y/N): " update_key
    if [[ ! "$update_key" =~ ^[Yy]$ ]]; then
        echo "Keeping existing license key. Exiting."
        exit 0
    fi
fi

# Prompt for New Relic License Key
echo "Enter your New Relic License Key:"
echo "(Find it at: https://one.newrelic.com/launcher/api-keys-ui.api-keys-launcher)"
echo ""
echo "Your license key should be a 40-character hexadecimal string"
echo ""
read -sp "License Key: " nr_license_key
echo ""

if [ -z "$nr_license_key" ]; then
    echo "Error: New Relic License Key cannot be empty"
    exit 1
fi

# Validate license key format (40 character hex string)
if [[ ! "$nr_license_key" =~ ^[A-Fa-f0-9]{40}$ ]]; then
    echo "Warning: License key doesn't match expected format (40 hexadecimal characters)"
    read -p "Continue anyway? (y/N): " continue_anyway
    if [[ ! "$continue_anyway" =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Determine which shell config file to use
SHELL_CONFIG=""
if [ -n "$ZSH_VERSION" ] || [[ "$SHELL" == *"zsh"* ]]; then
    SHELL_CONFIG="$HOME/.zshrc"
elif [ -n "$BASH_VERSION" ] || [[ "$SHELL" == *"bash"* ]]; then
    SHELL_CONFIG="$HOME/.bashrc"
    # On macOS, also check for .bash_profile
    if [[ "$OSTYPE" == "darwin"* ]] && [ -f "$HOME/.bash_profile" ]; then
        SHELL_CONFIG="$HOME/.bash_profile"
    fi
else
    echo "Warning: Couldn't detect shell type. Defaulting to ~/.bashrc"
    SHELL_CONFIG="$HOME/.bashrc"
fi

echo ""
echo "Updating $SHELL_CONFIG..."

# Create backup
if [ -f "$SHELL_CONFIG" ]; then
    cp "$SHELL_CONFIG" "${SHELL_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "✓ Created backup: ${SHELL_CONFIG}.backup.$(date +%Y%m%d_%H%M%S)"
fi

# Remove any existing NEW_RELIC_LICENSE_KEY exports
if grep -q "export NEW_RELIC_LICENSE_KEY=" "$SHELL_CONFIG" 2>/dev/null; then
    # Different sed syntax for macOS vs Linux
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' '/export NEW_RELIC_LICENSE_KEY=/d' "$SHELL_CONFIG"
    else
        sed -i '/export NEW_RELIC_LICENSE_KEY=/d' "$SHELL_CONFIG"
    fi
    echo "✓ Removed old NEW_RELIC_LICENSE_KEY entry"
fi

# Add new NEW_RELIC_LICENSE_KEY export
echo "" >> "$SHELL_CONFIG"
echo "# New Relic License Key (added by setup_newrelic_key.sh)" >> "$SHELL_CONFIG"
echo "export NEW_RELIC_LICENSE_KEY=\"$nr_license_key\"" >> "$SHELL_CONFIG"

echo "✓ Added NEW_RELIC_LICENSE_KEY to $SHELL_CONFIG"
echo ""

# Set in current session
export NEW_RELIC_LICENSE_KEY="$nr_license_key"
echo "✓ NEW_RELIC_LICENSE_KEY set in current session"

echo ""
echo "=========================================="
echo "Configuration completed successfully!"
echo "=========================================="
echo ""
echo "The NEW_RELIC_LICENSE_KEY is now:"
echo "  - Set in your current terminal session"
echo "  - Saved to $SHELL_CONFIG for future sessions"
echo ""
echo "To use it immediately in other open terminals, run:"
echo "  source $SHELL_CONFIG"
echo ""
echo "Or simply open a new terminal window."
