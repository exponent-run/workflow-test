#!/usr/bin/env python3
"""
Check the status of the workflow file and manage it.
"""

import sys
from run_workflow import GitHubWorkflowRunner
from workflow_manager import WorkflowManager

def main():
    """Check workflow status and optionally create PR."""
    try:
        # Get installation token
        runner = GitHubWorkflowRunner()
        token = runner.get_installation_token()
        
        # Create workflow manager
        manager = WorkflowManager(github_token=token)
        
        # Get detailed status
        print("Checking workflow status...\n")
        status = manager.get_workflow_status()
        
        if status['exists']:
            print("✓ Workflow file exists at .github/workflows/test-workflow.yml")
            print("\nYou can run the workflow with:")
            print("  uv run python run_workflow.py")
        else:
            print("✗ Workflow file does not exist")
            
            if status['open_prs']:
                print(f"\n⚠️  Found {len(status['open_prs'])} open PR(s) for the workflow:")
                for pr in status['open_prs']:
                    print(f"  - PR #{pr['number']}: {pr['title']}")
                    print(f"    URL: {pr['url']}")
                    print(f"    Created: {pr['created_at']}")
                    print(f"    Author: {pr['author']}")
            else:
                print("\nNo open PRs found for the workflow.")
                
                # Ask if they want to create a PR
                response = input("\nWould you like to create a PR to add the workflow? (y/n): ")
                if response.lower() == 'y':
                    print("\nCreating PR...")
                    result = manager.ensure_workflow_exists()
                    if result['status'] == 'pr_created':
                        print(f"\n✓ Created PR #{result['pr_number']}")
                        print(f"  URL: {result['pr_url']}")
                        print("\nNext steps:")
                        print("1. Review the PR at the URL above")
                        print("2. Merge the PR")
                        print("3. Run 'uv run python run_workflow.py' to execute the workflow")
                    else:
                        print(f"\nUnexpected result: {result}")
                else:
                    print("\nYou can create a PR later by running this script again.")
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()