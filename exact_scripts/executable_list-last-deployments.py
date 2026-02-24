#!/usr/bin/env python3

"""
List Last Deployment Events for Atlassian Compass

A portable script that prints the details of the last deployment event in each
environment for the Compass component. Determines the component from
catalog-info.yaml.

Prerequisites:
  - Forge CLI authenticated: forge login
  - catalog-info.yaml with metadata.name field
  - Component exists in Compass
  - Python 3.6+ with requests and pyyaml packages

Required environment variables:
  ATLASSIAN_USER_EMAIL
  ATLASSIAN_USER_API_KEY

Usage:
  python3 scripts/list-last-deployments.py
"""

import argparse
import json
import os
import subprocess
import shutil
import sys
import textwrap
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
import yaml

# Configuration
ATLASSIAN_USER_EMAIL = os.environ.get("ATLASSIAN_USER_EMAIL")
ATLASSIAN_USER_API_KEY = os.environ.get("ATLASSIAN_USER_API_KEY")

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
}

HTTPS_PREFIX = "https://"

def _terminal_width() -> int:
    """Terminal width for wrapping; default 80 if unavailable."""
    try:
        return shutil.get_terminal_size().columns
    except OSError:
        return 80


def _wrap_with_pipe(text: str) -> str:
    """Wrap text at word boundaries and prefix each line with | (like list-sonar-issues)."""
    if not text:
        return "|"
    width = max(40, _terminal_width() - 3)
    lines_out = []
    for line in text.splitlines():
        if line.strip():
            wrapped = textwrap.fill(
                line, width=width, break_long_words=False, break_on_hyphens=False
            )
            for w in wrapped.splitlines():
                lines_out.append("| " + w)
        else:
            lines_out.append("|")
    return "\n".join(lines_out)


def _format_local_time(utc_timestamp: str) -> str:
    """Convert UTC ISO timestamp to local time string."""
    try:
        dt_utc = datetime.fromisoformat(utc_timestamp.replace('Z', '+00:00'))
        dt_local = dt_utc.astimezone()
        return dt_local.strftime('%Y-%m-%d %H:%M:%S %Z')
    except (ValueError, AttributeError):
        return "invalid time"


def _create_compass_url(site_url: str, component_slug: str) -> str:
    """Create Compass component URL for the given site and component."""
    clean_site = site_url
    if clean_site.startswith(HTTPS_PREFIX):
        clean_site = clean_site[len(HTTPS_PREFIX) :]
    if clean_site.endswith("/"):
        clean_site = clean_site[:-1]
    return f"{HTTPS_PREFIX}{clean_site}/compass/component/{component_slug}"


def _get_state_emoji(state: str) -> str:
    """Get emoji for deployment state."""
    state_upper = state.upper()
    if state_upper == "SUCCESSFUL":
        return "🟢"
    elif state_upper == "FAILED":
        return "🔴"
    else:
        return "🟡"


DEPLOYMENT_ENVIRONMENTS = [
    "PRODUCTION",
    "STAGING",
    "TESTING",
    "DEVELOPMENT",
    "UNMAPPED",
]


def _normalize_site_url(site_url: str) -> str:
    """Strip https:// and trailing slash for GraphQL endpoint."""
    s = site_url
    if s.startswith(HTTPS_PREFIX):
        s = s[len(HTTPS_PREFIX) :]
    if s.endswith("/"):
        s = s[:-1]
    return s


