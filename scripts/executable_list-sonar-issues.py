#!/usr/bin/env python3
"""
Script to list SonarQube issues for this project.
Usage: ./list-sonar-issues.py [OPTIONS]
Run with -h or --help for full usage information.
"""

import argparse
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional


def get_terminal_width() -> int:
    """Get terminal width, default to 80 if not available."""
    try:
        return shutil.get_terminal_size().columns
    except OSError:
        return 80


def find_project_root() -> Optional[str]:
    """Find project root by searching up for sonar-project.properties."""
    dir_path = os.getcwd()
    while dir_path != "/":
        if os.path.isfile(os.path.join(dir_path, "sonar-project.properties")):
            return dir_path
        dir_path = os.path.dirname(dir_path)
    return None


def get_project_key() -> str:
    """Get project key from env or sonar-project.properties."""
    key = os.environ.get("SONAR_PROJECT_KEY")
    if key:
        return key.strip()
    root = find_project_root()
    if not root:
        sys.exit("Error: SONAR_PROJECT_KEY environment variable is not set and sonar-project.properties file not found")
    props_path = os.path.join(root, "sonar-project.properties")
    with open(props_path) as f:
        for line in f:
            if line.startswith("sonar.projectKey="):
                return line.split("=", 1)[1].strip()
    sys.exit("Error: Could not find sonar.projectKey in sonar-project.properties")


