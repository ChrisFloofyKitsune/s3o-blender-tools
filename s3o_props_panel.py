import bpy.utils
from bpy.types import Panel, Context
from .s3o_props import S3ORootProperties, S3OAimPointProperties


class S3OPropsPanel(Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "data"
    bl_options = set()


class S3ORootPropsPanel(S3OPropsPanel):
    bl_idname = "S3O_PT_s3o_root_props"
    bl_label = "S3O Properties (Root)"

    @classmethod
    def poll(cls, context):
        return S3ORootProperties.poll(context.object)

    def draw(self, context: Context):
        layout = self.layout
        layout.use_property_split = True

        props = context.object.s3o_root

        column = layout.column()
        for prop in ['s3o_name', 'collision_radius', 'height', 'midpoint', 'texture_path_1', 'texture_path_2']:
            column.prop(props, prop)


class S3OAimPointPropsPanel(S3OPropsPanel):
    bl_idname = "S3O_PT_s3o_aim_point_props"
    bl_label = "S3O Properties (Aim Point)"

    @classmethod
    def poll(cls, context):
        return S3OAimPointProperties.poll(context.object)

    def draw(self, context: Context):
        layout = self.layout
        layout.use_property_split = True

        props = context.object.s3o_aim_point

        column = layout.column()
        for prop in ['pos', 'dir']:
            column.prop(props, prop)


def register():
    bpy.utils.register_class(S3ORootPropsPanel)
    bpy.utils.register_class(S3OAimPointPropsPanel)


def unregister():
    bpy.utils.unregister_class(S3ORootPropsPanel)
    bpy.utils.unregister_class(S3OAimPointPropsPanel)
