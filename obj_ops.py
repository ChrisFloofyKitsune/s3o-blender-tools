import bpy.utils
from bpy.types import Operator, Context
from . import props


class RefreshS3OProps(Operator):
    """ Refresh all S3O props and their placeholders """
    bl_idname = "s3o_tools.refresh_s3o_props"
    bl_label = "Refresh s3o props and placeholders"
    bl_options = {'REGISTER'}

    def execute(self, context: Context) -> set[str]:
        props.refresh_all_s3o_props(context)
        return {'FINISHED'}


class SetAllRotationModes(Operator):
    """ Set all the rotation modes on all (or just selected) objects """
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


def register():
    bpy.utils.register_class(RefreshS3OProps)
    bpy.utils.register_class(SetAllRotationModes)


def unregister():
    bpy.utils.unregister_class(RefreshS3OProps)
    bpy.utils.unregister_class(SetAllRotationModes)