def auto_detect_pr() -> Optional[str]:
    """Auto-detect PR number from current branch via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "pr", "view", "--json", "number", "-q", ".number"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            num = result.stdout.strip()
            if num != "null":
                return num
    except (FileNotFoundError, subprocess.SubprocessError):
        pass
    return None


def strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]*>", "", text)


class SonarQubeClient:
    """Handles all API interactions with SonarQube."""

    def __init__(self, base_url: str, token: str, project_key: str, args: argparse.Namespace) -> None:
        self.base_url = base_url.rstrip("/") + "/"
        self.token = token
        self.project_key = project_key
        self.args = args
        self._auth_header = "Basic " + base64.b64encode(f"{token}:".encode()).decode()

    def _request(self, path: str, params: Optional[dict] = None) -> Any:
        """Make authenticated GET request and return JSON."""
        url = self.base_url + path.lstrip("/")
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        req = urllib.request.Request(url, headers={"Authorization": self._auth_header})
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode()
                return json.loads(body)
            except ValueError:
                return {}
        except urllib.error.URLError:
            return {}

    def get_project_info(self) -> dict:
        """Fetch project/component info for project name."""
        data = self._request("api/components/show", {"component": self.project_key})
        comp = data.get("component", {})
        return {"name": comp.get("name", ""), "key": comp.get("key", self.project_key)}

    def _build_issue_search_params(self) -> dict:
        """Build parameters for issue search API request."""
        params = {"componentKeys": self.project_key}
        if self.args.issue_key:
            params["ps"] = 500
        if self.args.status and self.args.status in ("OPEN", "CONFIRMED", "REOPENED", "RESOLVED", "CLOSED"):
            params["statuses"] = self.args.status
        elif not self.args.status and not self.args.issue_key:
            params["resolved"] = "false"
        if self.args.pull_request:
            params["pullRequest"] = self.args.pull_request
        if self.args.severity:
            params["severities"] = self.args.severity
        if self.args.type and self.args.type != "SECURITY_HOTSPOT":
            params["types"] = self.args.type
        if self.args.rule:
            params["rules"] = self.args.rule
        return params

    def _filter_issues_by_key(self, issues: list, params: dict) -> list:
        """Filter issues by issue_key, with fallback search if needed."""
        filtered = [i for i in issues if i.get("key") == self.args.issue_key]
        if not filtered and not self.args.status:
            params2 = dict(params)
            params2.pop("resolved", None)
            data2 = self._request("api/issues/search", params2)
            filtered = [i for i in (data2.get("issues") or []) if i.get("key") == self.args.issue_key]
        return filtered

    def _filter_issues_by_component(self, issues: list) -> list:
        """Filter issues by component."""
        if not self.args.component:
            return issues
        return [
            i for i in issues
            if i.get("component") == self.args.component
            or self.project_key + ":" + self.args.component == i.get("component")
        ]

    def get_issues(self) -> dict:
        """Fetch issues from api/issues/search."""
        params = self._build_issue_search_params()
        data = self._request("api/issues/search", params)
        if not data:
            return {"total": 0, "issues": []}

        issues = data.get("issues", [])
        if self.args.issue_key:
            issues = self._filter_issues_by_key(issues, params)
        elif not self.args.issue_key:
            issues = [i for i in issues if i.get("project") == self.project_key]
        issues = self._filter_issues_by_component(issues)

        return {"total": len(issues), "issues": issues, "components": data.get("components", []), "rules": data.get("rules", []), "users": data.get("users", [])}

    def _filter_hotspots(self, hotspots: list) -> list:
        """Apply issue_key, component, and status filters to hotspot list."""
        if self.args.issue_key:
            hotspots = [h for h in hotspots if h.get("key") == self.args.issue_key]
        if self.args.component:
            comp_match = self.args.component
            full_key = self.project_key + ":" + comp_match
            hotspots = [h for h in hotspots if h.get("component") in (comp_match, full_key)]
        if self.args.status and self.args.status not in ("TO_REVIEW", "REVIEWED", "FIXED", "SAFE"):
            hotspots = [h for h in hotspots if h.get("status") == "TO_REVIEW"]
        return hotspots

    def get_hotspots(self) -> dict:
        """Fetch security hotspots from api/hotspots/search."""
        params = {"projectKey": self.project_key}
        if self.args.issue_key:
            params["ps"] = 500
        if self.args.pull_request:
            params["pullRequest"] = self.args.pull_request
        if self.args.status and self.args.status in ("TO_REVIEW", "REVIEWED", "FIXED", "SAFE"):
            params["status"] = self.args.status
        if self.args.severity:
            params["severity"] = self.args.severity
        if self.args.rule:
            params["ruleKey"] = self.args.rule

        data = self._request("api/hotspots/search", params)
        if not data:
            return {"total": 0, "hotspots": [], "rules": []}
        errs = data.get("errors", [])
        if errs:
            if not self.args.json and not self.args.summary:
                print(f"Warning: Hotspots API returned error: {errs[0].get('msg', '')}", file=sys.stderr)
            return {"total": 0, "hotspots": [], "rules": []}

        hotspots = self._filter_hotspots(data.get("hotspots", []))
        return {"total": len(hotspots), "hotspots": hotspots, "rules": data.get("rules", [])}

    def get_issue_detail(self, issue_key: str) -> dict:
        """Fetch single issue detail."""
        data = self._request("api/issues/show", {"issue": issue_key})
        if data.get("errors"):
            return {}
        return data.get("issue", {})

    def get_hotspot_detail(self, hotspot_key: str) -> dict:
        """Fetch single hotspot detail."""
        data = self._request("api/hotspots/show", {"hotspot": hotspot_key})
        if data.get("errors"):
            return {}
        return data.get("hotspot", {})

    def _fetch_rule_via_show(self, rule_key: str) -> dict:
        """Try api/rules/show with key, rule_key, rule params; return rule dict or {}."""
        for param_name in ("key", "rule_key", "rule"):
            data = self._request("api/rules/show", {param_name: rule_key})
            if not data.get("errors"):
                rule = data.get("rule", {})
                if rule:
                    return rule
        return {}

    def _fetch_rule_via_search(self, rule_key: str) -> dict:
        """Try api/rules/search; return rule dict or {}."""
        for query_param in ("rule_key", "q"):
            data = self._request("api/rules/search", {query_param: rule_key})
            if data.get("errors"):
                continue
            for r in data.get("rules", []):
                if r.get("key") == rule_key:
                    return r
            if data.get("rules") and query_param == "rule_key":
                return data["rules"][0]
        return {}

    def get_rule_detail(self, rule_key: str) -> dict:
        """Fetch rule detail (e.g. vulnerabilityDescription, fixRecommendations) from api/rules/show or search."""
        if not rule_key or not isinstance(rule_key, str):
            return {}
        rule = self._fetch_rule_via_show(rule_key)
        return rule if rule else self._fetch_rule_via_search(rule_key)

    def get_coverage_metrics(self) -> dict:
        """Fetch coverage metrics from api/measures/component."""
        metrics = "coverage,new_coverage,lines_to_cover,new_lines_to_cover,uncovered_lines,new_uncovered_lines"
        params = {"component": self.project_key, "metricKeys": metrics, "additionalFields": "period"}
        if self.args.pull_request:
            params["pullRequest"] = self.args.pull_request
        data = self._request("api/measures/component", params)
        return data.get("component", {}).get("measures", [])

    def get_quality_gate_status(self) -> dict:
        """Fetch quality gate status."""
        params = {"projectKey": self.project_key}
        if self.args.pull_request:
            params["pullRequest"] = self.args.pull_request
        return self._request("api/qualitygates/project_status", params)

    def get_duplications_tree(self) -> list:
        """Fetch component tree with duplication metrics."""
        params = {
            "component": self.project_key,
            "metricKeys": "duplicated_lines,new_duplicated_lines,duplicated_lines_density,lines,new_lines",
            "qualifiers": "FIL",
            "additionalFields": "period",
            "ps": 500,
        }
        if self.args.pull_request:
            params["pullRequest"] = self.args.pull_request
        data = self._request("api/measures/component_tree", params)
        return data.get("components", [])

    def get_duplications_show(self, file_key: str) -> dict:
        """Fetch duplication blocks for a file."""
        return self._request("api/duplications/show", {"key": file_key})

    def get_coverage_tree(self) -> list:
        """Fetch component tree with new code coverage for PR."""
        if not self.args.pull_request:
            return []
        params = {
            "component": self.project_key,
            "metricKeys": "new_coverage,new_lines_to_cover,new_uncovered_lines",
            "qualifiers": "FIL",
            "additionalFields": "period",
            "pullRequest": self.args.pull_request,
            "ps": 500,
        }
        data = self._request("api/measures/component_tree", params)
        return data.get("components", [])

    def get_sources_lines(self, file_key: str) -> list:
        """Fetch line-level coverage for a file (new code)."""
        if not self.args.pull_request:
            return []
        data = self._request("api/sources/lines", {"key": file_key, "pullRequest": self.args.pull_request})
        return data.get("sources", [])


class OutputFormatter:
    """Handles all console output formatting with pipe-prefixed wrapped text."""

    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self._width = max(40, get_terminal_width() - 3)

    def wrap_with_pipe(self, text: str) -> str:
        """Wrap text at word boundaries and prefix each line with | """
        if not text:
            return "|"
        lines_out = []
        for line in text.splitlines():
            if line.strip():
                wrapped = textwrap.fill(line, width=self._width, break_long_words=False, break_on_hyphens=False)
                for w in wrapped.splitlines():
                    lines_out.append("| " + w)
            else:
                lines_out.append("|")
        return "\n".join(lines_out)

    def _measure_by_key(self, measures: list, metric: str, attr: str = "value") -> Optional[str]:
        for m in measures:
            if m.get("metric") == metric:
                if attr == "period":
                    period = m.get("period")
                    if period:
                        return str(period.get("value", ""))
                    return None
                return str(m.get(attr, ""))
        return None

    @staticmethod
    def _merge_issue_detail(item: dict, detail: dict) -> dict:
        """Merge issue detail into item and normalize component/project keys."""
        merged = {**item, **{k: v for k, v in detail.items() if k not in ("component", "project")}}
        comp = detail.get("component")
        if isinstance(comp, dict):
            merged["component"] = comp.get("key", item.get("component", "N/A"))
        proj = detail.get("project")
        if isinstance(proj, dict):
            merged["project"] = proj.get("key", item.get("project", "N/A"))
        return merged

    def _format_one_issue(self, client: SonarQubeClient, item: dict, key: str) -> list:
        """Return list of output lines for a single issue."""
        out = [
            f"Issue Key: {key}",
            "---",
            f"Key:              {item.get('key', 'N/A')}",
            f"Severity:         {(item.get('severity') or 'N/A').upper()}",
            f"Type:             {item.get('type', 'N/A')}",
            f"Status:           {item.get('status', 'N/A')}",
            f"Rule:             {item.get('rule', item.get('ruleKey', 'N/A'))}",
            f"Component:        {item.get('component', 'N/A')}",
            f"Project:          {item.get('project', 'N/A')}",
            f"Line:             {item.get('line', 'N/A')}",
            f"Author:           {item.get('author', 'N/A')}",
            f"Creation Date:    {item.get('creationDate', 'N/A')}",
            f"Update Date:      {item.get('updateDate', 'N/A')}",
            f"Resolution:       {item.get('resolution', 'N/A')}",
            f"Effort:           {item.get('effort', 'N/A')}",
            f"Debt:             {item.get('debt', 'N/A')}",
        ]
        msg = item.get("message")
        if msg and msg != "N/A":
            out.extend(["Message:", "", self.wrap_with_pipe(msg), ""])
        tr = item.get("textRange")
        if tr:
            out.extend([
                "Text Range:",
                f"  Start Line:     {tr.get('startLine', 'N/A')}",
                f"  Start Offset:   {tr.get('startOffset', 'N/A')}",
                f"  End Line:       {tr.get('endLine', 'N/A')}",
                f"  End Offset:     {tr.get('endOffset', 'N/A')}",
            ])
        rule_obj = item.get("rule") if isinstance(item.get("rule"), dict) else {}
        rule_desc_str = rule_obj.get("description") or rule_obj.get("htmlDescription") or ""
        if rule_desc_str:
            out.extend(["", "Rule Description:", "", self.wrap_with_pipe(strip_html(rule_desc_str))])
        why = rule_obj.get("whyIsThisAnIssue") or item.get("whyIsThisAnIssue")
        if why:
            out.extend(["", "Why is this an issue?:", "", self.wrap_with_pipe(strip_html(why))])
        how = rule_obj.get("howToFixIt") or item.get("howToFixIt")
        if how:
            out.extend(["", "How can I fix it?:", "", self.wrap_with_pipe(strip_html(how))])
        proj_key = item.get("project")
        if isinstance(proj_key, dict):
            proj_key = proj_key.get("key", "")
        out.append("")
        out.append(f"URL:              {client.base_url}project/issues?id={proj_key}&issues={key}&open={key}")
        out.append("")
        return out

    def format_issues_section(self, client: SonarQubeClient, issues_data: dict) -> str:
        """Format dedicated Issues section (non-hotspot issues only)."""
        issues_only = [i for i in issues_data.get("issues", []) if not i.get("isHotspot")]
        if not issues_only:
            return "=== Issues ===\nNo issues found.\n"

        n = len(issues_only)
        out = ["", "=== Issues ===", "", f"Found {n} issue{'s' if n != 1 else ''}", ""]
        for item in issues_only:
            key = item.get("key", "N/A")
            detail = client.get_issue_detail(key)
            if detail:
                item = self._merge_issue_detail(item, detail)
            out.extend(self._format_one_issue(client, item, key))
        return "\n".join(out)

    @staticmethod
    def _merge_hotspot_detail(item: dict, detail: dict) -> dict:
        """Merge hotspot detail into item and normalize component/project keys."""
        merged = {**item, **{k: v for k, v in detail.items() if k not in ("component", "project")}}
        comp = detail.get("component")
        if isinstance(comp, dict):
            merged["component"] = comp.get("key", item.get("component", "N/A"))
        proj = detail.get("project")
        if isinstance(proj, dict):
            merged["project"] = proj.get("key", item.get("project", "N/A"))
        return merged

    @staticmethod
    def _hotspot_rule_key(item: dict) -> Optional[str]:
        """Extract rule key string from a hotspot item."""
        r = item.get("rule")
        if item.get("ruleKey"):
            return item.get("ruleKey")
        if isinstance(r, dict) and r.get("key"):
            return r.get("key")
        return r if isinstance(r, str) else None

    @staticmethod
    def _initial_hotspot_rule_obj(item: dict) -> dict:
        """Return rule object from item, or empty dict if rule is not a dict."""
        r = item.get("rule")
        return r if isinstance(r, dict) else {}

    @staticmethod
    def _get_hotspot_rule_obj(client: SonarQubeClient, item: dict, rules_by_key: dict) -> dict:
        """Resolve full rule object for a hotspot (search rules + api/rules/show)."""
        rule_obj = OutputFormatter._initial_hotspot_rule_obj(item)
        rule_key_str = OutputFormatter._hotspot_rule_key(item)
        if rule_key_str:
            rule_obj = {**rule_obj, **rules_by_key.get(rule_key_str, {})}
            rule_detail = client.get_rule_detail(rule_key_str)
            rule_obj = {**rule_obj, **(rule_detail or {})}
        return rule_obj

    def _append_hotspot_rule_guidance(self, out: list, item: dict, rule_obj: dict) -> None:
        """Append rule description, risk, vulnerability, and fix sections to out."""
        rule_desc_str = rule_obj.get("description") or rule_obj.get("htmlDescription") or ""
        if rule_desc_str:
            out.extend(["", "Rule Description:", "", self.wrap_with_pipe(strip_html(rule_desc_str))])
        risk = item.get("riskDescription") or item.get("message")
        if risk and risk != rule_obj.get("description"):
            out.extend(["", "What's the risk?:", "", self.wrap_with_pipe(strip_html(risk))])
        vuln = (
            item.get("vulnerabilityDescription")
            or rule_obj.get("vulnerabilityDescription")
            or rule_obj.get("vulnerability_description")
            or rule_obj.get("mdDesc")
        )
        if vuln:
            out.extend(["", "Vulnerability Description:", "", self.wrap_with_pipe(strip_html(vuln))])
        remediation = rule_obj.get("remediation") or {}
        fix = (
            item.get("fixRecommendations")
            or rule_obj.get("fixRecommendations")
            or rule_obj.get("fix_recommendations")
            or remediation.get("func")
            or remediation.get("desc")
            or rule_obj.get("remediation")
        )
        if isinstance(fix, dict):
            fix = fix.get("func") or fix.get("desc") or ""
        if fix:
            out.extend(["", "How can I fix it?:", "", self.wrap_with_pipe(strip_html(fix))])

    def _format_one_hotspot(self, client: SonarQubeClient, item: dict, key: str, rule_obj: dict) -> list:
        """Return list of output lines for a single security hotspot."""
        sev = item.get("vulnerabilityProbability") or item.get("severity") or "N/A"
        out = [
            f"Security Hotspot Key: {key}",
            "---",
            f"Key:              {item.get('key', 'N/A')}",
            f"Severity:         {str(sev).upper()}",
            "Type:             SECURITY_HOTSPOT",
            f"Status:           {item.get('status', 'N/A')}",
            f"Component:        {item.get('component', 'N/A')}",
            f"Project:          {item.get('project', 'N/A')}",
            f"Line:             {item.get('line', 'N/A')}",
            f"Author:           {item.get('author', 'N/A')}",
            f"Creation Date:    {item.get('creationDate', 'N/A')}",
            f"Update Date:      {item.get('updateDate', 'N/A')}",
        ]
        if item.get("resolution"):
            out.append(f"Resolution:       {item.get('resolution')}")
        out.append(f"Rule:             {item.get('ruleKey', item.get('rule', 'N/A'))}")

        if item.get("message") and item.get("message") != "N/A":
            out.extend(["Message:", "", self.wrap_with_pipe(item.get("message")), ""])
        tr = item.get("textRange")
        if tr:
            out.extend([
                "Text Range:",
                f"  Start Line:     {tr.get('startLine', 'N/A')}",
                f"  Start Offset:   {tr.get('startOffset', 'N/A')}",
                f"  End Line:       {tr.get('endLine', 'N/A')}",
                f"  End Offset:     {tr.get('endOffset', 'N/A')}",
            ])

        self._append_hotspot_rule_guidance(out, item, rule_obj)

        proj_key = item.get("project")
        if isinstance(proj_key, dict):
            proj_key = proj_key.get("key", "")
        out.append("")
        out.append(f"URL:              {client.base_url}security_hotspots?id={proj_key}&hotspots={key}")
        out.append("")
        return out

    def format_hotspots_section(self, client: SonarQubeClient, hotspots_data: dict) -> str:
        """Format dedicated Security Hotspots section."""
        hotspots = hotspots_data.get("hotspots", [])
        if not hotspots:
            return "=== Security Hotspots ===\nNo security hotspots found.\n"

        rules_by_key = {r.get("key"): r for r in hotspots_data.get("rules", []) if r.get("key")}
        n = len(hotspots)
        out = ["", "=== Security Hotspots ===", "", f"Found {n} security hotspot{'s' if n != 1 else ''}", ""]
        for item in hotspots:
            key = item.get("key", "N/A")
            detail = client.get_hotspot_detail(key)
            if detail:
                item = self._merge_hotspot_detail(item, detail)
            rule_obj = self._get_hotspot_rule_obj(client, item, rules_by_key)
            out.extend(self._format_one_hotspot(client, item, key, rule_obj))
        return "\n".join(out)

    @staticmethod
    def _files_with_duplications(components: list, measure_by_key: Any) -> list:
        """Return list of {key, duplicated_lines} for components that have duplicated_lines > 0."""
        result = []
        for c in components:
            measures = c.get("measures", [])
            dup_val = measure_by_key(measures, "duplicated_lines")
            if dup_val and int(dup_val) > 0:
                result.append({"key": c.get("key"), "duplicated_lines": dup_val})
        return result

    def _format_file_duplications(self, client: SonarQubeClient, finfo: dict, project_key: str) -> list:
        """Return list of output lines for one file's duplication blocks."""
        file_key = finfo["key"]
        file_name = file_key.replace(project_key + ":", "") if file_key else ""
        out = [
            f"File: {file_name}",
            f"Duplicated Lines: {finfo['duplicated_lines']}",
            "---",
        ]
        dup_data = client.get_duplications_show(file_key)
        groups = dup_data.get("duplications", [])
        files_map = dup_data.get("files", {})
        for j, group in enumerate(groups):
            blocks = group.get("blocks", [])
            if not blocks:
                continue
            out.append(f"Duplication Group {j + 1}:")
            for k, block in enumerate(blocks):
                ref = block.get("_ref", "")
                from_line = block.get("from", "N/A")
                size = block.get("size", "N/A")
                ref_info = files_map.get(ref, {})
                ref_name = ref_info.get("name", ref_info.get("key", "N/A"))
                if from_line != "N/A" and size != "N/A":
                    to_line = from_line + size - 1
                    out.append(f"  Block {k + 1}: Lines {from_line}-{to_line} ({size} lines) in {ref_name}")
                else:
                    out.append(f"  Block {k + 1}: Line {from_line}, Size {size} in {ref_name}")
            out.append("")
        return out

    def format_duplications_section(self, client: SonarQubeClient, components: list) -> str:
        """Format Code Duplications section."""
        out = ["", "=== Code Duplications ===", ""]
        files_with_dup = self._files_with_duplications(components, self._measure_by_key)

        if not files_with_dup:
            out.append("No files with code duplications found in project.")
            return "\n".join(out) + "\n"

        out.append("Finding files with code duplications...")
        out.append(f"Found {len(files_with_dup)} file(s) with duplications")
        out.append("")
        for finfo in files_with_dup:
            out.extend(self._format_file_duplications(client, finfo, client.project_key))
        return "\n".join(out) + "\n"

    def format_coverage_section(self, client: SonarQubeClient, components: list) -> str:
        """Format New Code Test Coverage section (when PR is set)."""
        if not self.args.pull_request:
            return ""
        out = ["", "=== New Code Test Coverage ===", "", "Analyzing file-level coverage for new code..."]
        files_uncovered = []
        for c in components:
            measures = c.get("measures", [])
            new_unc = self._measure_by_key(measures, "new_uncovered_lines", "period")
            if new_unc and int(new_unc) > 0:
                new_cov = self._measure_by_key(measures, "new_coverage", "period") or "0"
                new_to_cover = self._measure_by_key(measures, "new_lines_to_cover", "period") or "0"
                files_uncovered.append({
                    "key": c.get("key"),
                    "path": c.get("path", c.get("key", "")),
                    "new_coverage": new_cov,
                    "new_lines_to_cover": new_to_cover,
                    "new_uncovered_lines": new_unc,
                })
        files_uncovered.sort(key=lambda x: int(x["new_uncovered_lines"]), reverse=True)

        if not files_uncovered:
            out.append("All new code is fully covered!")
            return "\n".join(out) + "\n"

        out.append(f"Found {len(files_uncovered)} file(s) with uncovered lines in new code")
        out.append("")
        for f in files_uncovered:
            new_cover = f["new_lines_to_cover"]
            new_unc = f["new_uncovered_lines"]
            try:
                new_covered = int(new_cover) - int(new_unc)
            except (ValueError, TypeError):
                new_covered = 0
            out.append(f"File: {f['path']}")
            out.append(f"  Coverage: {f['new_coverage']}% ({new_covered} of {new_cover} new lines covered)")
            out.append(f"  Uncovered: {new_unc} new lines need tests")
            sources = client.get_sources_lines(f["key"])
            uncovered_lines = [s["line"] for s in sources if s.get("isNew") and s.get("lineHits", 0) == 0]
            if uncovered_lines:
                ranges = self._line_ranges(uncovered_lines)
                out.append(f"  Lines needing coverage: {ranges}")
            out.append("")
        return "\n".join(out)

    def _line_ranges(self, numbers: list) -> str:
        """Convert list of line numbers to range string (e.g. 1-5, 8, 10-12)."""
        if not numbers:
            return ""
        nums = sorted(int(n) for n in numbers if n is not None)
        parts = []
        start = prev = nums[0]
        for n in nums[1:]:
            if n == prev + 1:
                prev = n
            else:
                parts.append(f"{start}-{prev}" if start != prev else str(start))
                start = prev = n
        parts.append(f"{start}-{prev}" if start != prev else str(start))
        return ", ".join(parts)

    @staticmethod
    def _quality_gate_line(cond: dict) -> Optional[str]:
        """Format one quality gate condition as a line, or None."""
        comp = cond.get("comparator", "")
        thresh = cond.get("errorThreshold", "")
        status = cond.get("status", "")
        status_str = {"OK": " (PASSING)", "ERROR": " (FAILING)", "WARN": " (WARNING)"}.get(status, "")
        thresh_str = {"LT": f"required >= {thresh}%", "GT": f"required <= {thresh}%", "EQ": f"required = {thresh}%"}.get(comp, "")
        return f"  Quality gate: {thresh_str}{status_str}" if thresh_str else None

    @staticmethod
    def _overall_coverage_line(cov_val: Any, lines_to_cover: Any, uncovered: Any) -> str:
        """Return one line for overall coverage."""
        if not (lines_to_cover and uncovered):
            return f"  Overall: {cov_val}%"
        try:
            covered = int(lines_to_cover) - int(uncovered)
            return f"  Overall: {cov_val}% ({covered} of {lines_to_cover} lines covered)"
        except (ValueError, TypeError):
            return f"  Overall: {cov_val}%"

    @staticmethod
    def _new_coverage_lines(new_cov_val: Any, new_lines_to_cover: Any, new_uncovered: Any) -> list:
        """Return list of lines for new code coverage."""
        if not new_lines_to_cover:
            return [f"  New code: {new_cov_val}%"]
        out = [f"  New code: {new_cov_val}% on {new_lines_to_cover} new lines to cover"]
        if new_uncovered:
            try:
                new_covered = int(new_lines_to_cover) - int(new_uncovered)
                out.append(f"    ({new_covered} of {new_lines_to_cover} new lines covered)")
            except (ValueError, TypeError):
                pass
        return out

    @staticmethod
    def _estimated_merge_coverage_line(
        lines_to_cover: Any,
        new_lines_to_cover: Any,
        uncovered: Any,
        new_uncovered: Any,
    ) -> Optional[str]:
        """Return estimated after merge line, or None."""
        try:
            tot = int(lines_to_cover) + int(new_lines_to_cover)
            cov_tot = int(lines_to_cover) - int(uncovered) + int(new_lines_to_cover) - int(new_uncovered)
            return f"  Estimated after merge: {cov_tot * 100.0 / tot:.1f}%" if tot > 0 else None
        except (ValueError, TypeError):
            return None

    @staticmethod
    def _coverage_summary_lines(
        cov_val: Any,
        new_cov_val: Any,
        lines_to_cover: Any,
        new_lines_to_cover: Any,
        uncovered: Any,
        new_uncovered: Any,
    ) -> list:
        """Return list of Test Coverage detail lines (overall, new code, estimated)."""
        out = []
        if cov_val:
            out.append(OutputFormatter._overall_coverage_line(cov_val, lines_to_cover, uncovered))
        if new_cov_val:
            out.extend(OutputFormatter._new_coverage_lines(new_cov_val, new_lines_to_cover, new_uncovered))
        if cov_val and new_cov_val and lines_to_cover and new_lines_to_cover and uncovered and new_uncovered:
            line = OutputFormatter._estimated_merge_coverage_line(lines_to_cover, new_lines_to_cover, uncovered, new_uncovered)
            if line:
                out.append(line)
        return out

    def _append_coverage_summary(self, out: list, coverage_measures: list, conditions: list) -> None:
        """Append Test Coverage and coverage quality gate to out."""
        cov_val = self._measure_by_key(coverage_measures, "coverage")
        new_cov_val = self._measure_by_key(coverage_measures, "new_coverage", "period")
        lines_to_cover = self._measure_by_key(coverage_measures, "lines_to_cover")
        new_lines_to_cover = self._measure_by_key(coverage_measures, "new_lines_to_cover", "period")
        uncovered = self._measure_by_key(coverage_measures, "uncovered_lines")
        new_uncovered = self._measure_by_key(coverage_measures, "new_uncovered_lines", "period")

        if not (cov_val or new_cov_val):
            return
        out.append("Test Coverage:")
        out.extend(self._coverage_summary_lines(cov_val, new_cov_val, lines_to_cover, new_lines_to_cover, uncovered, new_uncovered))
        for cond in conditions:
            if "coverage" in (cond.get("metricKey") or ""):
                line = self._quality_gate_line(cond)
                if line:
                    out.append(line)
                break

    @staticmethod
    def _dup_aggregates(dup_components: list) -> tuple:
        """Return (total_lines, total_dup, new_dup, new_lines) from dup_components."""
        total_lines = total_dup = new_dup = new_lines = 0
        for c in dup_components:
            for m in c.get("measures", []):
                met = m.get("metric")
                if met == "lines":
                    total_lines += int(m.get("value", 0) or 0)
                elif met == "duplicated_lines":
                    total_dup += int(m.get("value", 0) or 0)
                elif met == "new_duplicated_lines":
                    new_dup += int((m.get("period") or {}).get("value", 0) or 0)
                elif met == "new_lines":
                    new_lines += int((m.get("period") or {}).get("value", 0) or 0)
        return total_lines, total_dup, new_dup, new_lines

    def _append_duplication_summary(self, out: list, dup_components: list, conditions: list) -> None:
        """Append Code Duplication and duplication quality gate to out."""
        total_lines, total_dup, new_dup, new_lines = self._dup_aggregates(dup_components)
        out.append("")
        if total_lines <= 0:
            return
        out.append("Code Duplication:")
        out.append(f"  Overall: {total_dup * 100.0 / total_lines:.1f}%")
        if new_dup and new_lines:
            new_pct = new_dup * 100.0 / new_lines
            out.append(f"  New code: {new_pct:.1f}% on {new_lines} new lines")
            out.append(f"    ({new_dup} duplicated lines in new code)")
            tot_after = total_lines + new_lines
            if tot_after > 0:
                out.append(f"  Estimated after merge: {(total_dup + new_dup) * 100.0 / tot_after:.1f}%")
        for cond in conditions:
            if "duplication" in (cond.get("metricKey") or ""):
                line = self._quality_gate_line(cond)
                if line:
                    out.append(line)
                break

    def format_summary(
        self,
        project_name: str,
        project_key: str,
        issues_total: int,
        hotspots_total: int,
        coverage_measures: list,
        qg_status: dict,
        dup_components: list,
    ) -> str:
        """Format Summary section."""
        out = ["", "=== Summary ===", ""]
        if project_name:
            out.append(f"Project Name:  {project_name}")
        out.append(f"Project Key:   {project_key}")
        out.append("")
        out.append("Issues:")
        out.append("  No issues found" if issues_total == 0 else f"  Total: {issues_total}")
        out.append("")
        out.append("Security Hotspots:")
        out.append("  No security hotspots found" if hotspots_total == 0 else f"  Total: {hotspots_total}")
        out.append("")

        conditions = (qg_status.get("projectStatus") or {}).get("conditions", [])
        self._append_coverage_summary(out, coverage_measures, conditions)
        self._append_duplication_summary(out, dup_components, conditions)
        return "\n".join(out) + "\n"


