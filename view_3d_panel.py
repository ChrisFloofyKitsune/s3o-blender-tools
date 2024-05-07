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

        self.panel_view_settings(layout)

        self.panel_add(layout, context)
        self.panel_import_export(layout, context)

    def panel_view_settings(self, layout: UILayout):
        (header, body) = layout.panel('s3o_view')
        header.label(text="View Settings")
        if body is not None:
            col = body.column()
            col.prop(bpy.context.space_data.overlay, 'show_extras', text="Show Empties")


    def panel_add(self, layout: UILayout, context: Context):
        if context.mode != "OBJECT":
            return
        (header, body) = layout.panel('s3o_add')
        header.label(text="Add")
        if body is not None:
            col = body.column()
            col.operator('s3o_tools.add_s3o_root')
            col.operator('s3o_tools.add_s3o_aim_point')

    def panel_import_export(self, layout: UILayout, context: Context):
        (header, body) = layout.panel('s3o_import_export')
        header.label(text="Import / Export")
        if body is not None:
            col = body.column()
            col.operator("s3o_tools.import_textures")
            if context.mode == "OBJECT":
                col.operator("s3o_tools.import_s3o", text="Import *.s3o")
                col.operator("s3o_tools.export_s3o", text="Export *.s3o")


def register():
    bpy.utils.register_class(MainPanel)


def unregister():
    bpy.utils.unregister_class(MainPanel)
