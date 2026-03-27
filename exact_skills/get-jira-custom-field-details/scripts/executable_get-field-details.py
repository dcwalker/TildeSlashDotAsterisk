#!/usr/bin/env python3
"""
Usage: get-field-details.py "Field Name" [--site SITE]
Returns: custom field ID, field type, and (for option fields) list of options.

Requires: ATLASSIAN_USER_EMAIL, ATLASSIAN_USER_API_KEY
Site: Set ATLASSIAN_SITE (e.g. your-domain.atlassian.net) or pass --site
"""

import argparse
import json
import os
import re
import sys
import urllib.request
from base64 import b64encode
from typing import Callable, Optional, Tuple, Union


def jira_get(path: str, base_url: str, headers: dict) -> Tuple[Union[dict, list], int]:
    req = urllib.request.Request(f"{base_url}{path}", headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode()), resp.status
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            data = {}
        return data, e.code


def find_custom_field_by_name(fields: list, field_name: str) -> Optional[dict]:
    pattern = re.compile(re.escape(field_name), re.IGNORECASE)
    for f in fields:
        if not f.get("custom"):
            continue
        if pattern.search(f.get("name", "")):
            return f
    return None


def is_option_field(schema: dict) -> bool:
    schema_type = schema.get("type", "")
    schema_items = schema.get("items", "")
    return schema_type == "option" or (
        schema_type == "array" and schema_items == "option"
    )


def print_field_info(field: dict) -> None:
    schema = field.get("schema", {})
    print(f"Name:  {field.get('name', '')}")
    print(f"ID:    {field['id']}")
    print(f"Type:  {schema.get('type', '')}")
    if schema.get("custom"):
        print(f"Schema (custom): {schema['custom']}")
    if schema.get("items"):
        print(f"Items: {schema['items']}")


def fetch_and_print_options(
    field_id: str,
    get_fn: Callable[[str], Tuple[Union[dict, list], int]],
) -> None:
    contexts, status = get_fn(f"/field/{field_id}/contexts")
    if status == 403:
        print(
            "Options: (retrieval requires Administer Jira; use issue createmeta "
            "for a project/issue type to see allowed values)"
        )
        return
    if status != 200:
        print("Options: (failed to fetch contexts)", file=sys.stderr)
        sys.exit(1)

    values = contexts.get("values", [])
    if not values:
        print("Options: (no contexts configured)")
        return

    context_id = values[0].get("id")
    if not context_id:
        print("Options: (no context id)")
        return

    opts_data, opts_status = get_fn(
        f"/field/{field_id}/context/{context_id}/option?maxResults=500"
    )

    if opts_status == 403:
        print(
            "Options: (retrieval requires Administer Jira; use issue createmeta "
            "for a project/issue type to see allowed values)"
        )
        return

    if opts_status != 200:
        print(f"Options: (request failed with HTTP {opts_status})", file=sys.stderr)
        sys.exit(1)

    opts_list = opts_data.get("values", [])
    total = opts_data.get("total", len(opts_list))
    print(f"Options: ({total} values)")
    for opt in opts_list:
        print(f"  {opt.get('id', '')}\t{opt.get('value', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Get Jira custom field ID, type, and options by field name."
    )
    parser.add_argument(
        "field_name",
        help="Field name as shown in Jira (case-insensitive match)",
    )
    parser.add_argument(
        "--site",
        default=os.environ.get("ATLASSIAN_SITE"),
        help="Atlassian site host (e.g. your-domain.atlassian.net). Default: ATLASSIAN_SITE env.",
    )
    args = parser.parse_args()

    field_name = args.field_name.strip()
    if not field_name:
        print("Error: field_name must be non-empty.", file=sys.stderr)
        sys.exit(1)
    site = (args.site or "").strip()
    if not site:
        print(
            "Error: Site is required. Set ATLASSIAN_SITE or pass --site (e.g. your-domain.atlassian.net).",
            file=sys.stderr,
        )
        sys.exit(1)

    email = os.environ.get("ATLASSIAN_USER_EMAIL")
    api_key = os.environ.get("ATLASSIAN_USER_API_KEY")
    if not email or not api_key:
        print("Error: ATLASSIAN_USER_EMAIL and ATLASSIAN_USER_API_KEY must be set.", file=sys.stderr)
        sys.exit(1)

    base_url = f"https://{site}/rest/api/3"
    credentials = b64encode(f"{email}:{api_key}".encode()).decode()
    headers = {"Accept": "application/json", "Authorization": f"Basic {credentials}"}
    get_fn = lambda path: jira_get(path, base_url, headers)

    fields, status = get_fn("/field")
    if status != 200:
        print(f"Error: Failed to fetch fields (HTTP {status})", file=sys.stderr)
        sys.exit(1)

    field = find_custom_field_by_name(fields, field_name)
    if not field:
        print(f"Error: No custom field found matching \"{field_name}\".", file=sys.stderr)
        print(f"Check the field name in Jira or list fields with: GET {base_url}/field", file=sys.stderr)
        sys.exit(1)

    print_field_info(field)

    if not is_option_field(field.get("schema", {})):
        print("Options: (none – field is not a select/list/radio/checkbox type)")
        return

    fetch_and_print_options(field["id"], get_fn)


if __name__ == "__main__":
    main()
