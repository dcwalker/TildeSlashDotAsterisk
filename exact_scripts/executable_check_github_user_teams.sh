#!/bin/bash
USERNAME="$1"
ORG="procore"

if [ -z "$USERNAME" ]; then
  echo "Usage: $0 <github-username>"
  exit 1
fi

echo "Checking teams for user: $USERNAME"
echo "=================================="
echo ""

# Get all teams in the organization and check if user is a member
gh api orgs/$ORG/teams --paginate --jq '.[].slug' | while read team_slug; do
  # Check if user is a member of this team
  if gh api orgs/$ORG/teams/$team_slug/members/$USERNAME --silent 2>/dev/null; then
    echo "✓ $team_slug"
  fi
done
