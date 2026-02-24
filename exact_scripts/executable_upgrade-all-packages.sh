#!/bin/bash

# Upgrade all packages to latest versions in all directories containing package.json
# This script automatically discovers all package.json files and runs yarn upgrade --latest in each

# Parse command line arguments
if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
  echo "Usage: $0"
  echo ""
  echo "Description:"
  echo "  Automatically upgrades all NPM packages to their latest versions"
  echo "  in every directory containing a package.json file (excluding node_modules)."
  echo "  Runs yarn upgrade --latest in each directory and reports any failures."
  echo ""
  echo "Options:"
  echo "  -h, --help    Show this help message"
  echo ""
  echo "Example:"
  echo "  ./upgrade-all-packages.sh"
  exit 0
fi

set +e  # Don't exit on error - we want to upgrade all directories even if one fails

echo "Upgrading packages to latest versions in all directories..."
echo ""

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
  echo "Error: package.json not found. Please run this script from the project root."
  exit 1
fi

ERRORS=0
FAILED_UPGRADES=()

# Find all package.json files (excluding node_modules)
while IFS= read -r -d '' package_file; do
  # Get the directory containing the package.json
  package_dir=$(dirname "$package_file")
  
  # Skip if it's in node_modules (shouldn't happen with our find, but just in case)
  if [[ "$package_dir" == *"node_modules"* ]]; then
    continue
  fi
  
  # Get a readable name for the directory
  if [ "$package_dir" = "." ]; then
    dir_name="root"
  else
    dir_name="$package_dir"
  fi
  
  echo "Upgrading packages in $dir_name..."
  if ! (cd "$package_dir" && yarn upgrade --latest); then
    ERRORS=$((ERRORS + 1))
    FAILED_UPGRADES+=("$dir_name")
    echo "Failed to upgrade packages in $dir_name"
  else
    echo "Successfully upgraded packages in $dir_name"
  fi
  echo ""
done < <(find . -name "package.json" -not -path "*/node_modules/*" -print0)

echo ""
if [ $ERRORS -eq 0 ]; then
  echo "All packages upgraded successfully!"
  exit 0
else
  echo "========================================="
  echo "Upgrade Summary: $ERRORS directory(ies) failed"
  echo "========================================="
  echo ""
  echo "Failed directories:"
  for dir in "${FAILED_UPGRADES[@]}"; do
    echo "  - $dir"
  done
  echo ""
  echo "Please check the errors above and try again if needed."
  exit 1
fi
