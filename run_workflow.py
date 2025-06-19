#!/usr/bin/env python3
"""
Script to trigger GitHub workflow and display results using GitHub App authentication.
"""

import os
import sys
import time
import json
from datetime import datetime, timezone
from pathlib import Path

import jwt
import requests
from dotenv import load_dotenv
from github import Github, GithubIntegration

# Load environment variables
load_dotenv()

# Import workflow manager
from workflow_manager import WorkflowManager

class GitHubWorkflowRunner:
    def __init__(self):
        self.app_id = os.getenv('GITHUB_APP_ID')
        self.private_key_path = os.getenv('GITHUB_APP_PRIVATE_KEY_PATH', 'private-key.pem')
        self.owner = os.getenv('GITHUB_OWNER', 'exponent-run')
        self.repo = os.getenv('GITHUB_REPO', 'workflow-test')
        self.workflow_file = 'test-workflow.yml'
        
        if not self.app_id:
            raise ValueError("GITHUB_APP_ID not set in environment")
        
        # Load private key
        try:
            with open(self.private_key_path, 'r') as key_file:
                self.private_key = key_file.read()
        except FileNotFoundError:
            raise ValueError(f"Private key file not found at {self.private_key_path}")
    
    def create_jwt(self):
        """Create a JWT for GitHub App authentication."""
        now = int(time.time())
        payload = {
            'iat': now,
            'exp': now + 600,  # 10 minutes
            'iss': self.app_id
        }
        return jwt.encode(payload, self.private_key, algorithm='RS256')
    
    def get_installation_token(self):
        """Get an installation access token for the repository."""
        # First, get the installation ID
        jwt_token = self.create_jwt()
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Get installations
        resp = requests.get(
            f'https://api.github.com/app/installations',
            headers=headers
        )
        resp.raise_for_status()
        installations = resp.json()
        
        # Find installation for our repo
        installation_id = None
        for installation in installations:
            if installation['account']['login'] == self.owner:
                installation_id = installation['id']
                break
        
        if not installation_id:
            raise ValueError(f"No installation found for {self.owner}")
        
        # Get installation token
        resp = requests.post(
            f'https://api.github.com/app/installations/{installation_id}/access_tokens',
            headers=headers
        )
        resp.raise_for_status()
        return resp.json()['token']
    
    def trigger_workflow(self):
        """Trigger the GitHub workflow."""
        token = self.get_installation_token()
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Get current time for filtering
        trigger_time = datetime.now(timezone.utc)
        
        # Trigger workflow
        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/workflows/{self.workflow_file}/dispatches'
        data = {
            'ref': 'main'
        }
        
        print(f"Triggering workflow: {self.workflow_file}")
        resp = requests.post(url, headers=headers, json=data)
        resp.raise_for_status()
        print("Workflow triggered successfully!")
        
        # Poll for the new run
        print("Waiting for workflow run to be created...")
        runs_url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/runs'
        
        for attempt in range(10):  # Try for up to 30 seconds
            time.sleep(3)
            
            resp = requests.get(runs_url, headers=headers)
            resp.raise_for_status()
            runs = resp.json()['workflow_runs']
            
            # Look for a run created after we triggered
            for run in runs:
                created_at = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00'))
                if created_at > trigger_time and run['name'] == 'Test Workflow':
                    print(f"Found workflow run: {run['id']}")
                    return run['id'], token
            
            print(f"  Attempt {attempt + 1}/10: No new runs found yet...")
        
        raise ValueError("Workflow run was not created within 30 seconds")
    
    def wait_for_completion(self, run_id, token):
        """Poll for workflow completion."""
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
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
    
    def get_job_logs(self, run_id, token):
        """Get logs for all jobs in the workflow run."""
        headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Get jobs for the run
        jobs_url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/runs/{run_id}/jobs'
        resp = requests.get(jobs_url, headers=headers)
        resp.raise_for_status()
        jobs = resp.json()['jobs']
        
        logs = []
        for job in jobs:
            job_id = job['id']
            job_name = job['name']
            
            # Get logs for this job
            logs_url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/jobs/{job_id}/logs'
            resp = requests.get(logs_url, headers=headers)
            
            if resp.status_code == 200:
                logs.append({
                    'job_name': job_name,
                    'logs': resp.text
                })
        
        return logs
    
    def check_and_ensure_workflow(self):
        """Check if workflow exists and handle accordingly."""
        token = self.get_installation_token()
        manager = WorkflowManager(github_token=token)
        
        print("Checking workflow status...")
        result = manager.ensure_workflow_exists()
        
        if result['status'] == 'exists':
            print("✓ Workflow file exists")
            return True
        elif result['status'] == 'pr_open':
            print(f"⚠️  {result['message']}")
            print(f"   PR URL: {result['pr_url']}")
            print("\nPlease merge the PR and then run this script again.")
            return False
        elif result['status'] == 'pr_created':
            print(f"✓ {result['message']}")
            print(f"   PR URL: {result['pr_url']}")
            print("\nPlease review and merge the PR, then run this script again.")
            return False
        
        return False
    
    def run(self, skip_workflow_check=False):
        """Main execution flow."""
        try:
            # Check if workflow exists first (unless skipped)
            if not skip_workflow_check:
                if not self.check_and_ensure_workflow():
                    return
            
            # Trigger workflow
            run_id, token = self.trigger_workflow()
            
            # Wait for completion
            completed_run = self.wait_for_completion(run_id, token)
            
            print(f"\nWorkflow completed with conclusion: {completed_run['conclusion']}")
            print(f"URL: {completed_run['html_url']}")
            
            # Get and display logs
            print("\n" + "="*60)
            print("WORKFLOW LOGS:")
            print("="*60 + "\n")
            
            logs = self.get_job_logs(run_id, token)
            for job_logs in logs:
                print(f"\n--- Job: {job_logs['job_name']} ---")
                print(job_logs['logs'])
            
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)


if __name__ == '__main__':
    runner = GitHubWorkflowRunner()
    runner.run()