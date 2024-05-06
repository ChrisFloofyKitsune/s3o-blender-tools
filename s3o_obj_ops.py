import bpy.utils
from bpy.types import Operator, Context
from . import s3o_props


class RefreshS3OProps(Operator):
    """ Import *.s3o file """
    bl_idname = "s3o_tools.refresh_s3o_props"
    bl_label = "Refresh s3o props and placeholders"
    bl_options = {'REGISTER'}

    def execute(self, context: Context) -> set[str]:
        s3o_props.refresh_all_s3o_props(context)
        return {'FINISHED'}


def register():
    bpy.utils.register_class(RefreshS3OProps)


def unregister():
    bpy.utils.unregister_class(RefreshS3OProps)
