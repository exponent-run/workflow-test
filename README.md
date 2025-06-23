# Indent - GitHub Workflow Automation

A single-file tool that demonstrates programmatic execution of GitHub Actions workflows using a GitHub App.

## Quick Setup

Run the setup helper:
```bash
uv run python scripts/setup.py
```

This will guide you through creating and configuring the GitHub App.

## Manual Setup

### 1. Create GitHub App

1. Go to https://github.com/organizations/exponent-run/settings/apps/new
2. Fill in the following:
   - **GitHub App name**: Indent Test
   - **Homepage URL**: https://github.com/exponent-run/workflow-test
   - **Webhook**: Uncheck "Active"
   
3. Set Repository permissions:
   - **Actions**: Read and write
   - **Contents**: Read and write
   - **Pull requests**: Read and write
   - **Metadata**: Read
   
4. Where can this GitHub App be installed: "Only on this account"

5. Click "Create GitHub App"

### 2. Generate Private Key

1. After creating the app, click "Generate a private key"
2. Save the downloaded `.pem` file as `private-key.pem` in this directory

### 3. Install App to Repository

1. Go to the app settings page
2. Click "Install App" 
3. Select the `workflow-test` repository
4. Click "Install"

### 4. Configure Environment

Create a `.env` file with:

```
GITHUB_APP_ID=<your-app-id>
GITHUB_APP_PRIVATE_KEY_PATH=private-key.pem
GITHUB_OWNER=exponent-run
GITHUB_REPO=workflow-test
```

## Usage

### Check Workflow Status

```bash
uv run python indent.py check
```

To create a PR if the workflow is missing:
```bash
uv run python indent.py check --create-pr
```

### Run the Workflow

```bash
uv run python indent.py run
```

To skip the existence check:
```bash
uv run python indent.py run --skip-check
```

### Start Webhook Server

```bash
uv run python indent.py serve
```

To use a different port:
```bash
uv run python indent.py serve --port 8080
```

## Architecture

This project is implemented as a single Python file (`indent.py`) that includes:

- **GitHub App Authentication**: JWT creation and installation token management
- **Workflow Management**: Check status, create PRs, and manage workflow files
- **CLI Interface**: Command-line interface for all operations
- **Webhook Server**: Flask server to handle GitHub webhook events
- **PR Comments**: Automatically posts "Hi from Indent" on created PRs

The workflow file (`.github/workflows/test-workflow.yml`) is created via PR when needed.

## How it Works

1. The GitHub App authenticates using a JWT signed with its private key
2. It exchanges the JWT for an installation access token
3. The token is used to:
   - Check if the workflow file exists
   - Create PRs to add the workflow (with automatic PR comment)
   - Trigger workflows via the GitHub Actions API
4. The script polls the API to check workflow status
5. Once complete, it fetches and displays the logs