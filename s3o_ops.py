import bpy
from bpy.props import StringProperty, BoolProperty
from bpy.types import Operator, Context
from bpy_extras.io_utils import ImportHelper

from . import s3o, s3o_utils


def register():
    bpy.utils.register_class(ImportSpring3dObject)
    bpy.types.TOPBAR_MT_file_import.append(ImportSpring3dObject.menu_func)


def unregister():
    bpy.utils.unregister_class(ImportSpring3dObject)
    bpy.types.TOPBAR_MT_file_import.remove(ImportSpring3dObject.menu_func)


class ImportSpring3dObject(Operator, ImportHelper):
    """ Import *.s3o file """
    bl_idname = "s3o_tools.import_s3o"
    bl_label = "Import *.s3o file"
    bl_options = {'REGISTER', 'UNDO'}

    filename_ext = ".s3o"

    filter_glob: StringProperty(
        default="*.s3o",
        options={'HIDDEN'},
        maxlen=255
    )

    merge_vertices: BoolProperty(
        name="Merge Vertices",
        description="Merge Vertices that share the same position.",
        default=True,
    )

    unit_textures_folder: StringProperty(
        name="Unit Textures Folder",
        description="Location of the unit textures."
                    "Leave blank to let the importer search for it automatically.",
        default="",
        subtype="DIR_PATH",
    )

    @staticmethod
    def menu_func(menu: bpy.types.Menu, context: Context):
        menu.layout.operator(ImportSpring3dObject.bl_idname)

    def execute(self, context: Context) -> set[str]:
        if bpy.context.active_object:
            bpy.ops.object.mode_set(mode='OBJECT')

        with open(self.filepath, 'rb') as s3o_file:
            s3o_data = s3o.S3O(s3o_file.read())
        s3o_data.triangulate_faces()

        obj_name = bpy.path.display_name_from_filepath(self.filepath)
        obj = s3o_utils.create_blender_obj(
            s3o_data,
            name=obj_name,
            merge_vertices=self.merge_vertices
        )

        return {'FINISHED'}
