#!/usr/bin/env python3
"""
Usage: get-component-by-repo.py "repo-name" [--site SITE]
Looks up a Compass component by repo name (external alias) and prints
component name, type, URL, Jira project URL, and links by type.

Requires: ATLASSIAN_USER_EMAIL, ATLASSIAN_USER_API_KEY
Site: Set ATLASSIAN_SITE (e.g. your-domain.atlassian.net) or pass --site
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Optional, Tuple

try:
    import requests
except ImportError:
    print("Error: requests is required. Install with: pip install requests", file=sys.stderr)
    sys.exit(1)

COMPASS_BETA_HEADER = "X-ExperimentalApi"
COMPASS_BETA_VALUE = "compass-beta"

GET_COMPONENT_BY_ALIAS_QUERY = """
query getComponentByExternalAlias($cloudId: String!, $externalSource: String!, $externalId: String!) {
  compass @optIn(to: "compass-beta") {
    getComponentByExternalAlias(
      cloudId: $cloudId
      externalSource: $externalSource
      externalId: $externalId
    ) {
      __typename
      ... on CompassComponentPayload {
        component {
          id
          name
          typeMetadata {
            name
          }
          url
          slug
          links {
            type
            name
            url
          }
        }
      }
      ... on QueryError {
        message
        extensions {
          errorType
        }
      }
    }
  }
}
"""


def normalize_site(site: str) -> str:
    if not site.startswith("https://"):
        site = "https://" + site
    return site.rstrip("/") + "/"


def get_cloud_id(site_url: str) -> Optional[str]:
    url = f"{site_url}_edge/tenant_info"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("cloudId")
    except (requests.RequestException, json.JSONDecodeError):
        return None


def graphql_request(
    graphql_url: str,
    query: str,
    variables: dict,
    auth: Tuple[str, str],
) -> Optional[dict]:
    headers = {
        "Content-Type": "application/json",
        COMPASS_BETA_HEADER: COMPASS_BETA_VALUE,
    }
    try:
        resp = requests.post(
            graphql_url,
            auth=auth,
            headers=headers,
            json={"query": query, "variables": variables},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()
    except (requests.RequestException, json.JSONDecodeError):
        return None


def get_component_by_external_alias(
    graphql_url: str,
    cloud_id: str,
    external_source: str,
    external_id: str,
    auth: Tuple[str, str],
) -> Optional[dict]:
    data = graphql_request(
        graphql_url,
        GET_COMPONENT_BY_ALIAS_QUERY,
        {
            "cloudId": cloud_id,
            "externalSource": external_source,
            "externalId": external_id,
        },
        auth,
    )
    if not data or data.get("errors"):
        return None
    payload = (data.get("data") or {}).get("compass") or {}
    result = payload.get("getComponentByExternalAlias")
    if not result or result.get("__typename") == "QueryError":
        return None
    if result.get("__typename") == "CompassComponentPayload":
        return result.get("component")
    return None


def find_jira_project_url(links: list) -> Optional[str]:
    for link in links or []:
        url = (link.get("url") or "") or ""
        link_type = (link.get("type") or "") or ""
        if link_type == "PROJECT":
            return url or None
        if "/browse/" in url or "/projects/" in url:
            return url
    return None


def group_links_by_type(links: list) -> dict:
    by_type = defaultdict(list)
    for link in links or []:
        t = link.get("type") or "(no type)"
        by_type[t].append({"name": link.get("name") or "", "url": link.get("url") or ""})
    return dict(by_type)


def _format_link_entry(entry: dict) -> str:
    name_part = entry.get("name") or ""
    url_part = entry.get("url") or ""
    if name_part and url_part:
        return f"    - {name_part}: {url_part}"
    if url_part:
        return f"    - {url_part}"
    return "    - (no name or url)"


def print_component_details(component: dict) -> None:
    """Print component name, type, URL, Jira project URL, and links by type."""
    name = component.get("name") or ""
    type_meta = component.get("typeMetadata") or {}
    type_name = type_meta.get("name") or ""
    url = component.get("url") or ""
    links = component.get("links") or []

    print("Component name:", name)
    print("Component type:", type_name)
    print("URL:", url or "(none)")
    jira_url = find_jira_project_url(links)
    print("Jira project URL:", jira_url or "(none)")

    by_type = group_links_by_type(links)
    print("Links by type:")
    for link_type in sorted(by_type.keys()):
        print(f"  {link_type}:")
        for entry in by_type[link_type]:
            print(_format_link_entry(entry))


def resolve_component(
    graphql_url: str,
    cloud_id: str,
    repo_name: str,
    auth: Tuple[str, str],
) -> Optional[dict]:
    """Try atl_gh and github external sources; return component or None."""
    for external_source in ("atl_gh", "github"):
        component = get_component_by_external_alias(
            graphql_url, cloud_id, external_source, repo_name, auth
        )
        if component:
            return component
    return None


def get_config(site: str) -> Optional[Tuple[str, str, Tuple[str, str]]]:
    """Return (graphql_url, cloud_id, auth) or None if env or cloud ID missing."""
    email = os.environ.get("ATLASSIAN_USER_EMAIL")
    api_key = os.environ.get("ATLASSIAN_USER_API_KEY")
    if not email or not api_key:
        return None
    site_url = normalize_site(site)
    cloud_id = get_cloud_id(site_url)
    if not cloud_id:
        return None
    return (f"{site_url}gateway/api/graphql", cloud_id, (email, api_key))


def run(repo_name: str, site: str) -> int:
    """Resolve component by repo name and print details. Returns exit code."""
    config = get_config(site)
    if not config:
        print(
            "Error: Set ATLASSIAN_USER_EMAIL and ATLASSIAN_USER_API_KEY; "
            "site must allow cloud ID from /_edge/tenant_info.",
            file=sys.stderr,
        )
        return 1
    graphql_url, cloud_id, auth = config
    component = resolve_component(graphql_url, cloud_id, repo_name, auth)
    if not component:
        print(
            f"Error: No Compass component found for repo \"{repo_name}\" "
            "(tried external sources: atl_gh, github).",
            file=sys.stderr,
        )
        return 1
    print_component_details(component)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Get Compass component details by repository name (external alias)."
    )
    parser.add_argument(
        "repo_name",
        help='Repository name or "owner/repo" used as external alias in Compass',
    )
    parser.add_argument(
        "--site",
        default=os.environ.get("ATLASSIAN_SITE"),
        help="Atlassian site host (e.g. your-domain.atlassian.net). Default: ATLASSIAN_SITE env.",
    )
    args = parser.parse_args()
    repo_name = args.repo_name.strip()
    if not repo_name:
        print("Error: repo_name must be non-empty.", file=sys.stderr)
        return 1
    if not args.site or not args.site.strip():
        print(
            "Error: Site is required. Set ATLASSIAN_SITE or pass --site (e.g. your-domain.atlassian.net).",
            file=sys.stderr,
        )
        return 1
    return run(repo_name, args.site.strip())


if __name__ == "__main__":
    sys.exit(main())
