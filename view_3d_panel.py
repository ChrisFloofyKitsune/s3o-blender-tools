import bpy.utils
from bpy.types import Panel, Context


class MainPanel(Panel):
    bl_idname = "S3O_PT_view_3d_main"
    bl_label = "S3O Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "S3O"

    def draw(self, context: Context):
        if context.mode != "OBJECT":
            return

        layout = self.layout

        io_box = layout.box()
        io_box.label(text="Import / Export")
        column = io_box.column()
        column.operator("s3o_tools.import_s3o", text="Import *.s3o")


def register():
    bpy.utils.register_class(MainPanel)


def unregister():
    bpy.utils.unregister_class(MainPanel)
