#!/bin/bash

# Script to list all dependabot pull requests for this repository
# Usage: ./list-dependabot-prs.sh [OPTIONS]
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

JSON_OUTPUT=""
COUNT_ONLY=""

# Function to check if package is transitive and get parent
check_transitive_dependency() {
  local package="$1"
  local target_dir="$2"
  
  # Check if yarn is available
  if ! command -v yarn &> /dev/null; then
    echo "unknown (yarn not found)"
    return
  fi
  
  # Change to appropriate directory
  local work_dir="."
  if [ -n "$target_dir" ] && [ "$target_dir" = "/static" ]; then
    work_dir="static"
  fi
  
  # Check if package exists in package.json
  if [ -f "$work_dir/package.json" ]; then
    if grep -q "\"$package\"" "$work_dir/package.json"; then
      echo "direct"
      return
    fi
  fi
  
  # Package not in package.json, check if it's transitive
  cd "$work_dir" 2>/dev/null || return
  local why_output=$(yarn why "$package" 2>/dev/null)
  if echo "$why_output" | grep -q "Reasons this module exists"; then
    # Extract parent package from "Hoisted from" or depends line
    local parent=$(echo "$why_output" | grep -E "Hoisted from" | head -1 | sed -E 's/.*Hoisted from "([^"#]+).*/\1/' | cut -d'#' -f1)
    if [ -z "$parent" ]; then
      # Try alternative format - look for "package#dependency" depends on it
      parent=$(echo "$why_output" | grep "depends on it" | head -1 | sed -E 's/.*"([^"#]+)#[^"]+".*/\1/')
    fi
    if [ -n "$parent" ] && [ "$parent" != "$package" ]; then
      echo "transitive (via $parent)"
    else
      echo "transitive"
    fi
  else
    echo "not found"
  fi
  cd - > /dev/null 2>&1
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --json)
      JSON_OUTPUT="1"
      shift
      ;;
    --count)
      COUNT_ONLY="1"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Description:"
      echo "  Lists all open Dependabot pull requests for the repository."
      echo "  Shows package updates with dependency analysis (direct vs transitive),"
      echo "  file changes, and GitHub URLs for easy review and management."
      echo ""
      echo "Options:"
      echo "  --json                         Output only JSON (no formatted text)"
      echo "  --count                        Output only the count of items"
      echo "  -h, --help                     Show this help message"
      echo ""
      echo "Repository: $REPO"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      echo "Use -h or --help for usage information"
      exit 1
      ;;
  esac
done

# Check if gh CLI is available
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

# Check if jq is available
if ! command -v jq &> /dev/null; then
  echo "Error: jq is not installed. Install it to use this script."
  exit 1
fi

# Fetch all open pull requests
if [ -z "$JSON_OUTPUT" ]; then
  echo "Fetching open dependabot pull requests from ${REPO}..."
fi

# Use GitHub API to fetch open PRs
ALL_PRS=$(gh api "repos/${REPO}/pulls?state=open&per_page=100" 2>/dev/null)
API_EXIT_CODE=$?

if [ $API_EXIT_CODE -ne 0 ] || [ -z "$ALL_PRS" ]; then
  echo "Error: Failed to fetch pull requests from GitHub API" >&2
  exit 1
fi

# Filter for dependabot PRs
DEPENDABOT_PRS=$(echo "$ALL_PRS" | jq '[.[] | select(.user.login == "dependabot[bot]")]' 2>/dev/null)

if [ -z "$DEPENDABOT_PRS" ] || [ "$DEPENDABOT_PRS" = "null" ]; then
  DEPENDABOT_PRS="[]"
fi

# Get count
TOTAL=$(echo "$DEPENDABOT_PRS" | jq 'length' 2>/dev/null || echo "0")

# Enrich PRs with file information if not in count-only mode
if [ -z "$COUNT_ONLY" ] && [ "$TOTAL" -gt 0 ]; then
  if [ -z "$JSON_OUTPUT" ]; then
    echo "Fetching file changes for each dependabot PR..."
  fi
  
  ENRICHED_PRS="[]"
  for i in $(seq 0 $((TOTAL - 1))); do
    PR=$(echo "$DEPENDABOT_PRS" | jq ".[$i]")
    PR_NUMBER=$(echo "$PR" | jq -r '.number')
    
    # Fetch files for this PR
    PR_FILES=$(gh api "repos/${REPO}/pulls/${PR_NUMBER}/files" 2>/dev/null)
    if [ -n "$PR_FILES" ] && [ "$PR_FILES" != "null" ]; then
      # Add files to the PR object
      PR=$(echo "$PR" | jq --argjson files "$PR_FILES" '. + {files: $files}')
    else
      PR=$(echo "$PR" | jq '. + {files: []}')
    fi
    
    # Add to enriched array
    ENRICHED_PRS=$(echo "$ENRICHED_PRS" | jq --argjson pr "$PR" '. + [$pr]')
  done
  
  DEPENDABOT_PRS="$ENRICHED_PRS"
