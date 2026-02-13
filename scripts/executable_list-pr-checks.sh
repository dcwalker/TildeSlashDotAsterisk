#!/bin/bash

# Script to list all status checks for a pull request
# Usage: ./list-pr-checks.sh [OPTIONS]
# Run with -h or --help for full usage information

# Auto-detect repository from git remote
REPO=$(git remote get-url origin 2>/dev/null | sed -E 's/.*github.com[:/]([^/]+)\/([^/]+)(\.git)?$/\1\/\2/' | sed 's/\.git$//')
if [ -z "$REPO" ]; then
  if [ -n "$GITHUB_REPOSITORY" ]; then
    REPO="$GITHUB_REPOSITORY"
  else
    echo "Error: Could not detect repository. Set GITHUB_REPOSITORY environment variable or run from a git repository."
    exit 1
  fi
fi

# Extract owner and repo name
OWNER=$(echo "$REPO" | cut -d'/' -f1)
REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)

# CircleCI project slug format: vcs-type/org/repo (e.g., github/owner/repo)
# Read from catalog-info.yaml (required)
if [ ! -f "catalog-info.yaml" ]; then
  echo "Error: catalog-info.yaml is required but not found." >&2
  echo "       Expected format in catalog-info.yaml:" >&2
  echo "         annotations:" >&2
  echo "           circleci.com/project-slug: github/owner/repo" >&2
  exit 1
fi

CATALOG_SLUG=$(grep -E "^[[:space:]]*circleci\.com/project-slug:" catalog-info.yaml 2>/dev/null | sed 's/.*circleci\.com\/project-slug:[[:space:]]*//' | tr -d '"' | tr -d "'")
if [ -n "$CATALOG_SLUG" ]; then
  PROJECT_SLUG="$CATALOG_SLUG"
else
  echo "Error: catalog-info.yaml exists but does not contain circleci.com/project-slug annotation." >&2
  echo "       Expected format in catalog-info.yaml:" >&2
  echo "         annotations:" >&2
  echo "           circleci.com/project-slug: github/owner/repo" >&2
  exit 1
fi

# Extract vcs-type, org, and repo from project slug
VCS_TYPE=$(echo "$PROJECT_SLUG" | cut -d'/' -f1)
ORG=$(echo "$PROJECT_SLUG" | cut -d'/' -f2)
PROJECT_REPO=$(echo "$PROJECT_SLUG" | cut -d'/' -f3)

PULL_REQUEST=""
WORKFLOW_FILTER=""
JOB_FILTER=""
SHOW_FAILING=""
SHOW_PASSING=""
SHOW_IN_PROGRESS=""
JSON_OUTPUT=""
COUNT_ONLY=""
DETAILS=""
HIDE_JOB_OUTPUT=""
FOLLOW=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -pr|--pull-request)
      PULL_REQUEST="$2"
      shift 2
      ;;
    -w|--workflow)
      WORKFLOW_FILTER="$2"
      shift 2
      ;;
    -j|--job)
      JOB_FILTER="$2"
      shift 2
      ;;
    --show-failing)
      SHOW_FAILING="1"
      shift
      ;;
    --show-passing)
      SHOW_PASSING="1"
      shift
      ;;
    --show-in-progress)
      SHOW_IN_PROGRESS="1"
      shift
      ;;
    --json)
      JSON_OUTPUT="1"
      shift
      ;;
    --count)
      COUNT_ONLY="1"
      shift
      ;;
    --details)
      DETAILS="1"
      shift
      ;;
    --hide-job-output)
      HIDE_JOB_OUTPUT="1"
      shift
      ;;
    -f|--follow)
      FOLLOW="1"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Description:"
      echo "  Lists all status checks for a pull request including CircleCI jobs,"
      echo "  GitHub Actions, and other CI/CD checks. Shows status, duration,"
      echo "  and detailed logs for failed checks. Supports follow mode for"
      echo "  real-time monitoring until all checks complete."
      echo ""
      echo "Options:"
      echo "  -pr, --pull-request <number>  Filter by pull request number (required)"
      echo "  -w, --workflow <name>          Filter by workflow name (CircleCI checks only)"
      echo "  -j, --job <name>              Filter by check/job name"
      echo "  --show-failing                 Filter to show only failing/errored checks (default: show all statuses)"
      echo "  --show-passing                 Filter to show only passing/successful checks (default: show all statuses)"
      echo "  --show-in-progress             Filter to show only in-progress/running checks (default: show all statuses)"
      echo "  --json                         Output only JSON (no formatted text)"
      echo "  --count                        Output only the count of items"
      echo "  --details                      Include detailed information (test failures, step logs, CircleCI only)"
      echo "  --hide-job-output              Hide job output for failed checks (default: show output for failed CircleCI checks)"
      echo "  -f, --follow                   Follow mode: show only summary and update every second until all checks complete"
      echo "  -h, --help                     Show this help message"
      echo ""
      echo "Note: By default, only checks from the most recent pipeline/run are shown (matching GitHub UI)."
      echo ""
      echo "Note: Status filters (--show-failing, --show-passing, --show-in-progress) can be combined."
      echo "      If multiple are specified, checks matching any of the specified statuses will be shown (OR logic)."
      echo ""
      echo "Environment Variables:"
      echo "  CIRCLE_TOKEN                   CircleCI API token (required for CircleCI check details)"
      echo "                                Documentation: https://circleci.com/docs/managing-api-tokens/"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use -h or --help for usage information"
      exit 1
      ;;
  esac
done

# Note: CIRCLE_TOKEN is only required if there are CircleCI checks to enrich
# We'll validate it later when we actually need it

# Auto-detect PR number from current branch if not provided
if [ -z "$PULL_REQUEST" ]; then
  # Try to get PR number from current branch using gh CLI
  if command -v gh &> /dev/null && gh auth status &> /dev/null; then
    DETECTED_PR=$(gh pr view --json number 2>/dev/null | jq -r '.number // empty' 2>/dev/null)
    if [ -n "$DETECTED_PR" ] && [ "$DETECTED_PR" != "null" ] && [ "$DETECTED_PR" != "" ]; then
      PULL_REQUEST="$DETECTED_PR"
      if [ -z "$JSON_OUTPUT" ]; then
        echo "Auto-detected PR #${PULL_REQUEST} from current branch" >&2
      fi
    fi
  fi
fi

# Validate PR number is provided
if [ -z "$PULL_REQUEST" ]; then
  echo "Error: Pull request number is required. Use -pr or --pull-request to specify the PR number."
  echo "       Or run this script from a branch that has an associated pull request."
  echo "Use -h or --help for usage information"
  exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
  echo "Error: jq is not installed. Install it to use this script."
  exit 1
fi

# Check if curl is available
if ! command -v curl &> /dev/null; then
  echo "Error: curl is not installed. Install it to use this script."
  exit 1
fi

# Check if gh CLI is available (for GitHub API)
if ! command -v gh &> /dev/null; then
  echo "Error: GitHub CLI (gh) is not installed or not in PATH"
  echo "Install it from: https://cli.github.com/"
  exit 1
fi

# Check if gh is authenticated
if ! gh auth status &> /dev/null; then
  echo "Error: GitHub CLI is not authenticated."
  if [ -n "$GITHUB_TOKEN" ]; then
    echo ""
    echo "The GITHUB_TOKEN environment variable is set but appears to be invalid or expired."
    echo "To fix this, you can either:"
    echo "  1. Clear the invalid token: unset GITHUB_TOKEN"
    echo "  2. Set a valid token: export GITHUB_TOKEN=your_valid_token"
    echo "  3. Use GitHub CLI credentials: unset GITHUB_TOKEN && gh auth login"
  else
    echo "Run: gh auth login"
  fi
  exit 1
fi

# CircleCI API base URL
CIRCLE_API_BASE="https://circleci.com/api/v2"

# Function to make CircleCI API request
circleci_api_request() {
  local url="$1"
  local response
  response=$(curl -s -H "Circle-Token: ${CIRCLE_TOKEN}" "$url")
  local exit_code=$?
  
  if [ $exit_code -ne 0 ]; then
    echo "Error: Failed to make API request to $url" >&2
    return 1
  fi
  
  # Check for API errors in response
  if echo "$response" | jq -e '.message // .error // empty' >/dev/null 2>&1; then
    local error_msg
    error_msg=$(echo "$response" | jq -r '.message // .error // "Unknown error"')
    echo "Error: CircleCI API returned: $error_msg" >&2
    return 1
  fi
  
  echo "$response"
}

# Function to get PR branch name from GitHub
get_pr_branch() {
  local pr_num="$1"
  
  local branch_info
  branch_info=$(gh api "repos/${REPO}/pulls/${pr_num}" 2>/dev/null | jq -r '.head.ref // empty' 2>/dev/null)
  if [ -n "$branch_info" ] && [ "$branch_info" != "null" ]; then
    echo "$branch_info"
    return 0
  fi
  
  return 1
}

