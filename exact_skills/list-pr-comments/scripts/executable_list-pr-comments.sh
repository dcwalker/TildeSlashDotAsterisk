#!/bin/bash

# Script to list GitHub PR comments
# Usage: ./list-pr-comments.sh [OPTIONS]
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

PULL_REQUEST=""
COMMENT_URL=""
USER_FILTER="all"
COMMENT_TYPE="all"
PATH_FILTER=""
BODY_CONTAINS_STRING=""
SHOW_HIDDEN=""
JSON_OUTPUT=""
COUNT_ONLY=""
COMMENT_ID=""
ACTION_HIDE=""
ACTION_RESOLVE=""
ACTION_REPLY=""
HIDE_REASON=""
REPLY_TEXT=""
NO_PROMPT=""
GET_HIDE_REASONS=""
EFFICIENCY_TIP=""
BULK_MODE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    -pr|--pull-request)
      PULL_REQUEST="$2"
      shift 2
      ;;
    -u|--url)
      COMMENT_URL="$2"
      shift 2
      ;;
    --bots)
      USER_FILTER="bots"
      shift
      ;;
    --humans)
      USER_FILTER="humans"
      shift
      ;;
    -t|--type)
      COMMENT_TYPE="$2"
      shift 2
      ;;
    --json)
      JSON_OUTPUT="1"
      shift
      ;;
    --count)
      COUNT_ONLY="1"
      shift
      ;;
    -p|--path)
      PATH_FILTER="$2"
      shift 2
      ;;
    --show-hidden)
      SHOW_HIDDEN="1"
      shift
      ;;
    --body-contains-string)
      BODY_CONTAINS_STRING="$2"
      shift 2
      ;;
    -c|--comment-id)
      COMMENT_ID="$2"
      shift 2
      ;;
    --hide)
      ACTION_HIDE="1"
      shift
      ;;
    --resolve)
      ACTION_RESOLVE="1"
      shift
      ;;
    --reply)
      ACTION_REPLY="1"
      # Check if next argument is provided and doesn't start with -
      if [ $# -gt 1 ] && [[ ! "$2" =~ ^- ]]; then
        REPLY_TEXT="$2"
        shift 2
      else
        shift
      fi
      ;;
    --reason)
      HIDE_REASON="$2"
      shift 2
      ;;
    --no-prompt)
      NO_PROMPT="1"
      shift
      ;;
    --bulk)
      BULK_MODE="1"
      shift
      ;;
    --get-hide-reasons)
      GET_HIDE_REASONS="1"
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Description:"
      echo "  Lists, filters, and manages GitHub pull request comments (both review"
      echo "  and issue comments). Supports hiding, resolving, and replying to comments"
      echo "  with bulk operations. Auto-detects PR from current branch."
      echo ""
      echo "Options:"
      echo "  -pr, --pull-request <number>  Filter comments for a specific pull request"
      echo "  -u, --url <url>               Get a specific comment by URL"
      echo "  -c, --comment-id <id>         Comment ID to use (required for actions, optional for listing)"
      echo "  --bots                        Show only bot comments"
      echo "  --humans                      Show only human comments"
      echo "  -t, --type <type>            Filter by comment type: all, review, issue (default: all)"
      echo "                               - all: both review comments and issue comments"
      echo "                               - review: inline code review comments"
      echo "                               - issue: PR conversation comments"
      echo "  -p, --path <path>             Filter review comments by file path (exact match)"
      echo "                               Note: Only applies to review comments, not issue comments"
      echo "  --body-contains-string <str>  Filter comments by body text (exact substring match)"
      echo "  --show-hidden                 Show hidden/resolved comments (default: hide both)"
      echo "  --json                        Output only JSON (no formatted text)"
      echo "  --count                       Output only the count of items"
      echo ""
      echo "Actions (can be combined - --reply and --resolve can be used together):"
      echo "  --hide                        Hide an issue comment (use with --bulk to hide all filtered)"
      echo "  --resolve                     Resolve a review comment thread"
      echo "  --reply [text]                Reply to a review comment"
      echo "                               If text is provided, use it; otherwise prompt interactively"
      echo "                               Can be combined with --resolve (reply first, then resolve)"
      echo "  --bulk                        Apply action to all filtered comments (requires --hide)"
      echo ""
      echo "Action Options:"
      echo "  --reason <reason>             Reason for hiding (used with --hide)"
      echo "                               Must be one of the valid reasons from GitHub API"
      echo "                               Use --get-hide-reasons to see available options"
      echo "                               (prompts if not provided or invalid)"
      echo "  --get-hide-reasons            Display valid hide reason options from GitHub API"
      echo "  --no-prompt                   Skip interactive prompts (fail if required info missing)"
      echo ""
      echo "  -h, --help                    Show this help message"
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

# Auto-detect PR from current branch if not provided
if [ -z "$PULL_REQUEST" ] && [ -z "$COMMENT_URL" ] && [ -z "$COMMENT_ID" ]; then
  CURRENT_BRANCH=$(git branch --show-current 2>/dev/null || git rev-parse --abbrev-ref HEAD 2>/dev/null)
  if [ -n "$CURRENT_BRANCH" ]; then
    DETECTED_PR=$(gh pr view --json number -q .number 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$DETECTED_PR" ] && [ "$DETECTED_PR" != "null" ]; then
      PULL_REQUEST="$DETECTED_PR"
      if [ -z "$JSON_OUTPUT" ]; then
        echo "Auto-detected PR #${PULL_REQUEST} from current branch: ${CURRENT_BRANCH}"
      fi
    fi
  fi
fi

# Validation functions
# Cache for valid hide reasons (fetched from API)
VALID_HIDE_REASONS=""
VALID_HIDE_REASONS_GRAPHQL=""

# Function to build suggested command based on current arguments
build_suggested_command() {
  local cmd="$0"
  
  # Add PR number if available
  if [ -n "$PULL_REQUEST" ]; then
    cmd="$cmd -pr $PULL_REQUEST"
  fi
  
  # Add comment ID if available
  if [ -n "$COMMENT_ID" ]; then
    cmd="$cmd -c $COMMENT_ID"
  fi
  
  # Add comment type
  if [ -n "$COMMENT_TYPE" ] && [ "$COMMENT_TYPE" != "all" ]; then
    cmd="$cmd -t $COMMENT_TYPE"
  fi
  
  # Add user filter
  if [ -n "$USER_FILTER" ] && [ "$USER_FILTER" != "all" ]; then
    if [ "$USER_FILTER" = "bots" ]; then
      cmd="$cmd --bots"
    elif [ "$USER_FILTER" = "humans" ]; then
      cmd="$cmd --humans"
    fi
  fi
  
  # Add path filter
  if [ -n "$PATH_FILTER" ]; then
    cmd="$cmd -p \"$PATH_FILTER\""
  fi
  
  # Add body contains string filter
  if [ -n "$BODY_CONTAINS_STRING" ]; then
    cmd="$cmd --body-contains-string \"$BODY_CONTAINS_STRING\""
  fi
  
  # Add show resolved
      if [ -n "$SHOW_HIDDEN" ]; then
        cmd="$cmd --show-hidden"
      fi
  
  # Add actions
  if [ -n "$ACTION_HIDE" ]; then
    cmd="$cmd --hide"
  fi
  if [ -n "$ACTION_RESOLVE" ]; then
    cmd="$cmd --resolve"
  fi
  if [ -n "$ACTION_REPLY" ]; then
    if [ -n "$REPLY_TEXT" ]; then
      # Escape quotes in reply text
      local escaped_reply=$(echo "$REPLY_TEXT" | sed "s/\"/\\\\\"/g")
      cmd="$cmd --reply \"$escaped_reply\""
    else
      cmd="$cmd --reply"
    fi
  fi
  
  # Add bulk flag
  if [ -n "$BULK_MODE" ]; then
    cmd="$cmd --bulk"
  fi
  
  # Add reason if provided
  if [ -n "$1" ]; then
    cmd="$cmd --reason $1"
  elif [ -n "$HIDE_REASON" ]; then
    cmd="$cmd --reason $HIDE_REASON"
  fi
  
  # Add JSON output
  if [ -n "$JSON_OUTPUT" ]; then
    cmd="$cmd --json"
  fi
  
  echo "$cmd"
}

fetch_valid_hide_reasons() {
  # Use GraphQL introspection to get enum values
  # Try ReportedContentClassifiers first (used by hideIssueComment)
  local introspection_query="{
    __type(name: \"ReportedContentClassifiers\") {
      enumValues {
        name
      }
    }
  }"
  
  local result
  result=$(gh api graphql -f query="$introspection_query" 2>/dev/null)
  local exit_code=$?
  
  if [ $exit_code -eq 0 ] && [ -n "$result" ]; then
    # Check for errors in response
    if echo "$result" | jq -e '.errors' >/dev/null 2>&1; then
      # Try alternative enum name if first one fails
      introspection_query="{
        __type(name: \"ReportedContentClassifiers\") {
          enumValues {
            name
          }
        }
      }"
      result=$(gh api graphql -f query="$introspection_query" 2>/dev/null)
      exit_code=$?
    fi
    
    if [ $exit_code -eq 0 ] && [ -n "$result" ] && ! echo "$result" | jq -e '.errors' >/dev/null 2>&1; then
      # Store GraphQL enum values (UPPER_SNAKE_CASE)
      VALID_HIDE_REASONS_GRAPHQL=$(echo "$result" | jq -r '
        .data.__type.enumValues[]?.name // empty |
        select(. != null and . != "")
      ' 2>/dev/null | tr '\n' '|' | sed 's/|$//' 2>/dev/null)
      
      # Extract enum values and convert GraphQL enum format to API format
      # GraphQL uses UPPER_SNAKE_CASE, API expects lowercase-kebab-case
      # Use jq to transform and join with pipes
      VALID_HIDE_REASONS=$(echo "$result" | jq -r '
        .data.__type.enumValues[]?.name // empty |
        select(. != null and . != "") |
        (ascii_downcase | gsub("_"; "-"))
      ' 2>/dev/null | tr '\n' '|' | sed 's/|$//' 2>/dev/null)
      
      # If we got valid results, return success
      if [ -n "$VALID_HIDE_REASONS" ] && [ "$VALID_HIDE_REASONS" != "null" ] && [ "$VALID_HIDE_REASONS" != "" ]; then
        return 0
      fi
    fi
  fi
  
  # API call failed or returned invalid data
  echo "Error: Failed to fetch valid hide reasons from GitHub API" >&2
  return 1
}

convert_reason_to_graphql() {
  local api_reason="$1"
  
  # Fetch reasons if not already cached
  if [ -z "$VALID_HIDE_REASONS" ] || [ -z "$VALID_HIDE_REASONS_GRAPHQL" ]; then
    if ! fetch_valid_hide_reasons; then
      echo "Error: Could not fetch valid hide reasons from GitHub API" >&2
      return 1
    fi
  fi
  
  # Convert API format (lowercase-kebab-case) to GraphQL format (UPPER_SNAKE_CASE)
  # Match by position in the arrays
  local IFS='|'
  local api_reasons_list
  local graphql_reasons_list
  api_reasons_list=$VALID_HIDE_REASONS
  graphql_reasons_list=$VALID_HIDE_REASONS_GRAPHQL
  
  local i=1
  for api_reason_item in $api_reasons_list; do
    if [ "$api_reason" = "$api_reason_item" ]; then
      # Found matching API reason, get corresponding GraphQL value
      local j=1
      for graphql_reason_item in $graphql_reasons_list; do
        if [ "$i" -eq "$j" ]; then
          echo "$graphql_reason_item"
          return 0
        fi
        j=$((j + 1))
      done
    fi
    i=$((i + 1))
  done
  
  # If not found, try direct conversion as fallback
  echo "$api_reason" | tr '[:lower:]' '[:upper:]' | tr '-' '_'
  return 0
}

validate_hide_reason() {
  local reason="$1"
  
  # Fetch reasons if not already cached
  if [ -z "$VALID_HIDE_REASONS" ]; then
    if ! fetch_valid_hide_reasons; then
      return 1
    fi
  fi
  
  # Check if reason matches any valid reason (case-insensitive)
  local reason_lower
  reason_lower=$(echo "$reason" | tr '[:upper:]' '[:lower:]')
  
  # Convert pipe-separated string to check each reason
  local IFS='|'
  for valid_reason in $VALID_HIDE_REASONS; do
    if [ "$reason_lower" = "$valid_reason" ]; then
      return 0
    fi
  done
  
  return 1
}

prompt_for_reason() {
  # Fetch reasons if not already cached
  if [ -z "$VALID_HIDE_REASONS" ]; then
    if ! fetch_valid_hide_reasons; then
      echo "Error: Could not fetch valid hide reasons from GitHub API" >&2
      return 1
    fi
  fi
  
  # Convert pipe-separated string to array and display
  local IFS='|'
  local reasons_list
  reasons_list=$VALID_HIDE_REASONS
  
  echo "" >&2
  echo "Select a reason for hiding the comment:" >&2
  local i=1
  local selected_reason=""
  for reason in $reasons_list; do
    echo "  $i) $reason" >&2
    if [ "$i" -eq 1 ]; then
      # Store first reason to initialize
      selected_reason="$reason"
    fi
    i=$((i + 1))
  done
  
  local max_choice=$((i - 1))
  echo -n "Enter number (1-$max_choice): " >&2
  if [ -t 0 ]; then
    read -r choice
  else
    read -r choice < /dev/tty
  fi
  
  # Validate choice is a number and within range
  if ! [[ "$choice" =~ ^[0-9]+$ ]] || [ "$choice" -lt 1 ] || [ "$choice" -gt "$max_choice" ]; then
    echo "Error: Invalid selection" >&2
    return 1
  fi
  
  # Find and return the selected reason
  i=1
  for reason in $reasons_list; do
    if [ "$i" -eq "$choice" ]; then
      # Show the complete command the user could have run
      if [ -z "$JSON_OUTPUT" ]; then
        SUGGESTED_CMD=$(build_suggested_command "$reason")
        echo "" >&2
        EFFICIENCY_TIP="Tip: For faster execution next time, use: $SUGGESTED_CMD"
      fi
      echo "$reason"
      return 0
    fi
    i=$((i + 1))
  done
  
  echo "Error: Could not find selected reason" >&2
  return 1
}

prompt_for_reply() {
  echo -n "Enter reply text: "
  read -r reply
  echo "$reply"
}

# Validate comment type
case "$COMMENT_TYPE" in
  all|review|issue)
    ;;
  *)
    echo "Error: Invalid comment type '${COMMENT_TYPE}'. Must be one of: all, review, issue"
    exit 1
    ;;
