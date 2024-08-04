bl_info = {
    'name': 'S3O Kit (formerly S3O Blender Tools)',
    'author': 'ChrisFloofyKitsune, based on s3o code by Beherith and Muon. Logo by ZephyrSkies.',
    "description": "A small kit of tools for authoring and editing *.s3o files.",
    'category': 'Import-Export',
    'location': 'View3D > Sidebar > S3O',
    'support': 'COMMUNITY',
    'doc_url': 'https://github.com/ChrisFloofyKitsune/s3o-blender-tools',
    'tracker_url': 'https://github.com/ChrisFloofyKitsune/s3o-blender-tools/issues',
    'version': (0, 3, 1),
    'blender': (4, 1, 0)
}

"""
### Dev Loader Script ###
# Run from Blender's Text Editor

import sys
import importlib
import importlib.util

# https://docs.python.org/3/library/importlib.html#importing-a-source-file-directly

module_name = "s3o_kit"
file_path = "C:/bar_dev/blender_stuff/s3o_kit/__init__.py"

if module_name in sys.modules:
    try:
        sys.modules[module_name].unregister()
    except Exception as err:
        print(err)

spec = importlib.util.spec_from_file_location(module_name, file_path)
module = importlib.util.module_from_spec(spec)
sys.modules[module_name] = module
spec.loader.exec_module(module)

module.register()
"""

# bootstrapping code based on: https://b3d.interplanety.org/en/creating-multifile-add-on-for-blender/
import importlib
import sys
import time
from glob import glob

child_modules = {}


def bootstrap():
    global child_modules
    child_modules = {mod_name: f'{__name__}.{mod_name}' for mod_name in (
        p.replace('\\', '.').replace('/', '.').removesuffix('.py')
        for p in glob("**/[!_]*.py", root_dir=__path__[0], recursive=True)
    )}

    if 'package_for_release' in child_modules:
        child_modules.pop('package_for_release')

    print(f'{time.asctime()} (RE)LOADING: {__name__}')

    for mod_name, full_name in child_modules.items():
        if full_name in sys.modules:
            # print('Reload', full_name)
            importlib.reload(sys.modules[full_name])
        else:
            # print('Initial load', full_name)
            parent, name = (
                mod_name.rsplit('.', 1)
                if '.' in mod_name else ('', mod_name)
            )
            exec(f'from .{parent} import {name}')


try:
    bootstrap()
except Exception as e:
    print(f'{time.asctime()} ERROR: {__name__} failed to load')
    # print stacktrace
    import traceback

    traceback.print_exception(e)


def register():
    for full_module_name in child_modules.values():
        if full_module_name in sys.modules and hasattr(sys.modules[full_module_name], 'register'):
            sys.modules[full_module_name].register()


def unregister():
    for full_module_name in child_modules.values():
        if full_module_name in sys.modules and hasattr(sys.modules[full_module_name], 'unregister'):
            sys.modules[full_module_name].unregister()
