#!/usr/bin/env python3
"""
Unified GitHub client with authentication and API operations.
"""

import os
import time
import jwt
import requests
from datetime import datetime, timezone
from github import Github, GithubIntegration
from dotenv import load_dotenv

# Load environment variables
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
        
        # Load private key
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
        # Check if we have a valid cached token
        if not force_refresh and self._token and self._token_expires:
            if datetime.now(timezone.utc) < self._token_expires:
                return self._token
        
        # Get a new token
        jwt_token = self.create_jwt()
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        
        # Get installations
        resp = requests.get(
            'https://api.github.com/app/installations',
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
        
        token_data = resp.json()
        self._token = token_data['token']
        # Token expires in 1 hour, but we'll refresh after 50 minutes to be safe
        self._token_expires = datetime.now(timezone.utc).replace(microsecond=0) + \
                             datetime.timedelta(minutes=50)
        
        return self._token
    
    def get_github_instance(self):
        """Get an authenticated GitHub instance using PyGithub."""
        token = self.get_installation_token()
        return Github(token)
    
    def get_headers(self):
        """Get headers for direct API requests."""
        token = self.get_installation_token()
        return {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
    
    def trigger_workflow(self, workflow_file, ref='main'):
        """Trigger a GitHub workflow."""
        headers = self.get_headers()
        
        # Get current time for filtering
        trigger_time = datetime.now(timezone.utc)
        
        # Trigger workflow
        url = f'https://api.github.com/repos/{self.owner}/{self.repo}/actions/workflows/{workflow_file}/dispatches'
        data = {'ref': ref}
        
        print(f"Triggering workflow: {workflow_file}")
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
                if created_at > trigger_time and workflow_file in run['path']:
                    print(f"Found workflow run: {run['id']}")
                    return run['id']
            
            print(f"  Attempt {attempt + 1}/10: No new runs found yet...")
        
        raise ValueError("Workflow run was not created within 30 seconds")
    
    def wait_for_workflow_completion(self, run_id):
        """Poll for workflow completion."""
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
        """Get logs for all jobs in the workflow run."""
        headers = self.get_headers()
        
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