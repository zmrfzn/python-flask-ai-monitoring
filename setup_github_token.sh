#!/bin/bash

# Script to configure GitHub Personal Access Token (PAT)
# Prompts for token and stores it in ~/.zshrc for persistence

set -e  # Exit on error

echo "=========================================="
echo "GitHub Token Configuration"
echo "=========================================="
echo ""

# Check if GITHUB_TOKEN is already set
if [ -n "$GITHUB_TOKEN" ]; then
    echo "✓ GITHUB_TOKEN is already set in your environment"
    echo "Current value: ${GITHUB_TOKEN:0:10}..."
    echo ""
    read -p "Do you want to update it? (y/N): " update_token
    if [[ ! "$update_token" =~ ^[Yy]$ ]]; then
        echo "Keeping existing token. Exiting."
        exit 0
    fi
fi

# Prompt for GitHub Personal Access Token
echo "Enter your GitHub Personal Access Token (PAT):"
echo "(Create one at: https://github.com/settings/tokens)"
echo ""
echo "For GitHub Models API access, your token needs:"
echo "  - No specific scopes required for public models"
echo "  - 'repo' scope for private repository access (optional)"
echo ""
read -p "GitHub Token: " github_token

if [ -z "$github_token" ]; then
    echo "Error: GitHub token cannot be empty"
    exit 1
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

# Remove any existing GITHUB_TOKEN exports
if grep -q "export GITHUB_TOKEN=" "$SHELL_CONFIG" 2>/dev/null; then
    # Different sed syntax for macOS vs Linux
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' '/export GITHUB_TOKEN=/d' "$SHELL_CONFIG"
    else
        sed -i '/export GITHUB_TOKEN=/d' "$SHELL_CONFIG"
    fi
    echo "✓ Removed old GITHUB_TOKEN entry"
fi

# Add new GITHUB_TOKEN export
echo "" >> "$SHELL_CONFIG"
echo "# GitHub Personal Access Token (added by setup_github_token.sh)" >> "$SHELL_CONFIG"
echo "export GITHUB_TOKEN=\"$github_token\"" >> "$SHELL_CONFIG"

echo "✓ Added GITHUB_TOKEN to $SHELL_CONFIG"
echo ""

# Set in current session
export GITHUB_TOKEN="$github_token"
echo "✓ GITHUB_TOKEN set in current session"

echo ""
echo "=========================================="
echo "Configuration completed successfully!"
echo "=========================================="
echo ""
echo "The GITHUB_TOKEN is now:"
echo "  - Set in your current terminal session"
echo "  - Saved to $SHELL_CONFIG for future sessions"
echo ""
echo "To use it immediately in other open terminals, run:"
echo "  source $SHELL_CONFIG"
echo ""
echo "Or simply open a new terminal window."
