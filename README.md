# GitHub Workflow Test

This project demonstrates programmatic execution of GitHub Actions workflows using a GitHub App.

## Quick Setup

Run the setup helper:
```bash
uv run python setup_github_app.py
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
uv run python workflow_cli.py check
```

This will:
1. Check if the workflow file exists
2. Show any open PRs for the workflow

To create a PR if the workflow is missing:
```bash
uv run python workflow_cli.py check --create-pr
```

### Run the Workflow

```bash
uv run python workflow_cli.py run
```

This will:
1. Check if the workflow exists
2. Authenticate as the GitHub App
3. Trigger the test workflow
4. Poll for completion
5. Display the logs

To skip the existence check:
```bash
uv run python workflow_cli.py run --skip-check
```

### GitHub App Webhook Handler

The repository includes a Flask app (`app.py`) that can handle GitHub webhooks if needed:
```bash
uv run python app.py
```

## Architecture

The codebase has been simplified into three core modules:

### Core Modules

- `github_client.py` - Centralized GitHub authentication and API operations
  - JWT creation and token management
  - Workflow triggering and monitoring
  - Log retrieval

- `workflow_manager.py` - Workflow file management
  - Check if workflow exists
  - Find open PRs for workflow creation
  - Create PRs using Git Data API

- `workflow_cli.py` - Unified CLI for all workflow operations
  - Check workflow status
  - Create PRs for missing workflows
  - Run workflows with monitoring

### Entry Points

- `setup_github_app.py` - Interactive setup helper
- `workflow_cli.py` - Main CLI for workflow operations
- `app.py` - Webhook server for GitHub events

### Files

- `.github/workflows/test-workflow.yml` - The test workflow that gets triggered

## How it Works

1. The GitHub App authenticates using a JWT signed with its private key
2. It exchanges the JWT for an installation access token
3. The token is used to trigger the workflow via the GitHub Actions API
4. The script polls the API to check workflow status
5. Once complete, it fetches and displays the logs