fi

# Output count only if --count flag is set
if [ -n "$COUNT_ONLY" ]; then
  if [ -n "$JSON_OUTPUT" ]; then
    echo "$DEPENDABOT_PRS" | jq '{total: length}'
  else
    echo "Total dependabot PRs: $TOTAL"
  fi
elif [ -n "$JSON_OUTPUT" ]; then
  echo "$DEPENDABOT_PRS" | jq '.'
else
  if [ "$TOTAL" -gt 0 ]; then
    # Display each PR
    for i in $(seq 0 $((TOTAL - 1))); do
      PR=$(echo "$DEPENDABOT_PRS" | jq ".[$i]")
      PR_NUMBER=$(echo "$PR" | jq -r '.number // "N/A"')
      PR_TITLE=$(echo "$PR" | jq -r '.title // "N/A"')
      PR_URL=$(echo "$PR" | jq -r '.html_url // "N/A"')
      PR_CREATED=$(echo "$PR" | jq -r '.created_at // "N/A"')
      PR_UPDATED=$(echo "$PR" | jq -r '.updated_at // "N/A"')
      
      # Get files from enriched PR data
      PR_FILES=$(echo "$PR" | jq '.files // []')
      FILE_COUNT=$(echo "$PR_FILES" | jq 'length' 2>/dev/null || echo "0")
      
      # Calculate totals from files
      if [ "$FILE_COUNT" -gt 0 ]; then
        PR_ADDITIONS=$(echo "$PR_FILES" | jq '[.[] | .additions] | add' 2>/dev/null || echo "0")
        PR_DELETIONS=$(echo "$PR_FILES" | jq '[.[] | .deletions] | add' 2>/dev/null || echo "0")
      else
        PR_ADDITIONS="0"
        PR_DELETIONS="0"
      fi
      
      echo ""
      echo "PR #${PR_NUMBER}: ${PR_TITLE}"
      echo "---"
      echo "URL:               ${PR_URL}"
      echo "Created:           ${PR_CREATED}"
      echo "Updated:           ${PR_UPDATED}"
      echo "Changes:           +${PR_ADDITIONS} -${PR_DELETIONS} (${FILE_COUNT} file(s))"
      
      # Display files changed with diffs for package.json files
      if [ "$FILE_COUNT" -gt 0 ]; then
        echo ""
        echo "Files changed:"
        echo "$PR_FILES" | jq -r '.[] | "  - \(.filename) (+\(.additions) -\(.deletions))"' 2>/dev/null
        
        # Show patch for package.json files
        PACKAGE_JSON_FILES=$(echo "$PR_FILES" | jq -r '.[] | select(.filename | endswith("package.json")) | .filename')
        if [ -n "$PACKAGE_JSON_FILES" ]; then
          echo ""
          echo "Diff for package.json files:"
          while IFS= read -r filename; do
            if [ -n "$filename" ]; then
              echo ""
              echo "  File: $filename"
              PATCH=$(echo "$PR_FILES" | jq -r --arg fname "$filename" '.[] | select(.filename == $fname) | .patch // ""')
              if [ -n "$PATCH" ]; then
                echo "$PATCH" | sed 's/^/    /'
                
                # Extract package names from diff and check dependency type
                # Look for lines like: +    "lodash": "^4.17.23"
                CHANGED_PACKAGES=$(echo "$PATCH" | grep -E '^\+' | grep -E '"[^"]+":.*"[^"]*[0-9]' | sed -E 's/^[+[:space:]]*"([^"]+)".*/\1/' | head -5)
                if [ -n "$CHANGED_PACKAGES" ]; then
                  echo ""
                  echo "    Dependency analysis:"
                  # Determine target directory from filename
                  TARGET_DIR=""
                  if echo "$filename" | grep -q "static/"; then
                    TARGET_DIR="/static"
                  fi
                  
                  while IFS= read -r pkg; do
                    if [ -n "$pkg" ] && [ "$pkg" != "name" ] && [ "$pkg" != "version" ] && [ "$pkg" != "type" ] && [ "$pkg" != "homepage" ] && [ "$pkg" != "private" ]; then
                      DEP_STATUS=$(check_transitive_dependency "$pkg" "$TARGET_DIR")
                      echo "      $pkg: $DEP_STATUS"
                    fi
                  done <<< "$CHANGED_PACKAGES"
                fi
              else
                echo "    (patch not available)"
              fi
            fi
          done <<< "$PACKAGE_JSON_FILES"
        fi
      fi
    done
    
    echo ""
    echo "=== Summary ==="
    echo "Total dependabot PRs: $TOTAL"
  else
    echo "No dependabot pull requests found."
  fi
fi
