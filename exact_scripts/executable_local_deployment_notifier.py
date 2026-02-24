#!/usr/bin/env python3

"""
Local Deployment Notifier for Atlassian Compass

A portable script that sends deployment events to Compass during local Forge deployments.
Automatically creates event sources, tracks deployment state transitions (IN_PROGRESS → SUCCESSFUL/FAILED),
and uses GitHub commit URLs for meaningful, clickable deployment links.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SETUP INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. PREREQUISITES:
   - Forge CLI authenticated: `forge login`
   - catalog-info.yaml with metadata.name field
   - Component exists in Compass
   - Python 3.6+ with requests and pyyaml packages

2. REQUIRED ENVIRONMENT VARIABLES:
   export ATLASSIAN_USER_EMAIL="your.email@company.com"
   export ATLASSIAN_USER_API_KEY="your-atlassian-api-token"
   
   Get API token from: https://id.atlassian.com/manage-profile/security/api-tokens

3. OPTIONAL: Add GitHub repo to catalog-info.yaml for commit URLs:
   metadata:
     annotations:
       github.com/project-slug: org/repo-name

4. PACKAGE.JSON INTEGRATION:
   Add these scripts to your package.json:
   
   "scripts": {
     "deploy": "yarn build && python3 scripts/local_deployment_notifier.py",
     "deploy:dev": "yarn build && python3 scripts/local_deployment_notifier.py development",
     "deploy:staging": "yarn build && python3 scripts/local_deployment_notifier.py staging",
     "deploy:production": "yarn build && python3 scripts/local_deployment_notifier.py production"
   }

5. USAGE:
   yarn deploy:dev          # Deploy to development
   yarn deploy:staging      # Deploy to staging
   yarn deploy:production   # Deploy to production
   
   Or run directly with Python (not recommended):
   python3 scripts/local_deployment_notifier.py development --dry-run
   
   The script automatically:
   - Builds your Forge app (yarn build)
   - Sends IN_PROGRESS event to Compass
   - Runs forge deploy
   - Sends SUCCESSFUL/FAILED event based on result
   - Shows deployment events in Compass timeline with GitHub commit links

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOW IT WORKS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DEPLOYMENT FLOW:
  1. Loads component info from catalog-info.yaml
  2. Discovers all Forge installations via `forge install list`
  3. Verifies component exists in each Compass installation
  4. Sends IN_PROGRESS event to all installations
  5. Runs `forge deploy` command
  6. Sends SUCCESSFUL or FAILED event based on deployment result

AUTOMATIC EVENT SOURCE CREATION:
  - If event source doesn't exist (404 error), automatically creates it via GraphQL API
  - Creates event source with type DEPLOYMENT and externalEventSourceId = "forge_cli"
  - Attaches event source to component
  - Retries sending the event
  - Fails deployment if automatic creation fails

STATE TRANSITIONS:
  - Each deployment gets a unique deployment run ID (deploy-{timestamp})
  - Compass treats an event as an update (not a new event) when pipelineId, environment, and
    deploymentProperties.sequenceNumber are the same. To update the same event:
    * Same externalEventSourceId ("forge_cli"), pipelineId, environment, and deploymentProperties.sequenceNumber
    * Same url (GitHub commit URL or localhost URL) and startedAt timestamp
    * updateSequenceNumber (event level) must increment for each status update; otherwise the request is ignored
  - deploymentProperties.sequenceNumber identifies the deployment and must stay constant across all states
    (IN_PROGRESS, SUCCESSFUL, FAILED) for the same deployment run
  - This makes them appear as a single deployment in Compass timeline with state transitions

GITHUB COMMIT URLS:
  - Extracts github.com/project-slug from catalog-info.yaml
  - Uses full git commit hash to generate GitHub commit URL
  - Example: https://github.com/org/repo/commit/{full-hash}
  - Falls back to localhost URL if GitHub info unavailable
  - Provides clickable links to exact deployed code in Compass timeline

PAYLOAD STRUCTURE (Key fields for Compass to recognize state transitions):
  - updateSequenceNumber (event level): must increment for each status update; otherwise request is ignored
  - deploymentProperties.sequenceNumber: must stay the same for the same deployment so Compass updates in place
  {
    "cloudId": "...",
    "event": {
      "deployment": {
        "updateSequenceNumber": 1234567890123,  # Increments for each update (IN_PROGRESS then SUCCESSFUL/FAILED)
        "displayName": "component-name deployment",
        "description": "Branch: main, Hash: abc123, Env: dev, User: ...",  # Backend limit: 255 chars
        "url": "https://github.com/org/repo/commit/{hash}",  # Same for all states
        "externalEventSourceId": "forge_cli",  # Event source identifier (represents origin: Forge CLI)
        "deploymentProperties": {
          "sequenceNumber": 1234567890123,  # Same for all states; identifies this deployment run
          "state": "IN_PROGRESS" | "SUCCESSFUL" | "FAILED",
          "pipeline": {
            "pipelineId": "deploy-1234567890123",  # Unique per deployment, same for both events
            "url": "https://github.com/org/repo/commit/{hash}",  # Same as deployment.url
            "displayName": "Local Forge Deployment - abc123"
          },
          "environment": {
            "displayName": "development",
            "environmentId": "DEVELOPMENT",
            "category": "DEVELOPMENT"  # PRODUCTION | STAGING | TESTING | DEVELOPMENT | UNMAPPED
          },
          "startedAt": "2025-11-05T00:00:00Z",  # Same for both events
          "completedAt": "2025-11-05T00:01:00Z"  # Only in final state
        }
      }
    }
  }

ERROR HANDLING:
  - Validates authentication credentials before deployment
  - Sends FAILED events to successful installations if any installation fails during IN_PROGRESS
  - Shows detailed error messages with request/response details
  - Fails deployment if automatic event source creation fails
  - Graceful fallback for missing GitHub info or git commands

INSTALLATION DISCOVERY:
  - Uses `forge install list --json` to find all installations
  - Gets cloud IDs from /_edge/tenant_info endpoint
  - Queries Compass GraphQL API to verify component exists
  - Processes all installations regardless of Forge environment
  - Deployment environment metadata preserved in event payload

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

404 EVENT_SOURCE_NOT_FOUND:
  Script will automatically create the event source and retry. If that fails, deployment
  will abort with an error message.

Events appear as separate entries instead of state transitions:
  Compass updates in place when pipelineId, environment, and deploymentProperties.sequenceNumber
  are the same and updateSequenceNumber increments. In dry-run output, verify
  deploymentProperties.sequenceNumber is the same for IN_PROGRESS and SUCCESSFUL, and
  updateSequenceNumber is higher for SUCCESSFUL.

Authentication errors:
  Verify ATLASSIAN_USER_EMAIL and ATLASSIAN_USER_API_KEY are set correctly.
  Generate new token at: https://id.atlassian.com/manage-profile/security/api-tokens

Component not found:
  Ensure component with matching slug exists in Compass installation.
  Component slug must match metadata.name in catalog-info.yaml.

Git commands fail:
  Script gracefully handles missing git info, falling back to 'unknown' for hash/branch.
  GitHub URLs will use localhost fallback if git is unavailable.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import traceback
import requests
import yaml
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional, Tuple

# Configuration
ATLASSIAN_USER_EMAIL = os.environ.get("ATLASSIAN_USER_EMAIL")
ATLASSIAN_USER_API_KEY = os.environ.get("ATLASSIAN_USER_API_KEY")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

COMPASS_EVENTS_API_URL = "https://api.atlassian.com/compass/v1/events"
URL_HTTPS_PREFIX = "https://"

VALID_ENVIRONMENT_TYPES = [
    'PRODUCTION',
    'STAGING', 
    'TESTING',
    'DEVELOPMENT',
    'UNMAPPED'
]

class LocalDeploymentNotifier:
    def __init__(self, environment: str, dry_run: bool = False):
        self.environment = environment
        self.environment_type = self.validate_and_map_environment(environment)
        self.dry_run = dry_run
        self.component_slug = ""
        self.github_repo = None  # Will be loaded from catalog-info.yaml
        self.installations: List[Dict[str, str]] = []
        # Generate unique deployment run ID for this deployment
        # This ensures IN_PROGRESS and SUCCESSFUL/FAILED events are recognized as the same deployment
        self.deployment_run_id = f"deploy-{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        self.deployment_start_time = datetime.now(timezone.utc).isoformat()
        self.deployed_version: Optional[str] = None  # Will be extracted from forge deploy output
        self.schema_version: Optional[str] = None  # Will be extracted from migration response
        # Store base sequence number (timestamp) for this deployment
        # SUCCESSFUL/FAILED must have a higher updateSequenceNumber than IN_PROGRESS
        self.base_sequence_number = int(datetime.now(timezone.utc).timestamp() * 1000)
        
    def validate_and_map_environment(self, user_input: str) -> str:
        """Validate and map environment input to standard environment type"""
        normalized_input = user_input.upper()
        if normalized_input in VALID_ENVIRONMENT_TYPES:
            return normalized_input
        return 'UNMAPPED'
    
    def get_cloud_id(self, site_url: str) -> Optional[str]:
        """Get cloud ID from Atlassian site URL"""
        if not site_url.startswith(URL_HTTPS_PREFIX):
            site_url = URL_HTTPS_PREFIX + site_url
        if not site_url.endswith("/"):
            site_url = site_url + "/"
            
        tenant_info_url = f"{site_url}_edge/tenant_info"
        
        try:
            response = requests.get(tenant_info_url, timeout=10)
            response.raise_for_status()
            tenant_data = response.json()
            cloud_id = tenant_data.get("cloudId")
            
            if cloud_id:
                return cloud_id
            else:
                print(f"Error: Could not retrieve cloudId from {tenant_info_url}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"Error fetching Cloud ID from {tenant_info_url}: {e}")
            return None
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON response from {tenant_info_url}")
            return None
    
    def run_command(self, command: List[str]) -> Tuple[bool, str, str]:
        """Run shell command and return success, stdout, stderr"""
        try:
            result = subprocess.run(
                command, 
                capture_output=True, 
                text=True, 
                check=False
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except Exception as e:
            return False, "", str(e)
    
    def get_git_info(self) -> Dict[str, str]:
        """Get git branch and commit hash"""
        success, hash_output, _ = self.run_command(['git', 'rev-parse', '--short', 'HEAD'])
        git_hash = hash_output if success else 'unknown'
        
        success, branch_output, _ = self.run_command(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        branch = branch_output if success else 'unknown'
        
        return {'hash': git_hash, 'branch': branch}
    
    def get_forge_info(self) -> Dict[str, str]:
        """Get forge user information"""
        success, output, _ = self.run_command(['forge', 'whoami'])
        
        if not success:
            raise RuntimeError(
                'Failed to execute "forge whoami". Please ensure Forge CLI is installed and run "forge login" to authenticate.'
            )
        
        user = ""
        account_id = ""
        
        for line in output.split('\n'):
            if line.startswith('Logged in as:'):
                user = line.replace('Logged in as:', '').strip()
            elif line.startswith('Logged in as '):
                user = line.replace('Logged in as ', '').strip()
            elif line.startswith('Account ID:'):
                account_id = line.replace('Account ID:', '').strip()
        
        if not user or not account_id:
            raise RuntimeError(
                'Unable to get valid user information from Forge CLI. '
                'Please run "forge login" to authenticate with Atlassian Forge.'
            )
        
        return {'user': user, 'account_id': account_id}
    
    def get_user_name(self) -> str:
        """Get user name from forge whoami, prefer display name over email"""
        forge_info = self.get_forge_info()
        user = forge_info['user']
        
        # Extract just the name if present, otherwise use email
        if '(' in user and ')' in user:
            # Extract name part before parentheses
            name = user.split('(')[0].strip()
            if name:
                return name
            # If no name, extract email from parentheses
            email_match = re.search(r'\(([^)]+)\)', user)
            if email_match:
                return email_match.group(1)
        
        # Fallback: return as-is (likely just email or username)
        return user
    
    def _parse_numstat_line(self, line: str) -> Optional[Dict[str, Any]]:
        """Parse a single line from git diff --numstat output.
        
        Args:
            line: A line from git diff --numstat
            
        Returns:
            Dictionary with path, additions, and deletions, or None if line is invalid
        """
        if not line:
            return None
            
        parts = line.split('\t')
        if len(parts) < 3:
            return None
            
        add_str, del_str, filepath = parts[0], parts[1], parts[2]
        # Handle binary files (shown as '-')
        additions = int(add_str) if add_str.isdigit() else 0
        deletions = int(del_str) if del_str.isdigit() else 0
        
        return {
            'path': filepath,
            'additions': additions,
            'deletions': deletions
        }
    
    def _parse_numstat_output(self, numstat_output: str) -> Tuple[List[Dict[str, Any]], int, int]:
        """Parse git diff --numstat output to extract file statistics.
        
        Args:
            numstat_output: Output from git diff --numstat command
            
        Returns:
            Tuple of (file_stats, total_additions, total_deletions)
        """
        file_stats = []
        total_additions = 0
        total_deletions = 0
        
        for line in numstat_output.strip().split('\n'):
            parsed = self._parse_numstat_line(line)
            if parsed:
                file_stats.append(parsed)
                total_additions += parsed['additions']
                total_deletions += parsed['deletions']
        
        return file_stats, total_additions, total_deletions
    
    def get_uncommitted_changes_detailed(self) -> Optional[Dict[str, Any]]:
        """Get uncommitted changes with per-file statistics
        
        Returns:
            Dictionary with count, total_additions, total_deletions, and list of file stats
            None if no uncommitted changes
        """
        # Check for uncommitted changes
        success, status_output, _ = self.run_command(['git', 'status', '--porcelain'])
        if not success or not status_output.strip():
            return None
        
        # Parse modified/added files from status
        status_files = [line[3:] for line in status_output.strip().split('\n') if line]
        if not status_files:
            return None
        
        # Get per-file diff stats with git diff --numstat
        success, numstat_output, _ = self.run_command(['git', 'diff', '--numstat', 'HEAD'])
        
        file_stats = []
        total_additions = 0
        total_deletions = 0
        
        if success and numstat_output:
            file_stats, total_additions, total_deletions = self._parse_numstat_output(numstat_output)
        
        return {
            'count': len(status_files),
            'total_additions': total_additions,
            'total_deletions': total_deletions,
            'files': file_stats
        }
    
    def get_all_installations(self) -> List[Dict[str, str]]:
        """Get all forge installations (regardless of environment)"""
        success, output, error = self.run_command(['forge', 'install', 'list', '--json'])
        
        if not success:
            print(f"Failed to get forge installations: {error}")
            return []
        
        try:
            installations = json.loads(output)
        except json.JSONDecodeError:
            print(f"Failed to parse forge installations JSON: {output}")
            return []
        
        # Get all installations, not just matching environment
        # The deployment environment will be preserved in the notification payload
        result = []
        for install in installations:
            cloud_id = self.get_cloud_id(install['site'])
            if cloud_id:
                # Capture environment field - it should be 'production', 'development', etc.
                env = install.get('environment', 'unknown')
                result.append({
                    'site_url': install['site'], 
                    'cloud_id': cloud_id,
                    'forge_environment': env
                })
        
        return result
    
    def _handle_graphql_errors(self, data: Dict) -> None:
        """Handle GraphQL API errors in response"""
        # Silently handle GraphQL errors - they are logged elsewhere if needed
        pass
    
    def _handle_http_error(self, e: requests.exceptions.HTTPError, endpoint_url: str) -> None:
        """Handle HTTP errors, with special handling for 401 authentication errors"""
        if e.response is not None and e.response.status_code == 401:
            print(f"❌ Authentication failed (401 Unauthorized) for {endpoint_url}")
            print("   This indicates missing or invalid authentication credentials.")
            print("   Please ensure the following environment variables are set correctly:")
            print(f"   - ATLASSIAN_USER_EMAIL: {'✓ SET' if ATLASSIAN_USER_EMAIL else '❌ NOT SET'}")
            print(f"   - ATLASSIAN_USER_API_KEY: {'✓ SET' if ATLASSIAN_USER_API_KEY else '❌ NOT SET'}")
            print("   Generate an API token at: https://id.atlassian.com/manage-profile/security/api-tokens")
        else:
            print(f"Request to {endpoint_url} failed: {e}")
    
    def make_graphql_request(self, endpoint_url: str, query: str, variables: Optional[Dict] = None) -> Optional[Dict]:
        """Make GraphQL request to Compass API"""
        payload = {"query": query}
        if variables:
            payload["variables"] = variables
        
        auth = (ATLASSIAN_USER_EMAIL, ATLASSIAN_USER_API_KEY)
        
        try:
            response = requests.post(
                endpoint_url, 
                headers=HEADERS, 
                auth=auth, 
                json=payload, 
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            self._handle_graphql_errors(data)
            return data
            
        except requests.exceptions.HTTPError as e:
            self._handle_http_error(e, endpoint_url)
            return None
        except requests.exceptions.RequestException as e:
            print(f"Request to {endpoint_url} failed: {e}")
            return None
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON response: {e}")
            return None
    
    def search_component_by_slug(self, slug: str, cloud_id: str, site_url: str) -> Optional[str]:
        """Search for component by slug and return component ID"""
        graphql_endpoint = f"https://{site_url}/gateway/api/graphql"
        
        query = """
        query getComponentsByReferences($references: [ComponentReferenceInput!]!) {
          compass {
            componentsByReferences(references: $references) {
              __typename
              ... on CompassComponent {
                id
                name
                typeId
                slug
              }
            }
          }
        }
        """
        
        variables = {
            "references": [
                {
                    "slug": {
                        "slug": slug,
                        "cloudId": cloud_id
                    }
                }
            ]
        }
        
        response = self.make_graphql_request(graphql_endpoint, query, variables)
        
        if not response or not response.get("data"):
            return None
        
        components = response.get("data", {}).get("compass", {}).get("componentsByReferences", [])
        
        if not components:
            return None
        
        # Should only be one component since we're querying by specific slug
        component = components[0]
        
        if component.get("__typename") == "CompassComponent":
            component_id = component.get("id")
            return component_id
        else:
            print(f"❌ Component query returned unexpected type: {component.get('__typename')}")
            return None
    
    def create_and_attach_event_source(self, cloud_id: str, component_id: str, site_url: str, external_source_id: str) -> bool:
        """Create and attach a deployment event source for the component
        
        This creates an event source in Compass via GraphQL API and attaches it to the component.
        Returns True if successful, False otherwise.
        """
        graphql_endpoint = f"https://{site_url}/gateway/api/graphql"
        
        # Step 1: Create the event source
        print(f"   📝 Creating deployment event source '{external_source_id}'...")
        
        create_mutation = """
        mutation createEventSource($input: CreateEventSourceInput!) {
          compass {
            createEventSource(input: $input) {
              success
              eventSource {
                id
              }
              errors {
                message
              }
            }
          }
        }
        """
        
        create_variables = {
            "input": {
                "cloudId": cloud_id,
                "eventType": "DEPLOYMENT",
                "externalEventSourceId": external_source_id
            }
        }
        
        create_response = self.make_graphql_request(graphql_endpoint, create_mutation, create_variables)
        
        if not create_response or not create_response.get("data"):
            print("   ❌ Failed to create event source - no response data")
            return False
        
        result = create_response.get("data", {}).get("compass", {}).get("createEventSource", {})
        
        if result.get("errors"):
            print("   ❌ Errors creating event source:")
            for error in result["errors"]:
                print(f"      - {error.get('message')}")
            return False
        
        if not result.get("success") or not result.get("eventSource"):
            print("   ❌ Failed to create event source")
            return False
        
        event_source_id = result["eventSource"]["id"]
        print(f"   ✅ Created event source: {event_source_id}")
        
        # Step 2: Attach the event source to the component
        print("   🔗 Attaching event source to component...")
        
        attach_mutation = """
        mutation attachEventSource($input: AttachEventSourceInput!) {
          compass {
            attachEventSource(input: $input) {
              success
              errors {
                message
              }
            }
          }
        }
        """
        
        attach_variables = {
            "input": {
                "eventSourceId": event_source_id,
                "componentId": component_id
            }
        }
        
        attach_response = self.make_graphql_request(graphql_endpoint, attach_mutation, attach_variables)
        
        if not attach_response or not attach_response.get("data"):
            print("   ❌ Failed to attach event source - no response data")
            return False
        
        attach_result = attach_response.get("data", {}).get("compass", {}).get("attachEventSource", {})
        
        if attach_result.get("errors"):
            print("   ❌ Errors attaching event source:")
            for error in attach_result["errors"]:
                print(f"      - {error.get('message')}")
            return False
        
        if not attach_result.get("success"):
            print("   ❌ Failed to attach event source")
            return False
        
        print("   ✅ Event source attached successfully!")
        return True
    
    def load_catalog_info(self) -> Tuple[str, Optional[str]]:
        """Load component name and GitHub repo from catalog-info.yaml
        
        Returns:
            Tuple of (component_name, github_repo_slug)
            github_repo_slug will be None if not found in annotations
        """
        catalog_path = os.path.join(os.getcwd(), 'catalog-info.yaml')
        
        if not os.path.exists(catalog_path):
            raise FileNotFoundError('catalog-info.yaml not found')
        
        with open(catalog_path, 'r', encoding='utf-8') as f:
            catalog_content = f.read()
        
        catalog_docs = list(yaml.safe_load_all(catalog_content))
        
        # Find the Component document
        for doc in catalog_docs:
            if (doc and isinstance(doc, dict) and 
                'metadata' in doc and 
                'name' in doc['metadata']):
                
                component_name = doc['metadata']['name']
                
                # Try to extract GitHub repo from annotations
                github_repo = None
                if 'annotations' in doc['metadata']:
                    annotations = doc['metadata']['annotations']
                    # Check for github.com/project-slug annotation
                    if 'github.com/project-slug' in annotations:
                        github_repo = annotations['github.com/project-slug']
                        print(f"📦 GitHub repository: {github_repo}")
                
                return component_name, github_repo
        
        raise ValueError('No component metadata found in catalog-info.yaml')
    
    def initialize_installations(self) -> None:
        """Initialize installations and verify components exist
        
        Note: Event sources are created automatically when sending events if they don't exist.
        This method only verifies that components exist in Compass installations.
        """
        installations = self.get_all_installations()
        
        if not installations:
            print("⚠️  No forge installations found. "
                  "Deployment will proceed without sending notifications.")
            self.installations = []
            return
        
        self.installations = []
        
        for installation in installations:
            site_url = installation['site_url']
            cloud_id = installation['cloud_id']
            
            # Clean up site URL for GraphQL endpoint
            if site_url.startswith(URL_HTTPS_PREFIX):
                site_url = site_url[len(URL_HTTPS_PREFIX):]
            if site_url.endswith('/'):
                site_url = site_url[:-1]  # Remove trailing slash
            
            try:
                component_id = self.search_component_by_slug(
                    self.component_slug, 
                    cloud_id, 
                    site_url
                )
                
                if not component_id:
                    print(f"⚠️  Component '{self.component_slug}' not found in {installation['site_url']}")
                    continue
                
                print(f"✅ Component '{self.component_slug}' found in {installation['site_url']}")
                
                # Store installation info
                # Event source existence will be checked when sending events
                self.installations.append({
                    'site_url': installation['site_url'],
                    'cloud_id': cloud_id,
                    'component_id': component_id,
                    'forge_environment': installation.get('forge_environment', 'unknown')
                })
                    
            except Exception as e:
                print(f"❌ Failed to verify component in {installation['site_url']}: {e}")
                continue
        
        # If installations were found but none could be verified, fail
        if installations and not self.installations:
            raise RuntimeError(
                f"Found {len(installations)} forge installation(s), "
                f"but component '{self.component_slug}' could not be verified in any of them. "
                "Cannot proceed with deployment as notifications cannot be sent to existing installations."
            )
    
    def create_compass_url(self, site_url: str) -> str:
        """Create Compass component URL for the given site"""
        # Clean up the site URL
        clean_site = site_url
        if clean_site.startswith(URL_HTTPS_PREFIX):
            clean_site = clean_site[len(URL_HTTPS_PREFIX):]
        if clean_site.endswith('/'):
            clean_site = clean_site[:-1]
        
        return f"{URL_HTTPS_PREFIX}{clean_site}/compass/component/{self.component_slug}"
    
    def get_app_version(self) -> Optional[str]:
        """Get app version from forge deploy output
        
        Returns the version that was extracted from the forge deploy command output.
        Returns None if version hasn't been extracted yet (e.g., for IN_PROGRESS events).
        """
        return self.deployed_version
    
    def _format_uncommitted_line(self, uncommitted: Dict[str, Any], max_length: int) -> Optional[str]:
        """Format uncommitted changes line within space constraint
        
        Args:
            uncommitted: Dictionary with count, total_additions, total_deletions, and files
            max_length: Maximum length for this line
            
        Returns:
            Formatted uncommitted line or None if not enough space
        """
        count = uncommitted['count']
        total_add = uncommitted['total_additions']
        total_del = uncommitted['total_deletions']
        files = uncommitted['files']
        
        # Base format: "+ {count} uncommitted: (+{add}/-{del}) - "
        base = f"+ {count} uncommitted: (+{total_add}/-{total_del}) - "
        
        if len(base) + 3 > max_length:  # Not enough room even for "..."
            return None
        
        remaining_space = max_length - len(base)
        
        # Build complete list of file strings
        all_file_strs = []
        for file_stat in files:
            basename = os.path.basename(file_stat['path'])
            file_str = f"{basename} (+{file_stat['additions']}/-{file_stat['deletions']})"
            all_file_strs.append(file_str)
        
        # Try to fit as many files as possible based on available space
        file_parts = []
        for idx, file_str in enumerate(all_file_strs):
            # Build test string with this file included
            if file_parts:
                test_str = ", ".join(file_parts + [file_str])
            else:
                test_str = file_str
            
            # Check if there are more files after this one
            has_more_files = idx + 1 < len(all_file_strs)
            
            # Calculate required space (include ", ..." if there are more files)
            required_space = len(test_str) + (5 if has_more_files else 0)
            
            if required_space <= remaining_space:
                file_parts.append(file_str)
            else:
                # Can't fit this file, stop here
                break
        
        if file_parts:
            files_str = ", ".join(file_parts)
            # Add ellipsis if we didn't fit all files
            if len(file_parts) < len(all_file_strs):
                files_str += ", ..."
            return base + files_str
        else:
            # Not enough room for any files, just return base with "..."
            return base + "..."
    
    def create_deployment_description(self, state: str = 'IN_PROGRESS') -> str:
        """Create deployment description with git and forge info
        
        Format:
            Version: {version}
            Schema: {schema_version}
            Branch: {branch}
            Commit: {hash}
            + {count} uncommitted: (+{add}/-{del}) - file1 (+a/-d), file2 (+a/-d), ...
            User: {name or email}
        
        Args:
            state: The deployment state (IN_PROGRESS, SUCCESSFUL, FAILED)
                  For SUCCESSFUL state, includes app version at the top
        """
        git_info = self.get_git_info()
        user_name = self.get_user_name()
        uncommitted = self.get_uncommitted_changes_detailed()
        
        lines = []
        
        # Line 1: Version (SUCCESSFUL deployments only)
        if state == 'SUCCESSFUL':
            version = self.get_app_version()
            if version:
                lines.append(f"Version: {version}")
        
        # Line 2: Schema (if available)
        if self.schema_version:
            lines.append(f"Schema: {self.schema_version}")
        
        # Line 3: Branch (truncate past 30 chars)
        branch = git_info['branch']
        if len(branch) > 30:
            branch = branch[:27] + "..."
        lines.append(f"Branch: {branch}")
        
        # Line 4: Commit
        lines.append(f"Commit: {git_info['hash']}")
        
        # Calculate space for User field (always at end)
        user_line = f"User: {user_name}"
        
        # Calculate exact space available for uncommitted section
        separator = "\n"
        base_description = separator.join(lines)
        
        # Final format will be: base_description + \n + uncommitted_line + \n + user_line
        # So: 255 = len(base_description) + len(separator) + len(uncommitted_line) + len(separator) + len(user_line)
        # Therefore: len(uncommitted_line) = 255 - len(base_description) - 2*len(separator) - len(user_line)
        space_for_uncommitted = 255 - len(base_description) - len(user_line) - (2 * len(separator))
        
        # Line 5: Uncommitted changes (if present and space permits)
        if uncommitted and space_for_uncommitted > 30:
            uncommitted_line = self._format_uncommitted_line(uncommitted, space_for_uncommitted)
            if uncommitted_line:
                lines.append(uncommitted_line)
        
        # Line 6: User (always last)
        lines.append(user_line)
        
        description = separator.join(lines)
        
        # Safety truncation (should not be needed with proper calculation)
        if len(description) > 255:
            description = description[:252] + "..."
        
        return description
    
    def create_deployment_url(self, git_info: Dict[str, str]) -> str:
        """Create deployment URL - uses GitHub commit URL if available, otherwise localhost
        
        Returns:
            GitHub commit URL like: https://github.com/org/repo/commit/{hash}
            Or falls back to: https://localhost/{component-slug}/deploy-{id}
        """
        if self.github_repo and git_info.get('hash') != 'unknown':
            # Get full commit hash for GitHub URL
            success, full_hash, _ = self.run_command(['git', 'rev-parse', 'HEAD'])
            commit_hash = full_hash if success else git_info['hash']
            return f"https://github.com/{self.github_repo}/commit/{commit_hash}"
        else:
            # Fallback to localhost URL
            return f"https://localhost/{self.component_slug}/{self.deployment_run_id}"
    
    def validate_event_payload(self, payload: Dict, state: str) -> None:
        """Validate event payload structure before sending
        
        Ensures all required fields are present and properly formatted.
        Raises ValueError if validation fails.
        """
        required_fields = [
            'cloudId',
            'event.deployment.updateSequenceNumber',
            'event.deployment.displayName',
            'event.deployment.description',
            'event.deployment.url',
            'event.deployment.lastUpdated',
            'event.deployment.deploymentProperties.state',
            'event.deployment.deploymentProperties.sequenceNumber',
            'event.deployment.deploymentProperties.pipeline.pipelineId',
            'event.deployment.deploymentProperties.pipeline.url',
            'event.deployment.deploymentProperties.pipeline.displayName',
            'event.deployment.deploymentProperties.environment.displayName',
            'event.deployment.deploymentProperties.environment.environmentId',
            'event.deployment.deploymentProperties.environment.category',
            'event.deployment.deploymentProperties.startedAt'
        ]
        
        # externalEventSourceId is always required by the API
        required_fields.append('event.deployment.externalEventSourceId')
        
        # componentId should be present - we only send events to installations where we found the component
        required_fields.append('componentId')
        
        # For final states, completedAt is required
        if state in ['SUCCESSFUL', 'FAILED']:
            required_fields.append('event.deployment.deploymentProperties.completedAt')
        
        missing_fields = []
        for field_path in required_fields:
            parts = field_path.split('.')
            value = payload
            try:
                for part in parts:
                    value = value[part]
                if value is None:
                    missing_fields.append(field_path)
            except (KeyError, TypeError):
                missing_fields.append(field_path)
        
        if missing_fields:
            raise ValueError(
                f"Payload validation failed for {state} event. Missing required fields: {', '.join(missing_fields)}"
            )
        
        # Validate state value
        valid_states = ['IN_PROGRESS', 'SUCCESSFUL', 'FAILED', 'CANCELLED']
        deployment_state = payload.get('event', {}).get('deployment', {}).get('deploymentProperties', {}).get('state')
        if deployment_state not in valid_states:
            raise ValueError(
                f"Invalid deployment state: {deployment_state}. Must be one of: {', '.join(valid_states)}"
            )
        
        # Validate that pipelineId matches deployment_run_id for linking events
        pipeline_id = payload.get('event', {}).get('deployment', {}).get('deploymentProperties', {}).get('pipeline', {}).get('pipelineId')
        if pipeline_id != self.deployment_run_id:
            raise ValueError(
                f"Pipeline ID mismatch: expected {self.deployment_run_id}, got {pipeline_id}. "
                "This will prevent Compass from linking IN_PROGRESS and SUCCESSFUL events."
            )
    
    def create_event_payload(self, installation: Dict[str, str], state: str, 
                           description: str, git_info: Dict[str, str]) -> Dict:
        """Create Compass deployment event payload
        
        Note: The payload structure follows the Compass REST API format.
        To update the same event (state transition), we must:
        1. Use the same externalEventSourceId, pipelineId, environment, and deploymentProperties.sequenceNumber
        2. Use a higher updateSequenceNumber for each status update (IN_PROGRESS then SUCCESSFUL/FAILED)
        
        The URL will be a GitHub commit URL if available, providing a clickable link to the
        exact code that was deployed.
        """
        now = datetime.now(timezone.utc).isoformat()
        # updateSequenceNumber (event level): must increment for each status update so Compass accepts the request
        if state == 'IN_PROGRESS':
            update_sequence_number = self.base_sequence_number
        else:
            # SUCCESSFUL/FAILED must have a higher updateSequenceNumber than IN_PROGRESS
            update_sequence_number = int(datetime.now(timezone.utc).timestamp() * 1000)
            if update_sequence_number <= self.base_sequence_number:
                update_sequence_number = self.base_sequence_number + 1
        
        # Generate deployment URL - uses GitHub commit URL if available
        deployment_url = self.create_deployment_url(git_info)
        
        # deploymentProperties.sequenceNumber: must stay the same for the same deployment so Compass
        # treats the event as an update (same pipelineId + environment + sequenceNumber = update in place)
        deployment_properties = {
            "sequenceNumber": self.base_sequence_number,
            "state": state,
            "pipeline": {
                # Use deployment run ID to link IN_PROGRESS and SUCCESSFUL/FAILED events
                "pipelineId": f"{self.deployment_run_id}",
                # Use same URL for both events so Compass links them together
                "url": deployment_url,
                "displayName": f"Local Forge Deployment - {git_info['hash']}"
            },
            "environment": {
                "displayName": self.environment,
                "environmentId": self.environment_type,
                "category": self.environment_type
            }
        }
        
        # Use deployment start time for IN_PROGRESS, current time for completions
        # This ensures timeline shows accurate deployment duration
        if state == 'IN_PROGRESS':
            deployment_properties["startedAt"] = self.deployment_start_time
        else:
            deployment_properties["completedAt"] = now
            # Also include startedAt for completed deployments to show full lifecycle
            deployment_properties["startedAt"] = self.deployment_start_time
        
        payload = {
            "cloudId": installation['cloud_id'],
            "event": {
                "deployment": {
                    # CRITICAL: updateSequenceNumber must be higher for SUCCESSFUL/FAILED than IN_PROGRESS
                    "updateSequenceNumber": update_sequence_number,
                    # Keep displayName consistent between state transitions
                    "displayName": f"{self.component_slug} deployment",
                    "description": description,
                    # Use same deployment URL for event-level URL (required for event linking)
                    "url": deployment_url,
                    "lastUpdated": now,
                    # externalEventSourceId is required by the API and should represent the origin of the event
                    # Using "forge_cli" to identify that events come from local Forge CLI deployments
                    "externalEventSourceId": "forge_cli",
                    "deploymentProperties": deployment_properties
                }
            }
        }
        
        # Include componentId - this helps Compass associate the event with the component
        if 'component_id' in installation:
            payload["componentId"] = installation['component_id']
        
        return payload
    
    def send_deployment_event(self, state: str) -> None:
        """Send deployment event to all installations"""
        if not self.installations:
            print("ℹ️  No installations available - skipping deployment event notifications")
            return
        
        # Validate authentication credentials
        if not ATLASSIAN_USER_EMAIL or not ATLASSIAN_USER_API_KEY:
            print("❌ Missing authentication credentials:")
            print(f"   ATLASSIAN_USER_EMAIL: {'✓' if ATLASSIAN_USER_EMAIL else '❌ NOT SET'}")
            print(f"   ATLASSIAN_USER_API_KEY: {'✓' if ATLASSIAN_USER_API_KEY else '❌ NOT SET'}")
            raise RuntimeError("Missing required environment variables for API authentication")
        
        # Create description with state-specific information
        description = self.create_deployment_description(state)
        git_info = self.get_git_info()
        
        if self.dry_run:
            print(f"🔍 DRY RUN: Would send {state} event to {len(self.installations)} installation(s)")
            for installation in self.installations:
                payload = self.create_event_payload(installation, state, description, git_info)
                print(f"  - {installation['site_url']}: {json.dumps(payload, indent=2)}")
            return
        
        if state == 'IN_PROGRESS':
            self.send_in_progress_notifications(description, git_info)
        else:
            self.send_final_notifications(state, description, git_info)
    
    def _clean_site_url(self, site_url: str) -> str:
        """Clean site URL by removing https:// prefix and trailing slash"""
        clean_site = site_url
        if clean_site.startswith(URL_HTTPS_PREFIX):
            clean_site = clean_site[len(URL_HTTPS_PREFIX):]
        if clean_site.endswith('/'):
            clean_site = clean_site[:-1]
        return clean_site
    
    def _try_create_event_source_and_retry(self, installation: Dict[str, str], payload: Dict) -> bool:
        """Try to create event source and retry sending event
        
        Returns:
            True if event was successfully sent after creating event source, False otherwise
        """
        print("⚠️  Event source not found - attempting automatic creation...")
        
        clean_site = self._clean_site_url(installation['site_url'])
        
        if not self.create_and_attach_event_source(
            installation['cloud_id'],
            installation['component_id'],
            clean_site,
            "forge_cli"
        ):
            return False
        
        print("   🔄 Retrying event submission...")
        retry_response = requests.post(
            COMPASS_EVENTS_API_URL,
            headers=HEADERS,
            auth=(ATLASSIAN_USER_EMAIL, ATLASSIAN_USER_API_KEY),
            json=payload,
            timeout=30
        )
        
        if retry_response.status_code in [200, 202]:
            print(f"✅ IN_PROGRESS event sent to {installation['site_url']}")
            return True
        
        print(f"   ❌ Retry failed with status {retry_response.status_code}")
        return False
    
    def _log_error_response(self, response: requests.Response, payload: Dict) -> None:
        """Log error response details"""
        print(f"   Request URL: {COMPASS_EVENTS_API_URL}")
        print(f"   Request payload: {json.dumps(payload, indent=2)}")
        print(f"   Response status: {response.status_code}")
        print(f"   Response headers: {dict(response.headers)}")
        
        try:
            response_data = response.json()
            print(f"   Response body: {json.dumps(response_data, indent=2)}")
        except (ValueError, TypeError):
            print(f"   Response body (raw): {response.text}")
    
    def _send_single_event(self, installation: Dict[str, str], state: str, description: str, git_info: Dict[str, str]) -> requests.Response:
        """Send a single deployment event
        
        Returns:
            Response object from the API call
        """
        payload = self.create_event_payload(installation, state, description, git_info)
        return requests.post(
            COMPASS_EVENTS_API_URL,
            headers=HEADERS,
            auth=(ATLASSIAN_USER_EMAIL, ATLASSIAN_USER_API_KEY),
            json=payload,
            timeout=30
        )
    
    def _send_failed_to_successful_installations(self, successful_installations: List[Dict[str, str]], description: str, git_info: Dict[str, str]) -> None:
        """Send FAILED events to installations that previously succeeded"""
        for installation in successful_installations:
            try:
                payload = self.create_event_payload(installation, 'FAILED', description, git_info)
                response = requests.post(
                    COMPASS_EVENTS_API_URL,
                    headers=HEADERS,
                    auth=(ATLASSIAN_USER_EMAIL, ATLASSIAN_USER_API_KEY),
                    json=payload,
                    timeout=30
                )
                
                if response.status_code not in [200, 202]:
                    print(f"   Request payload: {json.dumps(payload, indent=2)}")
                    print(f"   Response status: {response.status_code}")
                    try:
                        response_data = response.json()
                        print(f"   Response body: {json.dumps(response_data, indent=2)}")
                    except (ValueError, TypeError):
                        print(f"   Response body (raw): {response.text}")
                
                compass_url = self.create_compass_url(installation['site_url'])
                print(f"☑️ FAILED event sent to {installation['site_url']}")
                print(f"   🔗 View component: {compass_url}")
                
            except Exception as e:
                print(f"❌ Failed to send FAILED event to {installation['site_url']}: {e}")
    
    def _handle_404_response(self, installation: Dict[str, str], payload: Dict, response: requests.Response) -> Tuple[bool, bool]:
        """Handle 404 response - attempt to create event source and retry
        
        Returns:
            Tuple of (success, needs_setup)
            success: True if event was successfully sent after creating event source
            needs_setup: True if event source creation failed
        """
        try:
            response_data = response.json()
            if any(err.get('type') == 'CREATE_EVENT_SOURCE_NOT_FOUND' 
                   for err in response_data.get('errors', [])):
                if self._try_create_event_source_and_retry(installation, payload):
                    return True, False
                return False, True
        except Exception as create_error:
            print(f"   ❌ Failed to auto-create event source: {create_error}")
        return False, True
    
    def _process_single_in_progress_notification(self, installation: Dict[str, str], description: str, 
                                                 git_info: Dict[str, str]) -> Tuple[bool, bool, Optional[str]]:
        """Process a single IN_PROGRESS notification
        
        Returns:
            Tuple of (success, needs_setup, error_message)
            success: True if notification was sent successfully
            needs_setup: True if event source needs to be created
            error_message: Error message if failed, None otherwise
        """
        try:
            payload = self.create_event_payload(installation, 'IN_PROGRESS', description, git_info)
            response = requests.post(
                COMPASS_EVENTS_API_URL,
                headers=HEADERS,
                auth=(ATLASSIAN_USER_EMAIL, ATLASSIAN_USER_API_KEY),
                json=payload,
                timeout=30
            )
            
            if response.status_code == 404:
                success, needs_setup = self._handle_404_response(installation, payload, response)
                if success:
                    print(f"✅ IN_PROGRESS event sent to {installation['site_url']}")
                    return True, False, None
                return False, needs_setup, None
            
            if response.status_code not in [200, 202]:
                self._log_error_response(response, payload)
                raise RuntimeError(f"HTTP {response.status_code}: {response.text}")
            
            print(f"✅ IN_PROGRESS event sent to {installation['site_url']}")
            return True, False, None
            
        except Exception as e:
            return False, False, str(e)
    
    def _validate_notification_results(self, needs_setup: List[Dict], failures: List[Dict]) -> None:
        """Validate notification results and raise appropriate errors"""
        if needs_setup:
            failed_sites = [installation['site_url'] for installation in needs_setup]
            raise RuntimeError(
                f"Event source creation failed for {len(needs_setup)} installation(s): {', '.join(failed_sites)}. "
                f"Automatic event source creation was attempted but failed."
            )
        
        if failures:
            failed_sites = [f['site_url'] for f in failures]
            raise RuntimeError(f"Deployment aborted: Failed to send notifications to {len(failures)} installation(s): {', '.join(failed_sites)}")
    
    def send_in_progress_notifications(self, description: str, git_info: Dict[str, str]) -> None:
        """Send IN_PROGRESS notifications - must all succeed"""
        successful_installations = []
        failures = []
        needs_setup = []
        
        for installation in self.installations:
            success, needs_setup_flag, error_msg = self._process_single_in_progress_notification(
                installation, description, git_info
            )
            
            if success:
                successful_installations.append(installation)
            elif needs_setup_flag:
                needs_setup.append(installation)
            else:
                failures.append({'site_url': installation['site_url'], 'error': error_msg})
                print(f"❌ Failed to send IN_PROGRESS event to {installation['site_url']}: {error_msg}")
        
        if failures:
            print(f"❌ {len(failures)} notification(s) failed. "
                  f"Sending FAILED events to {len(successful_installations)} successful installation(s) and aborting.")
            self._send_failed_to_successful_installations(successful_installations, description, git_info)
        
        self._validate_notification_results(needs_setup, failures)
    
    def _build_error_details(self, installation: Dict[str, str], response: requests.Response, payload: Dict) -> Dict:
        """Build error details dictionary from response"""
        error_details = {
            'site_url': installation['site_url'],
            'status_code': response.status_code,
            'request_payload': payload,
            'response_headers': dict(response.headers)
        }
        
        try:
            error_details['response_body'] = response.json()
        except (ValueError, TypeError):
            error_details['response_body'] = response.text
        
        return error_details
    
    def _log_final_error_response(self, installation: Dict[str, str], response: requests.Response, payload: Dict, error_details: Dict) -> None:
        """Log error response details for final notifications"""
        print("   ❌ Request failed for", installation['site_url'])
        print(f"   Request URL: {COMPASS_EVENTS_API_URL}")
        print(f"   Request payload: {json.dumps(payload, indent=2)}")
        print(f"   Response status: {response.status_code}")
        print(f"   Response headers: {dict(response.headers)}")
        response_body = error_details.get('response_body')
        body_str = json.dumps(response_body, indent=2) if isinstance(response_body, dict) else response_body
        print(f"   Response body: {body_str}")
    
    def _log_successful_final_notification(self, installation: Dict[str, str], state: str) -> None:
        """Log successful final notification with Compass URL"""
        if state in ['SUCCESSFUL', 'FAILED']:
            compass_url = self.create_compass_url(installation['site_url'])
            checkmark = "✅" if state == 'SUCCESSFUL' else "☑️"
            print(f"{checkmark} {state} event sent to {installation['site_url']} - 🔗 {compass_url}")
        else:
            print(f"✅ {state} event sent successfully to {installation['site_url']}")
    
    def _report_failed_notifications(self, failed_installations: List[Dict], state: str) -> None:
        """Report summary of failed notifications"""
        if not failed_installations:
            return
        
        print(f"❌ Failed to send {state} events to {len(failed_installations)} installation(s):")
        for failure in failed_installations:
            print(f"   - {failure['installation']['site_url']}: {failure['error']}")
        print("⚠️  WARNING:", len(failed_installations), "deployment notification(s) failed to send.")
        print("   Deployments may appear stuck in IN_PROGRESS state in Compass.")
        print("   Please check the error messages above and verify API credentials and network connectivity.")
    
    def send_final_notifications(self, state: str, description: str, git_info: Dict[str, str]) -> None:
        """Send final notifications (best effort) with detailed tracking and error reporting"""
        successful_installations = []
        failed_installations = []
        
        for installation in self.installations:
            try:
                payload = self.create_event_payload(installation, state, description, git_info)
                self.validate_event_payload(payload, state)
                
                if self.dry_run:
                    print(f"   Payload: {json.dumps(payload, indent=2)}")
                    successful_installations.append(installation)
                    continue
                
                response = requests.post(
                    COMPASS_EVENTS_API_URL,
                    headers=HEADERS,
                    auth=(ATLASSIAN_USER_EMAIL, ATLASSIAN_USER_API_KEY),
                    json=payload,
                    timeout=30
                )
                
                if response.status_code not in [200, 202]:
                    error_details = self._build_error_details(installation, response, payload)
                    self._log_final_error_response(installation, response, payload, error_details)
                    failed_installations.append({
                        'installation': installation,
                        'error': f"HTTP {response.status_code}: {response.text}",
                        'details': error_details
                    })
                    continue
                
                successful_installations.append(installation)
                self._log_successful_final_notification(installation, state)
                
            except Exception as e:
                error_msg = str(e)
                print(f"❌ Failed to send {state} event to {installation['site_url']}: {error_msg}")
                print(f"   Error type: {type(e).__name__}")
                print(f"   Traceback: {traceback.format_exc()}")
                
                failed_installations.append({
                    'installation': installation,
                    'error': error_msg,
                    'exception_type': type(e).__name__
                })
        
        self._report_failed_notifications(failed_installations, state)
    
    def run_forge_deploy(self) -> None:
        """Run forge deploy command and extract version from output"""
        if self.dry_run:
            print(f"🔍 DRY RUN: Would run 'forge deploy --environment {self.environment}'")
            return
        
        print("🚀 Running forge deploy...")
        success, stdout, stderr = self.run_command(['forge', 'deploy', '--environment', self.environment])
        
        # Combine stdout and stderr to search for version in all output
        all_output = stdout + "\n" + stderr if stderr else stdout
        
        # Extract version from output - looks for pattern like "[23.27.0]"
        # The version appears in messages like: "The version of your app [23.27.0] that was just deployed"
        version_pattern = r'\[(\d+\.\d+\.\d+)\]'
        version_match = re.search(version_pattern, all_output)
        
        if version_match:
            self.deployed_version = version_match.group(1)
            print(f"📦 Detected deployed version: {self.deployed_version}")
        else:
            print("⚠️  Warning: Could not extract version from forge deploy output")
        
        if stdout:
            print(stdout)
        if stderr:
            print(stderr, file=sys.stderr)
        
        if not success:
            raise RuntimeError("forge deploy command failed")
    
    def _execute_webtrigger_command(self, trigger_key: str, environment: str, clean_site: str) -> Tuple[bool, str, str]:
        """Execute forge webtrigger list command.
        
        Args:
            trigger_key: The web trigger key from manifest.yml
            environment: The deployment environment
            clean_site: Cleaned site URL without protocol
            
        Returns:
            Tuple of (success, output, error)
        """
        return self.run_command([
            'forge', 'webtrigger', 'list',
            '-f', trigger_key,
            '-e', environment,
            '-s', clean_site,
            '-p', 'Compass'
        ])
    
    def _extract_url_from_output(self, output: str) -> Optional[str]:
        """Extract HTTPS URL from forge webtrigger list output.
        
        Args:
            output: Command output to parse
            
        Returns:
            Extracted URL or None if not found
        """
        for line in output.split('\n'):
            if URL_HTTPS_PREFIX in line:
                url_match = re.search(r'https://[^\s]+', line)
                if url_match:
                    return url_match.group(0)
        return None
    
    def _print_debug_info(self, trigger_key: str, output: str, error: str, is_command_failure: bool) -> None:
        """Print debug information for failed webtrigger lookup.
        
        Args:
            trigger_key: The web trigger key
            output: Command stdout
            error: Command stderr
            is_command_failure: True if command failed, False if URL not found
        """
        if is_command_failure:
            print(f"⚠️  Failed to get web trigger URL for {trigger_key}: {error}")
            print(f"   Debug - stdout: {output[:200]}")
            print(f"   Debug - stderr: {error[:200]}")
        else:
            print(f"⚠️  Could not find URL in webtrigger list output for {trigger_key}")
            http_lines = sum(1 for l in output.split('\n') if 'http' in l)
            print(f"   Debug - output length: {len(output)}, lines with 'http': {http_lines}")
            print(f"   Debug - first 500 chars: {output[:500]}")
    
    def get_web_trigger_url(self, trigger_key: str, site_url: str, environment: str, max_retries: int = 3) -> Optional[str]:
        """Get web trigger URL from forge CLI with retry logic
        
        Args:
            trigger_key: The web trigger key from manifest.yml
            site_url: The site URL (e.g., example.atlassian.net)
            environment: The deployment environment
            max_retries: Maximum number of retry attempts (default 3)
            
        Returns:
            The web trigger URL if found, None otherwise
        """
        # Clean up site URL (remove https:// and trailing slash)
        clean_site = site_url.replace(URL_HTTPS_PREFIX, '').replace('http://', '').rstrip('/')
        
        import time
        
        for attempt in range(max_retries):
            if attempt > 0:
                # Wait before retry (web triggers might need time to propagate after deployment)
                wait_time = 2 * attempt  # 2s, 4s, 6s
                print(f"   Retrying in {wait_time}s... (attempt {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
            
            # Run forge webtrigger list command
            success, output, error = self._execute_webtrigger_command(trigger_key, environment, clean_site)
            
            if not success:
                if attempt == max_retries - 1:
                    self._print_debug_info(trigger_key, output, error, is_command_failure=True)
                continue
            
            # Check if web trigger URLs are available
            if 'No webtrigger URLs created' in output:
                if attempt == max_retries - 1:
                    print(f"⚠️  Web trigger {trigger_key} not found - it may not be deployed yet")
                    print(f"   Debug - output snippet: {output[:300]}")
                continue
            
            # Parse table output to extract URL
            url = self._extract_url_from_output(output)
            if url:
                if attempt > 0:
                    print(f"✅ Found web trigger URL on attempt {attempt + 1}: {url}")
                return url
            
            # If we didn't find the URL and this is the last attempt, show debug info
            if attempt == max_retries - 1:
                self._print_debug_info(trigger_key, output, error, is_command_failure=False)
        
        return None
    
    def _find_matching_installation(self) -> Optional[Dict[str, str]]:
        """Find installation matching the deployment environment
        
        Returns:
            Matching installation dict, or None if no match found
        """
        print(f"🔍 Checking installations for environment '{self.environment}'...")
        for installation in self.installations:
            install_env = installation.get('forge_environment', 'unknown')
            print(f"   Checking {installation['site_url']} (environment: {install_env})")
            if install_env.lower() == self.environment.lower():
                print(f"✅ Found matching installation: {installation['site_url']} for environment '{self.environment}'")
                return installation
        
        available_environments = [inst.get('forge_environment', 'unknown') for inst in self.installations]
        print(f"⚠️  No installation found for environment '{self.environment}'. Available environments: {', '.join(set(available_environments))}")
        return None
    
    def _validate_migration_response(self, response_data: Dict) -> None:
        """Validate migration response and raise if migrations failed"""
        success = response_data.get('success', False)
        status = response_data.get('status', 'UNKNOWN')
        pending_migrations = response_data.get('pendingMigrations', -1)
        completed_migrations = response_data.get('completedMigrations', 0)
        total_migrations = response_data.get('totalMigrations', 0)
        message = response_data.get('message', 'No message')
        
        if not success:
            error_msg = response_data.get('error', 'Unknown error')
            raise RuntimeError(
                f"SQL migrations failed: {error_msg}. "
                f"Status: {status}, Pending: {pending_migrations}"
            )
        
        if status != 'SUCCESS':
            raise RuntimeError(
                f"SQL migrations did not complete successfully. "
                f"Status: {status}, Pending migrations: {pending_migrations}, "
                f"Message: {message}"
            )
        
        if pending_migrations > 0:
            raise RuntimeError(
                f"SQL migrations incomplete. "
                f"Completed: {completed_migrations}/{total_migrations}, "
                f"Pending: {pending_migrations}, Status: {status}"
            )
        
        # Extract schema version from message
        # Message format: "[SQL-MIGRATION] ... | Schema versions: v001-v015"
        if message and 'Schema versions:' in message:
            schema_match = re.search(r'Schema versions:\s*([^\s|]+)', message)
            if schema_match:
                self.schema_version = schema_match.group(1)
        
        if message:
            print(f"✅ {message}")
        else:
            print(f"✅ SQL migrations completed successfully - Status: {status}, Completed: {completed_migrations}/{total_migrations}, Pending: {pending_migrations}")
    
    def _trigger_migration_request(self, trigger_url: str) -> None:
        """Make POST request to trigger SQL migration and validate response
        
        Status code handling:
        - 2xx: Success - validate response if JSON
        - 3xx: Warning - continue deployment but log warning
        - 4xx: Warning - continue deployment but log warning (client error, may indicate misconfiguration)
        - 5xx: Failure - abort deployment (server error indicates migration failed)
        """
        response = requests.post(
            trigger_url,
            headers={'Content-Type': 'application/json'},
            json={},
            timeout=30
        )
        
        status_code = response.status_code
        
        # 5xx: Server errors indicate migration failure - abort deployment
        if 500 <= status_code < 600:
            error_msg = f"SQL migration trigger returned server error {status_code}"
            print(f"❌ {error_msg}: {response.text}")
            raise RuntimeError(f"SQL migrations failed: {error_msg}")
        
        # 4xx: Client errors - log warning but continue (may indicate endpoint misconfiguration)
        if 400 <= status_code < 500:
            print(f"⚠️  WARNING: SQL migration trigger returned client error {status_code}: {response.text}")
            print("   This may indicate endpoint misconfiguration or authentication issues.")
            print("   Deployment will continue, but SQL migrations may not have been triggered successfully.")
            print("   Please check the migration status manually or trigger migrations again.")
            return
        
        # 3xx: Redirects - log warning but continue
        if 300 <= status_code < 400:
            print(f"⚠️  WARNING: SQL migration trigger returned redirect {status_code}: {response.text}")
            print("   Deployment will continue, but SQL migrations may not have been triggered successfully.")
            print("   Please check the migration status manually or verify the endpoint URL.")
            return
        
        # 2xx: Success codes - validate response if JSON
        if 200 <= status_code < 300:
            try:
                response_data = response.json()
                self._validate_migration_response(response_data)
            except json.JSONDecodeError:
                # Some 2xx responses like 204 No Content may not have a body
                print("✅ SQL migration triggered successfully (response not in JSON format)")
            return
        
        # Unexpected status code (< 200) - treat as failure
        error_msg = f"SQL migration trigger returned unexpected status {status_code}"
        print(f"❌ {error_msg}: {response.text}")
        raise RuntimeError(f"SQL migrations failed: {error_msg}")
    
    def run_sql_migrate(self) -> None:
        """Trigger SQL migration via web trigger after successful deployment"""
        if self.dry_run:
            print("🔍 DRY RUN: Would trigger SQL migration via web trigger")
            return
        
        if not self.installations:
            print("ℹ️  No installations available - skipping SQL migration trigger")
            return
        
        matching_installation = self._find_matching_installation()
        
        if not matching_installation:
            print("ℹ️  No matching installation found for this environment - skipping SQL migration trigger")
            return
        
        print("🔄 Triggering SQL migration via web trigger...")
        trigger_url = self.get_web_trigger_url(
            'sql-migrate',
            matching_installation['site_url'],
            self.environment
        )
        
        if not trigger_url:
            return
        
        try:
            self._trigger_migration_request(trigger_url)
        except Exception as e:
            if "SQL migrations" in str(e) and ("failed" in str(e) or "incomplete" in str(e) or "did not complete" in str(e)):
                raise
            print(f"⚠️  WARNING: Failed to trigger SQL migration: {e}")
            print("   Deployment will continue, but SQL migrations were not triggered.")
    
    def _is_migration_failure(self, error_message: str) -> bool:
        """Check if exception is migration-related failure"""
        return "SQL migrations" in error_message and (
            "failed" in error_message.lower() or 
            "incomplete" in error_message.lower() or 
            "did not complete" in error_message.lower()
        )
    
    def _should_send_failed_notification(self, in_progress_sent: bool, deployment_succeeded: bool, 
                                        post_deployment_phase: bool, is_migration_failure: bool) -> bool:
        """Determine if FAILED notification should be sent"""
        return (
            in_progress_sent and (
                not deployment_succeeded or 
                is_migration_failure or 
                (post_deployment_phase and deployment_succeeded)
            )
        )
    
    def _handle_deployment_failure(self, e: Exception, in_progress_sent: bool, deployment_succeeded: bool, 
                                   post_deployment_phase: bool) -> None:
        """Handle deployment failure by sending FAILED notifications if appropriate"""
        print(f"❌ Deployment failed: {e}")
        
        error_message = str(e)
        is_migration_failure = self._is_migration_failure(error_message)
        should_send_failed = self._should_send_failed_notification(
            in_progress_sent, deployment_succeeded, post_deployment_phase, is_migration_failure
        )
        
        if should_send_failed:
            try:
                if post_deployment_phase and deployment_succeeded:
                    print(f"❌ Post-deployment step failed: {error_message}")
                    print("   Sending FAILED notification to Compass since deployment succeeded but post-deployment steps failed.")
                self.send_deployment_event('FAILED')
            except Exception as failed_error:
                print(f"❌ Failed to send FAILED notifications: {failed_error}")
        elif in_progress_sent and deployment_succeeded and not post_deployment_phase:
            print("❌ Deployment succeeded but failed to send SUCCESS notifications. Not sending FAILED notifications.")
    
    def deploy(self) -> None:
        """Main deployment process"""
        in_progress_sent = False
        deployment_succeeded = False
        post_deployment_phase = False
        
        try:
            self.component_slug, self.github_repo = self.load_catalog_info()
            print(f"Component: {self.component_slug}")
            print(f"Environment: {self.environment} ({self.environment_type})")
            
            if self.dry_run:
                print("🔍 DRY RUN MODE - No actual deployment or API calls will be made")
            
            self.initialize_installations()
            self.send_deployment_event('IN_PROGRESS')
            in_progress_sent = True
            
            self.run_forge_deploy()
            deployment_succeeded = True
            post_deployment_phase = True
            
            self.run_sql_migrate()
            self.send_deployment_event('SUCCESSFUL')
            
        except Exception as e:
            self._handle_deployment_failure(e, in_progress_sent, deployment_succeeded, post_deployment_phase)
            sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="""Send deployment notifications to Atlassian Compass during forge deployments.
        
Automatically tracks deployment lifecycle (IN_PROGRESS -> SUCCESSFUL/FAILED),
creates event sources if needed, and triggers SQL migrations after successful deploys.
Uses GitHub commit URLs when available for clickable deployment links in Compass timeline.

Wraps 'forge deploy' command with Compass deployment event notifications."""
    )
    parser.add_argument(
        "environment", 
        help="Deployment environment (development, staging, production, etc.)"
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true",
        help="Show what would be done without making actual API calls or running deployment"
    )
    
    args = parser.parse_args()
    
    # Validate environment variables
    if not ATLASSIAN_USER_EMAIL or not ATLASSIAN_USER_API_KEY:
        print("❌ Error: ATLASSIAN_USER_EMAIL and ATLASSIAN_USER_API_KEY environment variables are required.")
        print("   Please set these variables with your Atlassian account email and API token.")
        print("   See: https://support.atlassian.com/atlassian-account/docs/manage-api-tokens-for-your-atlassian-account/")
        sys.exit(1)
    
    notifier = LocalDeploymentNotifier(args.environment, args.dry_run)
    notifier.deploy()


if __name__ == "__main__":
    main() 