def run(
    client: SonarQubeClient,
    formatter: OutputFormatter,
    project_key: str,
    args: argparse.Namespace,
    fetch_issues: bool,
    fetch_hotspots: bool,
) -> None:
    """Main run: fetch data and output sections."""
    project_info = client.get_project_info()
    project_name = project_info.get("name", "")
    coverage_measures = client.get_coverage_metrics()
    qg_status = client.get_quality_gate_status()
    dup_components = client.get_duplications_tree()

    issues_data = client.get_issues() if fetch_issues else {"total": 0, "issues": []}
    hotspots_data = client.get_hotspots() if fetch_hotspots else {"total": 0, "hotspots": []}

    # Add isHotspot to each hotspot for compatibility
    for h in hotspots_data.get("hotspots", []):
        h["isHotspot"] = True

    issues_total = issues_data.get("total", 0)
    hotspots_total = hotspots_data.get("total", 0)

    if args.json:
        combined = {
            "issues": issues_data.get("issues", []) + [{"isHotspot": True, **h} for h in hotspots_data.get("hotspots", [])],
            "total": issues_total + hotspots_total,
            "issuesTotal": issues_total,
            "hotspotsTotal": hotspots_total,
        }
        print(json.dumps(combined, indent=2))
        return

    if args.summary:
        print(formatter.format_summary(
            project_name, project_key, issues_total, hotspots_total,
            coverage_measures, qg_status, dup_components,
        ))
        return

    # 1. Issues section (dedicated)
    print(formatter.format_issues_section(client, {"issues": issues_data.get("issues", [])}))

    # 2. Security Hotspots section (dedicated)
    print(formatter.format_hotspots_section(client, hotspots_data))

    # 3. Code Duplications section
    print(formatter.format_duplications_section(client, dup_components))

    # 4. New Code Test Coverage section (when PR)
    if args.pull_request:
        coverage_tree = client.get_coverage_tree()
        print(formatter.format_coverage_section(client, coverage_tree))

    # 5. Summary section
    if fetch_issues or fetch_hotspots:
        print(formatter.format_summary(
            project_name, project_key, issues_total, hotspots_total,
            coverage_measures, qg_status, dup_components,
        ))


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="""List SonarQube issues, security hotspots, code duplications, and test coverage.

Fetches code quality metrics from SonarQube for the project, with support for
PR-specific analysis, filtering by severity/type/status, and detailed issue reports
including rule descriptions and fix recommendations.""",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s
  %(prog)s --summary
  %(prog)s -pr 42
  %(prog)s --status OPEN
