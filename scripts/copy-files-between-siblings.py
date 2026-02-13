#!/usr/bin/env python3

import os
import shutil
import sys
from pathlib import Path

try:
    import inquirer
except ImportError:
    print('Error: inquirer package is required. Install it with: pip3 install inquirer', file=sys.stderr)
    sys.exit(1)

FILES_TO_COPY = [
    '.circleci/helpers/check-eslint-disable.sh',
    '.circleci/helpers/check-markdown-placement.sh',
    '.circleci/helpers/check-unpkg-usage.sh',
    '.cursor',
    '.cursor/hooks.json',
    '.cursor/hooks/',
    '.cursor/skills/',
    '.prettierrc.cjs',
    'AGENTS.md',
    'CONTRIBUTING.md',
    'eslint.config.mjs',
    'eslint-local-rules/index.mjs',
    'eslint-local-rules/no-consecutive-logging.mjs',
    'ISSUE_REPORTING_GUIDELINES.md',
    'scripts/list-last-deployments.py',
    'scripts/list-pr-checks.sh',
    'scripts/list-sonar-issues.py',
    'scripts/local_deployment_notifier.py',
    'scripts/run-ci-checks-local.sh',
    'scripts/upgrade-all-packages.sh',
]

# Path mappings for home directory: maps project path to home directory path
# When copying to/from home directory, these mappings override the default paths
HOME_DIR_PATH_MAPPINGS = {
    'eslint.config.mjs': '.config/eslint.config.mjs',
    'eslint-local-rules/index.mjs': '.config/eslint-local-rules/index.mjs',
    'eslint-local-rules/no-consecutive-logging.mjs': '.config/eslint-local-rules/no-consecutive-logging.mjs',
}

CANCELLED_MESSAGE = '\nSelection cancelled by user.'
NO_FILES_SELECTED_MESSAGE = 'No files selected. Exiting.'


def is_home_directory(path: Path) -> bool:
    """Check if the given path is the home directory."""
    return path.resolve() == Path.home().resolve()


def get_mapped_path(file_path: str, is_target_home: bool, is_source_home: bool) -> str:
    """Get the mapped path for a file based on whether source/target is home directory.
    
    Args:
        file_path: Original file path
        is_target_home: True if copying TO home directory
        is_source_home: True if copying FROM home directory
        
    Returns:
        Mapped path (may be the same as input if no mapping exists)
    """
    if is_target_home:
        # Copying TO home: use home mapping if it exists
        return HOME_DIR_PATH_MAPPINGS.get(file_path, file_path)
    elif is_source_home:
        # Copying FROM home: reverse lookup to get project path
        for project_path, home_path in HOME_DIR_PATH_MAPPINGS.items():
            if home_path == file_path:
                return project_path
        return file_path
    else:
        # Between siblings: use original path
        return file_path


def get_existing_files(source_dir: Path, files: list[str]) -> list[str]:
    """Check which files or directories exist in the source directory. Returns list of existing paths.
    
    Handles path mappings for home directory automatically.
    """
    existing = []
    is_source_home = is_home_directory(source_dir)
    
    for file in files:
        # Get the actual path to check (may be mapped for home directory)
        check_path = get_mapped_path(file, is_target_home=False, is_source_home=is_source_home)
        source_path = source_dir / check_path
        
        if source_path.exists():
            existing.append(file)
        else:
            print(f'  ⚠ Skipping {file} (not found in source)', file=sys.stderr)
    return existing


def get_sibling_directories(parent_dir: Path, current_dir_name: str) -> list[str]:
    """Read parent directory and return list of sibling directory names."""
    try:
        entries = list(parent_dir.iterdir())
    except Exception as error:
        print(f'Error reading parent directory: {error}', file=sys.stderr)
        sys.exit(1)

    directories = [
        entry.name
        for entry in entries
        if entry.is_dir() and entry.name != current_dir_name
    ]
    return directories


def get_available_locations(parent_dir: Path, current_dir_name: str) -> tuple[list[str], dict[str, Path]]:
    """Get available locations including siblings and home directory. Returns (display_names, path_mapping)."""
    siblings = get_sibling_directories(parent_dir, current_dir_name)
    home_dir = Path.home()
    
    display_names = []
    path_mapping = {}
    
    # Add home directory
    home_display = f'Home Directory ({home_dir})'
    display_names.append(home_display)
    path_mapping[home_display] = home_dir
    
    # Add sibling directories
    for sibling in siblings:
        display_names.append(sibling)
        path_mapping[sibling] = parent_dir / sibling
    
    return display_names, path_mapping


