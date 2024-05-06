import bpy.utils
from bpy.types import Operator, Context, Menu
from . import props, util


class RefreshS3OProps(Operator):
    """Refresh all S3O props and their placeholders"""
    bl_idname = "s3o_tools.refresh_s3o_props"
    bl_label = "Refresh s3o props and placeholders"
    bl_options = {'REGISTER'}

    def execute(self, context: Context) -> set[str]:
        props.refresh_all_s3o_props(context)
        return {'FINISHED'}


class SetAllRotationModes(Operator):
    """Set all the rotation modes on all (or just selected) objects"""
    bl_idname = "s3o_tools.set_all_rotation_modes"
    bl_label = "Set Rotation Modes"
    bl_options = {'REGISTER', 'UNDO'}

    rotation_modes = bpy.types.Object.bl_rna.properties['rotation_mode'].enum_items
    mode: bpy.props.EnumProperty(
        name="Rotation Mode",
        items=[(m.identifier, m.name, m.description, m.value) for m in rotation_modes]
    )

    preserve_rotations: bpy.props.BoolProperty(
        name="Preserve Rotations",
        default=True
    )

    def execute(self, context: Context) -> set[str]:
        if next(iter(context.selected_objects), None) is None:
            bpy.ops.object.select_all(action="SELECT")

        changes_made = False

        for obj in context.selected_objects:
            if not obj.rotation_mode == self.mode:
                if self.preserve_rotations:
                    obj.rotation_mode = 'QUATERNION'

                obj.rotation_mode = self.mode
                changes_made = True

        return {'FINISHED'} if changes_made else {'CANCELLED'}


class AddS3ORoot(Operator):
    """Add a new S3O Root Object to the scene"""
    bl_idname = "s3o_tools.add_s3o_root"
    bl_label = "Add S3O Root"
    bl_options = {'REGISTER', 'UNDO'}

    name: bpy.props.StringProperty(
        name="Name",
        default="new s3o model"
    )

    collision_radius: bpy.props.FloatProperty(
        name="Collision Radius",
        subtype="DISTANCE",
        default=20
    )

    height: bpy.props.FloatProperty(
        name="Height",
        subtype="DISTANCE",
        default=40
    )

    midpoint: bpy.props.FloatVectorProperty(
        name="Midpoint",
        subtype="XYZ_LENGTH",
        size=3,
        default=(0, 20, 0)
    )

    texture_path_1: bpy.props.StringProperty(
        name='Color Texture',
        default="",
    )

    texture_path_2: bpy.props.StringProperty(
        name='Other Texture',
        default="",
    )

    def execute(self, context: Context) -> set[str]:
        bpy.ops.object.empty_add(type='ARROWS')
        root = bpy.context.object
        root.name = self.name
        root.empty_display_size = self.collision_radius / 4

        root.rotation_mode = 'YXZ'
        root.matrix_basis = util.TO_FROM_BLENDER_SPACE
        root.s3o_empty_type = 'ROOT'

        root.s3o_root.s3o_name = self.name
        root.s3o_root.collision_radius = self.collision_radius
        root.s3o_root.height = self.height
        root.s3o_root.midpoint = self.midpoint
        root.s3o_root.texture_path_1 = self.texture_path_1
        root.s3o_root.texture_path_2 = self.texture_path_2

        bpy.ops.object.select_all(action='DESELECT')
        root.select_set(True)
        bpy.context.view_layer.objects.active = root

        return {'FINISHED'}


class AddS3OAimPoint(Operator):
    """Add a new S3O Aim Point to the scene"""
    bl_idname = "s3o_tools.add_s3o_aim_point"
    bl_label = "Add S3O Aim Point"
    bl_options = {'REGISTER', 'UNDO'}

    name: bpy.props.StringProperty(
        name="Name",
        default="flare"
    )

    def execute(self, context: Context) -> set[str]:
        bpy.ops.object.empty_add(type='SPHERE', radius=1.5)
        aim_point = bpy.context.object
        aim_point.name = self.name
        aim_point.rotation_mode = 'YXZ'
        aim_point.s3o_empty_type = 'AIM_POINT'
        aim_point.s3o_aim_point.pos = (0, 0, 0)
        aim_point.s3o_aim_point.dir = (0, 0, 1)

        bpy.ops.object.select_all(action='DESELECT')
        aim_point.select_set(True)
        bpy.context.view_layer.objects.active = aim_point

        return {'FINISHED'}


def add_ops_menu_func(menu: Menu, context: Context):
    menu.layout.operator(AddS3ORoot.bl_idname)
    menu.layout.operator(AddS3OAimPoint.bl_idname)
    menu.layout.separator()


def register():
    bpy.utils.register_class(RefreshS3OProps)
    bpy.utils.register_class(SetAllRotationModes)
    bpy.utils.register_class(AddS3ORoot)
    bpy.utils.register_class(AddS3OAimPoint)

    bpy.types.VIEW3D_MT_add.prepend(add_ops_menu_func)


def unregister():
    bpy.utils.unregister_class(RefreshS3OProps)
    bpy.utils.unregister_class(SetAllRotationModes)
    bpy.utils.unregister_class(AddS3ORoot)
    bpy.utils.unregister_class(AddS3OAimPoint)

    bpy.types.VIEW3D_MT_add.remove(add_ops_menu_func)