""",
    )
    parser.add_argument(
        "-pr", "--pull-request",
        metavar="number",
        help="Filter issues for a specific pull request",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Fetch all project issues (not PR-specific)",
    )
    parser.add_argument(
        "-s", "--severity",
        metavar="level",
        choices=["BLOCKER", "CRITICAL", "MAJOR", "MINOR", "INFO"],
        help="Filter by severity",
    )
    parser.add_argument(
        "-t", "--type",
        metavar="type",
        choices=["CODE_SMELL", "BUG", "VULNERABILITY", "SECURITY_HOTSPOT"],
        help="Filter by type",
    )
    parser.add_argument(
        "--status",
        metavar="status",
        help="Filter by status (Issues: OPEN, CONFIRMED, REOPENED, RESOLVED, CLOSED; Hotspots: TO_REVIEW, REVIEWED)",
    )
    parser.add_argument(
        "-r", "--rule",
        metavar="ruleKey",
        help="Filter by rule key (e.g., typescript:S6606)",
    )
    parser.add_argument(
        "-k", "--key",
        metavar="issueKey",
        dest="issue_key",
        help="Filter by specific issue key",
    )
    parser.add_argument(
        "-c", "--component",
        metavar="path",
        help="Filter by component (file path, exact match)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output only JSON (no formatted text)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Output only the summary section (coverage, duplications, counts)",
    )
    args = parser.parse_args()

    # Auto-detect PR if not provided and --all is not set
    if not args.pull_request and not args.all:
        detected = auto_detect_pr()
        if detected:
            args.pull_request = detected
            if not args.json:
                try:
                    branch = subprocess.run(
                        ["git", "branch", "--show-current"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    branch_name = branch.stdout.strip() if branch.returncode == 0 else ""
                    print(f"Auto-detected PR #{args.pull_request} from current branch: {branch_name}")
                except (FileNotFoundError, subprocess.SubprocessError):
                    print(f"Auto-detected PR #{args.pull_request}")

    return args


def _resolve_fetch_mode(args: argparse.Namespace) -> tuple:
    """Return (fetch_issues, fetch_hotspots) from args."""
    if args.issue_key or not args.type:
        return True, True
    if args.type == "SECURITY_HOTSPOT":
        return False, True
    return True, False


def _build_filter_message(args: argparse.Namespace, project_key: str) -> list:
    """Return list of filter message parts for console output."""
    if args.issue_key:
        parts = [f"Fetching issue by key: {args.issue_key}"]
        if args.pull_request:
            parts.append(f"PR: {args.pull_request}")
        elif not args.json:
            parts.append("(tip: use -pr <number> if issue is from a PR)")
        return parts
    parts = [f"Fetching issues for project: {project_key}"]
    if args.pull_request:
        parts.append(f"PR: {args.pull_request}")
    if args.status:
        parts.append(f"Status: {args.status}")
    if args.severity:
        parts.append(f"Severity: {args.severity}")
    if args.type:
        parts.append(f"Type: {args.type}")
    if args.rule:
        parts.append(f"Rule: {args.rule}")
    if args.component:
        parts.append(f"Component: {args.component}")
    return parts


def main() -> None:
    """Entry point."""
    args = parse_args()

    sonar_host = os.environ.get("SONAR_HOST_URL", "").rstrip("/") + "/"
    sonar_token = os.environ.get("SONAR_TOKEN", "")

    if not sonar_host or sonar_host == "/":
        sys.exit("Error: SONAR_HOST_URL environment variable is not set")
    if not sonar_token:
        sys.exit("Error: SONAR_TOKEN environment variable is not set")

    project_key = get_project_key()
    fetch_issues, fetch_hotspots = _resolve_fetch_mode(args)
    filter_parts = _build_filter_message(args, project_key)

    if not args.json:
        print(", ".join(filter_parts))

    client = SonarQubeClient(sonar_host, sonar_token, project_key, args)
    formatter = OutputFormatter(args)

    run(
        client=client,
        formatter=formatter,
        project_key=project_key,
        args=args,
        fetch_issues=fetch_issues,
        fetch_hotspots=fetch_hotspots,
    )


if __name__ == "__main__":
    main()
