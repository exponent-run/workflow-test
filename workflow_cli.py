#!/usr/bin/env python3
"""
Unified CLI for GitHub workflow operations - check status, create PRs, and run workflows.
"""

import os
import sys
import argparse
from datetime import datetime
from github import Github, GithubException, InputGitTreeElement
from github_client import GitHubClient


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
    
    def main(self):
        parser = argparse.ArgumentParser(
            description='GitHub Workflow CLI - Check status, create PRs, and run workflows',
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
        
        args = parser.parse_args()
        
        if not args.command:
            parser.print_help()
            sys.exit(0)
        
        if args.command == 'check':
            self.check_status(create_pr=args.create_pr)
        elif args.command == 'run':
            self.run_workflow(check_first=not args.skip_check)


if __name__ == '__main__':
    cli = WorkflowCLI()
    cli.main()