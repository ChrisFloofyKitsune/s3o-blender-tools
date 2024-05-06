import bpy.utils
from bpy.types import Panel, Context
from .s3o_props import S3ORootProperties, S3OAimPointProperties, S3OPlaceholderProperties


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

        props: S3ORootProperties = context.object.s3o_root

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

        props: S3OAimPointProperties = context.object.s3o_aim_point

        column = layout.column()
        column.prop(props, 'pos')
        column.use_property_split = False
        column.prop(props, 'align_to_rotation')
        column.use_property_split = True
        
        row = column.row()
        row.enabled = not props.align_to_rotation
        row.prop(props, 'dir')

class S3OPlaceholderPropsPanel(S3OPropsPanel):
    bl_idname = "S3O_PT_s3o_placeholder_props"
    bl_label = "S3O Properties (Placeholder)"

    @classmethod
    def poll(cls, context):
        return S3OPlaceholderProperties.poll(context.object)

    def draw(self, context: Context):
        layout = self.layout

        props: S3OPlaceholderProperties = context.object.s3o_placeholder
        row = layout.row()
        row.prop(props, 'tag')
        row.enabled = False

        op = layout.operator(operator='object.select_grouped', text='Select Parent')
        op.type = 'PARENT'


def register():
    bpy.utils.register_class(S3ORootPropsPanel)
    bpy.utils.register_class(S3OAimPointPropsPanel)
    bpy.utils.register_class(S3OPlaceholderPropsPanel)


def unregister():
    bpy.utils.unregister_class(S3ORootPropsPanel)
    bpy.utils.unregister_class(S3OAimPointPropsPanel)
    bpy.utils.unregister_class(S3OPlaceholderPropsPanel)
