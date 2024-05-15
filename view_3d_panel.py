import typing

import bpy.utils
from bl_ui.generic_ui_list import draw_ui_list
from bpy.types import Panel, Context, UILayout
from .ambient_occlusion import AOProps, ObjectExplodeEntry


class MainPanel(Panel):
    bl_idname = "S3O_PT_view_3d_main"
    bl_label = "S3O Tools"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "S3O"

    def draw(self, context: Context):
        layout = self.layout
        self.panel_view_settings(layout)
        self.panel_add(layout, context)
        self.panel_import_export(layout, context)
        self.panel_util(layout, context)

    def panel_view_settings(self, layout: UILayout):
        (header, body) = layout.panel('s3o_view')
        header.label(text="View Settings")
        if body is not None:
            col = body.column()
            col.prop(bpy.context.space_data.overlay, 'show_extras', text="Show Empties")

    def panel_add(self, layout: UILayout, _: Context):
        (header, body) = layout.panel('s3o_add')
        header.label(text="Add")
        if body is not None:
            col: bpy.types.UILayout = body.column(align=True)
            col.operator('s3o_tools.add_s3o_root', icon='EMPTY_ARROWS')
            col.operator('s3o_tools.add_s3o_aim_point', icon='EMPTY_SINGLE_ARROW')
            row = col.row()
            row.enabled = bpy.ops.s3o_tools.add_mesh_as_child.poll()
            row.operator_menu_enum("s3o_tools.add_mesh_as_child", 'mesh_type', icon='OUTLINER_OB_MESH')

    def panel_import_export(self, layout: UILayout, _: Context):
        (header, body) = layout.panel('s3o_import_export')
        header.label(text="Import / Export")
        if body is not None:
            col = body.column(align=True)
            col.operator("s3o_tools.import_textures", icon='TEXTURE')
            col.operator("s3o_tools.import_s3o", text="Import *.s3o", icon='IMPORT')
            col.operator("s3o_tools.export_s3o", text="Export *.s3o", icon='EXPORT')

    def panel_util(self, layout: UILayout, _: Context):
        (header, body) = layout.panel('s3o_import_util')
        header.label(text="Utilities")
        if body is not None:
            col = body.column(align=True)
            col.operator_menu_enum("s3o_tools.set_all_rotation_modes", 'mode', icon='ORIENTATION_GIMBAL')
            col.operator("s3o_tools.s3oify_object_hierarchy", icon='SHADERFX')


class ObjectsToExplodeList(bpy.types.UIList):
    bl_idname = "S3O_UL_objects_to_explode"

    def draw_item(
        self,
        context: Context | None,
        layout: UILayout,
        data: AOProps,
        item: ObjectExplodeEntry,
        icon: int | None,
        active_data: AOProps,
        active_property: str,
        index: typing.Optional[typing.Any] = 0,
        flt_flag: typing.Optional[typing.Any] = 0
    ):
        row = layout.row(align=True)
        row.prop(item, 'obj', text="")


class AOPanel(Panel):
    bl_idname = "S3O_PT_view_3d_ao"
    bl_label = "Ambient Occlusion"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "S3O"

    def draw(self, context: Context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column(align=True)
        col.operator('s3o_tools_ao.to_ao_view')
        col.operator('s3o_tools_ao.to_rendered_view')

        self.panel_settings(layout, context)
        self.panel_objs_to_explode(layout, context)
        self.panel_bake(layout, context)

    def panel_settings(self, layout: UILayout, context: Context):
        header: UILayout
        body: UILayout | None
        (header, body) = layout.panel('s3o_ao_settings_panel')
        header.label(text="AO Settings")
        if body is None:
            return
        col = body.column(align=True)
        col.prop(context.scene.s3o_ao, "distance", slider=True)
        col.prop(context.scene.s3o_ao, "min_clamp")
        col.prop(context.scene.s3o_ao, "bias")
        col.prop(context.scene.s3o_ao, "gain")

        body.use_property_split = False
        body.prop(context.scene.s3o_ao, "ground_plate")
        body.use_property_split = True

        plate_col = body.column(align=True)
        plate_col.active = context.scene.s3o_ao.ground_plate
        plate_col.prop(context.scene.s3o_ao, "building_plate_size_x")
        plate_col.prop(context.scene.s3o_ao, "building_plate_size_z")
        plate_col.prop(context.scene.s3o_ao, "building_plate_resolution")
        # Not sure if this does anything for this use case
        # col.prop(context.scene.cycles, "ao_bounces_render", text="AO Bounces")

    def panel_objs_to_explode(self, layout: UILayout, context: Context):
        header: UILayout
        body: UILayout | None
        (header, body) = layout.panel('s3o_ao_objs_to_explode_panel')
        header.label(text="Objects to 'Explode'")
        if body is None:
            return
        col = body.column()
        row = col.row(align=True)

        draw_ui_list(
            row,
            context,
            class_name='S3O_UL_objects_to_explode',
            unique_id='s3o_ao_objs_to_explode_ui_list',
            list_path='scene.s3o_ao.objects_to_explode',
            active_index_path='scene.s3o_ao.selected_explode_entry',
            insertion_operators=False,
            move_operators=False,
        )

        list_buttons_col = row.column()
        list_buttons_col.operator("s3o_tools_ao.add_explode_entry", icon='ADD', text="")
        list_buttons_col.operator("s3o_tools_ao.remove_explode_entry", icon='REMOVE', text="")

    def panel_bake(self, layout: UILayout, context: Context):
        header: UILayout
        body: UILayout | None
        (header, body) = layout.panel('s3o_ao_bake_panel')
        header.label(text="AO Bake")
        if body is None:
            return

        col = body.column(align=True)

        (bake_header, bake_box) = col.panel('s3o_ao_bake_panel_target')
        bake_header.label(text="Target")
        if bake_box is not None:
            bake_box: UILayout
            bake_box.use_property_split = False
            bake_box.prop(context.scene.s3o_ao, 'bake_target', expand=True)

        col.separator()

        reset_row = col.row(align=True)
        reset_row.operator('s3o_tools_ao.reset_ao_value')
        reset_row.prop(context.scene.s3o_ao, 'reset_ao_value', text="")

        col.operator('s3o_tools_ao.bake_vertex_ao')
        col.operator('s3o_tools_ao.bake_building_plate')


def register():
    bpy.utils.register_class(MainPanel)
    bpy.utils.register_class(ObjectsToExplodeList)
    bpy.utils.register_class(AOPanel)


def unregister():
    bpy.utils.unregister_class(MainPanel)
    bpy.utils.unregister_class(ObjectsToExplodeList)
    bpy.utils.unregister_class(AOPanel)
