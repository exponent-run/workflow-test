#!/usr/bin/env python3
"""
Workflow manager to check and create GitHub workflows via PR.
"""

import os
import base64
from datetime import datetime
from github import Github, GithubException
from dotenv import load_dotenv

load_dotenv()

class WorkflowManager:
    def __init__(self, github_token=None):
        """Initialize with GitHub token (can be installation token or PAT)."""
        self.token = github_token
        self.g = Github(self.token)
        self.owner = os.getenv('GITHUB_OWNER', 'exponent-run')
        self.repo_name = os.getenv('GITHUB_REPO', 'workflow-test')
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
        """Get the repository object."""
        return self.g.get_repo(f"{self.owner}/{self.repo_name}")
    
    def check_workflow_exists(self):
        """Check if the workflow file exists in the default branch."""
        repo = self.get_repo()
        try:
            repo.get_contents(self.workflow_path)
            return True
        except GithubException as e:
            if e.status == 404:
                return False
            raise
    
    def check_open_prs(self):
        """Check for open PRs that create the workflow file."""
        repo = self.get_repo()
        open_prs = repo.get_pulls(state='open')
        
        workflow_prs = []
        for pr in open_prs:
            # Check if this PR modifies our workflow file
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
            # Get the SHA of the latest commit on the default branch
            base_sha = repo.get_branch(default_branch).commit.sha
            
            # Get the commit
            base_commit = repo.get_git_commit(base_sha)
            
            # Get the tree
            base_tree = repo.get_git_tree(base_commit.tree.sha, recursive=True)
            
            # Create blob for the workflow file
            workflow_blob = repo.create_git_blob(
                content=self.workflow_content,
                encoding='utf-8'
            )
            
            # Create tree elements using InputGitTreeElement
            from github import InputGitTreeElement
            tree_elements = []
            
            # Add the workflow file
            tree_elements.append(InputGitTreeElement(
                path=self.workflow_path,
                mode='100644',
                type='blob',
                sha=workflow_blob.sha
            ))
            
            # Create new tree
            new_tree = repo.create_git_tree(
                tree=tree_elements,
                base_tree=base_tree
            )
            
            # Create commit
            commit_message = 'Add test workflow'
            new_commit = repo.create_git_commit(
                message=commit_message,
                tree=new_tree,
                parents=[base_commit]
            )
            
            # Create branch reference
            repo.create_git_ref(
                ref=f'refs/heads/{branch_name}',
                sha=new_commit.sha
            )
            
            # Create pull request
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
            
            return {
                'number': pr.number,
                'url': pr.html_url,
                'branch': branch_name
            }
            
        except Exception as e:
            # Try to clean up branch if it was created
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
        
        # Check if workflow exists
        status['exists'] = self.check_workflow_exists()
        
        if not status['exists']:
            # Check for open PRs
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
        
        # Create a new PR
        pr_info = self.create_workflow_pr()
        return {
            'status': 'pr_created',
            'message': f'Created PR #{pr_info["number"]} to add the workflow',
            'pr_url': pr_info['url'],
            'pr_number': pr_info['number']
        }


if __name__ == '__main__':
    # Example usage
    from run_workflow import GitHubWorkflowRunner
    
    # Get an installation token
    runner = GitHubWorkflowRunner()
    token = runner.get_installation_token()
    
    # Create workflow manager
    manager = WorkflowManager(github_token=token)
    
    # Check status
    print("Checking workflow status...")
    status = manager.get_workflow_status()
    
    print(f"\nWorkflow exists: {status['exists']}")
    if status['open_prs']:
        print(f"Open PRs: {len(status['open_prs'])}")
        for pr in status['open_prs']:
            print(f"  - PR #{pr['number']}: {pr['title']} ({pr['url']})")
    
    if status['needs_creation']:
        print("\nNo workflow or PR found. Creating PR...")
        result = manager.ensure_workflow_exists()
        print(f"Result: {result['message']}")
        if 'pr_url' in result:
            print(f"PR URL: {result['pr_url']}")
    else:
        print("\nEnsuring workflow exists...")
        result = manager.ensure_workflow_exists()
        print(f"Result: {result['message']}")
        if 'pr_url' in result:
            print(f"PR URL: {result['pr_url']}")