import bpy.utils
from bpy.types import Panel, Context, UILayout


class MainPanel(Panel):
    bl_idname = "S3O_PT_view_3d_main"
    bl_label = "S3O Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "S3O"

    def draw(self, context: Context):
        layout = self.layout
        
        layout.operator_menu_enum("s3o_tools.set_all_rotation_modes", 'mode')
        
        self.panel_window_settings(layout)

        if context.mode != "OBJECT":
            return

        self.panel_add(layout)
        self.panel_import_export(layout)

    def panel_window_settings(self, layout: UILayout):
        ...

    def panel_add(self, layout: UILayout):
        ...

    def panel_import_export(self, layout: UILayout):
        (header, body) = layout.panel('s3o_import_export')
        header.label(text="Import / Export")
        if body is not None:
            col = body.column()
            col.operator("s3o_tools.import_s3o", text="Import *.s3o")
            col.operator("s3o_tools.export_s3o", text="Export *.s3o")


def register():
    bpy.utils.register_class(MainPanel)


def unregister():
    bpy.utils.unregister_class(MainPanel)
