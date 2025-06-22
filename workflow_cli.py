#!/usr/bin/env python3
"""
Unified CLI for GitHub workflow operations - check status, create PRs, and run workflows.
"""

import os
import sys
import argparse
from github_client import GitHubClient
from workflow_manager import WorkflowManager


class WorkflowCLI:
    def __init__(self):
        self.client = GitHubClient()
        self.manager = WorkflowManager(github_client=self.client)
        self.workflow_file = 'test-workflow.yml'
    
    def check_status(self, create_pr=False):
        print("Checking workflow status...")
        status = self.manager.get_workflow_status()
        
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
            result = self.manager.ensure_workflow_exists()
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