def select_direction() -> str:
    """Display interactive menu for selecting copy direction. Returns 'to' or 'from'."""
    try:
        questions = [
            inquirer.List(
                'direction',
                message='Select copy direction',
                choices=['Copy to sibling directories or home', 'Copy from sibling directory or home'],
            ),
        ]
        answers = inquirer.prompt(questions)

        if not answers or 'direction' not in answers:
            print('No direction selected. Exiting.', file=sys.stderr)
            sys.exit(0)

        direction = answers['direction']
        return 'to' if direction == 'Copy to sibling directories or home' else 'from'

    except KeyboardInterrupt:
        print(CANCELLED_MESSAGE, file=sys.stderr)
        sys.exit(0)
    except Exception as error:
        print(f'Error during direction selection: {error}', file=sys.stderr)
        sys.exit(1)


def select_directories(display_names: list[str]) -> list[str]:
    """Display interactive menu for selecting directories. Returns list of selected display names."""
    if not display_names:
        return []

    # Create menu options with "All" at the top
    options = ['All'] + display_names

    try:
        questions = [
            inquirer.Checkbox(
                'selected',
                message='Select sibling directories or home directory to copy to (use arrow keys to navigate, space to select, Enter to confirm)',
                choices=options,
            ),
        ]
        answers = inquirer.prompt(questions)

        if not answers or 'selected' not in answers or not answers['selected']:
            print('No locations selected. Exiting.', file=sys.stderr)
            sys.exit(0)

        selected = answers['selected']

        # Handle "All" selection
        if 'All' in selected:
            return display_names

        return selected

    except KeyboardInterrupt:
        print(CANCELLED_MESSAGE, file=sys.stderr)
        sys.exit(0)
    except Exception as error:
        print(f'Error during directory selection: {error}', file=sys.stderr)
        sys.exit(1)


def select_single_directory(display_names: list[str]) -> str:
    """Display interactive menu for selecting a single directory. Returns selected display name."""
    if not display_names:
        return ''

    options = display_names

    try:
        questions = [
            inquirer.List(
                'selected',
                message='Select sibling directory or home directory to copy from (use arrow keys to navigate, Enter to confirm)',
                choices=options,
            ),
        ]
        answers = inquirer.prompt(questions)

        if not answers or 'selected' not in answers:
            print('No location selected. Exiting.', file=sys.stderr)
            sys.exit(0)

        return answers['selected']

    except KeyboardInterrupt:
        print(CANCELLED_MESSAGE, file=sys.stderr)
        sys.exit(0)
    except Exception as error:
        print(f'Error during directory selection: {error}', file=sys.stderr)
        sys.exit(1)


def select_files_to_copy(available_files: list[str]) -> list[str]:
    """Display interactive menu for selecting files to copy. Returns list of selected file paths."""
    if not available_files:
        return []

    try:
        questions = [
            inquirer.Checkbox(
                'selected',
                message='Select files to copy (use arrow keys to navigate, space to select/deselect, Enter to confirm)',
                choices=available_files,
                default=available_files,  # All files selected by default
            ),
        ]
        answers = inquirer.prompt(questions)

        if not answers or 'selected' not in answers or not answers['selected']:
            print(NO_FILES_SELECTED_MESSAGE, file=sys.stderr)
            sys.exit(0)

        return answers['selected']

    except KeyboardInterrupt:
        print(CANCELLED_MESSAGE, file=sys.stderr)
        sys.exit(0)
    except Exception as error:
        print(f'Error during file selection: {error}', file=sys.stderr)
        sys.exit(1)


def copy_file_to_directory(source_path: Path, target_path: Path, file: str) -> bool:
    """Copy a single file to target directory. Returns True on success, False on failure."""
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, target_path)
        print(f'  ✓ Copied {file}')
        return True
    except Exception as error:
        print(f'  ✗ Failed to copy {file}: {error}', file=sys.stderr)
        return False


def copy_directory_to_directory(source_path: Path, target_path: Path, directory: str) -> bool:
    """Copy a directory recursively to target directory. Returns True on success, False on failure."""
    try:
        # Remove target directory if it exists to allow clean copy
        if target_path.exists():
            shutil.rmtree(target_path)
        shutil.copytree(source_path, target_path, dirs_exist_ok=True)
        print(f'  ✓ Copied {directory}')
        return True
    except Exception as error:
        print(f'  ✗ Failed to copy {directory}: {error}', file=sys.stderr)
        return False


def copy_item(source_path: Path, target_path: Path, item: str) -> bool:
    """Copy a file or directory. Returns True on success, False on failure."""
    if source_path.is_dir():
        return copy_directory_to_directory(source_path, target_path, item)
    return copy_file_to_directory(source_path, target_path, item)