# Function to get all status checks for a PR from GitHub
get_github_status_checks() {
  local pr_num="$1"
  
  # Get PR details to get the head SHA
  local pr_data
  pr_data=$(gh api "repos/${REPO}/pulls/${pr_num}" 2>/dev/null)
  if [ $? -ne 0 ] || [ -z "$pr_data" ]; then
    echo "[]"
    return 0
  fi
  
  local head_sha
  head_sha=$(echo "$pr_data" | jq -r '.head.sha // empty' 2>/dev/null)
  if [ -z "$head_sha" ] || [ "$head_sha" = "null" ]; then
    echo "[]"
    return 0
  fi
  
  # Get check runs for the commit (REST API - more reliable)
  # Use --paginate to get all pages of check runs
  local check_runs
  check_runs=$(gh api --paginate "repos/${REPO}/commits/${head_sha}/check-runs?per_page=100" 2>/dev/null)
  local check_runs_exit=$?
  
  # Get status contexts for the commit (REST API)
  # Note: Status endpoint is not paginated, returns all statuses in one response
  local statuses
  statuses=$(gh api "repos/${REPO}/commits/${head_sha}/status" 2>/dev/null)
  local statuses_exit=$?
  
  local all_checks="[]"
  
  # Process check runs
  # When using --paginate, gh api returns multiple JSON objects (one per page)
  # Each object has a .check_runs array, so we need to collect all of them
  if [ $check_runs_exit -eq 0 ] && [ -n "$check_runs" ]; then
    local runs
    # Collect all check_runs arrays from all pages and flatten into a single array
    runs=$(echo "$check_runs" | jq -s '[.[] | .check_runs[]?] | 
      map({
        name: .name,
        status: (if .status == "completed" then (.conclusion | ascii_downcase) else (.status | ascii_downcase) end),
        conclusion: (.conclusion // "" | ascii_downcase),
        description: (.output.summary // .app.name // "Unknown"),
        html_url: .html_url,
        started_at: .started_at,
        completed_at: .completed_at,
        context: .name,
        check_run_id: .id,
        is_circleci: ((.app.slug // .app.name // "") | test("circleci"; "i")),
        is_codeql: ((.name | test("^CodeQL$"; "i")) or ((.app.name // "") | test("^CodeQL$"; "i"))),
        type: "check_run"
      })
    ' 2>/dev/null)
    
    if [ -n "$runs" ] && [ "$runs" != "null" ] && [ "$runs" != "[]" ]; then
      all_checks=$(echo "$all_checks" | jq --argjson runs "$runs" '. + $runs' 2>/dev/null || echo "$all_checks")
    fi
  fi
  
  # Process status contexts
  # Status endpoint returns a single object with a .statuses array
  if [ $statuses_exit -eq 0 ] && [ -n "$statuses" ]; then
    local contexts
    # Extract statuses array and map to our format
    contexts=$(echo "$statuses" | jq -r '
      .statuses[]? | {
        name: .context,
        status: (.state | ascii_downcase),
        conclusion: (.state | ascii_downcase),
        description: (.description // ""),
        html_url: .target_url,
        started_at: null,
        completed_at: null,
        context: .context,
        check_run_id: null,
        is_circleci: (.context | test("circleci"; "i")),
        is_codeql: false,
        type: "status"
      }
    ' 2>/dev/null | jq -s '.' 2>/dev/null)
    
    if [ -n "$contexts" ] && [ "$contexts" != "null" ] && [ "$contexts" != "[]" ]; then
      all_checks=$(echo "$all_checks" | jq --argjson contexts "$contexts" '. + $contexts' 2>/dev/null || echo "$all_checks")
    fi
  fi
  
  # Remove duplicates (same context/name) - prefer check_runs over status contexts
  all_checks=$(echo "$all_checks" | jq '
    group_by(.context) |
    map(
      # If multiple entries for same context, prefer check_run over status
      (sort_by(.type == "status") | .[0])
    )
  ' 2>/dev/null || echo "$all_checks")
  
  
  if [ -z "$all_checks" ] || [ "$all_checks" = "null" ]; then
    echo "[]"
  else
    echo "$all_checks"
  fi
}

# Function to get all pipelines for a PR (handling pagination)
get_pipelines_for_pr() {
  local pr_num="$1"
  local all_pipelines="[]"
  local page_token=""
  
  # Get the actual branch name from GitHub PR
  local actual_branch=""
  actual_branch=$(get_pr_branch "$pr_num")
  
  # Build list of branch formats to try
  local branch_formats=()
  
  # Add actual branch name if we got it
  if [ -n "$actual_branch" ] && [ "$actual_branch" != "null" ]; then
    branch_formats+=("$actual_branch")
  fi
  
  # Add standard PR branch formats
  branch_formats+=("pull/${pr_num}/head" "pull/${pr_num}/merge")
  
  # Try each branch format
  for branch_format in "${branch_formats[@]}"; do
    local url="${CIRCLE_API_BASE}/project/${PROJECT_SLUG}/pipeline?branch=${branch_format}"
    page_token=""
    
    while true; do
      local request_url="$url"
      if [ -n "$page_token" ]; then
        # Check if URL already has query params
        if echo "$request_url" | grep -q "?"; then
          request_url="${request_url}&page-token=${page_token}"
        else
          request_url="${request_url}?page-token=${page_token}"
        fi
      fi
      
      local response
      response=$(circleci_api_request "$request_url" 2>/dev/null)
      if [ $? -ne 0 ]; then
        break
      fi
      
      # Check if response is valid JSON
      if ! echo "$response" | jq empty 2>/dev/null; then
        break
      fi
      
      local pipelines
      pipelines=$(echo "$response" | jq -r '.items // []' 2>/dev/null)
      if [ -z "$pipelines" ] || [ "$pipelines" = "null" ] || [ "$pipelines" = "[]" ]; then
        break
      fi
      
      # Merge pipelines into all_pipelines array
      all_pipelines=$(echo "$all_pipelines" | jq --argjson new "$pipelines" '. + $new' 2>/dev/null || echo "$all_pipelines")
      
      # Check for next page token
      page_token=$(echo "$response" | jq -r '.next_page_token // empty' 2>/dev/null)
      if [ -z "$page_token" ] || [ "$page_token" = "null" ]; then
        break
      fi
    done
    
    # If we found pipelines, we can stop trying other formats
    local found_count
    found_count=$(echo "$all_pipelines" | jq 'length' 2>/dev/null || echo "0")
    if [ "$found_count" -gt 0 ]; then
      break
    fi
  done
  
  echo "$all_pipelines"
}

# Function to get workflows for a pipeline
get_workflows_for_pipeline() {
  local pipeline_id="$1"
  local url="${CIRCLE_API_BASE}/pipeline/${pipeline_id}/workflow"
  local all_workflows="[]"
  local page_token=""
  
  while true; do
    local request_url="$url"
    if [ -n "$page_token" ]; then
      request_url="${url}?page-token=${page_token}"
    fi
    
    local response
    response=$(circleci_api_request "$request_url")
    if [ $? -ne 0 ]; then
      break
    fi
    
    local workflows
    workflows=$(echo "$response" | jq -r '.items // []' 2>/dev/null)
    if [ -z "$workflows" ] || [ "$workflows" = "null" ] || [ "$workflows" = "[]" ]; then
      break
    fi
    
    # Merge workflows into all_workflows array
    all_workflows=$(echo "$all_workflows" | jq --argjson new "$workflows" '. + $new' 2>/dev/null || echo "$all_workflows")
    
    # Check for next page token
    page_token=$(echo "$response" | jq -r '.next_page_token // empty' 2>/dev/null)
    if [ -z "$page_token" ] || [ "$page_token" = "null" ]; then
      break
    fi
  done
  
  echo "$all_workflows"
}

# Function to get jobs for a workflow
get_jobs_for_workflow() {
  local workflow_id="$1"
  local url="${CIRCLE_API_BASE}/workflow/${workflow_id}/job"
  local all_jobs="[]"
  local page_token=""
  
  while true; do
    local request_url="$url"
    if [ -n "$page_token" ]; then
      request_url="${url}?page-token=${page_token}"
    fi
    
    local response
    response=$(circleci_api_request "$request_url")
    if [ $? -ne 0 ]; then
      break
    fi
    
    local jobs
    jobs=$(echo "$response" | jq -r '.items // []' 2>/dev/null)
    if [ -z "$jobs" ] || [ "$jobs" = "null" ] || [ "$jobs" = "[]" ]; then
      break
    fi
    
    # Merge jobs into all_jobs array
    all_jobs=$(echo "$all_jobs" | jq --argjson new "$jobs" '. + $new' 2>/dev/null || echo "$all_jobs")
    
    # Check for next page token
    page_token=$(echo "$response" | jq -r '.next_page_token // empty' 2>/dev/null)
    if [ -z "$page_token" ] || [ "$page_token" = "null" ]; then
      break
    fi
  done
  
  echo "$all_jobs"
}

# Function to get job details (v2 API)
get_job_details() {
  local job_number="$1"
  local url="${CIRCLE_API_BASE}/project/${PROJECT_SLUG}/job/${job_number}"
  circleci_api_request "$url"
}

# Function to get test metadata for a job (v2 API)
get_job_tests() {
  local job_number="$1"
  local url="${CIRCLE_API_BASE}/project/${PROJECT_SLUG}/${job_number}/tests"
  circleci_api_request "$url"
}

# Function to get job details with steps/actions from v1.1 API
# Note: v1.1 API is needed here to get steps/actions with output_url (v2 doesn't provide this)
# v1.1 API uses "github" not "gh" as the vcs-type
get_job_with_steps_v1() {
  local job_number="$1"
  
  # Convert project slug from v2 format (gh/org/repo or github/org/repo) to v1.1 format (github/org/repo)
  local v1_project_slug
  if echo "$PROJECT_SLUG" | grep -q "^gh/"; then
    v1_project_slug=$(echo "$PROJECT_SLUG" | sed 's|^gh/|github/|')
  else
    v1_project_slug="$PROJECT_SLUG"
  fi
  
  local url="https://circleci.com/api/v1.1/project/${v1_project_slug}/${job_number}"
  local response
  local http_code
  
  # Get response and HTTP status code
  response=$(curl -s -w "\nHTTP_CODE:%{http_code}" -H "Circle-Token: ${CIRCLE_TOKEN}" "$url" 2>/dev/null)
  http_code=$(echo "$response" | grep "HTTP_CODE:" | cut -d: -f2)
  response=$(echo "$response" | sed '/HTTP_CODE:/d')
  
  # Check if request failed or returned error status
  if [ -z "$http_code" ] || [ "$http_code" != "200" ]; then
    return 1
  fi
  
  # Check for API errors in JSON response
  if echo "$response" | jq -e '.message // .error // empty' >/dev/null 2>&1; then
    return 1
  fi
  
  echo "$response"
}

# Function to download and extract log content from S3 URL
download_log_from_url() {
  local output_url="$1"
  if [ -z "$output_url" ] || [ "$output_url" = "null" ] || [ "$output_url" = "" ]; then
    return 1
  fi
  
  # Download the log file from S3 (requires Circle-Token for authentication)
  curl -s -H "Circle-Token: ${CIRCLE_TOKEN}" "$output_url" 2>/dev/null
}

# Function to format log content from JSON array format
# The log content is a JSON array with objects containing "message", "time", "type", "truncated"
format_log_output() {
  local log_content="$1"
  if [ -z "$log_content" ]; then
    return 1
  fi
  
  # Check if it's a JSON array
  if ! echo "$log_content" | jq -e 'type == "array"' >/dev/null 2>&1; then
    # Not JSON, return as-is
    echo "$log_content"
    return 0
  fi
  
  # Extract messages from JSON array, preserving order
  # jq -r will decode Unicode escape sequences (\u001b, \r, etc.) and output raw text
  # Then strip ANSI escape codes and control characters for cleaner output
  echo "$log_content" | jq -r '.[]? | select(.message != null and .message != "") | .message' 2>/dev/null | \
    while IFS= read -r line || [ -n "$line" ]; do
      # Remove carriage returns
      line=$(echo "$line" | tr -d '\r')
      # Remove ANSI escape codes (color codes, cursor movement, etc.)
      # This regex handles: \x1b[ followed by numbers/semicolons and ending with a letter
      line=$(echo "$line" | sed 's/\x1b\[[0-9;]*[a-zA-Z]//g')
      # Remove other common ANSI codes
      line=$(echo "$line" | sed 's/\x1b\[K//g' | sed 's/\x1b\[2K//g' | sed 's/\x1b\[1G//g' | sed 's/\x1b\[0K//g')
      # Only print non-empty lines
      if [ -n "$line" ]; then
        echo "$line"
      fi
    done
}

# Function to get check run annotations from GitHub API
get_check_run_annotations() {
  local check_run_id="$1"
  if [ -z "$check_run_id" ] || [ "$check_run_id" = "null" ] || [ "$check_run_id" = "" ]; then
    echo "[]"
    return 1
  fi
  
  # Fetch annotations with pagination support (--paginate handles all pages automatically)
  local annotations
  annotations=$(gh api --paginate "repos/${REPO}/check-runs/${check_run_id}/annotations?per_page=100" 2>/dev/null)
  local exit_code=$?
  
  if [ $exit_code -ne 0 ] || [ -z "$annotations" ]; then
    echo "[]"
    return 1
  fi
  
  # Check if it's a JSON array
  if ! echo "$annotations" | jq -e 'type == "array"' >/dev/null 2>&1; then
    echo "[]"
    return 1
  fi
  
  echo "$annotations"
}

# Function to query recent pipelines as fallback (when branch-based query fails)
get_recent_pipelines() {
  local url="${CIRCLE_API_BASE}/project/${PROJECT_SLUG}/pipeline?page-size=50"
  local all_pipelines="[]"
  local page_token=""
  
  # Get first page of recent pipelines
  while true; do
    local request_url="$url"
    if [ -n "$page_token" ]; then
      if echo "$request_url" | grep -q "?"; then
        request_url="${request_url}&page-token=${page_token}"
      else
        request_url="${request_url}?page-token=${page_token}"
      fi
    fi
    
    local response
    response=$(circleci_api_request "$request_url" 2>/dev/null)
    if [ $? -ne 0 ]; then
      break
    fi
    
    if ! echo "$response" | jq empty 2>/dev/null; then
      break
    fi
    
    local pipelines
    pipelines=$(echo "$response" | jq -r '.items // []' 2>/dev/null)
    if [ -z "$pipelines" ] || [ "$pipelines" = "null" ] || [ "$pipelines" = "[]" ]; then
      break
    fi
    
    # Filter pipelines that might be related to this PR by checking branch name or vcs metadata
    # We'll check if the branch contains the PR number or matches PR branch patterns
    local filtered
    filtered=$(echo "$pipelines" | jq --arg pr "$PULL_REQUEST" '
      [.[] | 
        select(
          (.vcs.branch // "" | test("pull/" + $pr + "/"; "")) or
          (.vcs.branch // "" | test("pr/" + $pr; "")) or
          (.vcs.branch // "" | test("/" + $pr + "/"; "")) or
          (.vcs.branch // "" | test("^" + $pr + "-"; "")) or
          (.vcs.branch // "" | test("-" + $pr + "-"; "")) or
          (.vcs.branch // "" | test("-" + $pr + "$"; ""))
        )
      ]
    ' 2>/dev/null || echo "[]")
    
    if [ -n "$filtered" ] && [ "$filtered" != "null" ] && [ "$filtered" != "[]" ]; then
      all_pipelines=$(echo "$all_pipelines" | jq --argjson new "$filtered" '. + $new' 2>/dev/null || echo "$all_pipelines")
    fi
    
    # Only check first page for performance
    break
  done
  
  echo "$all_pipelines"
}

# Function to fetch checks and display summary (for follow mode)
fetch_and_display_summary() {
  local is_update="$1"  # "1" if updating in-place, "0" if first display
  local is_first="$2"   # "true" if first iteration, "false" otherwise
  
  # Generate timestamp for when status was last refreshed
  local timestamp
  timestamp=$(date '+%b %d, %Y %H:%M:%S')
  
  # Get all status checks from GitHub (fetch data BEFORE clearing screen)
  local github_checks
  github_checks=$(get_github_status_checks "$PULL_REQUEST")
  
  # Ensure we have valid JSON
  if ! echo "$github_checks" | jq empty 2>/dev/null; then
    github_checks="[]"
  fi
  
  local check_count
  check_count=$(echo "$github_checks" | jq 'length // 0' 2>/dev/null || echo "0")
  
  # Ensure CHECK_COUNT is numeric
  if ! [[ "$check_count" =~ ^[0-9]+$ ]]; then
    check_count=0
  fi
  
  if [ "$check_count" -eq 0 ]; then
    if [ -z "$JSON_OUTPUT" ]; then
      if [ "$is_update" = "1" ]; then
        printf "\033[8A\033[0J"  # Clear previous output
      fi
      echo "No status checks found for PR #${PULL_REQUEST}"
    fi
    return 1
  fi
  
  # For CircleCI checks, enrich with CircleCI API data
  local circle_jobs_map="{}"
  local pipeline_errors_map="{}"
  if echo "$github_checks" | jq '[.[] | select(.is_circleci == true)] | length' 2>/dev/null | grep -q '[1-9]'; then
    # We have CircleCI checks, validate CIRCLE_TOKEN is set
    if [ -z "$CIRCLE_TOKEN" ]; then
      echo "Error: CIRCLE_TOKEN environment variable is not set (required for CircleCI check details)"
      echo ""
      echo "Documentation: https://circleci.com/docs/managing-api-tokens/"
      return 1
    fi
    
    # We have CircleCI checks, fetch pipeline data
    local pipelines
    pipelines=$(get_pipelines_for_pr "$PULL_REQUEST")
    local pipeline_count
    pipeline_count=$(echo "$pipelines" | jq 'length' 2>/dev/null || echo "0")
    
    if [ "$pipeline_count" -gt 0 ]; then
      # Filter to latest pipeline
      pipelines=$(echo "$pipelines" | jq 'sort_by(.created_at // "") | reverse | .[0:1]' 2>/dev/null || echo "$pipelines")
      local pipeline_ids
      pipeline_ids=$(echo "$pipelines" | jq -r '.[].id' 2>/dev/null)
      
      for pipeline_id in $pipeline_ids; do
        if [ -z "$pipeline_id" ] || [ "$pipeline_id" = "null" ]; then
          continue
        fi
        
        local pipeline_number
        pipeline_number=$(echo "$pipelines" | jq -r --arg id "$pipeline_id" '.[] | select(.id == $id) | .number // "N/A"' 2>/dev/null)
        local pipeline_created
        pipeline_created=$(echo "$pipelines" | jq -r --arg id "$pipeline_id" '.[] | select(.id == $id) | .created_at // "N/A"' 2>/dev/null)
        local pipeline_vcs_branch
        pipeline_vcs_branch=$(echo "$pipelines" | jq -r --arg id "$pipeline_id" '.[] | select(.id == $id) | .vcs.branch // "N/A"' 2>/dev/null)
        
        # Extract pipeline errors if any
        local pipeline_errors
        pipeline_errors=$(echo "$pipelines" | jq -r --arg id "$pipeline_id" '.[] | select(.id == $id) | .errors // []' 2>/dev/null)
        if [ -n "$pipeline_errors" ] && [ "$pipeline_errors" != "null" ] && [ "$pipeline_errors" != "[]" ]; then
          if [ "$pipeline_number" != "N/A" ] && [ "$pipeline_number" != "null" ]; then
            pipeline_errors_map=$(echo "$pipeline_errors_map" | jq --arg pipeline_number "$pipeline_number" --argjson errors "$pipeline_errors" '.[$pipeline_number] = $errors' 2>/dev/null || echo "$pipeline_errors_map")
          fi
        fi
        
        local workflows
        workflows=$(get_workflows_for_pipeline "$pipeline_id")
        local workflow_ids
        workflow_ids=$(echo "$workflows" | jq -r '.[].id' 2>/dev/null)
        
        for workflow_id in $workflow_ids; do
          if [ -z "$workflow_id" ] || [ "$workflow_id" = "null" ]; then
            continue
          fi
        
          local workflow_name
          workflow_name=$(echo "$workflows" | jq -r --arg id "$workflow_id" '.[] | select(.id == $id) | .name' 2>/dev/null)
          local jobs
          jobs=$(get_jobs_for_workflow "$workflow_id")
          
          # Create a map of job name -> job data for quick lookup
          local jobs_map
          jobs_map=$(echo "$jobs" | jq --arg workflow_name "$workflow_name" --arg pipeline_number "$pipeline_number" --arg pipeline_created "$pipeline_created" --arg pipeline_branch "$pipeline_vcs_branch" '
            reduce .[] as $job ({}; .[$job.name] = ($job + {
              workflow_name: $workflow_name,
              pipeline_number: ($pipeline_number | if . == "N/A" then null else . end),
              pipeline_created_at: ($pipeline_created | if . == "N/A" then null else . end),
              pipeline_branch: ($pipeline_branch | if . == "N/A" then null else . end)
            }))
          ' 2>/dev/null || echo "{}")
          
          # Merge into CIRCLE_JOBS_MAP
          circle_jobs_map=$(echo "$circle_jobs_map" | jq --argjson jobs "$jobs_map" '. + $jobs' 2>/dev/null || echo "$circle_jobs_map")
        done
      done
    fi
  fi
  
  # Enrich GitHub checks with CircleCI data where applicable
  local all_checks
  all_checks=$(echo "$github_checks" | jq --argjson circle_jobs "$circle_jobs_map" --argjson pipeline_errors "$pipeline_errors_map" '
    map(
      . as $check |
      if $check.is_circleci == true then
        # Extract job name from context (e.g., "ci/circleci: job_name" -> "job_name")
        ($check.context | split(": ") | if length > 1 then .[1] else $check.context end) as $job_name |
        ($circle_jobs[$job_name] // {}) as $circle_job |
        ($circle_job.pipeline_number // null) as $pipeline_num |
        # If no pipeline number from job, try to get first pipeline number from errors map
        (if $pipeline_num == null then ($pipeline_errors | keys | if length > 0 then .[0] else null end) else ($pipeline_num | tostring) end) as $pipeline_key |
        ($pipeline_errors[$pipeline_key] // null) as $errors |
        $check + {
          job_number: $circle_job.job_number,
          workflow_name: $circle_job.workflow_name,
          pipeline_number: ($circle_job.pipeline_number // (if $pipeline_key != null then ($pipeline_key | tonumber) else null end)),
          pipeline_created_at: $circle_job.pipeline_created_at,
          pipeline_branch: $circle_job.pipeline_branch,
          pipeline_errors: $errors,
          started_at: ($circle_job.started_at // $check.started_at),
          stopped_at: ($circle_job.stopped_at // $check.completed_at)
        }
      else
        $check
      end
    )
  ' 2>/dev/null || echo "$github_checks")
  
  # Find expected CircleCI jobs (jobs in workflow but no check run yet)
  if [ -n "$circle_jobs_map" ] && [ "$circle_jobs_map" != "{}" ] && [ "$circle_jobs_map" != "null" ]; then
    # Get list of job names from CircleCI workflow
    local workflow_job_names
    workflow_job_names=$(echo "$circle_jobs_map" | jq -r 'keys[]' 2>/dev/null)
    
    # Get list of existing CircleCI check names from GitHub
    local existing_check_names
    existing_check_names=$(echo "$all_checks" | jq -r '.[] | select(.is_circleci == true) | (.context | split(": ") | if length > 1 then .[1] else .context end)' 2>/dev/null)
    
    # Find missing jobs (in workflow but not in GitHub checks)
    for job_name in $workflow_job_names; do
      if [ -z "$job_name" ] || [ "$job_name" = "null" ]; then
        continue
      fi
      
      # Check if this job already has a check run
      if ! echo "$existing_check_names" | grep -q "^${job_name}$"; then
        # This job is expected - create an expected check entry
        local job_data
        job_data=$(echo "$circle_jobs_map" | jq --arg job "$job_name" '.[$job] // {}' 2>/dev/null)
        
        local expected_check
        expected_check=$(jq -n \
          --arg name "ci/circleci: $job_name" \
          --arg workflow "$(echo "$job_data" | jq -r '.workflow_name // ""' 2>/dev/null)" \
          --arg pipeline "$(echo "$job_data" | jq -r '.pipeline_number // ""' 2>/dev/null)" \
          --arg created "$(echo "$job_data" | jq -r '.pipeline_created_at // ""' 2>/dev/null)" \
          --arg branch "$(echo "$job_data" | jq -r '.pipeline_branch // ""' 2>/dev/null)" \
          '{
            name: $name,
            status: "pending",
            conclusion: "pending",
            description: "Expected — Waiting for status to be reported",
            html_url: null,
            started_at: null,
            completed_at: null,
            context: $name,
            is_circleci: true,
            type: "expected",
            workflow_name: (if $workflow != "" then $workflow else null end),
            pipeline_number: (if $pipeline != "" then $pipeline else null end),
            pipeline_created_at: (if $created != "" then $created else null end),
            pipeline_branch: (if $branch != "" then $branch else null end)
          }' 2>/dev/null)
        
        if [ -n "$expected_check" ]; then
          all_checks=$(echo "$all_checks" | jq --argjson expected "$expected_check" '. + [$expected]' 2>/dev/null || echo "$all_checks")
        fi
      fi
    done
  fi
  
  # Apply filters
  local filtered_checks="$all_checks"
  
  # Apply job/check name filter
  if [ -n "$JOB_FILTER" ]; then
    filtered_checks=$(echo "$filtered_checks" | jq --arg filter "$JOB_FILTER" '[.[] | select(.name == $filter or .context == $filter or (.context | contains($filter)))]' 2>/dev/null || echo "$filtered_checks")
  fi
  
  # Apply workflow filter (only applies to CircleCI checks)
  if [ -n "$WORKFLOW_FILTER" ]; then
    filtered_checks=$(echo "$filtered_checks" | jq --arg filter "$WORKFLOW_FILTER" '[.[] | select(.is_circleci != true or .workflow_name == $filter)]' 2>/dev/null || echo "$filtered_checks")
  fi
  
  # Apply status filters (OR logic - if multiple are specified, show checks matching any)
  # Map GitHub status values to our filter values
  if [ -n "$SHOW_FAILING" ] || [ -n "$SHOW_PASSING" ] || [ -n "$SHOW_IN_PROGRESS" ]; then
    local status_filter_parts=()
    
    if [ -n "$SHOW_FAILING" ]; then
      status_filter_parts+=("failed|error|failure")
    fi
    
    if [ -n "$SHOW_PASSING" ]; then
      status_filter_parts+=("success|successful")
    fi
    
    if [ -n "$SHOW_IN_PROGRESS" ]; then
      status_filter_parts+=("running|pending|in_progress|queued|in_progress|waiting")
    fi
    
    # Join all filter parts with |
    local status_filter
    status_filter=$(IFS='|'; echo "${status_filter_parts[*]}")
    
    # Filter checks by status (case-insensitive)
    filtered_checks=$(echo "$filtered_checks" | jq --arg filter "$status_filter" '
      [.[] | select(.status | ascii_downcase | test($filter; "i"))]
    ' 2>/dev/null || echo "$filtered_checks")
  fi
  
  # Calculate summary counts
  local failing_count
  failing_count=$(echo "$filtered_checks" | jq '[.[] | select(.status | ascii_downcase | test("failure|failed|error"; "i"))] | length' 2>/dev/null || echo "0")
  local expected_count
  expected_count=$(echo "$filtered_checks" | jq '[.[] | select((.type | ascii_downcase) == "expected")] | length' 2>/dev/null || echo "0")
  local pending_count
  pending_count=$(echo "$filtered_checks" | jq '[.[] | select((.status | ascii_downcase | test("pending|queued|waiting"; "i")) and ((.type | ascii_downcase) != "expected"))] | length' 2>/dev/null || echo "0")
  local success_count
  success_count=$(echo "$filtered_checks" | jq '[.[] | select(.status | ascii_downcase | test("success|successful"; "i"))] | length' 2>/dev/null || echo "0")
  local in_progress_count
  in_progress_count=$(echo "$filtered_checks" | jq '[.[] | select(.status | ascii_downcase | test("in_progress|running|inprogress"; "i"))] | length' 2>/dev/null || echo "0")
  local neutral_count
  neutral_count=$(echo "$filtered_checks" | jq '[.[] | select(.status | ascii_downcase | test("neutral|cancelled|canceled|skipped"; "i"))] | length' 2>/dev/null || echo "0")
  local unknown_count
  unknown_count=$(echo "$filtered_checks" | jq '[.[] | 
    (.type | ascii_downcase) as $type |
    (.status | ascii_downcase) as $status |
    select(
      ($type != "expected") and
      ($status | test("success|successful|failure|failed|error|pending|queued|waiting|in_progress|running|inprogress|neutral|cancelled|canceled|skipped"; "i") | not)
    )
  ] | length' 2>/dev/null || echo "0")
  
  # Ensure counts are numeric
  if ! [[ "$failing_count" =~ ^[0-9]+$ ]]; then
    failing_count=0
  fi
  if ! [[ "$expected_count" =~ ^[0-9]+$ ]]; then
    expected_count=0
  fi
  if ! [[ "$pending_count" =~ ^[0-9]+$ ]]; then
    pending_count=0
  fi
  if ! [[ "$success_count" =~ ^[0-9]+$ ]]; then
    success_count=0
  fi
  if ! [[ "$in_progress_count" =~ ^[0-9]+$ ]]; then
    in_progress_count=0
  fi
  if ! [[ "$neutral_count" =~ ^[0-9]+$ ]]; then
    neutral_count=0
  fi
  if ! [[ "$unknown_count" =~ ^[0-9]+$ ]]; then
    unknown_count=0
  fi
  
  # Build status key lines with only statuses that have counts > 0
  local status_key_lines=()
  if [ "$success_count" -gt 0 ]; then
    status_key_lines+=("🟢 Success ($success_count)")
  fi
  if [ "$in_progress_count" -gt 0 ] || [ "$expected_count" -gt 0 ]; then
    local total_in_progress=$((in_progress_count + expected_count))
    status_key_lines+=("🟠 In Progress/Expected ($total_in_progress)")
  fi
  if [ "$failing_count" -gt 0 ]; then
    status_key_lines+=("🔴 Failed ($failing_count)")
  fi
  if [ "$pending_count" -gt 0 ]; then
    status_key_lines+=("🟡 Pending ($pending_count)")
  fi
  if [ "$neutral_count" -gt 0 ]; then
    status_key_lines+=("⚪ Neutral/Cancelled ($neutral_count)")
  fi
  if [ "$unknown_count" -gt 0 ]; then
    status_key_lines+=("⚫ Unknown ($unknown_count)")
  fi
  
  # Get last commit SHA and summary from origin (via GitHub API) BEFORE clearing screen
  # Always fetch commit data for consistent line count
  local pr_data
  pr_data=$(gh api "repos/${REPO}/pulls/${PULL_REQUEST}" 2>/dev/null)
  local head_sha=""
  local short_sha=""
  local commit_summary=""
  
  if [ $? -eq 0 ] && [ -n "$pr_data" ]; then
    head_sha=$(echo "$pr_data" | jq -r '.head.sha // empty' 2>/dev/null)
    if [ -n "$head_sha" ] && [ "$head_sha" != "null" ] && [ "$head_sha" != "" ]; then
      # Get short SHA (first 7 characters)
      short_sha=$(echo "$head_sha" | cut -c1-7)
      
      # Get commit message summary (first line) from GitHub API
      local commit_data
      commit_data=$(gh api "repos/${REPO}/commits/${head_sha}" 2>/dev/null)
      if [ $? -eq 0 ] && [ -n "$commit_data" ]; then
        commit_summary=$(echo "$commit_data" | jq -r '.commit.message // ""' 2>/dev/null | head -n1 | sed 's/\r$//')
      fi
    fi
  fi
  
  # Build summary text BEFORE clearing screen - list each check with its status emoji
  local summary_lines
  summary_lines=$(echo "$filtered_checks" | jq -r '.[] | 
    (.type | ascii_downcase) as $type |
    (.status | ascii_downcase) as $status |
    (if $type == "expected" then "🟠"
     elif $status == "success" or $status == "successful" then "🟢"
     elif $status == "failure" or $status == "failed" or $status == "error" then "🔴"
     elif $status == "pending" or $status == "queued" or $status == "waiting" then "🟡"
     elif $status == "in_progress" or $status == "running" or $status == "inprogress" then "🟠"
     elif $status == "neutral" or $status == "cancelled" or $status == "canceled" or $status == "skipped" then "⚪"
     else "⚫" end) as $emoji |
    "\($emoji)  Check: \(.name // .context // "N/A")"
  ' 2>/dev/null)
  
  local summary_text=""
  if [ -n "$summary_lines" ] && [ "$summary_lines" != "" ]; then
    summary_text="$summary_lines"
  else
    summary_text="No checks found"
  fi
  
  # Now that we have ALL data ready (checks, counts, commit info), clear and display
  if [ "$is_update" = "1" ]; then
    # Restore cursor to saved position (start of our output area) and clear from there to end of screen
    printf "\033[u\033[0J"  # Restore cursor position and clear from cursor to end of screen
  elif [ "$is_first" = true ]; then
    # Save cursor position at start of output (after any initial messages)
    printf "\033[s"  # Save cursor position
  fi
  
  # Display summary (all data is now ready, print everything at once)
  # \033[2K clears the entire line (both before and after cursor)
  if [ "$is_update" = "1" ]; then
    # Print all lines at once, clearing each line first
    printf "\033[2K\rSummary:\n"
    # Print each check on its own line
    echo "$summary_text" | while IFS= read -r line || [ -n "$line" ]; do
      if [ -n "$line" ]; then
        printf "\033[2K\r%s\n" "$line"
      fi
    done
    # Print status key if there are any statuses to show
    if [ ${#status_key_lines[@]} -gt 0 ]; then
      printf "\033[2K\r\n"
      for key_line in "${status_key_lines[@]}"; do
        printf "\033[2K\r  %s\n" "$key_line"
      done
    fi
    printf "\033[2K\r\n"
    printf "\033[2K\rLast commit:\n"
    if [ -n "$short_sha" ] && [ "$short_sha" != "" ]; then
      if [ -n "$commit_summary" ] && [ "$commit_summary" != "" ] && [ "$commit_summary" != "null" ]; then
        printf "\033[2K\r  %s - %s\n" "$short_sha" "$commit_summary"
      else
        printf "\033[2K\r  %s\n" "$short_sha"
      fi
    else
      printf "\033[2K\r  (no commit info)\n"
    fi
    printf "\033[2K\r\n"
    # Show PR link
    printf "\033[2K\rPR: https://github.com/${REPO}/pull/${PULL_REQUEST}\n"
    # Show timestamp on its own line at the end of output
    printf "\033[2K\rStatus last updated: %s\n" "$timestamp"
  else
    echo "Summary:"
    # Print each check on its own line
    echo "$summary_text"
    # Print status key if there are any statuses to show
    if [ ${#status_key_lines[@]} -gt 0 ]; then
      echo ""
      for key_line in "${status_key_lines[@]}"; do
        echo "  $key_line"
      done
    fi
    echo ""
    echo "Last commit:"
    if [ -n "$short_sha" ] && [ "$short_sha" != "" ]; then
      if [ -n "$commit_summary" ] && [ "$commit_summary" != "" ] && [ "$commit_summary" != "null" ]; then
        echo "  ${short_sha} - ${commit_summary}"
      else
        echo "  ${short_sha}"
      fi
    else
      echo "  (no commit info)"
    fi
    echo ""
    # Show PR link
    echo "PR: https://github.com/${REPO}/pull/${PULL_REQUEST}"
    # Show timestamp on its own line at the end of output
    echo "Status last updated: $timestamp"
  fi
  
  # Return 0 if all checks are complete (ignored in follow mode, which runs until user interrupts)
  if [ "$pending_count" -eq 0 ] && [ "$in_progress_count" -eq 0 ]; then
    return 0
  else
    return 1
  fi
}

# Main execution
if [ -z "$JSON_OUTPUT" ] && [ -z "$FOLLOW" ]; then
  echo "Fetching status checks for PR #${PULL_REQUEST}..."
fi

# Get all status checks from GitHub
GITHUB_CHECKS=$(get_github_status_checks "$PULL_REQUEST")

# Ensure we have valid JSON
if ! echo "$GITHUB_CHECKS" | jq empty 2>/dev/null; then
  GITHUB_CHECKS="[]"
fi

CHECK_COUNT=$(echo "$GITHUB_CHECKS" | jq 'length // 0' 2>/dev/null || echo "0")

# Ensure CHECK_COUNT is numeric
if ! [[ "$CHECK_COUNT" =~ ^[0-9]+$ ]]; then
  CHECK_COUNT=0
fi

if [ "$CHECK_COUNT" -eq 0 ]; then
  if [ -z "$JSON_OUTPUT" ]; then
    echo "No status checks found for PR #${PULL_REQUEST}"
  else
    echo '{"checks": []}'
  fi
  exit 0
fi

# Handle follow mode
if [ -n "$FOLLOW" ]; then
  # Follow mode is incompatible with JSON output and count-only mode
  if [ -n "$JSON_OUTPUT" ] || [ -n "$COUNT_ONLY" ]; then
    echo "Error: --follow cannot be used with --json or --count options"
    exit 1
  fi
  
  # Exit on first Ctrl+C (SIGINT) instead of continuing the loop
  trap 'exit 130' INT
  
  # Loop indefinitely, updating every second until user interrupts (Ctrl+C)
  FIRST_ITERATION=true
  while true; do
    is_update="0"
    if [ "$FIRST_ITERATION" != true ]; then
      is_update="1"
    fi
    
    fetch_and_display_summary "$is_update" "$([ "$FIRST_ITERATION" = true ] && echo "true" || echo "false")"
    
    FIRST_ITERATION=false
    sleep 1
  done
  
  exit 0
fi

# Only print "Found" message if not in follow mode
if [ -z "$JSON_OUTPUT" ] && [ -z "$FOLLOW" ]; then
  echo "Found $CHECK_COUNT status check(s)"
fi

# For CircleCI checks, enrich with CircleCI API data
# Get CircleCI pipelines to match jobs
CIRCLE_JOBS_MAP="{}"
PIPELINE_ERRORS_MAP="{}"
if echo "$GITHUB_CHECKS" | jq '[.[] | select(.is_circleci == true)] | length' 2>/dev/null | grep -q '[1-9]'; then
  # We have CircleCI checks, validate CIRCLE_TOKEN is set
  if [ -z "$CIRCLE_TOKEN" ]; then
    echo "Error: CIRCLE_TOKEN environment variable is not set (required for CircleCI check details)"
    echo ""
    echo "Documentation: https://circleci.com/docs/managing-api-tokens/"
    exit 1
  fi
  
  # We have CircleCI checks, fetch pipeline data
  PIPELINES=$(get_pipelines_for_pr "$PULL_REQUEST")
  PIPELINE_COUNT=$(echo "$PIPELINES" | jq 'length' 2>/dev/null || echo "0")
  
  if [ "$PIPELINE_COUNT" -gt 0 ]; then
    # Filter to latest pipeline
    PIPELINES=$(echo "$PIPELINES" | jq 'sort_by(.created_at // "") | reverse | .[0:1]' 2>/dev/null || echo "$PIPELINES")
    PIPELINE_IDS=$(echo "$PIPELINES" | jq -r '.[].id' 2>/dev/null)
    
    for pipeline_id in $PIPELINE_IDS; do
      if [ -z "$pipeline_id" ] || [ "$pipeline_id" = "null" ]; then
        continue
      fi
      
      PIPELINE_NUMBER=$(echo "$PIPELINES" | jq -r --arg id "$pipeline_id" '.[] | select(.id == $id) | .number // "N/A"' 2>/dev/null)
      PIPELINE_CREATED=$(echo "$PIPELINES" | jq -r --arg id "$pipeline_id" '.[] | select(.id == $id) | .created_at // "N/A"' 2>/dev/null)
      PIPELINE_VCS_BRANCH=$(echo "$PIPELINES" | jq -r --arg id "$pipeline_id" '.[] | select(.id == $id) | .vcs.branch // "N/A"' 2>/dev/null)
      
      # Extract pipeline errors if any
      PIPELINE_ERRORS=$(echo "$PIPELINES" | jq -r --arg id "$pipeline_id" '.[] | select(.id == $id) | .errors // []' 2>/dev/null)
      if [ -n "$PIPELINE_ERRORS" ] && [ "$PIPELINE_ERRORS" != "null" ] && [ "$PIPELINE_ERRORS" != "[]" ]; then
        if [ "$PIPELINE_NUMBER" != "N/A" ] && [ "$PIPELINE_NUMBER" != "null" ]; then
          PIPELINE_ERRORS_MAP=$(echo "$PIPELINE_ERRORS_MAP" | jq --arg pipeline_number "$PIPELINE_NUMBER" --argjson errors "$PIPELINE_ERRORS" '.[$pipeline_number] = $errors' 2>/dev/null || echo "$PIPELINE_ERRORS_MAP")
        fi
      fi
      
      WORKFLOWS=$(get_workflows_for_pipeline "$pipeline_id")
      WORKFLOW_IDS=$(echo "$WORKFLOWS" | jq -r '.[].id' 2>/dev/null)
      
      for workflow_id in $WORKFLOW_IDS; do
        if [ -z "$workflow_id" ] || [ "$workflow_id" = "null" ]; then
          continue
        fi
        
        WORKFLOW_NAME=$(echo "$WORKFLOWS" | jq -r --arg id "$workflow_id" '.[] | select(.id == $id) | .name' 2>/dev/null)
        JOBS=$(get_jobs_for_workflow "$workflow_id")
        
        # Create a map of job name -> job data for quick lookup
        JOBS_MAP=$(echo "$JOBS" | jq --arg workflow_name "$WORKFLOW_NAME" --arg pipeline_number "$PIPELINE_NUMBER" --arg pipeline_created "$PIPELINE_CREATED" --arg pipeline_branch "$PIPELINE_VCS_BRANCH" '
          reduce .[] as $job ({}; .[$job.name] = ($job + {
            workflow_name: $workflow_name,
            pipeline_number: ($pipeline_number | if . == "N/A" then null else . end),
            pipeline_created_at: ($pipeline_created | if . == "N/A" then null else . end),
            pipeline_branch: ($pipeline_branch | if . == "N/A" then null else . end)
          }))
        ' 2>/dev/null || echo "{}")
        
        # Merge into CIRCLE_JOBS_MAP
        CIRCLE_JOBS_MAP=$(echo "$CIRCLE_JOBS_MAP" | jq --argjson jobs "$JOBS_MAP" '. + $jobs' 2>/dev/null || echo "$CIRCLE_JOBS_MAP")
      done
    done
  fi
fi

# Enrich GitHub checks with CircleCI data where applicable
ALL_CHECKS=$(echo "$GITHUB_CHECKS" | jq --argjson circle_jobs "$CIRCLE_JOBS_MAP" --argjson pipeline_errors "$PIPELINE_ERRORS_MAP" '
  map(
    . as $check |
    if $check.is_circleci == true then
      # Extract job name from context (e.g., "ci/circleci: job_name" -> "job_name")
      ($check.context | split(": ") | if length > 1 then .[1] else $check.context end) as $job_name |
      ($circle_jobs[$job_name] // {}) as $circle_job |
      ($circle_job.pipeline_number // null) as $pipeline_num |
      # If no pipeline number from job, try to get first pipeline number from errors map
      (if $pipeline_num == null then ($pipeline_errors | keys | if length > 0 then .[0] else null end) else ($pipeline_num | tostring) end) as $pipeline_key |
      ($pipeline_errors[$pipeline_key] // null) as $errors |
      $check + {
        job_number: $circle_job.job_number,
        workflow_name: $circle_job.workflow_name,
        pipeline_number: ($circle_job.pipeline_number // (if $pipeline_key != null then ($pipeline_key | tonumber) else null end)),
        pipeline_created_at: $circle_job.pipeline_created_at,
        pipeline_branch: $circle_job.pipeline_branch,
        pipeline_errors: $errors,
        started_at: ($circle_job.started_at // $check.started_at),
        stopped_at: ($circle_job.stopped_at // $check.completed_at)
      }
    else
      $check
    end
  )
' 2>/dev/null || echo "$GITHUB_CHECKS")

# Enrich CodeQL checks with annotations for failed checks
ALL_CHECKS=$(echo "$ALL_CHECKS" | jq '
  map(
    . as $check |
    if $check.is_codeql == true and ($check.status | ascii_downcase | test("failure|failed|error"; "i")) and ($check.check_run_id != null) then
      # Annotations will be fetched and added in the display section
      $check
    else
      $check
    end
  )
' 2>/dev/null || echo "$ALL_CHECKS")

# Find expected CircleCI jobs (jobs in workflow but no check run yet)
if [ -n "$CIRCLE_JOBS_MAP" ] && [ "$CIRCLE_JOBS_MAP" != "{}" ] && [ "$CIRCLE_JOBS_MAP" != "null" ]; then
  # Get list of job names from CircleCI workflow
  WORKFLOW_JOB_NAMES=$(echo "$CIRCLE_JOBS_MAP" | jq -r 'keys[]' 2>/dev/null)
  
  # Get list of existing CircleCI check names from GitHub
  EXISTING_CHECK_NAMES=$(echo "$ALL_CHECKS" | jq -r '.[] | select(.is_circleci == true) | (.context | split(": ") | if length > 1 then .[1] else .context end)' 2>/dev/null)
  
  # Find missing jobs (in workflow but not in GitHub checks)
  for job_name in $WORKFLOW_JOB_NAMES; do
    if [ -z "$job_name" ] || [ "$job_name" = "null" ]; then
      continue
    fi
    
    # Check if this job already has a check run
    if ! echo "$EXISTING_CHECK_NAMES" | grep -q "^${job_name}$"; then
      # This job is expected - create an expected check entry
      JOB_DATA=$(echo "$CIRCLE_JOBS_MAP" | jq --arg job "$job_name" '.[$job] // {}' 2>/dev/null)
      
      EXPECTED_CHECK=$(jq -n \
        --arg name "ci/circleci: $job_name" \
        --arg workflow "$(echo "$JOB_DATA" | jq -r '.workflow_name // ""' 2>/dev/null)" \
        --arg pipeline "$(echo "$JOB_DATA" | jq -r '.pipeline_number // ""' 2>/dev/null)" \
        --arg created "$(echo "$JOB_DATA" | jq -r '.pipeline_created_at // ""' 2>/dev/null)" \
        --arg branch "$(echo "$JOB_DATA" | jq -r '.pipeline_branch // ""' 2>/dev/null)" \
        '{
          name: $name,
          status: "pending",
          conclusion: "pending",
          description: "Expected — Waiting for status to be reported",
          html_url: null,
          started_at: null,
          completed_at: null,
          context: $name,
          is_circleci: true,
          type: "expected",
          workflow_name: (if $workflow != "" then $workflow else null end),
          pipeline_number: (if $pipeline != "" then $pipeline else null end),
          pipeline_created_at: (if $created != "" then $created else null end),
          pipeline_branch: (if $branch != "" then $branch else null end)
        }' 2>/dev/null)
      
      if [ -n "$EXPECTED_CHECK" ]; then
        ALL_CHECKS=$(echo "$ALL_CHECKS" | jq --argjson expected "$EXPECTED_CHECK" '. + [$expected]' 2>/dev/null || echo "$ALL_CHECKS")
      fi
    fi
  done
fi

# Apply filters
FILTERED_CHECKS="$ALL_CHECKS"

# Apply job/check name filter
if [ -n "$JOB_FILTER" ]; then
  FILTERED_CHECKS=$(echo "$FILTERED_CHECKS" | jq --arg filter "$JOB_FILTER" '[.[] | select(.name == $filter or .context == $filter or (.context | contains($filter)))]' 2>/dev/null || echo "$FILTERED_CHECKS")
fi

# Apply workflow filter (only applies to CircleCI checks)
if [ -n "$WORKFLOW_FILTER" ]; then
  FILTERED_CHECKS=$(echo "$FILTERED_CHECKS" | jq --arg filter "$WORKFLOW_FILTER" '[.[] | select(.is_circleci != true or .workflow_name == $filter)]' 2>/dev/null || echo "$FILTERED_CHECKS")
fi

# Apply status filters (OR logic - if multiple are specified, show checks matching any)
# Map GitHub status values to our filter values
if [ -n "$SHOW_FAILING" ] || [ -n "$SHOW_PASSING" ] || [ -n "$SHOW_IN_PROGRESS" ]; then
  STATUS_FILTER_PARTS=()
  
  if [ -n "$SHOW_FAILING" ]; then
    STATUS_FILTER_PARTS+=("failed|error|failure")
  fi
  
  if [ -n "$SHOW_PASSING" ]; then
    STATUS_FILTER_PARTS+=("success|successful")
  fi
  
  if [ -n "$SHOW_IN_PROGRESS" ]; then
    STATUS_FILTER_PARTS+=("running|pending|in_progress|queued|in_progress|waiting")
  fi
  
  # Join all filter parts with |
  STATUS_FILTER=$(IFS='|'; echo "${STATUS_FILTER_PARTS[*]}")
  
  # Filter checks by status (case-insensitive)
  FILTERED_CHECKS=$(echo "$FILTERED_CHECKS" | jq --arg filter "$STATUS_FILTER" '
    [.[] | select(.status | ascii_downcase | test($filter; "i"))]
  ' 2>/dev/null || echo "$FILTERED_CHECKS")
fi

# Enrich checks with details if requested (for CircleCI checks only)
if [ -n "$DETAILS" ]; then
  ENRICHED_CHECKS="[]"
  CHECK_COUNT=$(echo "$FILTERED_CHECKS" | jq 'length' 2>/dev/null || echo "0")
  
  for i in $(seq 0 $((CHECK_COUNT - 1))); do
    CHECK=$(echo "$FILTERED_CHECKS" | jq ".[$i]" 2>/dev/null)
    IS_CIRCLECI=$(echo "$CHECK" | jq -r '.is_circleci // false' 2>/dev/null)
    JOB_NUMBER=$(echo "$CHECK" | jq -r '.job_number // empty' 2>/dev/null)
    
    if [ "$IS_CIRCLECI" = "true" ] && [ -n "$JOB_NUMBER" ] && [ "$JOB_NUMBER" != "null" ]; then
      # Get job details
      JOB_DETAILS=$(get_job_details "$JOB_NUMBER")
      if [ $? -eq 0 ] && [ -n "$JOB_DETAILS" ]; then
        CHECK=$(echo "$CHECK" | jq --argjson details "$JOB_DETAILS" '. + $details' 2>/dev/null || echo "$CHECK")
      fi
      
      # Get test metadata for failed jobs
      CHECK_STATUS=$(echo "$CHECK" | jq -r '.status // "unknown"' 2>/dev/null | tr '[:upper:]' '[:lower:]')
      if [ "$CHECK_STATUS" = "failed" ] || [ "$CHECK_STATUS" = "error" ] || [ "$CHECK_STATUS" = "failure" ]; then
        TEST_DATA=$(get_job_tests "$JOB_NUMBER" 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$TEST_DATA" ]; then
          # Check if test data is valid JSON and has tests
          if echo "$TEST_DATA" | jq empty 2>/dev/null; then
            # Extract failed tests (v2 API uses .items[])
            FAILED_TESTS=$(echo "$TEST_DATA" | jq '[.items[]? | select(.result == "failure" or .result == "error")]' 2>/dev/null)
            if [ -n "$FAILED_TESTS" ] && [ "$FAILED_TESTS" != "null" ] && [ "$FAILED_TESTS" != "[]" ]; then
              CHECK=$(echo "$CHECK" | jq --argjson tests "$FAILED_TESTS" '. + {failed_tests: $tests}' 2>/dev/null || echo "$CHECK")
            fi
          fi
        fi
      fi
    fi
    
    ENRICHED_CHECKS=$(echo "$ENRICHED_CHECKS" | jq --argjson check "$CHECK" '. + [$check]' 2>/dev/null || echo "$ENRICHED_CHECKS")
  done
  
  FILTERED_CHECKS="$ENRICHED_CHECKS"
fi

# Output results
TOTAL=$(echo "$FILTERED_CHECKS" | jq 'length // 0' 2>/dev/null || echo "0")

# Ensure TOTAL is numeric
if ! [[ "$TOTAL" =~ ^[0-9]+$ ]]; then
  TOTAL=0
fi

# Calculate summary counts (for display at the end)
if [ -z "$JSON_OUTPUT" ] && [ -z "$COUNT_ONLY" ]; then
  FAILING_COUNT=$(echo "$FILTERED_CHECKS" | jq '[.[] | select(.status | ascii_downcase | test("failure|failed|error"; "i"))] | length' 2>/dev/null || echo "0")
  EXPECTED_COUNT=$(echo "$FILTERED_CHECKS" | jq '[.[] | select((.type | ascii_downcase) == "expected")] | length' 2>/dev/null || echo "0")
  PENDING_COUNT=$(echo "$FILTERED_CHECKS" | jq '[.[] | select((.status | ascii_downcase | test("pending|queued|waiting"; "i")) and ((.type | ascii_downcase) != "expected"))] | length' 2>/dev/null || echo "0")
  SUCCESS_COUNT=$(echo "$FILTERED_CHECKS" | jq '[.[] | select(.status | ascii_downcase | test("success|successful"; "i"))] | length' 2>/dev/null || echo "0")
  IN_PROGRESS_COUNT=$(echo "$FILTERED_CHECKS" | jq '[.[] | select(.status | ascii_downcase | test("in_progress|running|inprogress"; "i"))] | length' 2>/dev/null || echo "0")
  NEUTRAL_COUNT=$(echo "$FILTERED_CHECKS" | jq '[.[] | select(.status | ascii_downcase | test("neutral|cancelled|canceled|skipped"; "i"))] | length' 2>/dev/null || echo "0")
  UNKNOWN_COUNT=$(echo "$FILTERED_CHECKS" | jq '[.[] | 
    (.type | ascii_downcase) as $type |
    (.status | ascii_downcase) as $status |
    select(
      ($type != "expected") and
      ($status | test("success|successful|failure|failed|error|pending|queued|waiting|in_progress|running|inprogress|neutral|cancelled|canceled|skipped"; "i") | not)
    )
  ] | length' 2>/dev/null || echo "0")
  
  # Ensure counts are numeric
  if ! [[ "$FAILING_COUNT" =~ ^[0-9]+$ ]]; then
    FAILING_COUNT=0
  fi
  if ! [[ "$EXPECTED_COUNT" =~ ^[0-9]+$ ]]; then
    EXPECTED_COUNT=0
  fi
  if ! [[ "$PENDING_COUNT" =~ ^[0-9]+$ ]]; then
    PENDING_COUNT=0
  fi
  if ! [[ "$SUCCESS_COUNT" =~ ^[0-9]+$ ]]; then
    SUCCESS_COUNT=0
  fi
  if ! [[ "$IN_PROGRESS_COUNT" =~ ^[0-9]+$ ]]; then
    IN_PROGRESS_COUNT=0
  fi
  if ! [[ "$NEUTRAL_COUNT" =~ ^[0-9]+$ ]]; then
    NEUTRAL_COUNT=0
  fi
  if ! [[ "$UNKNOWN_COUNT" =~ ^[0-9]+$ ]]; then
    UNKNOWN_COUNT=0
  fi
fi

if [ -n "$COUNT_ONLY" ]; then
  if [ -n "$JSON_OUTPUT" ]; then
    echo "$FILTERED_CHECKS" | jq "{total: length, checks: .}"
  else
    echo "Total: $TOTAL"
  fi
elif [ -n "$JSON_OUTPUT" ]; then
  echo "$FILTERED_CHECKS" | jq '.'
else
  if [ "$TOTAL" -gt 0 ]; then
    for i in $(seq 0 $((TOTAL - 1))); do
      CHECK=$(echo "$FILTERED_CHECKS" | jq ".[$i]" 2>/dev/null)
      
      CHECK_NAME=$(echo "$CHECK" | jq -r '.name // .context // "N/A"')
      CHECK_STATUS=$(echo "$CHECK" | jq -r '.status // "N/A"')
      CHECK_TYPE=$(echo "$CHECK" | jq -r '.type // ""' 2>/dev/null)
      CHECK_DESCRIPTION=$(echo "$CHECK" | jq -r '.description // "N/A"')
      CHECK_URL=$(echo "$CHECK" | jq -r '.html_url // .url // .detailsUrl // "N/A"')
      STARTED_AT=$(echo "$CHECK" | jq -r '.started_at // "N/A"')
      STOPPED_AT=$(echo "$CHECK" | jq -r '.stopped_at // .completed_at // "N/A"')
      IS_CIRCLECI=$(echo "$CHECK" | jq -r '.is_circleci // false' 2>/dev/null)
      IS_CODEQL=$(echo "$CHECK" | jq -r '.is_codeql // false' 2>/dev/null)
      CHECK_RUN_ID=$(echo "$CHECK" | jq -r '.check_run_id // null' 2>/dev/null)
      
      # CircleCI-specific fields
      WORKFLOW_NAME=$(echo "$CHECK" | jq -r '.workflow_name // "N/A"')
      JOB_NUMBER=$(echo "$CHECK" | jq -r '.job_number // "N/A"')
      PIPELINE_NUMBER=$(echo "$CHECK" | jq -r '.pipeline_number // "N/A"')
      PIPELINE_CREATED=$(echo "$CHECK" | jq -r '.pipeline_created_at // "N/A"')
      PIPELINE_BRANCH=$(echo "$CHECK" | jq -r '.pipeline_branch // "N/A"')
      PIPELINE_ERRORS=$(echo "$CHECK" | jq '.pipeline_errors // null' 2>/dev/null)
      
      # Determine emoji based on status and type
      STATUS_LOWER=$(echo "$CHECK_STATUS" | tr '[:upper:]' '[:lower:]')
      TYPE_LOWER=$(echo "$CHECK_TYPE" | tr '[:upper:]' '[:lower:]')
      # Expected checks should show as orange (🟠) even if status is pending
      if [ "$TYPE_LOWER" = "expected" ]; then
        STATUS_EMOJI="🟠"
      else
        case "$STATUS_LOWER" in
          success|successful)
            STATUS_EMOJI="🟢"
            ;;
          failure|failed|error)
            STATUS_EMOJI="🔴"
            ;;
          pending|queued|waiting)
            STATUS_EMOJI="🟡"
            ;;
          in_progress|running|inprogress)
            STATUS_EMOJI="🟠"
            ;;
          neutral|cancelled|canceled|skipped)
            STATUS_EMOJI="⚪"
            ;;
          *)
            STATUS_EMOJI="⚫"
            ;;
        esac
      fi
      
      echo ""
      echo "Check: $CHECK_NAME"
      echo "---"
      echo "Status:           $STATUS_EMOJI $CHECK_STATUS"
      if [ "$CHECK_DESCRIPTION" != "N/A" ] && [ "$CHECK_DESCRIPTION" != "null" ] && [ "$CHECK_DESCRIPTION" != "" ]; then
        echo "Description:      $CHECK_DESCRIPTION"
      fi
      
      # Show CircleCI-specific info if applicable
      if [ "$IS_CIRCLECI" = "true" ]; then
        if [ "$WORKFLOW_NAME" != "N/A" ] && [ "$WORKFLOW_NAME" != "null" ]; then
          echo "Workflow:         $WORKFLOW_NAME"
        fi
        # Format pipeline info more descriptively
        if [ "$PIPELINE_BRANCH" != "N/A" ] && [ "$PIPELINE_BRANCH" != "null" ] && [ "$PIPELINE_NUMBER" != "N/A" ]; then
          echo "Pipeline:         #${PIPELINE_NUMBER} (${PIPELINE_BRANCH})"
        elif [ "$PIPELINE_NUMBER" != "N/A" ]; then
          echo "Pipeline:         #${PIPELINE_NUMBER}"
        fi
        if [ "$PIPELINE_CREATED" != "N/A" ] && [ "$PIPELINE_CREATED" != "null" ]; then
          echo "Pipeline Created: $PIPELINE_CREATED"
        fi
        # Display pipeline errors if any
        if [ "$PIPELINE_ERRORS" != "null" ] && [ "$PIPELINE_ERRORS" != "" ] && [ -n "$PIPELINE_ERRORS" ]; then
          ERROR_COUNT=$(echo "$PIPELINE_ERRORS" | jq 'length' 2>/dev/null || echo "0")
          if [ "$ERROR_COUNT" -gt 0 ] 2>/dev/null; then
            echo ""
            echo "Pipeline Errors:"
            echo "$PIPELINE_ERRORS" | jq -r '.[] | "  - \(.type // "error"): \(.message // "Unknown error")"' 2>/dev/null
          fi
        fi
        if [ "$JOB_NUMBER" != "N/A" ] && [ "$JOB_NUMBER" != "null" ]; then
          echo "Job Number:       $JOB_NUMBER"
        fi
      fi
      
      if [ "$STARTED_AT" != "N/A" ] && [ "$STARTED_AT" != "null" ]; then
        echo "Started:          $STARTED_AT"
      fi
      if [ "$STOPPED_AT" != "N/A" ] && [ "$STOPPED_AT" != "null" ]; then
        echo "Completed:        $STOPPED_AT"
      fi
      
      # Calculate duration if both started and completed are available
      if [ "$STARTED_AT" != "N/A" ] && [ "$STARTED_AT" != "null" ] && [ "$STOPPED_AT" != "N/A" ] && [ "$STOPPED_AT" != "null" ]; then
        # Convert ISO 8601 timestamps to seconds since epoch
        # Handle both with and without timezone (Z suffix)
        STARTED_SECONDS=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$STARTED_AT" +%s 2>/dev/null)
        if [ $? -ne 0 ]; then
          # Try without Z suffix
          STARTED_SECONDS=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$STARTED_AT" +%s 2>/dev/null)
        fi
        
        STOPPED_SECONDS=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$STOPPED_AT" +%s 2>/dev/null)
        if [ $? -ne 0 ]; then
          # Try without Z suffix
          STOPPED_SECONDS=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$STOPPED_AT" +%s 2>/dev/null)
        fi
        
        if [ -n "$STARTED_SECONDS" ] && [ -n "$STOPPED_SECONDS" ] && [ "$STARTED_SECONDS" != "" ] && [ "$STOPPED_SECONDS" != "" ]; then
          DURATION_SECONDS=$((STOPPED_SECONDS - STARTED_SECONDS))
          
          # Format duration in human-readable format
          if [ "$DURATION_SECONDS" -lt 0 ]; then
            DURATION="N/A (invalid)"
          elif [ "$DURATION_SECONDS" -lt 60 ]; then
            DURATION="${DURATION_SECONDS}s"
          elif [ "$DURATION_SECONDS" -lt 3600 ]; then
            MINUTES=$((DURATION_SECONDS / 60))
            SECONDS=$((DURATION_SECONDS % 60))
            if [ "$SECONDS" -eq 0 ]; then
              DURATION="${MINUTES}m"
            else
              DURATION="${MINUTES}m ${SECONDS}s"
            fi
          else
            HOURS=$((DURATION_SECONDS / 3600))
            REMAINING_SECONDS=$((DURATION_SECONDS % 3600))
            MINUTES=$((REMAINING_SECONDS / 60))
            SECONDS=$((REMAINING_SECONDS % 60))
            if [ "$MINUTES" -eq 0 ] && [ "$SECONDS" -eq 0 ]; then
              DURATION="${HOURS}h"
            elif [ "$SECONDS" -eq 0 ]; then
              DURATION="${HOURS}h ${MINUTES}m"
            else
              DURATION="${HOURS}h ${MINUTES}m ${SECONDS}s"
            fi
          fi
          
          echo "Duration:         $DURATION"
        fi
      fi
      
      if [ "$CHECK_URL" != "N/A" ] && [ "$CHECK_URL" != "null" ] && [ "$CHECK_URL" != "" ]; then
        echo "URL:              $CHECK_URL"
      fi
      
      # Show failed tests if available (CircleCI only)
      if [ "$IS_CIRCLECI" = "true" ]; then
        FAILED_TESTS=$(echo "$CHECK" | jq '.failed_tests // empty' 2>/dev/null)
        if [ -n "$FAILED_TESTS" ] && [ "$FAILED_TESTS" != "null" ] && [ "$FAILED_TESTS" != "[]" ]; then
          FAILED_COUNT=$(echo "$FAILED_TESTS" | jq 'length' 2>/dev/null || echo "0")
          echo ""
          echo "Failed Tests:     $FAILED_COUNT"
          echo "$FAILED_TESTS" | jq -r '.[] | "  - \(.name // "Unknown test"): \(.message // "No message")"' 2>/dev/null
        fi
        
        # Show job output/logs for failed jobs (unless --hide-job-output is set)
        # Following forum post: use v1.1 API to get job with steps/actions that have output_url
        if [ -z "$HIDE_JOB_OUTPUT" ] && [ "$CHECK_STATUS" != "success" ] && [ "$CHECK_STATUS" != "successful" ] && [ "$CHECK_STATUS" != "N/A" ] && [ "$JOB_NUMBER" != "N/A" ] && [ "$JOB_NUMBER" != "null" ]; then
          # Get job details from v1.1 API to access steps/actions with output_url
          # (v2 API doesn't provide steps/actions, so v1.1 is required for this step)
          JOB_V1=$(get_job_with_steps_v1 "$JOB_NUMBER" 2>/dev/null)
          if [ $? -eq 0 ] && [ -n "$JOB_V1" ] && echo "$JOB_V1" | jq empty 2>/dev/null; then
            # Get all steps with their status (success/failure)
            ALL_STEPS=$(echo "$JOB_V1" | jq '[.steps[]? | {
              name: .name,
              is_failed: (if any(.actions[]?; .failed == true or .status == "failed" or (.exit_code != null and .exit_code != 0)) then true else false end),
              actions: [.actions[]? | {
                name: .name,
                failed: (.failed // false),
                status: .status,
                exit_code: .exit_code,
                output_url: .output_url
              }]
            }]' 2>/dev/null)
            
            if [ -n "$ALL_STEPS" ] && [ "$ALL_STEPS" != "null" ] && [ "$ALL_STEPS" != "[]" ]; then
              STEP_COUNT=$(echo "$ALL_STEPS" | jq 'length' 2>/dev/null || echo "0")
              if [ "$STEP_COUNT" -gt 0 ]; then
                echo ""
                echo "Job Steps:"
                
                # Process each step
                echo "$ALL_STEPS" | jq -c '.[]' 2>/dev/null | while IFS= read -r step_json; do
                  step_name=$(echo "$step_json" | jq -r '.name // "Unknown step"' 2>/dev/null)
                  is_failed=$(echo "$step_json" | jq -r '.is_failed // false' 2>/dev/null)
                  
                  # Display step status
                  if [ "$is_failed" = "true" ]; then
                    echo "  🔴 $step_name (Failed)"
                  else
                    echo "  🟢 $step_name (Success)"
                  fi
                  
                  # Only show log output for failed steps
                  if [ "$is_failed" = "true" ]; then
                    # Find failed actions in this step
                    failed_actions=$(echo "$step_json" | jq '[.actions[]? | select(.failed == true or .status == "failed" or (.exit_code != null and .exit_code != 0))]' 2>/dev/null)
                    
                    if [ -n "$failed_actions" ] && [ "$failed_actions" != "null" ] && [ "$failed_actions" != "[]" ]; then
                      echo "$failed_actions" | jq -c '.[]' 2>/dev/null | while IFS= read -r action_json; do
                        action_name=$(echo "$action_json" | jq -r '.name // "Unknown action"' 2>/dev/null)
                        exit_code=$(echo "$action_json" | jq -r '.exit_code // "unknown"' 2>/dev/null)
                        output_url=$(echo "$action_json" | jq -r '.output_url // ""' 2>/dev/null)
                        
                        echo "    Action: $action_name"
                        echo "    Exit Code: $exit_code"
                        
                        # Download and display log if output_url is available
                        if [ -n "$output_url" ] && [ "$output_url" != "" ] && [ "$output_url" != "null" ]; then
                          echo ""
                          echo "      Log Output:"
                          log_content=$(download_log_from_url "$output_url" 2>/dev/null)
                          if [ -n "$log_content" ]; then
                            formatted_log=$(format_log_output "$log_content")
                            if [ -n "$formatted_log" ]; then
                              echo "$formatted_log" | sed 's/^/        /'
                            else
                              echo "        (Log content is empty)"
                            fi
                          else
                            echo "        (Failed to download log or log is empty)"
                          fi
                          echo ""
                        fi
                      done
                    fi
                  fi
                done
              fi
            fi
          fi
        fi
        
      fi
      
      # Show CodeQL annotations for failed checks (unless --hide-job-output is set)
      if [ "$IS_CODEQL" = "true" ] && [ -z "$HIDE_JOB_OUTPUT" ] && [ "$CHECK_STATUS" != "success" ] && [ "$CHECK_STATUS" != "successful" ] && [ "$CHECK_STATUS" != "N/A" ] && [ "$CHECK_RUN_ID" != "null" ] && [ -n "$CHECK_RUN_ID" ]; then
        # Fetch annotations for this CodeQL check run
        ANNOTATIONS=$(get_check_run_annotations "$CHECK_RUN_ID" 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$ANNOTATIONS" ] && echo "$ANNOTATIONS" | jq empty 2>/dev/null; then
          ANNOTATION_COUNT=$(echo "$ANNOTATIONS" | jq 'length' 2>/dev/null || echo "0")
          if [ "$ANNOTATION_COUNT" -gt 0 ]; then
            echo ""
            echo "Security Alerts:"
            
            # Group annotations by severity level (annotation_level: failure, warning, notice)
            # Map to more readable severity names
            HIGH_ALERTS=$(echo "$ANNOTATIONS" | jq '[.[] | select(.annotation_level == "failure")]' 2>/dev/null)
            MEDIUM_ALERTS=$(echo "$ANNOTATIONS" | jq '[.[] | select(.annotation_level == "warning")]' 2>/dev/null)
            LOW_ALERTS=$(echo "$ANNOTATIONS" | jq '[.[] | select(.annotation_level == "notice")]' 2>/dev/null)
            
            HIGH_COUNT=$(echo "$HIGH_ALERTS" | jq 'length' 2>/dev/null || echo "0")
            MEDIUM_COUNT=$(echo "$MEDIUM_ALERTS" | jq 'length' 2>/dev/null || echo "0")
            LOW_COUNT=$(echo "$LOW_ALERTS" | jq 'length' 2>/dev/null || echo "0")
            
            if [ "$HIGH_COUNT" -gt 0 ] || [ "$MEDIUM_COUNT" -gt 0 ] || [ "$LOW_COUNT" -gt 0 ]; then
              if [ "$HIGH_COUNT" -gt 0 ]; then
                echo "  High: $HIGH_COUNT"
              fi
              if [ "$MEDIUM_COUNT" -gt 0 ]; then
                echo "  Medium: $MEDIUM_COUNT"
              fi
              if [ "$LOW_COUNT" -gt 0 ]; then
                echo "  Low: $LOW_COUNT"
              fi
              echo ""
            fi
            
            # Display annotations, prioritizing high severity first
            if [ "$HIGH_COUNT" -gt 0 ]; then
              echo "$HIGH_ALERTS" | jq -c '.[]' 2>/dev/null | while IFS= read -r annotation; do
                path=$(echo "$annotation" | jq -r '.path // "N/A"' 2>/dev/null)
                start_line=$(echo "$annotation" | jq -r '.start_line // "N/A"' 2>/dev/null)
                end_line=$(echo "$annotation" | jq -r '.end_line // "N/A"' 2>/dev/null)
                title=$(echo "$annotation" | jq -r '.title // "Security Alert"' 2>/dev/null)
                message=$(echo "$annotation" | jq -r '.message // "No message"' 2>/dev/null)
                
                if [ "$start_line" = "$end_line" ]; then
                  line_info="line $start_line"
                else
                  line_info="lines $start_line-$end_line"
                fi
                
                echo "  🔴 $path:$line_info"
                echo "     $title"
                if [ "$message" != "No message" ] && [ -n "$message" ]; then
                  # Truncate long messages to first 200 characters
                  message_len=$(echo "$message" | wc -c | tr -d ' ')
                  if [ "$message_len" -gt 200 ]; then
                    message=$(echo "$message" | cut -c1-200)"..."
                  fi
                  echo "     $message"
                fi
                echo ""
              done
            fi
            
            if [ "$MEDIUM_COUNT" -gt 0 ]; then
              echo "$MEDIUM_ALERTS" | jq -c '.[]' 2>/dev/null | while IFS= read -r annotation; do
                path=$(echo "$annotation" | jq -r '.path // "N/A"' 2>/dev/null)
                start_line=$(echo "$annotation" | jq -r '.start_line // "N/A"' 2>/dev/null)
                end_line=$(echo "$annotation" | jq -r '.end_line // "N/A"' 2>/dev/null)
                title=$(echo "$annotation" | jq -r '.title // "Security Alert"' 2>/dev/null)
                message=$(echo "$annotation" | jq -r '.message // "No message"' 2>/dev/null)
                
                if [ "$start_line" = "$end_line" ]; then
                  line_info="line $start_line"
                else
                  line_info="lines $start_line-$end_line"
                fi
                
                echo "  🟡 $path:$line_info"
                echo "     $title"
                if [ "$message" != "No message" ] && [ -n "$message" ]; then
                  message_len=$(echo "$message" | wc -c | tr -d ' ')
                  if [ "$message_len" -gt 200 ]; then
                    message=$(echo "$message" | cut -c1-200)"..."
                  fi
                  echo "     $message"
                fi
                echo ""
              done
            fi
            
            if [ "$LOW_COUNT" -gt 0 ]; then
              echo "$LOW_ALERTS" | jq -c '.[]' 2>/dev/null | while IFS= read -r annotation; do
                path=$(echo "$annotation" | jq -r '.path // "N/A"' 2>/dev/null)
                start_line=$(echo "$annotation" | jq -r '.start_line // "N/A"' 2>/dev/null)
                end_line=$(echo "$annotation" | jq -r '.end_line // "N/A"' 2>/dev/null)
                title=$(echo "$annotation" | jq -r '.title // "Security Alert"' 2>/dev/null)
                message=$(echo "$annotation" | jq -r '.message // "No message"' 2>/dev/null)
                
                if [ "$start_line" = "$end_line" ]; then
                  line_info="line $start_line"
                else
                  line_info="lines $start_line-$end_line"
                fi
                
                echo "  ⚪ $path:$line_info"
                echo "     $title"
                if [ "$message" != "No message" ] && [ -n "$message" ]; then
                  message_len=$(echo "$message" | wc -c | tr -d ' ')
                  if [ "$message_len" -gt 200 ]; then
                    message=$(echo "$message" | cut -c1-200)"..."
                  fi
                  echo "     $message"
                fi
                echo ""
              done
            fi
          fi
        fi
      fi
      
      echo ""
    done
    
    # Display summary at the end
    echo "---"
    echo "Summary:"
    # List each check with its status emoji
    SUMMARY_LINES=$(echo "$FILTERED_CHECKS" | jq -r '.[] | 
      (.type | ascii_downcase) as $type |
      (.status | ascii_downcase) as $status |
      (if $type == "expected" then "🟠"
       elif $status == "success" or $status == "successful" then "🟢"
       elif $status == "failure" or $status == "failed" or $status == "error" then "🔴"
       elif $status == "pending" or $status == "queued" or $status == "waiting" then "🟡"
       elif $status == "in_progress" or $status == "running" or $status == "inprogress" then "🟠"
       elif $status == "neutral" or $status == "cancelled" or $status == "canceled" or $status == "skipped" then "⚪"
       else "⚫" end) as $emoji |
      "\($emoji)  Check: \(.name // .context // "N/A")"
    ' 2>/dev/null)
    
    if [ -n "$SUMMARY_LINES" ] && [ "$SUMMARY_LINES" != "" ]; then
      echo "$SUMMARY_LINES"
    else
      echo "No checks found"
    fi
    
    # Build status key lines with only statuses that have counts > 0
    if [ -z "$JSON_OUTPUT" ] && [ -z "$COUNT_ONLY" ]; then
      STATUS_KEY_LINES=()
      if [ "$SUCCESS_COUNT" -gt 0 ]; then
        STATUS_KEY_LINES+=("🟢 Success ($SUCCESS_COUNT)")
      fi
      if [ "$IN_PROGRESS_COUNT" -gt 0 ] || [ "$EXPECTED_COUNT" -gt 0 ]; then
        TOTAL_IN_PROGRESS=$((IN_PROGRESS_COUNT + EXPECTED_COUNT))
        STATUS_KEY_LINES+=("🟠 In Progress/Expected ($TOTAL_IN_PROGRESS)")
      fi
      if [ "$FAILING_COUNT" -gt 0 ]; then
        STATUS_KEY_LINES+=("🔴 Failed ($FAILING_COUNT)")
      fi
      if [ "$PENDING_COUNT" -gt 0 ]; then
        STATUS_KEY_LINES+=("🟡 Pending ($PENDING_COUNT)")
      fi
      if [ "$NEUTRAL_COUNT" -gt 0 ]; then
        STATUS_KEY_LINES+=("⚪ Neutral/Cancelled ($NEUTRAL_COUNT)")
      fi
      if [ "$UNKNOWN_COUNT" -gt 0 ]; then
        STATUS_KEY_LINES+=("⚫ Unknown ($UNKNOWN_COUNT)")
      fi
      
      if [ ${#STATUS_KEY_LINES[@]} -gt 0 ]; then
        echo ""
        for key_line in "${STATUS_KEY_LINES[@]}"; do
          echo "  $key_line"
        done
      fi
    fi
    echo ""
    
    # Get last commit SHA and summary from origin (via GitHub API)
    PR_DATA=$(gh api "repos/${REPO}/pulls/${PULL_REQUEST}" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$PR_DATA" ]; then
      HEAD_SHA=$(echo "$PR_DATA" | jq -r '.head.sha // empty' 2>/dev/null)
      if [ -n "$HEAD_SHA" ] && [ "$HEAD_SHA" != "null" ] && [ "$HEAD_SHA" != "" ]; then
        # Get short SHA (first 7 characters)
        SHORT_SHA=$(echo "$HEAD_SHA" | cut -c1-7)
        
        # Get commit message summary (first line) from GitHub API
        COMMIT_DATA=$(gh api "repos/${REPO}/commits/${HEAD_SHA}" 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$COMMIT_DATA" ]; then
          COMMIT_SUMMARY=$(echo "$COMMIT_DATA" | jq -r '.commit.message // ""' 2>/dev/null | head -n1 | sed 's/\r$//')
          
          echo "Last commit:"
          if [ -n "$COMMIT_SUMMARY" ] && [ "$COMMIT_SUMMARY" != "" ] && [ "$COMMIT_SUMMARY" != "null" ]; then
            echo "  ${SHORT_SHA} - ${COMMIT_SUMMARY}"
          else
            echo "  ${SHORT_SHA}"
          fi
        else
          echo "Last commit:"
          echo "  ${SHORT_SHA}"
        fi
      fi
    fi
    echo ""
    
    echo "PR: https://github.com/${REPO}/pull/${PULL_REQUEST}"
      else
        echo "No checks found matching the specified filters."
      fi
    fi
