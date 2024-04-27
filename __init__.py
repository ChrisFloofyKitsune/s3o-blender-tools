import sys
import importlib

bl_info = {
    'name': 'Spring 3D Object (*.s3o) Tools',
    'category': 'All',
    'version': (0, 0, 1),
    'blender': (4, 1, 0)
}

modulesNames = ['s3o', 'vertex_cache']

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