esac

# Validate user filter
case "$USER_FILTER" in
  bots|humans|all)
    ;;
  *)
    echo "Error: Invalid user filter '${USER_FILTER}'. Must be one of: bots, humans, all"
    exit 1
    ;;
esac

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

# Handle --get-hide-reasons option
if [ -n "$GET_HIDE_REASONS" ]; then
  echo "Fetching valid hide reasons from GitHub API..."
  echo ""
  if fetch_valid_hide_reasons; then
    echo "Valid hide reasons:"
    IFS_SAVE="$IFS"
    IFS='|'
    reasons_list=$VALID_HIDE_REASONS
    i=1
    for reason in $reasons_list; do
      echo "  $i) $reason"
      i=$((i + 1))
    done
    IFS="$IFS_SAVE"
    echo ""
    echo "These values can be used with --reason when using --hide"
  else
    echo "Error: Could not fetch valid hide reasons from GitHub API" >&2
    exit 1
  fi
  exit 0
fi

# Initialize ALL_COMMENTS to empty array
ALL_COMMENTS="[]"
# Initialize filter totals (used in summary)
REVIEW_TOTAL_BEFORE_FILTER=0
ISSUE_TOTAL_BEFORE_FILTER=0

# If URL is provided, extract comment ID (and optionally fetch that specific comment)
if [ -n "$COMMENT_URL" ]; then
  # Parse URL to extract comment ID
  # URLs can be in formats like:
  # https://github.com/owner/repo/pull/PR_NUMBER#discussion_rCOMMENT_ID (review comment)
  # https://github.com/owner/repo/pull/PR_NUMBER#issuecomment-COMMENT_ID (issue comment)
  # https://github.com/owner/repo/pull/PR_NUMBER (just PR, will need to list all)
  
  if echo "$COMMENT_URL" | grep -q "#discussion_r"; then
    # Review comment
    EXTRACTED_COMMENT_ID=$(echo "$COMMENT_URL" | sed -E 's/.*#discussion_r([0-9]+)/\1/')
    PR_NUM=$(echo "$COMMENT_URL" | sed -E 's/.*\/pull\/([0-9]+).*/\1/')
    
    if [ -n "$EXTRACTED_COMMENT_ID" ] && [ -n "$PR_NUM" ]; then
      # If COMMENT_ID not set and action is specified, use extracted ID
      if [ -z "$COMMENT_ID" ] && { [ -n "$ACTION_HIDE" ] || [ -n "$ACTION_RESOLVE" ] || [ -n "$ACTION_REPLY" ]; }; then
        COMMENT_ID="$EXTRACTED_COMMENT_ID"
      fi
      
      # Only fetch comment if not performing an action (actions will fetch it themselves)
      if [ -z "$ACTION_HIDE" ] && [ -z "$ACTION_RESOLVE" ] && [ -z "$ACTION_REPLY" ]; then
        if [ -z "$JSON_OUTPUT" ]; then
          echo "Fetching review comment #${EXTRACTED_COMMENT_ID} from PR #${PR_NUM}"
        fi
        COMMENT=$(gh api "repos/${REPO}/pulls/comments/${EXTRACTED_COMMENT_ID}" 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$COMMENT" ]; then
          COMMENT_WITH_TYPE=$(echo "$COMMENT" | jq '. + {type: "review"}' 2>/dev/null)
          if [ $? -eq 0 ] && [ -n "$COMMENT_WITH_TYPE" ]; then
            ALL_COMMENTS="[$COMMENT_WITH_TYPE]"
          else
            echo "Error: Could not process comment #${EXTRACTED_COMMENT_ID}"
            exit 1
          fi
        else
          echo "Error: Could not fetch comment #${EXTRACTED_COMMENT_ID}"
          exit 1
        fi
      fi
    else
      echo "Error: Could not parse review comment ID from URL: $COMMENT_URL"
      exit 1
    fi
  elif echo "$COMMENT_URL" | grep -q "#issuecomment-"; then
    # Issue comment
    EXTRACTED_COMMENT_ID=$(echo "$COMMENT_URL" | sed -E 's/.*#issuecomment-([0-9]+)/\1/')
    PR_NUM=$(echo "$COMMENT_URL" | sed -E 's/.*\/pull\/([0-9]+).*/\1/')
    
    if [ -n "$EXTRACTED_COMMENT_ID" ] && [ -n "$PR_NUM" ]; then
      # If COMMENT_ID not set and action is specified, use extracted ID
      if [ -z "$COMMENT_ID" ] && { [ -n "$ACTION_HIDE" ] || [ -n "$ACTION_RESOLVE" ] || [ -n "$ACTION_REPLY" ]; }; then
        COMMENT_ID="$EXTRACTED_COMMENT_ID"
      fi
      
      # Only fetch comment if not performing an action (actions will fetch it themselves)
      if [ -z "$ACTION_HIDE" ] && [ -z "$ACTION_RESOLVE" ] && [ -z "$ACTION_REPLY" ]; then
        if [ -z "$JSON_OUTPUT" ]; then
          echo "Fetching issue comment #${EXTRACTED_COMMENT_ID} from PR #${PR_NUM}"
        fi
        COMMENT=$(gh api "repos/${REPO}/issues/comments/${EXTRACTED_COMMENT_ID}" 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$COMMENT" ]; then
          # Map REST API fields to match GraphQL format
          COMMENT_WITH_TYPE=$(echo "$COMMENT" | jq '
            . + {
              type: "issue",
              isMinimized: (if .hidden == true then true else false end),
              minimizedReason: (if .hidden_reason then (.hidden_reason | ascii_downcase | gsub("_"; "-")) else null end)
            }
          ' 2>/dev/null)
          if [ $? -eq 0 ] && [ -n "$COMMENT_WITH_TYPE" ]; then
            ALL_COMMENTS="[$COMMENT_WITH_TYPE]"
          else
            echo "Error: Could not process comment #${EXTRACTED_COMMENT_ID}"
            exit 1
          fi
        else
          echo "Error: Could not fetch comment #${EXTRACTED_COMMENT_ID}"
          exit 1
        fi
      fi
    else
      echo "Error: Could not parse issue comment ID from URL: $COMMENT_URL"
      exit 1
    fi
  elif echo "$COMMENT_URL" | grep -q "/pull/"; then
    # Just a PR URL, extract PR number and list all comments
    PULL_REQUEST=$(echo "$COMMENT_URL" | sed -E 's/.*\/pull\/([0-9]+).*/\1/')
    if [ -z "$PULL_REQUEST" ]; then
      echo "Error: Could not parse PR number from URL: $COMMENT_URL"
      exit 1
    fi
    if [ -z "$JSON_OUTPUT" ]; then
      echo "Extracted PR #${PULL_REQUEST} from URL, fetching all comments..."
    fi
  else
    echo "Error: Invalid comment URL format: $COMMENT_URL"
    echo "Expected format: https://github.com/owner/repo/pull/PR_NUMBER#discussion_rCOMMENT_ID"
    echo "              or: https://github.com/owner/repo/pull/PR_NUMBER#issuecomment-COMMENT_ID"
    exit 1
  fi
fi

# If we have a PR number (from -pr flag or extracted from URL), fetch all comments
# Condition: PR is set AND (no URL provided OR URL is just a PR URL without comment anchor)
# Exception: If both -pr and -c are provided, fetch just that comment via GraphQL (skip REST call)
SHOULD_FETCH_PR=false
if [ -n "$PULL_REQUEST" ]; then
  # If both PR and COMMENT_ID are provided (without action), fetch just that comment via GraphQL
  if [ -n "$COMMENT_ID" ] && [ -z "$ACTION_HIDE" ] && [ -z "$ACTION_RESOLVE" ] && [ -z "$ACTION_REPLY" ]; then
    if [ -z "$JSON_OUTPUT" ]; then
      echo "Fetching comment #${COMMENT_ID} from PR #${PULL_REQUEST}..."
    fi
    
    OWNER=$(echo "$REPO" | cut -d'/' -f1)
    REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
    COMMENT_WITH_TYPE=""
    
    # Try as review comment first
    REVIEW_QUERY="{
      repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
        pullRequest(number: $PULL_REQUEST) {
          reviewThreads(first: 100) {
            nodes {
              comments(first: 100) {
                nodes {
                  databaseId
                  id
                  bodyText
                  path
                  line
                  diffHunk
                  createdAt
                  updatedAt
                  author {
                    login
                    ... on Bot {
                      id
                    }
                  }
                  url
                }
              }
            }
          }
        }
      }
    }"
    REVIEW_DATA=$(gh api graphql -f query="$REVIEW_QUERY" 2>/dev/null)
    if [ $? -eq 0 ] && [ -n "$REVIEW_DATA" ]; then
      COMMENT_WITH_TYPE=$(echo "$REVIEW_DATA" | jq --arg id "$COMMENT_ID" --arg pr "$PULL_REQUEST" --arg owner "$OWNER" --arg repo "$REPO_NAME" '
        .data.repository.pullRequest.reviewThreads.nodes[].comments.nodes[] |
        select(.databaseId == ($id | tonumber)) |
        {
          id: .databaseId,
          node_id: .id,
          body: .bodyText,
          path: .path,
          line: .line,
          diff_hunk: .diffHunk,
          created_at: .createdAt,
          updated_at: .updatedAt,
          user: {
            login: .author.login,
            type: (if (.author | has("id")) then "Bot" else "User" end)
          },
          html_url: ("https://github.com/\($owner)/\($repo)/pull/\($pr)#discussion_r\(.databaseId)"),
          url: .url,
          type: "review"
        }
      ' 2>/dev/null)
      if [ -n "$COMMENT_WITH_TYPE" ] && [ "$COMMENT_WITH_TYPE" != "null" ]; then
        ALL_COMMENTS="[$COMMENT_WITH_TYPE]"
        SHOULD_FETCH_PR=false
      else
        COMMENT_WITH_TYPE=""
      fi
    fi
    
    # If not found as review comment, try as issue comment
    if [ -z "$COMMENT_WITH_TYPE" ] || [ "$COMMENT_WITH_TYPE" = "null" ]; then
      ISSUE_QUERY="{
        repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
          pullRequest(number: $PULL_REQUEST) {
            comments(first: 100) {
              nodes {
                databaseId
                id
                bodyText
                createdAt
                updatedAt
                author {
                  login
                  ... on Bot {
                    id
                  }
                }
                url
                isMinimized
                minimizedReason
              }
            }
          }
        }
      }"
      ISSUE_DATA=$(gh api graphql -f query="$ISSUE_QUERY" 2>/dev/null)
      if [ $? -eq 0 ] && [ -n "$ISSUE_DATA" ]; then
        COMMENT_WITH_TYPE=$(echo "$ISSUE_DATA" | jq --arg id "$COMMENT_ID" --arg pr "$PULL_REQUEST" --arg owner "$OWNER" --arg repo "$REPO_NAME" '
          .data.repository.pullRequest.comments.nodes[] |
          select(.databaseId == ($id | tonumber)) |
          {
            id: .databaseId,
            node_id: .id,
            body: .bodyText,
            created_at: .createdAt,
            updated_at: .updatedAt,
            user: {
              login: .author.login,
              type: (if (.author | has("id")) then "Bot" else "User" end)
            },
            html_url: ("https://github.com/\($owner)/\($repo)/pull/\($pr)#issuecomment-\(.databaseId)"),
            url: .url,
            isMinimized: (if .isMinimized then true else false end),
            minimizedReason: (if .minimizedReason then (.minimizedReason | ascii_downcase | gsub("_"; "-")) else null end),
            type: "issue"
          }
        ' 2>/dev/null)
        if [ -n "$COMMENT_WITH_TYPE" ] && [ "$COMMENT_WITH_TYPE" != "null" ]; then
          ALL_COMMENTS="[$COMMENT_WITH_TYPE]"
          SHOULD_FETCH_PR=false
        else
          echo "Error: Comment #${COMMENT_ID} not found in PR #${PULL_REQUEST}" >&2
          exit 1
        fi
      else
        echo "Error: Failed to fetch comment via GraphQL" >&2
        exit 1
      fi
    fi
  elif [ -z "$COMMENT_URL" ]; then
    SHOULD_FETCH_PR=true
  elif echo "$COMMENT_URL" | grep -q "/pull/" && ! echo "$COMMENT_URL" | grep -q "#"; then
    SHOULD_FETCH_PR=true
  fi
fi

if [ "$SHOULD_FETCH_PR" = "true" ]; then
  # Skip fetching comments if we're only performing actions (no listing needed)
  # Exception: Always fetch when bulk mode is enabled (needs comments to filter)
  SHOULD_FETCH_COMMENTS=false
  if [ -n "$BULK_MODE" ]; then
    SHOULD_FETCH_COMMENTS=true
  elif [ -z "$ACTION_HIDE" ] && [ -z "$ACTION_RESOLVE" ] && [ -z "$ACTION_REPLY" ]; then
    SHOULD_FETCH_COMMENTS=true
  fi
  
  if [ "$SHOULD_FETCH_COMMENTS" = "true" ]; then
    if [ -z "$JSON_OUTPUT" ]; then
      echo "Fetching comments for PR #${PULL_REQUEST} in ${REPO}"
    fi
  
    # Extract owner and repo from REPO variable for GraphQL queries
  OWNER=$(echo "$REPO" | cut -d'/' -f1)
  REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
  
  # Fetch comments using GraphQL for consistency
  REVIEW_COMMENTS="[]"
  ISSUE_COMMENTS="[]"
  
  # Build GraphQL query to fetch both review comments and issue comments
  if [ "$COMMENT_TYPE" = "all" ] || [ "$COMMENT_TYPE" = "review" ] || [ "$COMMENT_TYPE" = "issue" ]; then
    # GraphQL query to get review threads (with resolved status) and issue comments
    GRAPHQL_QUERY="{
      repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
        pullRequest(number: $PULL_REQUEST) {
          reviewThreads(first: 100) {
            nodes {
              isResolved
              comments(first: 100) {
                nodes {
                  id
                  databaseId
                  bodyText
                  path
                  line
                  diffHunk
                  createdAt
                  updatedAt
                  author {
                    login
                    ... on Bot {
                      id
                    }
                  }
                  url
                }
              }
            }
          }
          comments(first: 100) {
            nodes {
              id
              databaseId
              bodyText
              createdAt
              updatedAt
              author {
                login
                ... on Bot {
                  id
                }
              }
              url
              isMinimized
              minimizedReason
            }
          }
        }
      }
    }"
    
    GRAPHQL_RESPONSE=$(gh api graphql -f query="$GRAPHQL_QUERY" 2>&1)
    API_EXIT_CODE=$?
    
    if [ $API_EXIT_CODE -ne 0 ] || [ -z "$GRAPHQL_RESPONSE" ]; then
      echo "Warning: Failed to fetch comments via GraphQL (exit code: $API_EXIT_CODE)"
      if [ -n "$GRAPHQL_RESPONSE" ]; then
        echo "Error details: $GRAPHQL_RESPONSE" | head -3
      fi
    else
      # Validate it's valid JSON
      if ! echo "$GRAPHQL_RESPONSE" | jq empty 2>/dev/null; then
        echo "Warning: Invalid JSON received from GraphQL"
      else
        # Extract review comments from review threads and flatten into array
        # Also add resolved status and transform to match REST API format
        if [ "$COMMENT_TYPE" = "all" ] || [ "$COMMENT_TYPE" = "review" ]; then
          REVIEW_COMMENTS=$(echo "$GRAPHQL_RESPONSE" | jq --arg pr "$PULL_REQUEST" --arg owner "$OWNER" --arg repo "$REPO_NAME" '
            .data.repository.pullRequest.reviewThreads.nodes[] |
            .isResolved as $resolved |
            .comments.nodes[] |
            {
              id: .databaseId,
              node_id: .id,
              body: .bodyText,
              path: .path,
              line: .line,
              diff_hunk: .diffHunk,
              created_at: .createdAt,
              updated_at: .updatedAt,
              user: {
                login: .author.login,
                type: (if (.author | has("id")) then "Bot" else "User" end)
              },
              html_url: ("https://github.com/\($owner)/\($repo)/pull/\($pr)#discussion_r\(.databaseId)"),
              url: .url,
              isResolved: $resolved
            }
          ' 2>/dev/null | jq -s '.' 2>/dev/null || echo "[]")
          
          REVIEW_COUNT_TOTAL=$(echo "$REVIEW_COMMENTS" | jq 'length' 2>/dev/null || echo "0")
          if [ -z "$JSON_OUTPUT" ]; then
            echo "Found $REVIEW_COUNT_TOTAL review comment(s)"
          fi
        fi
        
        # Extract issue comments
        if [ "$COMMENT_TYPE" = "all" ] || [ "$COMMENT_TYPE" = "issue" ]; then
          # Note: GitHub GraphQL API doesn't support replyTo field for issue comments
          # Replies would need to be identified through other means (e.g., REST API or content analysis)
          ISSUE_COMMENTS=$(echo "$GRAPHQL_RESPONSE" | jq --arg pr "$PULL_REQUEST" --arg owner "$OWNER" --arg repo "$REPO_NAME" '
            .data.repository.pullRequest.comments.nodes[] |
            {
              id: .databaseId,
              node_id: .id,
              body: .bodyText,
              created_at: .createdAt,
              updated_at: .updatedAt,
              user: {
                login: .author.login,
                type: (if (.author | has("id")) then "Bot" else "User" end)
              },
              html_url: ("https://github.com/\($owner)/\($repo)/pull/\($pr)#issuecomment-\(.databaseId)"),
              url: .url,
              isMinimized: (if .isMinimized then true else false end),
              minimizedReason: (if .minimizedReason then (.minimizedReason | ascii_downcase | gsub("_"; "-")) else null end),
              replies: []
            }
          ' 2>/dev/null | jq -s '.' 2>/dev/null || echo "[]")
          
          ISSUE_COUNT_TOTAL=$(echo "$ISSUE_COMMENTS" | jq 'length' 2>/dev/null || echo "0")
          if [ -z "$JSON_OUTPUT" ]; then
            echo "Found $ISSUE_COUNT_TOTAL issue comment(s)"
          fi
        fi
      fi
    fi
  fi
  
  # Filter and combine comments
  ALL_COMMENTS="[]"
  
  # Track totals before filtering for summary display
  REVIEW_TOTAL_BEFORE_FILTER=0
  ISSUE_TOTAL_BEFORE_FILTER=0
  if [ -n "$REVIEW_COMMENTS" ] && [ "$REVIEW_COMMENTS" != "[]" ]; then
    REVIEW_TOTAL_BEFORE_FILTER=$(echo "$REVIEW_COMMENTS" | jq 'length' 2>/dev/null || echo "0")
  fi
  if [ -n "$ISSUE_COMMENTS" ] && [ "$ISSUE_COMMENTS" != "[]" ]; then
    ISSUE_TOTAL_BEFORE_FILTER=$(echo "$ISSUE_COMMENTS" | jq 'length' 2>/dev/null || echo "0")
  fi
  
  if [ "$COMMENT_TYPE" = "all" ] || [ "$COMMENT_TYPE" = "review" ]; then
    if [ -n "$REVIEW_COMMENTS" ] && [ "$REVIEW_COMMENTS" != "[]" ]; then
      if [ -n "$PATH_FILTER" ] && [ -n "$SHOW_HIDDEN" ]; then
        REVIEW_FILTERED=$(echo "$REVIEW_COMMENTS" | jq --arg filter "$USER_FILTER" --arg path "$PATH_FILTER" --arg body_str "$BODY_CONTAINS_STRING" '
          [.[] | 
            if $filter == "bots" then select(.user.type == "Bot")
            elif $filter == "humans" then select(.user.type != "Bot")
            else .
            end |
            select(.path == $path) |
            if $body_str != "" then select((.body // "") | contains($body_str)) else . end |
            . + {type: "review"}]
        ' 2>/dev/null)
      elif [ -n "$PATH_FILTER" ] && [ -z "$SHOW_HIDDEN" ]; then
        REVIEW_FILTERED=$(echo "$REVIEW_COMMENTS" | jq --arg filter "$USER_FILTER" --arg path "$PATH_FILTER" --arg body_str "$BODY_CONTAINS_STRING" '
          [.[] | 
            if $filter == "bots" then select(.user.type == "Bot")
            elif $filter == "humans" then select(.user.type != "Bot")
            else .
            end |
            select(.path == $path) |
            select(.isResolved != true) |
            if $body_str != "" then select((.body // "") | contains($body_str)) else . end |
            . + {type: "review"}]
        ' 2>/dev/null)
      elif [ -n "$SHOW_HIDDEN" ]; then
        REVIEW_FILTERED=$(echo "$REVIEW_COMMENTS" | jq --arg filter "$USER_FILTER" --arg body_str "$BODY_CONTAINS_STRING" '
          [.[] | 
            if $filter == "bots" then select(.user.type == "Bot")
            elif $filter == "humans" then select(.user.type != "Bot")
            else .
            end |
            if $body_str != "" then select((.body // "") | contains($body_str)) else . end |
            . + {type: "review"}]
        ' 2>/dev/null)
      else
        REVIEW_FILTERED=$(echo "$REVIEW_COMMENTS" | jq --arg filter "$USER_FILTER" --arg body_str "$BODY_CONTAINS_STRING" '
          [.[] | 
            if $filter == "bots" then select(.user.type == "Bot")
            elif $filter == "humans" then select(.user.type != "Bot")
            else .
            end |
            select(.isResolved != true) |
            if $body_str != "" then select((.body // "") | contains($body_str)) else . end |
            . + {type: "review"}]
        ' 2>/dev/null)
      fi
      if [ $? -eq 0 ] && [ -n "$REVIEW_FILTERED" ]; then
        FILTERED_COUNT=$(echo "$REVIEW_FILTERED" | jq 'length' 2>/dev/null || echo "0")
        if [ "$FILTERED_COUNT" -gt 0 ]; then
          ALL_COMMENTS=$(echo "$ALL_COMMENTS" | jq --argjson reviews "$REVIEW_FILTERED" '. + $reviews' 2>/dev/null)
          if [ $? -ne 0 ] || [ -z "$ALL_COMMENTS" ]; then
            echo "Warning: Failed to merge review comments into result"
            ALL_COMMENTS="[]"
          fi
        fi
      else
        echo "Warning: Failed to filter review comments"
      fi
    fi
  fi
  
  if [ "$COMMENT_TYPE" = "all" ] || [ "$COMMENT_TYPE" = "issue" ]; then
    if [ -n "$ISSUE_COMMENTS" ] && [ "$ISSUE_COMMENTS" != "[]" ]; then
      if [ -n "$SHOW_HIDDEN" ]; then
        ISSUE_FILTERED=$(echo "$ISSUE_COMMENTS" | jq --arg filter "$USER_FILTER" --arg body_str "$BODY_CONTAINS_STRING" '
          [.[] | 
            if $filter == "bots" then select(.user.type == "Bot")
            elif $filter == "humans" then select(.user.type != "Bot")
            else .
            end |
            if $body_str != "" then select((.bodyText // .body // "") | contains($body_str)) else . end |
            . + {type: "issue"}]
        ' 2>/dev/null)
      else
        ISSUE_FILTERED=$(echo "$ISSUE_COMMENTS" | jq --arg filter "$USER_FILTER" --arg body_str "$BODY_CONTAINS_STRING" '
          [.[] | 
            if $filter == "bots" then select(.user.type == "Bot")
            elif $filter == "humans" then select(.user.type != "Bot")
            else .
            end |
            select(.isMinimized != true) |
            if $body_str != "" then select((.bodyText // .body // "") | contains($body_str)) else . end |
            . + {type: "issue"}]
        ' 2>/dev/null)
      fi
      if [ $? -eq 0 ] && [ -n "$ISSUE_FILTERED" ]; then
        FILTERED_COUNT=$(echo "$ISSUE_FILTERED" | jq 'length' 2>/dev/null || echo "0")
        if [ "$FILTERED_COUNT" -gt 0 ]; then
          ALL_COMMENTS=$(echo "$ALL_COMMENTS" | jq --argjson issues "$ISSUE_FILTERED" '. + $issues' 2>/dev/null)
          if [ $? -ne 0 ] || [ -z "$ALL_COMMENTS" ]; then
            echo "Warning: Failed to merge issue comments into result"
            ALL_COMMENTS="[]"
          fi
        fi
      else
        echo "Warning: Failed to filter issue comments"
      fi
    fi
  fi
  fi
elif [ -z "$PULL_REQUEST" ] && [ -z "$COMMENT_URL" ]; then
  # Only require PR/URL if we're not doing an action (hide/resolve/reply) and no comment ID for viewing
  if [ -z "$ACTION_HIDE" ] && [ -z "$ACTION_RESOLVE" ] && [ -z "$ACTION_REPLY" ]; then
    # If COMMENT_ID is provided without an action, try to fetch and display the comment
    if [ -n "$COMMENT_ID" ]; then
      if [ -z "$JSON_OUTPUT" ]; then
        echo "Fetching comment #${COMMENT_ID}..."
      fi
      
      # Try to fetch as review comment first
      COMMENT=$(gh api "repos/${REPO}/pulls/comments/${COMMENT_ID}" 2>/dev/null)
      if [ $? -eq 0 ] && [ -n "$COMMENT" ]; then
        COMMENT_WITH_TYPE=$(echo "$COMMENT" | jq '. + {type: "review"}' 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$COMMENT_WITH_TYPE" ]; then
          ALL_COMMENTS="[$COMMENT_WITH_TYPE]"
        else
          echo "Error: Could not process comment #${COMMENT_ID}"
          exit 1
        fi
      else
        # Try as issue comment - use REST API only to get PR number, then GraphQL for everything
        COMMENT_REST=$(gh api "repos/${REPO}/issues/comments/${COMMENT_ID}" 2>/dev/null)
        if [ $? -eq 0 ] && [ -n "$COMMENT_REST" ]; then
          # Get PR number from comment (minimal REST call just for PR number)
          PR_NUM=$(echo "$COMMENT_REST" | jq -r '.issue_url // ""' 2>/dev/null | sed -E 's|.*/issues/([0-9]+).*|\1|' 2>/dev/null)
          if [ -z "$PR_NUM" ] || [ "$PR_NUM" = "null" ]; then
            PR_NUM=$(echo "$COMMENT_REST" | jq -r '.pull_request_url // ""' 2>/dev/null | sed -E 's|.*/pulls/([0-9]+).*|\1|' 2>/dev/null)
          fi
          
          # Suggest more efficient command if PR number was found
          if [ -n "$PR_NUM" ] && [ "$PR_NUM" != "null" ] && [ "$PR_NUM" != "" ]; then
            if [ -z "$JSON_OUTPUT" ]; then
              # Temporarily set PULL_REQUEST to build the suggested command
              OLD_PULL_REQUEST="$PULL_REQUEST"
              PULL_REQUEST="$PR_NUM"
              SUGGESTED_CMD=$(build_suggested_command)
              PULL_REQUEST="$OLD_PULL_REQUEST"
              EFFICIENCY_TIP="Tip: For faster response, use: $SUGGESTED_CMD"
            fi
            # Fetch everything via GraphQL (including minimized status)
            OWNER=$(echo "$REPO" | cut -d'/' -f1)
            REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
            COMMENT_QUERY="{
              repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
                pullRequest(number: $PR_NUM) {
                  comments(first: 100) {
                    nodes {
                      databaseId
                      id
                      bodyText
                      createdAt
                      updatedAt
                      author {
                        login
                        ... on Bot {
                          id
                        }
                      }
                      url
                      isMinimized
                      minimizedReason
                    }
                  }
                }
              }
            }"
            COMMENT_DATA=$(gh api graphql -f query="$COMMENT_QUERY" 2>/dev/null)
            if [ $? -eq 0 ] && [ -n "$COMMENT_DATA" ]; then
              COMMENT_WITH_TYPE=$(echo "$COMMENT_DATA" | jq --arg id "$COMMENT_ID" --arg pr "$PR_NUM" --arg owner "$OWNER" --arg repo "$REPO_NAME" '
                .data.repository.pullRequest.comments.nodes[] |
                select(.databaseId == ($id | tonumber)) |
                {
                  id: .databaseId,
                  node_id: .id,
                  body: .bodyText,
                  created_at: .createdAt,
                  updated_at: .updatedAt,
                  user: {
                    login: .author.login,
                    type: (if (.author | has("id")) then "Bot" else "User" end)
                  },
                  html_url: ("https://github.com/\($owner)/\($repo)/pull/\($pr)#issuecomment-\(.databaseId)"),
                  url: .url,
                  isMinimized: (if .isMinimized then true else false end),
                  minimizedReason: (if .minimizedReason then (.minimizedReason | ascii_downcase | gsub("_"; "-")) else null end),
                  type: "issue"
                }
              ' 2>/dev/null)
              if [ -n "$COMMENT_WITH_TYPE" ] && [ "$COMMENT_WITH_TYPE" != "null" ]; then
                ALL_COMMENTS="[$COMMENT_WITH_TYPE]"
              else
                echo "Error: Comment #${COMMENT_ID} not found in PR #${PR_NUM}" >&2
                exit 1
              fi
            else
              echo "Error: Failed to fetch comment via GraphQL" >&2
              exit 1
            fi
          else
            echo "Error: Could not determine PR number for comment #${COMMENT_ID}" >&2
            exit 1
          fi
        else
          echo "Error: Could not fetch comment #${COMMENT_ID}"
          echo "The comment may not exist, or you may not have access to it."
          exit 1
        fi
      fi
    else
      echo "Error: Either pull request number (-pr), comment URL (-u), or -c/--comment-id is required"
      echo "Use -h or --help for usage information"
      exit 1
    fi
  fi
fi

# API Functions
hide_issue_comment() {
  local comment_id="$1"
  local reason="$2"
  local owner=$(echo "$REPO" | cut -d'/' -f1)
  local repo_name=$(echo "$REPO" | cut -d'/' -f2)
  
  # First, get the node ID for the comment
  local node_id
  node_id=$(gh api "repos/${REPO}/issues/comments/${comment_id}" 2>/dev/null | jq -r '.node_id // empty' 2>/dev/null)
  
  if [ -z "$node_id" ] || [ "$node_id" = "null" ]; then
    echo "Error: Could not fetch issue comment #${comment_id} or get node ID" >&2
    return 1
  fi
  
  # Execute GraphQL mutation using minimizeComment
  local mutation="mutation {
    minimizeComment(input: {subjectId: \"$node_id\", classifier: $reason}) {
      minimizedComment {
        isMinimized
      }
    }
  }"
  
  local result
  result=$(gh api graphql -f query="$mutation" 2>&1)
  local exit_code=$?
  
  if [ $exit_code -ne 0 ]; then
    echo "Error: Failed to hide comment: $result" >&2
    return 1
  fi
  
  # Check for errors in response
  if echo "$result" | jq -e '.errors' >/dev/null 2>&1; then
    echo "Error: $(echo "$result" | jq -r '.errors[0].message // "Unknown error"')" >&2
    return 1
  fi
  
  return 0
}

resolve_review_thread() {
  local thread_id="$1"
  
  # Execute GraphQL mutation
  local mutation="mutation {
    resolveReviewThread(input: {threadId: \"$thread_id\"}) {
      thread {
        isResolved
      }
    }
  }"
  
  local result
  result=$(gh api graphql -f query="$mutation" 2>&1)
  local exit_code=$?
  
  if [ $exit_code -ne 0 ]; then
    echo "Error: Failed to resolve thread: $result" >&2
    return 1
  fi
  
  # Check for errors in response
  if echo "$result" | jq -e '.errors' >/dev/null 2>&1; then
    echo "Error: $(echo "$result" | jq -r '.errors[0].message // "Unknown error"')" >&2
    return 1
  fi
  
  return 0
}

reply_to_review_comment() {
  local comment_id="$1"
  local reply_text="$2"
  local owner=$(echo "$REPO" | cut -d'/' -f1)
  local repo_name=$(echo "$REPO" | cut -d'/' -f2)
  
  # First, get the PR number and comment details
  local comment_data
  comment_data=$(gh api "repos/${REPO}/pulls/comments/${comment_id}" 2>/dev/null)
  local exit_code=$?
  
  if [ $exit_code -ne 0 ] || [ -z "$comment_data" ]; then
    echo "Error: Could not fetch review comment #${comment_id}" >&2
    return 1
  fi
  
  local pr_number
  pr_number=$(echo "$comment_data" | jq -r '.pull_request_url // ""' 2>/dev/null | sed -E 's|.*/pulls/([0-9]+).*|\1|' 2>/dev/null)
  
  if [ -z "$pr_number" ]; then
    echo "Error: Could not determine PR number from comment" >&2
    return 1
  fi
  
  # Post reply
  local reply_json
  reply_json=$(echo "{\"body\": $(echo "$reply_text" | jq -Rs .)}" 2>/dev/null)
  
  local result
  result=$(gh api "repos/${REPO}/pulls/${pr_number}/comments/${comment_id}/replies" \
    -X POST \
    -f body="$reply_text" 2>&1)
  local api_exit_code=$?
  
  if [ $api_exit_code -ne 0 ]; then
    echo "Error: Failed to post reply: $result" >&2
    return 1
  fi
  
  return 0
}

# Function to display a single comment (used after updates)
display_comment() {
  local comment_json="$1"
  local comment_type="$2"
  
  if [ -z "$comment_json" ] || [ "$comment_json" = "null" ]; then
    return 1
  fi
  
  COMMENT_ID=$(echo "$comment_json" | jq -r '.id // .databaseId // "N/A"')
  
  echo ""
  echo "Comment ID: $COMMENT_ID"
  echo "---"
  
  # Display comment details
  echo "$comment_json" | jq -r '
    "Type:              \((.type // "N/A") | ascii_upcase)
Author:            \(.user.login // .author.login // "N/A")
Author Type:       \(.user.type // (if (.author | has("id")) then "Bot" else "User" end) // "N/A")
Created:           \(.created_at // .createdAt // "N/A")
Updated:           \(.updated_at // .updatedAt // "N/A")"
  '
  
  # For review comments, show file and line info and resolved status
  if [ "$comment_type" = "review" ]; then
    RESOLVED_VALUE=$(echo "$comment_json" | jq -r 'if .isResolved == true then "Yes" elif .isResolved == false then "No" else "N/A" end' 2>/dev/null)
    echo "$comment_json" | jq -r '
      "Path:              \(.path // "N/A")
Line:              \(.line // "N/A")
Diff Hunk:         \(.diff_hunk // .diffHunk // "N/A" | split("\n") | .[0:3] | join(" | "))"
    '
    if [ "$RESOLVED_VALUE" != "N/A" ]; then
      echo "Resolved:          $RESOLVED_VALUE"
    fi
  fi
  
  # For issue comments, show hidden status and reason if hidden
  if [ "$comment_type" = "issue" ]; then
    IS_HIDDEN=$(echo "$comment_json" | jq -r '.isMinimized // .hidden // false' 2>/dev/null)
    if [ "$IS_HIDDEN" = "true" ]; then
      HIDE_REASON=$(echo "$comment_json" | jq -r '.minimizedReason // .hidden_reason // "unknown"' 2>/dev/null)
      # Convert reason format if needed
      HIDE_REASON=$(echo "$HIDE_REASON" | tr '[:upper:]' '[:lower:]' | tr '_' '-' 2>/dev/null || echo "$HIDE_REASON")
      echo "Hidden:              Yes"
      echo "Hide Reason:         $HIDE_REASON"
    fi
  fi
  
  # Show comment body
  BODY=$(echo "$comment_json" | jq -r '.body // .bodyText // ""')
  echo "Body:"
  echo ""
  echo "$BODY" | sed 's/^/                   /'
  
  # Show URL
  HTML_URL=$(echo "$comment_json" | jq -r '.html_url // .url // ""')
  if [ -n "$HTML_URL" ] && [ "$HTML_URL" != "null" ]; then
    echo ""
    echo "URL:               $HTML_URL"
  fi
  
  echo ""
}

# Main Action Logic
# Validate that comment ID is provided if an action is specified (non-bulk mode)
if { [ -n "$ACTION_HIDE" ] || [ -n "$ACTION_RESOLVE" ] || [ -n "$ACTION_REPLY" ]; } && [ -z "$COMMENT_ID" ] && [ -z "$BULK_MODE" ]; then
  echo "Error: -c/--comment-id or -u (URL) is required when using --hide, --resolve, or --reply (or use --bulk with --hide)" >&2
  exit 1
fi

# Validate action combinations (skip for bulk mode)
if [ -z "$BULK_MODE" ]; then
  if [ -n "$ACTION_HIDE" ] && { [ -n "$ACTION_RESOLVE" ] || [ -n "$ACTION_REPLY" ]; }; then
    echo "Error: --hide cannot be combined with --resolve or --reply" >&2
    exit 1
  fi
fi

ACTION_ERROR=0

# Reply Flow (if --reply is specified) - do this first (skip if bulk mode)
if [ -n "$ACTION_REPLY" ] && [ -z "$BULK_MODE" ]; then
  if [ -z "$JSON_OUTPUT" ]; then
    echo "Replying to review comment #${COMMENT_ID}..."
  fi
  
  # Get reply text
  final_reply_text=""
  if [ -n "$REPLY_TEXT" ]; then
    final_reply_text="$REPLY_TEXT"
  elif [ -z "$NO_PROMPT" ]; then
    final_reply_text=$(prompt_for_reply)
    if [ -z "$final_reply_text" ]; then
      echo "Error: Reply text cannot be empty" >&2
      ACTION_ERROR=1
    fi
  else
    echo "Error: --reply specified but no reply text provided and --no-prompt is set" >&2
    ACTION_ERROR=1
  fi
  
  if [ -n "$final_reply_text" ] && [ "$ACTION_ERROR" -eq 0 ]; then
    if ! reply_to_review_comment "$COMMENT_ID" "$final_reply_text"; then
      ACTION_ERROR=1
    elif [ -z "$JSON_OUTPUT" ]; then
      echo "Successfully posted reply to comment #${COMMENT_ID}"
      # Show the complete command the user could have run
      if [ -z "$REPLY_TEXT" ]; then
        # User was prompted, show them the command with their reply
        REPLY_TEXT="$final_reply_text"
        SUGGESTED_CMD=$(build_suggested_command)
        EFFICIENCY_TIP="Tip: For faster execution next time, use: $SUGGESTED_CMD"
        REPLY_TEXT=""
      fi
      # Only display the comment if we're not also resolving (resolve will display it)
      if [ -z "$ACTION_RESOLVE" ]; then
        echo ""
        echo "Updated comment:"
        # Fetch the entire thread to get all comments including the reply
      UPDATED_COMMENT=$(gh api "repos/${REPO}/pulls/comments/${COMMENT_ID}" 2>/dev/null)
      if [ $? -eq 0 ] && [ -n "$UPDATED_COMMENT" ]; then
        # Get PR number to fetch thread with all comments
        PR_NUM=$(echo "$UPDATED_COMMENT" | jq -r '.pull_request_url // ""' 2>/dev/null | sed -E 's|.*/pulls/([0-9]+).*|\1|' 2>/dev/null)
        if [ -n "$PR_NUM" ]; then
          OWNER=$(echo "$REPO" | cut -d'/' -f1)
          REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
          # Fetch entire thread with all comments
          THREAD_QUERY="{
            repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
              pullRequest(number: $PR_NUM) {
                reviewThreads(first: 100) {
                  nodes {
                    isResolved
                    comments(first: 100) {
                      nodes {
                        databaseId
                        id
                        bodyText
                        path
                        line
                        diffHunk
                        createdAt
                        updatedAt
                        author {
                          login
                          ... on Bot {
                            id
                          }
                        }
                        url
                      }
                    }
                  }
                }
              }
            }
          }"
          THREAD_DATA=$(gh api graphql -f query="$THREAD_QUERY" 2>/dev/null)
          if [ $? -eq 0 ] && [ -n "$THREAD_DATA" ]; then
            # Find the thread containing this comment and display all comments in the thread
            THREAD_COMMENTS=$(echo "$THREAD_DATA" | jq --arg id "$COMMENT_ID" --arg pr "$PR_NUM" --arg owner "$OWNER" --arg repo "$REPO_NAME" '
              .data.repository.pullRequest.reviewThreads.nodes[] |
              select(.comments.nodes[].databaseId == ($id | tonumber)) |
              .isResolved as $resolved |
              .comments.nodes[] |
              {
                id: .databaseId,
                node_id: .id,
                body: .bodyText,
                path: .path,
                line: .line,
                diff_hunk: .diffHunk,
                created_at: .createdAt,
                updated_at: .updatedAt,
                user: {
                  login: .author.login,
                  type: (if (.author | has("id")) then "Bot" else "User" end)
                },
                html_url: ("https://github.com/\($owner)/\($repo)/pull/\($pr)#discussion_r\(.databaseId)"),
                url: .url,
                isResolved: $resolved,
                type: "review"
              }
            ' 2>/dev/null | jq -s '.' 2>/dev/null)
            
            if [ -n "$THREAD_COMMENTS" ] && [ "$THREAD_COMMENTS" != "null" ] && [ "$THREAD_COMMENTS" != "[]" ]; then
              # Display all comments in the thread
              COMMENT_COUNT=$(echo "$THREAD_COMMENTS" | jq 'length' 2>/dev/null || echo "0")
              for i in $(seq 0 $((COMMENT_COUNT - 1))); do
                COMMENT_JSON=$(echo "$THREAD_COMMENTS" | jq ".[$i]" 2>/dev/null)
                if [ "$i" -eq 0 ]; then
                  # First comment is the original
                  display_comment "$COMMENT_JSON" "review"
                else
                  # Subsequent comments are replies
                  REPLY_ID=$(echo "$COMMENT_JSON" | jq -r '.id // .databaseId // "N/A"')
                  REPLY_AUTHOR=$(echo "$COMMENT_JSON" | jq -r '.user.login // .author.login // "N/A"')
                  REPLY_CREATED=$(echo "$COMMENT_JSON" | jq -r '.created_at // .createdAt // "N/A"')
                  REPLY_BODY=$(echo "$COMMENT_JSON" | jq -r '.body // .bodyText // ""')
                  
                  echo ""
                  echo "  └─ Reply by $REPLY_AUTHOR on $REPLY_CREATED"
                  echo "     $REPLY_BODY" | sed 's/^/     /'
                fi
              done
            else
              # Fallback to single comment display if thread fetch fails
              COMMENT_WITH_TYPE=$(echo "$UPDATED_COMMENT" | jq '. + {type: "review"}' 2>/dev/null)
              RESOLVED_STATUS=$(echo "$THREAD_DATA" | jq -r --arg id "$COMMENT_ID" '
                .data.repository.pullRequest.reviewThreads.nodes[] |
                select(.comments.nodes[].databaseId == ($id | tonumber)) |
                .isResolved
              ' 2>/dev/null)
              if [ -n "$RESOLVED_STATUS" ] && [ "$RESOLVED_STATUS" != "null" ]; then
                COMMENT_WITH_TYPE=$(echo "$COMMENT_WITH_TYPE" | jq --argjson resolved "$RESOLVED_STATUS" '. + {isResolved: $resolved}' 2>/dev/null)
              fi
              display_comment "$COMMENT_WITH_TYPE" "review"
            fi
          else
            # Fallback to REST API if GraphQL fails
            COMMENT_WITH_TYPE=$(echo "$UPDATED_COMMENT" | jq '. + {type: "review"}' 2>/dev/null)
            display_comment "$COMMENT_WITH_TYPE" "review"
          fi
        else
          # Fallback if PR number can't be determined
          COMMENT_WITH_TYPE=$(echo "$UPDATED_COMMENT" | jq '. + {type: "review"}' 2>/dev/null)
          display_comment "$COMMENT_WITH_TYPE" "review"
        fi
      fi
      fi
    fi
  fi
fi

# Hide Flow (if --hide is specified) - last step (skip if bulk mode)
if [ -n "$ACTION_HIDE" ] && [ "$ACTION_ERROR" -eq 0 ] && [ -z "$BULK_MODE" ]; then
  # Validate comment type is issue
  comment_data=$(gh api "repos/${REPO}/issues/comments/${COMMENT_ID}" 2>/dev/null)
  if [ $? -ne 0 ] || [ -z "$comment_data" ]; then
    echo "Error: Could not fetch comment #${COMMENT_ID} or comment does not exist" >&2
    ACTION_ERROR=1
  else
    if [ -z "$JSON_OUTPUT" ]; then
      echo "Hiding issue comment #${COMMENT_ID}..."
    fi
    
    # Get reason
    final_reason=""
    if [ -n "$HIDE_REASON" ]; then
      if validate_hide_reason "$HIDE_REASON"; then
        final_reason="$HIDE_REASON"
      else
        echo "Error: Invalid hide reason '${HIDE_REASON}'. Valid reasons: spam, abuse, off-topic, outdated, duplicate, resolved" >&2
        ACTION_ERROR=1
      fi
    elif [ -z "$NO_PROMPT" ]; then
      final_reason=$(prompt_for_reason)
      if [ $? -ne 0 ]; then
        ACTION_ERROR=1
      fi
    else
      echo "Error: --hide specified but --reason not provided and --no-prompt is set" >&2
      ACTION_ERROR=1
    fi
    
    if [ -n "$final_reason" ] && [ "$ACTION_ERROR" -eq 0 ]; then
      # Convert reason to GraphQL enum format (uppercase with underscores)
      graphql_reason=$(convert_reason_to_graphql "$final_reason")
      if [ $? -ne 0 ] || [ -z "$graphql_reason" ]; then
        echo "Error: Could not convert reason to GraphQL format" >&2
        ACTION_ERROR=1
      fi
      
      if [ "$ACTION_ERROR" -eq 0 ]; then
        if ! hide_issue_comment "$COMMENT_ID" "$graphql_reason"; then
          ACTION_ERROR=1
        elif [ -z "$JSON_OUTPUT" ]; then
          echo "Successfully hid comment #${COMMENT_ID} with reason: $final_reason"
          # Show the complete command the user could have run
          if [ -z "$HIDE_REASON" ]; then
            # User was prompted, show them the command with their selected reason
            SUGGESTED_CMD=$(build_suggested_command "$final_reason")
            EFFICIENCY_TIP="Tip: For faster execution next time, use: $SUGGESTED_CMD"
          fi
          echo ""
          echo "Updated comment:"
          # Fetch updated comment via GraphQL to get minimized status
          # First get PR number from the comment
          PR_NUM=$(echo "$comment_data" | jq -r '.issue_url // ""' 2>/dev/null | sed -E 's|.*/issues/([0-9]+).*|\1|' 2>/dev/null)
          if [ -z "$PR_NUM" ]; then
            # Try alternative: get from pull_request_url if available
            PR_NUM=$(echo "$comment_data" | jq -r '.pull_request_url // ""' 2>/dev/null | sed -E 's|.*/pulls/([0-9]+).*|\1|' 2>/dev/null)
          fi
          
          if [ -n "$PR_NUM" ]; then
            OWNER=$(echo "$REPO" | cut -d'/' -f1)
            REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
            COMMENT_QUERY="{
              repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
                pullRequest(number: $PR_NUM) {
                  comments(first: 100) {
                    nodes {
                      databaseId
                      id
                      bodyText
                      createdAt
                      updatedAt
                      author {
                        login
                        ... on Bot {
                          id
                        }
                      }
                      url
                      isMinimized
                      minimizedReason
                    }
                  }
                }
              }
            }"
            COMMENT_DATA=$(gh api graphql -f query="$COMMENT_QUERY" 2>/dev/null)
            if [ $? -eq 0 ] && [ -n "$COMMENT_DATA" ]; then
              COMMENT_WITH_TYPE=$(echo "$COMMENT_DATA" | jq --arg id "$COMMENT_ID" --arg pr "$PR_NUM" --arg owner "$OWNER" --arg repo "$REPO_NAME" '
                .data.repository.pullRequest.comments.nodes[] |
                select(.databaseId == ($id | tonumber)) |
                {
                  id: .databaseId,
                  node_id: .id,
                  body: .bodyText,
                  created_at: .createdAt,
                  updated_at: .updatedAt,
                  user: {
                    login: .author.login,
                    type: (if (.author | has("id")) then "Bot" else "User" end)
                  },
                  html_url: ("https://github.com/\($owner)/\($repo)/pull/\($pr)#issuecomment-\(.databaseId)"),
                  url: .url,
                  isMinimized: (if .isMinimized then true else false end),
                  minimizedReason: (if .minimizedReason then (.minimizedReason | ascii_downcase | gsub("_"; "-")) else null end),
                  type: "issue"
                }
              ' 2>/dev/null)
              if [ -n "$COMMENT_WITH_TYPE" ] && [ "$COMMENT_WITH_TYPE" != "null" ]; then
                display_comment "$COMMENT_WITH_TYPE" "issue"
              else
                # Fallback to REST API if GraphQL fails
                UPDATED_COMMENT=$(gh api "repos/${REPO}/issues/comments/${COMMENT_ID}" 2>/dev/null)
                if [ $? -eq 0 ] && [ -n "$UPDATED_COMMENT" ]; then
                  COMMENT_WITH_TYPE=$(echo "$UPDATED_COMMENT" | jq '
                    . + {
                      type: "issue",
                      isMinimized: (if .hidden == true then true else false end),
                      minimizedReason: (if .hidden_reason then (.hidden_reason | ascii_downcase | gsub("_"; "-")) else null end)
                    }
                  ' 2>/dev/null)
                  display_comment "$COMMENT_WITH_TYPE" "issue"
                fi
              fi
            else
              # Fallback to REST API if GraphQL fails
              UPDATED_COMMENT=$(gh api "repos/${REPO}/issues/comments/${COMMENT_ID}" 2>/dev/null)
              if [ $? -eq 0 ] && [ -n "$UPDATED_COMMENT" ]; then
                COMMENT_WITH_TYPE=$(echo "$UPDATED_COMMENT" | jq '
                  . + {
                    type: "issue",
                    isMinimized: (if .hidden == true then true else false end),
                    minimizedReason: (if .hidden_reason then (.hidden_reason | ascii_downcase | gsub("_"; "-")) else null end)
                  }
                ' 2>/dev/null)
                display_comment "$COMMENT_WITH_TYPE" "issue"
              fi
            fi
          else
            # Fallback to REST API if we can't get PR number
            UPDATED_COMMENT=$(gh api "repos/${REPO}/issues/comments/${COMMENT_ID}" 2>/dev/null)
            if [ $? -eq 0 ] && [ -n "$UPDATED_COMMENT" ]; then
              COMMENT_WITH_TYPE=$(echo "$UPDATED_COMMENT" | jq '
                . + {
                  type: "issue",
                  isMinimized: (if .hidden == true then true else false end),
                  minimizedReason: (if .hidden_reason then (.hidden_reason | ascii_downcase | gsub("_"; "-")) else null end)
                }
              ' 2>/dev/null)
              display_comment "$COMMENT_WITH_TYPE" "issue"
            fi
          fi
        fi
      fi
    fi
  fi
fi

# Resolve Flow (if --resolve is specified) - last step (after reply if both are specified) (skip if bulk mode)
if [ -n "$ACTION_RESOLVE" ] && [ "$ACTION_ERROR" -eq 0 ] && [ -z "$BULK_MODE" ]; then
  # Get thread ID from comment
  # First, get the comment to find which thread it belongs to
  OWNER=$(echo "$REPO" | cut -d'/' -f1)
  REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)
  
  # Get PR number from comment
  comment_data=$(gh api "repos/${REPO}/pulls/comments/${COMMENT_ID}" 2>/dev/null)
  if [ $? -ne 0 ] || [ -z "$comment_data" ]; then
    echo "Error: Could not fetch comment #${COMMENT_ID} or comment does not exist" >&2
    ACTION_ERROR=1
  else
    PR_NUM=$(echo "$comment_data" | jq -r '.pull_request_url // ""' 2>/dev/null | sed -E 's|.*/pulls/([0-9]+).*|\1|' 2>/dev/null)
    if [ -z "$PR_NUM" ]; then
      echo "Error: Could not determine PR number from comment" >&2
      ACTION_ERROR=1
    else
      # Find thread ID for this comment
      THREAD_QUERY="{
        repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
          pullRequest(number: $PR_NUM) {
            reviewThreads(first: 100) {
              nodes {
                id
                comments(first: 100) {
                  nodes {
                    databaseId
                  }
                }
              }
            }
          }
        }
      }"
      THREAD_DATA=$(gh api graphql -f query="$THREAD_QUERY" 2>/dev/null)
      THREAD_ID=$(echo "$THREAD_DATA" | jq -r --arg id "$COMMENT_ID" '
        .data.repository.pullRequest.reviewThreads.nodes[] |
        select(.comments.nodes[].databaseId == ($id | tonumber)) |
        .id
      ' 2>/dev/null | head -1)
      
      if [ -z "$THREAD_ID" ] || [ "$THREAD_ID" = "null" ]; then
        echo "Error: Could not find thread for comment #${COMMENT_ID}" >&2
        ACTION_ERROR=1
      else
        if [ -z "$JSON_OUTPUT" ]; then
          echo ""
          echo "Resolving review thread for comment #${COMMENT_ID}..."
        fi
        
        if ! resolve_review_thread "$THREAD_ID"; then
          ACTION_ERROR=1
        elif [ -z "$JSON_OUTPUT" ]; then
          echo "Successfully resolved thread for comment #${COMMENT_ID}"
          echo ""
          echo "Updated comment:"
          # Fetch updated thread to show resolved status and all replies
          THREAD_QUERY="{
            repository(owner: \"$OWNER\", name: \"$REPO_NAME\") {
              pullRequest(number: $PR_NUM) {
                reviewThreads(first: 100) {
                  nodes {
                    id
                    isResolved
                    comments(first: 100) {
                      nodes {
                        id
                        databaseId
                        bodyText
                        path
                        line
                        diffHunk
                        createdAt
                        updatedAt
                        author {
                          login
                          ... on Bot {
                            id
                          }
                        }
                        url
                      }
                    }
                  }
                }
              }
            }
          }"
          THREAD_DATA=$(gh api graphql -f query="$THREAD_QUERY" 2>/dev/null)
          if [ $? -eq 0 ] && [ -n "$THREAD_DATA" ]; then
            # Find the thread and display all comments including replies
            THREAD_COMMENTS=$(echo "$THREAD_DATA" | jq --arg thread_id "$THREAD_ID" --arg pr "$PR_NUM" --arg owner "$OWNER" --arg repo "$REPO_NAME" '
              .data.repository.pullRequest.reviewThreads.nodes[] |
              select(.id == $thread_id) |
              .isResolved as $resolved |
              .comments.nodes[] |
              {
                id: .databaseId,
                node_id: .id,
                body: .bodyText,
                path: .path,
                line: .line,
                diff_hunk: .diffHunk,
                created_at: .createdAt,
                updated_at: .updatedAt,
                user: {
                  login: .author.login,
                  type: (if (.author | has("id")) then "Bot" else "User" end)
                },
                html_url: ("https://github.com/\($owner)/\($repo)/pull/\($pr)#discussion_r\(.databaseId)"),
                url: .url,
                isResolved: $resolved,
                type: "review"
              }
            ' 2>/dev/null | jq -s '.' 2>/dev/null)
            
            if [ -n "$THREAD_COMMENTS" ] && [ "$THREAD_COMMENTS" != "null" ] && [ "$THREAD_COMMENTS" != "[]" ]; then
              # Display all comments in the thread
              COMMENT_COUNT=$(echo "$THREAD_COMMENTS" | jq 'length' 2>/dev/null || echo "0")
              for i in $(seq 0 $((COMMENT_COUNT - 1))); do
                COMMENT_JSON=$(echo "$THREAD_COMMENTS" | jq ".[$i]" 2>/dev/null)
                if [ "$i" -eq 0 ]; then
                  # First comment is the original
                  display_comment "$COMMENT_JSON" "review"
                else
                  # Subsequent comments are replies
                  REPLY_ID=$(echo "$COMMENT_JSON" | jq -r '.id // .databaseId // "N/A"')
                  REPLY_AUTHOR=$(echo "$COMMENT_JSON" | jq -r '.user.login // .author.login // "N/A"')
                  REPLY_CREATED=$(echo "$COMMENT_JSON" | jq -r '.created_at // .createdAt // "N/A"')
                  REPLY_BODY=$(echo "$COMMENT_JSON" | jq -r '.body // .bodyText // ""')
                  
                  echo ""
                  echo "  └─ Reply by $REPLY_AUTHOR on $REPLY_CREATED"
                  echo "     $REPLY_BODY" | sed 's/^/     /'
                fi
              done
            else
              # Fallback to single comment display if thread fetch fails
              THREAD_COMMENT=$(echo "$THREAD_DATA" | jq --arg thread_id "$THREAD_ID" --arg pr "$PR_NUM" --arg owner "$OWNER" --arg repo "$REPO_NAME" --arg comment_id "$COMMENT_ID" '
                .data.repository.pullRequest.reviewThreads.nodes[] |
                select(.id == $thread_id) |
                .isResolved as $resolved |
                .comments.nodes[] |
                select(.databaseId == ($comment_id | tonumber)) |
                {
                  id: .databaseId,
                  node_id: .id,
                  body: .bodyText,
                  path: .path,
                  line: .line,
                  diff_hunk: .diffHunk,
                  created_at: .createdAt,
                  updated_at: .updatedAt,
                  user: {
                    login: .author.login,
                    type: (if (.author | has("id")) then "Bot" else "User" end)
                  },
                  html_url: ("https://github.com/\($owner)/\($repo)/pull/\($pr)#discussion_r\(.databaseId)"),
                  url: .url,
                  isResolved: $resolved,
                  type: "review"
                }
              ' 2>/dev/null)
              if [ -n "$THREAD_COMMENT" ] && [ "$THREAD_COMMENT" != "null" ]; then
                display_comment "$THREAD_COMMENT" "review"
              fi
            fi
          fi
        fi
      fi
    fi
  fi
fi

# Exit if there was an action error
if [ "$ACTION_ERROR" -ne 0 ]; then
  exit 1
fi

# If only actions were requested (no listing), exit here
# Skip listing if actions were performed and no explicit listing was requested
# (i.e., if we have actions but no filters that would indicate listing intent)
if [ -n "$ACTION_HIDE" ] || [ -n "$ACTION_RESOLVE" ] || [ -n "$ACTION_REPLY" ]; then
  # If we have actions and no listing-related filters (except those used with actions), exit
  # Listing intent is indicated by: --type (without action), --bots/--humans (without action), 
  # --path (without action), --body-contains-string (without --bulk), --show-hidden (without action),
  # --count, or --json
  HAS_LISTING_INTENT=false
  if [ -n "$COUNT_ONLY" ] || [ -n "$JSON_OUTPUT" ]; then
    HAS_LISTING_INTENT=true
  elif [ -n "$COMMENT_TYPE" ] && [ "$COMMENT_TYPE" != "all" ] && [ -z "$ACTION_HIDE" ] && [ -z "$ACTION_RESOLVE" ] && [ -z "$ACTION_REPLY" ]; then
    HAS_LISTING_INTENT=true
  elif [ -n "$USER_FILTER" ] && [ "$USER_FILTER" != "all" ] && [ -z "$BULK_MODE" ]; then
    HAS_LISTING_INTENT=true
  elif [ -n "$PATH_FILTER" ] && [ -z "$ACTION_RESOLVE" ] && [ -z "$ACTION_REPLY" ]; then
    HAS_LISTING_INTENT=true
  elif [ -n "$BODY_CONTAINS_STRING" ] && [ -z "$BULK_MODE" ]; then
    HAS_LISTING_INTENT=true
  elif [ -n "$SHOW_HIDDEN" ] && [ -z "$ACTION_HIDE" ]; then
    HAS_LISTING_INTENT=true
  fi
  
  # If no listing intent and we have a PR/URL but also have a comment ID (which means we're targeting a specific comment)
  # then we should exit after actions since we've already displayed the updated comment
  if [ "$HAS_LISTING_INTENT" = "false" ] && [ -n "$COMMENT_ID" ]; then
    # Actions completed, no listing requested
    # Display efficiency tip at the end if one was generated
    if [ -n "$EFFICIENCY_TIP" ] && [ -z "$JSON_OUTPUT" ]; then
      echo ""
      echo "$EFFICIENCY_TIP"
    fi
    exit 0
  elif [ "$HAS_LISTING_INTENT" = "false" ] && [ -z "$PULL_REQUEST" ] && [ -z "$COMMENT_URL" ]; then
    # Actions completed, no listing requested
    # Display efficiency tip at the end if one was generated
    if [ -n "$EFFICIENCY_TIP" ] && [ -z "$JSON_OUTPUT" ]; then
      echo ""
      echo "$EFFICIENCY_TIP"
    fi
    exit 0
  fi
fi

# Handle bulk mode (after comments are fetched and filtered)
if [ -n "$BULK_MODE" ]; then
  if [ -z "$ACTION_HIDE" ]; then
    echo "Error: --bulk requires --hide action" >&2
    exit 1
  fi
  
  if [ -z "$PULL_REQUEST" ]; then
    echo "Error: --bulk requires -pr to specify the pull request" >&2
    exit 1
  fi
  
  # Get reason for hiding (prompt if not provided)
  final_reason=""
  if [ -n "$HIDE_REASON" ]; then
    if validate_hide_reason "$HIDE_REASON"; then
      final_reason="$HIDE_REASON"
    else
      echo "Error: Invalid hide reason '${HIDE_REASON}'" >&2
      exit 1
    fi
  elif [ -z "$NO_PROMPT" ]; then
    final_reason=$(prompt_for_reason)
    if [ $? -ne 0 ]; then
      echo "Error: Failed to get hide reason" >&2
      exit 1
    fi
  else
    echo "Error: --bulk --hide specified but --reason not provided and --no-prompt is set" >&2
    exit 1
  fi
  
  # Convert reason to GraphQL enum format
  graphql_reason=$(convert_reason_to_graphql "$final_reason")
  if [ $? -ne 0 ] || [ -z "$graphql_reason" ]; then
    echo "Error: Could not convert reason to GraphQL format" >&2
    exit 1
  fi
  
  # Get all filtered issue comments (bulk hide only works on issue comments)
  if [ -z "$JSON_OUTPUT" ]; then
    echo "Bulk hiding issue comments matching filters..."
    if [ -n "$BODY_CONTAINS_STRING" ]; then
      echo "  Filter: body contains \"$BODY_CONTAINS_STRING\""
    fi
    if [ -n "$USER_FILTER" ] && [ "$USER_FILTER" != "all" ]; then
      echo "  Filter: $USER_FILTER comments only"
    fi
    echo "  Reason: $final_reason"
    echo ""
  fi
  
  # Extract issue comments from ALL_COMMENTS
  # Note: ALL_COMMENTS already has filters applied (hidden status, body text, etc.)
  TOTAL_BEFORE_FILTER=$(echo "$ALL_COMMENTS" | jq 'length' 2>/dev/null || echo "0")
  ISSUE_COMMENTS_TO_HIDE=$(echo "$ALL_COMMENTS" | jq '[.[] | select(.type == "issue")]' 2>/dev/null)
  ISSUE_COUNT=$(echo "$ISSUE_COMMENTS_TO_HIDE" | jq 'length' 2>/dev/null || echo "0")
  
  if [ "$ISSUE_COUNT" -eq 0 ] || [ "$ISSUE_COUNT" = "null" ]; then
    if [ -z "$JSON_OUTPUT" ]; then
      echo "No issue comments found matching the filters."
      if [ "$TOTAL_BEFORE_FILTER" -eq 0 ]; then
        echo ""
        echo "Note: No comments were fetched. Make sure -pr is specified correctly."
      else
        echo ""
        echo "Note: Found $TOTAL_BEFORE_FILTER total comment(s) but none are issue comments matching the filters."
        echo "      You can list comments first without --bulk to see what matches."
      fi
    fi
    exit 0
  fi
  
  if [ -z "$JSON_OUTPUT" ]; then
    echo "Found $ISSUE_COUNT issue comment(s) to hide"
    echo ""
  fi
  
  # Process each comment
  SUCCESS_COUNT=0
  FAIL_COUNT=0
  i=0
  while [ "$i" -lt "$ISSUE_COUNT" ]; do
    COMMENT_JSON=$(echo "$ISSUE_COMMENTS_TO_HIDE" | jq ".[$i]" 2>/dev/null)
    COMMENT_ID_TO_HIDE=$(echo "$COMMENT_JSON" | jq -r '.id // .databaseId // ""' 2>/dev/null)
    
    if [ -n "$COMMENT_ID_TO_HIDE" ] && [ "$COMMENT_ID_TO_HIDE" != "null" ]; then
      if [ -z "$JSON_OUTPUT" ]; then
        echo "[$((i + 1))/$ISSUE_COUNT] Hiding comment #${COMMENT_ID_TO_HIDE}..."
      fi
      
      if hide_issue_comment "$COMMENT_ID_TO_HIDE" "$graphql_reason"; then
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        if [ -z "$JSON_OUTPUT" ]; then
          echo "  ✓ Success"
        fi
      else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        if [ -z "$JSON_OUTPUT" ]; then
          echo "  ✗ Failed"
        fi
      fi
    else
      FAIL_COUNT=$((FAIL_COUNT + 1))
    fi
    
    i=$((i + 1))
  done
  
  # Summary
  if [ -z "$JSON_OUTPUT" ]; then
    echo ""
    echo "=== Bulk Hide Summary ==="
    echo "Total processed: $ISSUE_COUNT"
    echo "Successful:      $SUCCESS_COUNT"
    echo "Failed:          $FAIL_COUNT"
    echo ""
    
    if [ "$SUCCESS_COUNT" -gt 0 ]; then
      SUGGESTED_CMD=$(build_suggested_command "$final_reason")
      EFFICIENCY_TIP="Tip: For faster execution next time, use: $SUGGESTED_CMD"
      echo "$EFFICIENCY_TIP"
    fi
  else
    echo "{\"total\": $ISSUE_COUNT, \"successful\": $SUCCESS_COUNT, \"failed\": $FAIL_COUNT}"
  fi
  
  # Exit after bulk operation
  exit 0
fi

# If we only performed actions on a specific comment (via -c), skip listing
# This check is here as a safety net in case the earlier exit didn't catch it
if { [ -n "$ACTION_HIDE" ] || [ -n "$ACTION_RESOLVE" ] || [ -n "$ACTION_REPLY" ]; } && [ -n "$COMMENT_ID" ] && [ -z "$COUNT_ONLY" ] && [ -z "$JSON_OUTPUT" ]; then
  # Check if we have any listing intent (filters that suggest listing, not just action support)
  HAS_ANY_LISTING_INTENT=false
  if [ -n "$COMMENT_TYPE" ] && [ "$COMMENT_TYPE" != "all" ]; then
    HAS_ANY_LISTING_INTENT=true
  elif [ -n "$USER_FILTER" ] && [ "$USER_FILTER" != "all" ] && [ -z "$BULK_MODE" ]; then
    HAS_ANY_LISTING_INTENT=true
  elif [ -n "$PATH_FILTER" ] && [ -z "$ACTION_RESOLVE" ] && [ -z "$ACTION_REPLY" ]; then
    HAS_ANY_LISTING_INTENT=true
  elif [ -n "$BODY_CONTAINS_STRING" ] && [ -z "$BULK_MODE" ]; then
    HAS_ANY_LISTING_INTENT=true
  elif [ -n "$SHOW_HIDDEN" ] && [ -z "$ACTION_HIDE" ]; then
    HAS_ANY_LISTING_INTENT=true
  fi
  
  # If no listing intent, exit here (actions already completed and displayed)
  if [ "$HAS_ANY_LISTING_INTENT" = "false" ]; then
    if [ -n "$EFFICIENCY_TIP" ] && [ -z "$JSON_OUTPUT" ]; then
      echo ""
      echo "$EFFICIENCY_TIP"
    fi
    exit 0
  fi
fi

# Sort comments by created date (oldest first) before displaying
ALL_COMMENTS=$(echo "$ALL_COMMENTS" | jq 'sort_by(.created_at // .createdAt // "")' 2>/dev/null || echo "$ALL_COMMENTS")

# Calculate total, defaulting to 0 if jq fails or returns empty
TOTAL=$(echo "$ALL_COMMENTS" | jq -r 'length // 0' 2>/dev/null)
if [ -z "$TOTAL" ] || [ "$TOTAL" = "null" ]; then
  TOTAL=0
fi

# Output count only if --count flag is set
if [ -n "$COUNT_ONLY" ]; then
  if [ -n "$JSON_OUTPUT" ]; then
    echo "$ALL_COMMENTS" | jq '{total: length}'
  else
    echo "Total: $TOTAL"
  fi
elif [ -n "$JSON_OUTPUT" ]; then
  echo "$ALL_COMMENTS" | jq '.'
else
  if [ "$TOTAL" -gt 0 ]; then
    for i in $(seq 0 $((TOTAL - 1))); do
      COMMENT=$(echo "$ALL_COMMENTS" | jq ".[$i]")
      COMMENT_ID=$(echo "$COMMENT" | jq -r '.id // "N/A"')
      
      echo ""
      echo "Comment ID: $COMMENT_ID"
      echo "---"
      
      # Display comment details
      echo "$COMMENT" | jq -r '
        "Type:              \((.type // "N/A") | ascii_upcase)
Author:            \(.user.login // "N/A")
Author Type:       \(.user.type // "N/A")
Created:           \(.created_at // "N/A")
Updated:           \(.updated_at // "N/A")"
      '
      
      # For review comments, show file and line info and resolved status
      if [ "$(echo "$COMMENT" | jq -r '.type')" = "review" ]; then
        RESOLVED_VALUE=$(echo "$COMMENT" | jq -r 'if .isResolved == true then "Yes" elif .isResolved == false then "No" else "N/A" end' 2>/dev/null)
        echo "$COMMENT" | jq -r '
          "Path:              \(.path // "N/A")
Line:              \(.line // "N/A")
Diff Hunk:         \(.diff_hunk // "N/A" | split("\n") | .[0:3] | join(" | "))"
        '
        if [ "$RESOLVED_VALUE" != "N/A" ]; then
          echo "Resolved:          $RESOLVED_VALUE"
        fi
      fi
      
      # For issue comments, show hidden status and reason if hidden
      if [ "$(echo "$COMMENT" | jq -r '.type')" = "issue" ]; then
        IS_HIDDEN=$(echo "$COMMENT" | jq -r '.isMinimized // false' 2>/dev/null)
        if [ "$IS_HIDDEN" = "true" ]; then
          HIDE_REASON=$(echo "$COMMENT" | jq -r '.minimizedReason // "unknown"' 2>/dev/null)
          echo "Hidden:             Yes"
          echo "Hide Reason:        $HIDE_REASON"
        fi
      fi
      
      # Show comment body
      BODY=$(echo "$COMMENT" | jq -r '.body // ""')
      echo "Body:"
      echo ""
      echo "$BODY" | sed 's/^/                   /'
      
      # Show URL
      HTML_URL=$(echo "$COMMENT" | jq -r '.html_url // ""')
      if [ -n "$HTML_URL" ] && [ "$HTML_URL" != "null" ]; then
        echo ""
        echo "URL:               $HTML_URL"
      fi
      
      # For issue comments, show replies if any
      if [ "$(echo "$COMMENT" | jq -r '.type')" = "issue" ]; then
        REPLY_COUNT=$(echo "$COMMENT" | jq -r '(.replies // []) | length' 2>/dev/null || echo "0")
        if [ "$REPLY_COUNT" -gt 0 ] && [ "$REPLY_COUNT" != "null" ]; then
          echo ""
          echo "                   Replies ($REPLY_COUNT):"
          echo "$COMMENT" | jq -r '.replies[]? | 
            "                   
                   └─ Reply by \(.user.login // "N/A") on \(.created_at // "N/A")
                      \(.body // "" | split("\n") | map("                      " + .) | join("\n"))"
          ' 2>/dev/null
        fi
      fi
      
      echo ""
    done
  else
    echo "No comments found."
    if [ -n "$COMMENT_URL" ]; then
      echo "The comment URL may be invalid or you may not have access to it."
    fi
  fi
  
  # Display summary at the end
  echo ""
  echo "=== Comments Summary ==="
  # Build summary text with proper formatting (only show non-zero counts)
  SUMMARY_PARTS=""
  # Ensure variables are set (default to 0 if not set)
  REVIEW_TOTAL_BEFORE_FILTER=${REVIEW_TOTAL_BEFORE_FILTER:-0}
  ISSUE_TOTAL_BEFORE_FILTER=${ISSUE_TOTAL_BEFORE_FILTER:-0}
  
  if [ "$REVIEW_TOTAL_BEFORE_FILTER" -gt 0 ]; then
    SUMMARY_PARTS="$REVIEW_TOTAL_BEFORE_FILTER review"
  fi
  if [ "$ISSUE_TOTAL_BEFORE_FILTER" -gt 0 ]; then
    if [ -n "$SUMMARY_PARTS" ]; then
      SUMMARY_PARTS="$SUMMARY_PARTS, $ISSUE_TOTAL_BEFORE_FILTER issue"
    else
      SUMMARY_PARTS="$ISSUE_TOTAL_BEFORE_FILTER issue"
    fi
  fi
  
  case "$USER_FILTER" in
    bots)
      if [ -n "$SUMMARY_PARTS" ]; then
        echo "Total bot comments: $TOTAL (from $SUMMARY_PARTS)"
      else
        echo "Total bot comments: $TOTAL"
      fi
      ;;
    humans)
      if [ -n "$SUMMARY_PARTS" ]; then
        echo "Total human comments: $TOTAL (from $SUMMARY_PARTS)"
      else
        echo "Total human comments: $TOTAL"
      fi
      ;;
    all)
      if [ -n "$SUMMARY_PARTS" ]; then
        echo "Total comments: $TOTAL (from $SUMMARY_PARTS)"
      else
        echo "Total comments: $TOTAL"
      fi
      ;;
  esac
  TOTAL_BEFORE_FILTER=$((REVIEW_TOTAL_BEFORE_FILTER + ISSUE_TOTAL_BEFORE_FILTER))
  if [ "$TOTAL" -ne "$TOTAL_BEFORE_FILTER" ]; then
    FILTER_NOTES=""
    # Build filter notes
    if [ -z "$SHOW_HIDDEN" ]; then
      FILTER_PARTS=""
      if [ "$REVIEW_TOTAL_BEFORE_FILTER" -gt 0 ]; then
        FILTER_PARTS="unresolved review comments"
      fi
      if [ "$ISSUE_TOTAL_BEFORE_FILTER" -gt 0 ]; then
        if [ -n "$FILTER_PARTS" ]; then
          FILTER_PARTS="${FILTER_PARTS}, hidden issue comments"
        else
          FILTER_PARTS="hidden issue comments"
        fi
      fi
      if [ -n "$FILTER_PARTS" ]; then
        FILTER_NOTES="$FILTER_PARTS"
      fi
    fi
    if [ -n "$PATH_FILTER" ]; then
      if [ -n "$FILTER_NOTES" ]; then
        FILTER_NOTES="${FILTER_NOTES}, path filter"
      else
        FILTER_NOTES="path filter"
      fi
    fi
    if [ -n "$BODY_CONTAINS_STRING" ]; then
      if [ -n "$FILTER_NOTES" ]; then
        FILTER_NOTES="${FILTER_NOTES}, body text filter"
      else
        FILTER_NOTES="body text filter"
      fi
    fi
    if [ -n "$FILTER_NOTES" ]; then
      echo "Note: Filtered by $FILTER_NOTES"
    fi
  fi
  
  # Display efficiency tip at the end if one was generated
  if [ -n "$EFFICIENCY_TIP" ] && [ -z "$JSON_OUTPUT" ]; then
    echo ""
    echo "$EFFICIENCY_TIP"
  fi
fi