def copy_files_to_target(source_dir: Path, target_dir: Path, files: list[str], location_name: str, direction: str = 'to') -> int:
    """Copy multiple files from source to target directory. Returns count of successfully copied items.
    
    Handles path mappings for home directory automatically.
    """
    print(f'Copying {direction} {location_name}...')
    is_source_home = is_home_directory(source_dir)
    is_target_home = is_home_directory(target_dir)
    
    copied_count = 0
    for item in files:
        # Get source path (may be mapped if source is home)
        source_mapped = get_mapped_path(item, is_target_home=False, is_source_home=is_source_home)
        source_path = source_dir / source_mapped
        
        # Get target path (may be mapped if target is home)
        target_mapped = get_mapped_path(item, is_target_home=is_target_home, is_source_home=False)
        target_path = target_dir / target_mapped
        
        if copy_item(source_path, target_path, item):
            copied_count += 1
    return copied_count


def print_missing_files_message(existing_count: int, total_count: int, location_name: str = 'current directory') -> None:
    """Print message about missing files if any are not found."""
    if existing_count < total_count:
        missing_count = total_count - existing_count
        print(f'Note: {missing_count} file{"s" if missing_count != 1 else ""} not found in {location_name} and will be skipped.\n')


def copy_files_to_locations():
    """Copy files from current repository to selected locations."""
    current_dir = Path.cwd()
    current_dir_name = current_dir.name
    parent_dir = current_dir.parent

    print(f'Current repository: {current_dir_name}')
    print(f'Parent directory: {parent_dir}\n')

    existing_files = get_existing_files(current_dir, FILES_TO_COPY)

    if not existing_files:
        print('No source files found in current directory. Exiting.', file=sys.stderr)
        return

    print_missing_files_message(len(existing_files), len(FILES_TO_COPY))

    selected_files = select_files_to_copy(existing_files)

    if not selected_files:
        print(NO_FILES_SELECTED_MESSAGE)
        return

    print(f'\nSelected {len(selected_files)} file{"s" if len(selected_files) != 1 else ""} for copying.\n')

    display_names, path_mapping = get_available_locations(parent_dir, current_dir_name)

    if not display_names:
        print('No locations found.')
        return

    sibling_count = len(display_names) - 1
    print(f'Found {sibling_count} sibling director{"y" if sibling_count == 1 else "ies"} and home directory.\n')

    selected_locations = select_directories(display_names)

    if not selected_locations:
        print('No locations selected. Exiting.')
        return

    print(f'\nSelected {len(selected_locations)} location{"s" if len(selected_locations) != 1 else ""} for copying.\n')

    copied_count = 0
    for location_name in selected_locations:
        target_dir = path_mapping[location_name]
        copied_count += copy_files_to_target(current_dir, target_dir, selected_files, location_name, 'to')

    print(f'\nCompleted: Copied {copied_count} file{"s" if copied_count != 1 else ""} to {len(selected_locations)} location{"s" if len(selected_locations) != 1 else ""}.')


def copy_files_from_location():
    """Copy files from a selected location to current repository."""
    current_dir = Path.cwd()
    current_dir_name = current_dir.name
    parent_dir = current_dir.parent

    print(f'Current repository: {current_dir_name}')
    print(f'Parent directory: {parent_dir}\n')

    display_names, path_mapping = get_available_locations(parent_dir, current_dir_name)

    if not display_names:
        print('No locations found.')
        return

    sibling_count = len(display_names) - 1
    print(f'Found {sibling_count} sibling director{"y" if sibling_count == 1 else "ies"} and home directory.\n')

    selected_location_name = select_single_directory(display_names)

    if not selected_location_name:
        print('No location selected. Exiting.')
        return

    source_dir = path_mapping[selected_location_name]
    print(f'\nSelected location: {selected_location_name}\n')

    existing_files = get_existing_files(source_dir, FILES_TO_COPY)

    if not existing_files:
        print(f'No files found in {selected_location_name}. Exiting.', file=sys.stderr)
        return

    print_missing_files_message(len(existing_files), len(FILES_TO_COPY), selected_location_name)

    selected_files = select_files_to_copy(existing_files)

    if not selected_files:
        print(NO_FILES_SELECTED_MESSAGE)
        return

    print(f'\nSelected {len(selected_files)} file{"s" if len(selected_files) != 1 else ""} for copying.\n')

    copied_count = copy_files_to_target(source_dir, current_dir, selected_files, selected_location_name, 'from')

    print(f'\nCompleted: Copied {copied_count} file{"s" if copied_count != 1 else ""} from {selected_location_name}.')


def main():
    """Main function that handles direction selection and calls appropriate copy function."""
    direction = select_direction()

    if direction == 'to':
        copy_files_to_locations()
    else:
        copy_files_from_location()


if __name__ == '__main__':
    main()
