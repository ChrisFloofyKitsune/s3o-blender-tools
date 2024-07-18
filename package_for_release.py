""" standalone script to package the project for release in a zip file"""

import fnmatch
import os
import zipfile

from __init__ import bl_info


def read_gitignore_patterns():
    patterns = ['/.git']
    with open('.gitignore', 'r') as f:
        for line in f:
            stripped_line = line.strip().strip('*')
            if stripped_line and not stripped_line.startswith('#'):
                patterns.append(stripped_line)
    return patterns


def should_exclude(path, patterns):
    for pattern in patterns:
        if fnmatch.fnmatch(path, f'*{pattern}*'):
            return True
    return False


def zip_directory(path):
    for root, dirs, files in os.walk(path):
        for dir in dirs.copy():
            if should_exclude(f'/{dir}/', exclude_patterns):
                print(f"Skipping directory {dir}")
                dirs.remove(dir)

        for file in files:
            # print(f"Checking file {file}")
            file_path = os.path.join(root, file)
            if os.path.abspath(file_path) == os.path.abspath(zip_file_path):
                continue  # Skip the zip file itself
            relative_path = os.path.relpath(file_path, os.path.join(path, '..'))
            if not should_exclude(relative_path, exclude_patterns):
                print(f"Adding {relative_path}")
                zipf.write(file_path, relative_path)


exclude_patterns = read_gitignore_patterns()
zip_filename = f"../s3o_kit_v{'_'.join(str(n) for n in bl_info['version'])}.zip"
zip_file_path = os.path.join(os.getcwd(), zip_filename)

with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
    zip_directory('.')

print(
    f"Created zip file {zip_filename} for release"
)
