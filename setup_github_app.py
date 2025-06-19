#!/usr/bin/env python3
"""
Helper script to set up the GitHub App.
"""

import webbrowser
import json
from pathlib import Path

def main():
    print("GitHub App Setup Helper")
    print("="*50)
    print("\nThis script will help you create and configure the GitHub App.")
    
    # Open browser to create app
    print("\n1. Opening browser to create GitHub App...")
    print("   Please fill in the following:")
    print("   - App name: Indent Test")
    print("   - Homepage URL: https://github.com/exponent-run/workflow-test")
    print("   - Webhook: Uncheck 'Active'")
    print("\n   Repository permissions:")
    print("   - Actions: Read and write")
    print("   - Contents: Read and write")
    print("   - Pull requests: Read and write")
    print("   - Metadata: Read")
    print("\n   - Where can this GitHub App be installed: 'Only on this account'")
    
    input("\nPress Enter to open the browser...")
    webbrowser.open("https://github.com/organizations/exponent-run/settings/apps/new")
    
    # Get App ID
    print("\n2. After creating the app, you'll see the App ID on the settings page.")
    app_id = input("   Enter the App ID: ").strip()
    
    # Private key
    print("\n3. Click 'Generate a private key' and save it as 'private-key.pem' in this directory.")
    input("   Press Enter when you've saved the private key...")
    
    # Installation
    print("\n4. Now we need to install the app to the repository.")
    print("   On the app settings page, click 'Install App'")
    print("   Select the 'workflow-test' repository and click 'Install'")
    input("   Press Enter when you've installed the app...")
    
    # Create .env file
    print("\n5. Creating .env file...")
    env_content = f"""# GitHub App Configuration
GITHUB_APP_ID={app_id}
GITHUB_APP_PRIVATE_KEY_PATH=private-key.pem
GITHUB_OWNER=exponent-run
GITHUB_REPO=workflow-test
"""
    
    with open('.env', 'w') as f:
        f.write(env_content)
    
    print("\nSetup complete! You can now run:")
    print("  uv run python run_workflow.py")

if __name__ == '__main__':
    main()