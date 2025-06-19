#!/usr/bin/env python3
"""
GitHub App webhook handler and utilities.
"""

import os
import hmac
import hashlib
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# GitHub App configuration
WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', '')

def verify_webhook_signature(payload, signature):
    """Verify that the webhook payload was sent from GitHub."""
    if not WEBHOOK_SECRET:
        return True  # Skip verification if no secret is set
    
    expected_signature = 'sha256=' + hmac.new(
        WEBHOOK_SECRET.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

@app.route('/webhook', methods=['POST'])
def handle_webhook():
    """Handle GitHub webhook events."""
    # Verify signature
    signature = request.headers.get('X-Hub-Signature-256', '')
    if not verify_webhook_signature(request.data, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # Parse event
    event = request.headers.get('X-GitHub-Event', '')
    payload = request.json
    
    print(f"Received {event} event")
    
    # Handle different events
    if event == 'installation':
        action = payload.get('action')
        print(f"Installation {action} for {payload.get('installation', {}).get('account', {}).get('login')}")
    elif event == 'workflow_run':
        run = payload.get('workflow_run', {})
        print(f"Workflow run {run.get('status')} for {run.get('name')}")
    
    return jsonify({'status': 'ok'})

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({'status': 'healthy'})

if __name__ == '__main__':
    # Note: In production, use a proper WSGI server
    app.run(host='0.0.0.0', port=3000, debug=True)