class LastDeploymentsRunner:
    def __init__(self, json_output: bool = False) -> None:
        self.json_output = json_output
        self.component_slug = ""
        self.installations: List[Dict[str, Any]] = []

    def run_command(self, command: List[str]) -> Tuple[bool, str, str]:
        """Run shell command and return success, stdout, stderr."""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=False,
            )
            return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
        except Exception as e:
            return False, "", str(e)

    def get_cloud_id(self, site_url: str) -> Optional[str]:
        """Get cloud ID from Atlassian site URL."""
        if not site_url.startswith(HTTPS_PREFIX):
            site_url = HTTPS_PREFIX + site_url
        if not site_url.endswith("/"):
            site_url = site_url + "/"
        tenant_info_url = f"{site_url}_edge/tenant_info"
        try:
            response = requests.get(tenant_info_url, timeout=10)
            response.raise_for_status()
            tenant_data = response.json()
            cloud_id = tenant_data.get("cloudId")
            return cloud_id if cloud_id else None
        except (requests.exceptions.RequestException, json.JSONDecodeError):
            return None

    def load_catalog_info(self) -> Tuple[str, Optional[str]]:
        """Load component name and optional GitHub repo from catalog-info.yaml.

        Returns:
            Tuple of (component_name, github_repo_slug).
            github_repo_slug is None if not in annotations.
        """
        catalog_path = os.path.join(os.getcwd(), "catalog-info.yaml")
        if not os.path.exists(catalog_path):
            raise SystemExit("catalog-info.yaml not found")
        with open(catalog_path, "r") as f:
            catalog_content = f.read()
        catalog_docs = list(yaml.safe_load_all(catalog_content))
        for doc in catalog_docs:
            if (
                doc
                and isinstance(doc, dict)
                and "metadata" in doc
                and "name" in doc["metadata"]
            ):
                component_name = doc["metadata"]["name"]
                github_repo = None
                if "annotations" in doc.get("metadata", {}):
                    ann = doc["metadata"]["annotations"]
                    if isinstance(ann, dict) and "github.com/project-slug" in ann:
                        github_repo = ann["github.com/project-slug"]
                return component_name, github_repo
        raise SystemExit("No component metadata found in catalog-info.yaml")

    def get_all_installations(self) -> List[Dict[str, str]]:
        """Get all forge installations."""
        success, output, error = self.run_command(["forge", "install", "list", "--json"])
        if not success:
            print(f"Failed to get forge installations: {error}", file=sys.stderr)
            return []
        try:
            installations = json.loads(output)
        except json.JSONDecodeError:
            print(f"Failed to parse forge installations JSON: {output}", file=sys.stderr)
            return []
        result = []
        for install in installations:
            site_url = install.get("site")
            if not site_url:
                continue
            cloud_id = self.get_cloud_id(site_url)
            if cloud_id:
                result.append({
                    "site_url": site_url,
                    "cloud_id": cloud_id,
                    "forge_environment": install.get("environment", "unknown"),
                })
        return result

    def make_graphql_request(
        self,
        endpoint_url: str,
        query: str,
        variables: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Make GraphQL request to Compass API."""
        if not ATLASSIAN_USER_EMAIL or not ATLASSIAN_USER_API_KEY:
            return None
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
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            if data.get("errors"):
                for err in data["errors"]:
                    print(f"GraphQL error: {err.get('message', 'Unknown')}", file=sys.stderr)
            return data
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}", file=sys.stderr)
            return None
        except json.JSONDecodeError as e:
            print(f"Failed to decode JSON: {e}", file=sys.stderr)
            return None

    def search_component_by_slug(
        self, slug: str, cloud_id: str, site_url: str
    ) -> Optional[str]:
        """Search for component by slug and return component ID."""
        clean_site = _normalize_site_url(site_url)
        graphql_endpoint = f"{HTTPS_PREFIX}{clean_site}/gateway/api/graphql"
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
                {"slug": {"slug": slug, "cloudId": cloud_id}}
            ]
        }
        response = self.make_graphql_request(graphql_endpoint, query, variables)
        if not response or not response.get("data"):
            return None
        components = (
            response.get("data", {})
            .get("compass", {})
            .get("componentsByReferences", [])
        )
        if not components:
            return None
        comp = components[0]
        if comp.get("__typename") == "CompassComponent":
            return comp.get("id")
        return None

    def fetch_last_deployment_for_environment(
        self,
        site_url: str,
        cloud_id: str,
        slug: str,
        environment: str,
    ) -> Optional[Dict[str, Any]]:
        """Fetch the most recent deployment event for one environment."""
        clean_site = _normalize_site_url(site_url)
        graphql_endpoint = f"{HTTPS_PREFIX}{clean_site}/gateway/api/graphql"
        query = """
        query getComponentDeploymentEvents(
          $references: [ComponentReferenceInput!]!
          $environments: [CompassDeploymentEventEnvironmentCategory!]!
        ) {
          compass {
            componentsByReferences(references: $references) {
              __typename
              ... on CompassComponent {
                id
                name
                events(query: {
                  eventTypes: [DEPLOYMENT]
                  first: 1
                  eventFilters: {
                    deployments: {
                      environments: $environments
                    }
                  }
                }) {
                  __typename
                  ... on CompassEventConnection {
                    nodes {
                      __typename
                      ... on CompassDeploymentEvent {
                        displayName
                        state
                        url
                        description
                        environment {
                          displayName
                          category
                        }
                        deploymentProperties {
                          startedAt
                          completedAt
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
        variables = {
            "references": [
                {"slug": {"slug": slug, "cloudId": cloud_id}}
            ],
            "environments": [environment],
        }
        response = self.make_graphql_request(graphql_endpoint, query, variables)
        if not response or not response.get("data"):
            return None
        components = (
            response.get("data", {})
            .get("compass", {})
            .get("componentsByReferences", [])
        )
        if not components:
            return None
        comp = components[0]
        if comp.get("__typename") != "CompassComponent":
            return None
        events_result = comp.get("events")
        if not events_result or events_result.get("__typename") != "CompassEventConnection":
            return None
        nodes = events_result.get("nodes") or []
        if not nodes:
            return None
        node = nodes[0]
        if node.get("__typename") != "CompassDeploymentEvent":
            return None
        return node

    def initialize_installations(self) -> None:
        """Resolve component in each installation and populate self.installations."""
        raw = self.get_all_installations()
        seen_cloud_ids = set()
        for install in raw:
            cloud_id = install["cloud_id"]
            if cloud_id in seen_cloud_ids:
                continue
            seen_cloud_ids.add(cloud_id)
            site_url = install["site_url"]
            clean_site = _normalize_site_url(site_url)
            component_id = self.search_component_by_slug(
                self.component_slug, cloud_id, clean_site
            )
            if not component_id:
                print(
                    f"Component '{self.component_slug}' not found in {site_url}",
                    file=sys.stderr,
                )
                continue
            self.installations.append({
                "site_url": site_url,
                "cloud_id": cloud_id,
                "component_id": component_id,
                "forge_environment": install.get("forge_environment", "unknown"),
            })

    def run(self) -> None:
        """Load catalog, resolve installations, fetch last deployment per env, print."""
        if not ATLASSIAN_USER_EMAIL or not ATLASSIAN_USER_API_KEY:
            print(
                "Error: ATLASSIAN_USER_EMAIL and ATLASSIAN_USER_API_KEY must be set.",
                file=sys.stderr,
            )
            print(
                "See: https://id.atlassian.com/manage-profile/security/api-tokens",
                file=sys.stderr,
            )
            sys.exit(1)
        self.component_slug, _ = self.load_catalog_info()
        self.initialize_installations()
        if not self.installations:
            print("No installations with this component found.", file=sys.stderr)
            sys.exit(1)
        all_results = []
        for installation in self.installations:
            site_url = installation["site_url"]
            cloud_id = installation["cloud_id"]
            per_env = {}
            for env in DEPLOYMENT_ENVIRONMENTS:
                event = self.fetch_last_deployment_for_environment(
                    site_url, cloud_id, self.component_slug, env
                )
                per_env[env] = event
            all_results.append({
                "installation": site_url,
                "component": self.component_slug,
                "environments": per_env,
            })
        if self.json_output:
            print(json.dumps(all_results, indent=2))
        else:
            format_output(all_results)


def _format_one_event(event: Dict[str, Any]) -> None:
    """Print a single deployment event (caller must ensure event is not None)."""
    state = event.get("state", "N/A")
    emoji = _get_state_emoji(state)
    print(f"  State: {emoji} {state}")
    props = event.get("deploymentProperties") or {}
    started = props.get("startedAt") or event.get("startedAt")
    completed = props.get("completedAt") or event.get("completedAt")
    if started:
        local_time = _format_local_time(started)
        print(f"  Started: {started} ({local_time})")
    if completed:
        local_time = _format_local_time(completed)
        print(f"  Completed: {completed} ({local_time})")
    if event.get("description"):
        print("  Description:")
        print()
        for line in _wrap_with_pipe(event["description"]).splitlines():
            print("  " + line)
        print()
    if event.get("url"):
        print(f"  URL: {event['url']}")


def format_output(results: List[Dict[str, Any]]) -> None:
    """Print last deployment per environment in human-readable form."""
    for item in results:
        print(f"Installation: {item['installation']}")
        component_slug = item['component']
        compass_url = _create_compass_url(item['installation'], component_slug)
        print(f"Component: {component_slug}")
        print(f"🔗 {compass_url}")
        print()
        per_env = item["environments"]
        for env in DEPLOYMENT_ENVIRONMENTS:
            event = per_env.get(env)
            if not event:
                continue
            print(f"{env}:")
            _format_one_event(event)
            print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="""Print the last deployment event in each environment for the Compass component.

Queries all Forge installations to find deployment events across all environments
(PRODUCTION, STAGING, TESTING, DEVELOPMENT, UNMAPPED). Shows deployment state,
timestamps, and descriptions with Compass URLs for easy access."""
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON instead of human-readable format",
    )
    args = parser.parse_args()
    runner = LastDeploymentsRunner(json_output=args.json)
    runner.run()


if __name__ == "__main__":
    main()
