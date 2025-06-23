#!/usr/bin/env python3
"""
Indent - GitHub workflow automation tool.
Combines GitHub client, workflow management, CLI, and webhook server in one file.
"""

import os
import sys
import time
import jwt
import hmac
import hashlib
import json
import argparse
import requests
from datetime import datetime, timezone, timedelta
from github import Github, GithubException, InputGitTreeElement
from flask import Flask, request, jsonify
from dotenv import load_dotenv

load_dotenv()


class GitHubClient:
    """Handles GitHub App authentication and API operations."""
    
    def __init__(self):
        self.app_id = os.getenv('GITHUB_APP_ID')
        self.private_key_path = os.getenv('GITHUB_APP_PRIVATE_KEY_PATH', 'private-key.pem')
        self.owner = os.getenv('GITHUB_OWNER', 'exponent-run')
        self.repo = os.getenv('GITHUB_REPO', 'workflow-test')
        
        if not self.app_id:
            raise ValueError("GITHUB_APP_ID not set in environment")
        
        try:
            with open(self.private_key_path, 'r') as key_file:
                self.private_key = key_file.read()
        except FileNotFoundError:
            raise ValueError(f"Private key file not found at {self.private_key_path}")
        
        self._token = None
        self._token_expires = None
    
    def create_jwt(self):
        """Create a JWT for GitHub App authentication."""
        now = int(time.time())
        payload = {
            'iat': now,
            'exp': now + 600,  # 10 minutes
            'iss': self.app_id
        }
        return jwt.encode(payload, self.private_key, algorithm='RS256')
    
    def get_installation_token(self, force_refresh=False):
        """Get an installation access token for the repository."""
        if not force_refresh and self._token and self._token_expires:
            if datetime.now(timezone.utc) < self._token_expires:
                return self._token
        
        jwt_token = self.create_jwt()
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        resp = requests.get(
            'https://api.github.com/app/installations',
            headers=headers
        )
        resp.raise_for_status()
        installations = resp.json()
        
        installation_id = None
        for installation in installations:
            if installation['account']['login'] == self.owner:
                installation_id = installation['id']
                break
        
        if not installation_id:
            raise ValueError(f"No installation found for {self.owner}")
        
        resp = requests.post(
            f'https://api.github.com/app/installations/{installation_id}/access_tokens',
            headers=headers
        )
        resp.raise_for_status()
        
        token_data = resp.json()
        self._token = token_data['token']
        # Token expires in 1 hour, but we'll refresh after 50 minutes to be safe
        self._token_expires = datetime.now(timezone.utc).replace(microsecond=0) + timedelta(minutes=50)
        
        return self._token
    
    def get_github_instance(self):
        token = self.get_installation_token()
        return Github(token)
    
    def get_headers(self):
        token = self.get_installation_token()
        return {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def trigger_workflow(self, workflow_file, ref='main'):
        headers = self.get_headers()
        trigger_time = datetime.now(timezone.utc)
        
        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/workflows/{workflow_file}/dispatches'
        data = {'ref': ref}
        
        print(f"Triggering workflow: {workflow_file}")
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        print("Workflow triggered successfully!")
        
        print("Waiting for workflow run to be created...")
        runs_url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/runs'
        
        for attempt in range(10):  # Try for up to 30 seconds
            time.sleep(3)
            
            resp = requests.get(runs_url, headers=headers)
            resp.raise_for_status()
            runs = resp.json()['workflow_runs']
            
            for run in runs:
                created_at = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
                if created_at > trigger_time and workflow_file in run['path']:
                    print(f"Found workflow run: {run['id']}")
                    return run['id']
            
            print(f"  Attempt {attempt + 1}/10: No new runs found yet...")
        
        raise ValueError("Workflow run was not created within 30 seconds")
    
    def wait_for_workflow_completion(self, run_id):
        headers = self.get_headers()
        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/runs/{run_id}'
        
        print(f"\nWaiting for workflow run {run_id} to complete...")
        while True:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            run = resp.json()
            
            status = run['status']
            conclusion = run.get('conclusion', 'N/A')
            
            print(f"Status: {status}, Conclusion: {conclusion}")
            
            if status == 'completed':
                return run
            
            time.sleep(5)
    
    def get_workflow_logs(self, run_id):
        headers = self.get_headers()
        
        jobs_url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/jobs'
        resp = requests.get(jobs_url, headers=headers)
        resp.raise_for_status()
        jobs = resp.json()['jobs']
        
        logs = []
        for job in jobs:
            job_id = job['id']
            job_name = job['name']
            
            logs_url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/jobs/{job_id}/logs'
            resp = requests.get(logs_url, headers=headers)
            
            if resp.status_code == 200:
                logs.append({
                    'job_name': job_name,
                    'logs': resp.text
                })
        
        return logs


class WorkflowCLI:
    def __init__(self):
        self.client = GitHubClient()
        self.g = self.client.get_github_instance()
        self.owner = self.client.owner
        self.repo_name = self.client.repo
        self.workflow_file = 'test-workflow.yml'
        self.workflow_path = '.github/workflows/test-workflow.yml'
        self.workflow_content = """name: Test Workflow

on:
  workflow_dispatch:

jobs:
  test-job:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
      
      - name: Echo Hi
        run: echo "Hi from GitHub Actions!"
      
      - name: Tree command
        run: tree || (apt-get update && apt-get install -y tree && tree)"""
    
    def get_repo(self):
        return self.g.get_repo(f"{self.owner}/{self.repo_name}")
    
    def check_workflow_exists(self):
        repo = self.get_repo()
        try:
            repo.get_contents(self.workflow_path)
            return True
        except GithubException as e:
            if e.status == 404:
                return False
            raise
    
    def check_open_prs(self):
        repo = self.get_repo()
        open_prs = repo.get_pulls(state='open')
        
        workflow_prs = []
        for pr in open_prs:
            files = pr.get_files()
            for file in files:
                if file.filename == self.workflow_path:
                    workflow_prs.append({
                        'number': pr.number,
                        'title': pr.title,
                        'url': pr.html_url,
                        'created_at': pr.created_at,
                        'author': pr.user.login
                    })
                    break
        
        return workflow_prs
    
    def create_workflow_pr(self):
        """Create a PR to add the workflow file using Git Data API."""
        repo = self.get_repo()
        default_branch = repo.default_branch
        branch_name = f'add-workflow-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
        
        try:
            base_sha = repo.get_branch(default_branch).commit.sha
            base_commit = repo.get_git_commit(base_sha)
            base_tree = repo.get_git_tree(base_commit.tree.sha, recursive=True)
            
            workflow_blob = repo.create_git_blob(
                content=self.workflow_content,
                encoding='utf-8'
            )
            
            tree_elements = []
            tree_elements.append(InputGitTreeElement(
                path=self.workflow_path,
                mode='100644',
                type='blob',
                sha=workflow_blob.sha
            ))
            
            new_tree = repo.create_git_tree(
                tree=tree_elements,
                base_tree=base_tree
            )
            
            commit_message = 'Add test workflow'
            new_commit = repo.create_git_commit(
                message=commit_message,
                tree=new_tree,
                parents=[base_commit]
            )
            
            repo.create_git_ref(
                ref=f'refs/heads/{branch_name}',
                sha=new_commit.sha
            )
            
            pr = repo.create_pull(
                title='Add test workflow',
                body='''This PR adds a GitHub Actions workflow that:
- Can be triggered manually via workflow_dispatch
- Checks out the repository
- Echoes a greeting message
- Runs the tree command to show repository structure

This workflow is used for testing programmatic workflow execution via the GitHub App.''',
                head=branch_name,
                base=default_branch
            )
            
            # Add comment to the PR
            pr.create_issue_comment("Hi from Indent")
            
            return {
                'number': pr.number,
                'url': pr.html_url,
                'branch': branch_name
            }
            
        except Exception as e:
            try:
                ref = repo.get_git_ref(f'heads/{branch_name}')
                ref.delete()
            except:
                pass
            raise e
    
    def get_workflow_status(self):
        """Get comprehensive status of the workflow file."""
        status = {
            'exists': False,
            'open_prs': [],
            'needs_creation': False
        }
        
        status['exists'] = self.check_workflow_exists()
        
        if not status['exists']:
            status['open_prs'] = self.check_open_prs()
            status['needs_creation'] = len(status['open_prs']) == 0
        
        return status
    
    def ensure_workflow_exists(self):
        """Ensure the workflow exists, creating a PR if necessary."""
        status = self.get_workflow_status()
        
        if status['exists']:
            return {
                'status': 'exists',
                'message': 'Workflow file already exists'
            }
        
        if status['open_prs']:
            pr = status['open_prs'][0]
            return {
                'status': 'pr_open',
                'message': f'PR #{pr["number"]} is open to create the workflow',
                'pr_url': pr['url'],
                'pr_number': pr['number']
            }
        
        pr_info = self.create_workflow_pr()
        return {
            'status': 'pr_created',
            'message': f'Created PR #{pr_info["number"]} to add the workflow',
            'pr_url': pr_info['url'],
            'pr_number': pr_info['number']
        }
    
    def check_status(self, create_pr=False):
        print("Checking workflow status...")
        status = self.get_workflow_status()
        
        if status['exists']:
            print("✓ Workflow file exists in the repository")
            return True
        
        if status['open_prs']:
            print("\n⚠️  Workflow file not found, but PR(s) exist to create it:")
            for pr in status['open_prs']:
                print(f"   - PR #{pr['number']}: {pr['title']}")
                print(f"     URL: {pr['url']}")
                print(f"     Author: {pr['author']}")
                print(f"     Created: {pr['created_at']}")
            
            if not create_pr:
                print("\nPlease merge one of these PRs before running workflows.")
            return False
        
        print("\n❌ Workflow file not found and no PRs exist to create it.")
        
        if create_pr:
            print("\nCreating PR to add workflow file...")
            result = self.ensure_workflow_exists()
            if result['status'] == 'pr_created':
                print(f"✓ Created PR #{result['pr_number']}")
                print(f"  URL: {result['pr_url']}")
                print("\nPlease review and merge this PR before running workflows.")
            return False
        else:
            print("\nRun with --create-pr to create a PR for the workflow file.")
            return False
    
    def run_workflow(self, check_first=True):
        if check_first:
            if not self.check_status():
                return
        
        try:
            run_id = self.client.trigger_workflow(self.workflow_file)
            completed_run = self.client.wait_for_workflow_completion(run_id)
            
            print(f"\nWorkflow completed with conclusion: {completed_run['conclusion']}")
            print(f"URL: {completed_run['html_url']}")
            
            print("\n" + "="*60)
            print("WORKFLOW LOGS:")
            print("="*60 + "\n")
            
            logs = self.client.get_workflow_logs(run_id)
            for job_logs in logs:
                print(f"\n--- Job: {job_logs['job_name']} ---")
                print(job_logs['logs'])
                
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    
    def serve_webhook(self, port=3000):
        """Run the webhook server."""
        app = Flask(__name__)
        webhook_secret = os.getenv('GITHUB_WEBHOOK_SECRET', '')
        
        def verify_webhook_signature(payload, signature):
            """Verify that the webhook payload was sent from GitHub."""
            if not webhook_secret:
                return True  # Skip verification if no secret is set
            
            expected_signature = 'sha256=' + hmac.new(
                webhook_secret.encode('utf-8'),
                payload,
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(expected_signature, signature)
        
        @app.route('/webhook', methods=['POST'])
        def handle_webhook():
            signature = request.headers.get('X-Hub-Signature-256', '')
            if not verify_webhook_signature(request.data, signature):
                return jsonify({'error': 'Invalid signature'}), 401
            
            event = request.headers.get('X-GitHub-Event', '')
            payload = request.json
            
            print(f"Received {event} event")
            
            if event == 'installation':
                action = payload.get('action')
                print(f"Installation {action} for {payload.get('installation', {}).get('account', {}).get('login')}")
            elif event == 'workflow_run':
                run = payload.get('workflow_run', {})
                print(f"Workflow run {run.get('status')} for {run.get('name')}")
            
            return jsonify({'status': 'ok'})
        
        @app.route('/health', methods=['GET'])
        def health_check():
            return jsonify({'status': 'healthy'})
        
        print(f"Starting webhook server on port {port}...")
        app.run(host='0.0.0.0', port=port, debug=True)


def main():
    cli = WorkflowCLI()
    
    parser = argparse.ArgumentParser(
        description='Indent - GitHub workflow automation tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check workflow status
  %(prog)s check
  
  # Check status and create PR if missing
  %(prog)s check --create-pr
  
  # Run workflow (checks status first)
  %(prog)s run
  
  # Run workflow without status check
  %(prog)s run --skip-check
  
  # Start webhook server
  %(prog)s serve
"""
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    check_parser = subparsers.add_parser('check', help='Check workflow status')
    check_parser.add_argument(
        '--create-pr', 
        action='store_true',
        help='Create PR if workflow file is missing'
    )
    
    run_parser = subparsers.add_parser('run', help='Run the workflow')
    run_parser.add_argument(
        '--skip-check',
        action='store_true',
        help='Skip workflow existence check'
    )
    
    serve_parser = subparsers.add_parser('serve', help='Start webhook server')
    serve_parser.add_argument(
        '--port',
        type=int,
        default=3000,
        help='Port to run the webhook server on (default: 3000)'
    )
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    if args.command == 'check':
        cli.check_status(create_pr=args.create_pr)
    elif args.command == 'run':
        cli.run_workflow(check_first=not args.skip_check)
    elif args.command == 'serve':
        cli.serve_webhook(port=args.port)


if __name__ == '__main__':
    main()