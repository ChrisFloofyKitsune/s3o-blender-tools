bl_info = {
    'name': 'Spring 3D Object (*.s3o) Tools',
    'author': 'ChrisFloofyKitsune, based on s3o code by Beherith and Muon',
    "description": "Tools for working with *.s3o files.",
    'category': 'Import-Export',
    'version': (0, 0, 1),
    'blender': (4, 1, 0)
}

# boilerplate code from: https://b3d.interplanety.org/en/creating-multifile-add-on-for-blender/
import sys
import importlib

modulesNames = ['s3o', 's3o_ops', 'vertex_cache']
modulesFullNames = {}

for name in modulesNames:
    if 'DEBUG_MODE' in sys.argv:
        modulesFullNames[name] = ('{}'.format(name))
    else:
        modulesFullNames[name] = ('{}.{}'.format(__name__, name))

for fullName in modulesFullNames.values():
    if fullName in sys.modules:
        importlib.reload(sys.modules[fullName])
    else:
        globals()[fullName] = importlib.import_module(fullName)
        setattr(globals()[fullName], 'modulesNames', modulesFullNames)


def register():
    for currentModuleName in modulesFullNames.values():
        if currentModuleName in sys.modules:
            if hasattr(sys.modules[currentModuleName], 'register'):
                sys.modules[currentModuleName].register()


def unregister():
    for currentModuleName in modulesFullNames.values():
        if currentModuleName in sys.modules:
            if hasattr(sys.modules[currentModuleName], 'unregister'):
                sys.modules[currentModuleName].unregister()


if __name__ == "__main__":
    register()
