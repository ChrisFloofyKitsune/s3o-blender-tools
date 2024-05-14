import itertools
import math

import bpy.utils
from bpy.types import Operator, Context, Menu, Event
from mathutils import Matrix, Vector
from . import obj_props, util


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

    texture_name_1: bpy.props.StringProperty(
        name='Color Texture',
        default="",
    )

    texture_name_2: bpy.props.StringProperty(
        name='Other Texture',
        default="",
    )

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: Context) -> set[str]:
        bpy.ops.object.empty_add(type='ARROWS')
        root = bpy.context.object
        root.name = self.name
        root.empty_display_size = self.collision_radius / 4

        root.rotation_mode = 'YXZ'
        root.matrix_basis = util.TO_FROM_BLENDER_SPACE
        root.s3o_empty_type = 'ROOT'

        s3o_root: props.S3ORootProperties = root.s3o_root
        s3o_root.s3o_name = self.name
        s3o_root.collision_radius = self.collision_radius
        s3o_root.height = self.height
        s3o_root.midpoint = self.midpoint
        s3o_root.texture_path_1 = self.texture_name_1
        s3o_root.texture_path_2 = self.texture_name_2

        bpy.ops.object.select_all(action='DESELECT')
        root.select_set(True)
        bpy.context.view_layer.objects.active = root

        return {'FINISHED'}


class AddS3OAimPoint(Operator):
    """Add a new S3O Aim Point to the scene as a child of the Active Object"""
    bl_idname = "s3o_tools.add_s3o_aim_point"
    bl_label = "Add Aim Point as Child"
    bl_options = {'REGISTER', 'UNDO'}

    name: bpy.props.StringProperty(
        name="Name",
        default="flare"
    )

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.active_object is not None

    def execute(self, context: Context) -> set[str]:
        bpy.ops.object.mode_set(mode='OBJECT')
        parent_obj = context.active_object

        bpy.ops.object.empty_add(type='SPHERE', radius=1.5)
        aim_point = context.object
        aim_point.name = self.name
        aim_point.rotation_mode = 'YXZ'
        aim_point.s3o_empty_type = 'AIM_POINT'
        aim_point.s3o_aim_point.pos = (0, 0, 0)
        aim_point.s3o_aim_point.dir = (0, 0, 1)

        bpy.ops.object.select_all(action='DESELECT')
        aim_point.select_set(True)
        context.view_layer.objects.active = aim_point

        aim_point.parent = parent_obj
        aim_point.matrix_parent_inverse = Matrix.Identity(4)
        aim_point.matrix_basis = Matrix.Identity(4)
        util.select_active_in_outliner(context)

        return {'FINISHED'}


class AddMeshAsChild(Operator):
    """ Add new Mesh as child of Active Object"""
    bl_idname = "s3o_tools.add_mesh_as_child"
    bl_label = "Add Mesh as Child"
    bl_options = {'REGISTER', 'UNDO'}

    mesh_type: bpy.props.EnumProperty(
        name='Mesh Type',
        items=[
            # @formatter:off
            ('plane',       'Plane',        '', 'MESH_PLANE',       0),
            ('cube',        'Cube',         '', 'MESH_CUBE',        1),
            ('circle',      'Circle',       '', 'MESH_CIRCLE',      2),
            ('uv_sphere',   'UV Sphere',    '', 'MESH_UVSPHERE',    3),
            ('ico_sphere',  'Ico Sphere',   '', 'MESH_ICOSPHERE',   4),
            ('cylinder',    'Cylinder',     '', 'MESH_CYLINDER',    5),
            ('cone',        'Cone',         '', 'MESH_CONE',        6),
            ('torus',       'Torus',        '', 'MESH_TORUS',       7),
            # @formatter:on
        ]
    )

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.active_object is not None

    def execute(self, context: Context) -> set[str]:
        bpy.ops.object.mode_set(mode='OBJECT')
        parent_obj = context.active_object

        getattr(bpy.ops.mesh, f'primitive_{self.mesh_type}_add')()
        new_obj = context.object
        new_obj.parent = parent_obj
        new_obj.rotation_mode = parent_obj.rotation_mode

        util.select_active_in_outliner(context)

        return {'FINISHED'}


class S3OifyExistingObjectHierarchy(Operator):
    """ Prepare existing Object Parent->Child Hierarchy for S3O Export """
    bl_idname = "s3o_tools.s3oify_object_hierarchy"
    bl_label = "S3Oify Object Hierarchy"
    bl_options = {'REGISTER', 'UNDO'}

    s3o_model_name: bpy.props.StringProperty(
        name="S3O Model Name"
    )

    create_copy: bpy.props.BoolProperty(
        name="Create Copy",
        default=True,
    )

    auto_height: bpy.props.BoolProperty(
        name="Auto Height",
        description="Automatically determine height",
        default=True,
    )

    auto_collision_radius: bpy.props.BoolProperty(
        name="Auto Collision Radius",
        description="Automatically determine Collision Radius",
        default=True,
    )

    auto_midpoint_y: bpy.props.BoolProperty(
        name="Auto Midpoint Y",
        description="Automatically determine Midpoint Y Coordinate",
        default=True,
    )

    auto_midpoint_xz: bpy.props.BoolProperty(
        name="Auto Midpoint XZ",
        description="Automatically determine Midpoint XZ",
        default=False
    )

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.active_object and props.get_s3o_root_object(context.active_object) is None

    def invoke(self, context: Context, event: Event) -> set[str]:
        self.s3o_model_name = util.strip_suffix(context.active_object.name)

        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context: Context) -> set[str]:
        top_level_object = context.active_object
        while top_level_object.parent is not None:
            top_level_object = top_level_object.parent

        # Create Copy ?
        if self.create_copy:
            bpy.ops.object.select_all(action='DESELECT')
            context.view_layer.objects.active = top_level_object
            top_level_object.select_set(True)
            bpy.ops.object.select_grouped(extend=True, type='CHILDREN_RECURSIVE')
            bpy.ops.object.duplicate()
            top_level_object = context.active_object

        min_corner, max_corner = util.get_world_bounds_min_max(
            itertools.chain([top_level_object], top_level_object.children_recursive)
        )
 
        max_corner = util.TO_FROM_BLENDER_SPACE @ max_corner
        min_corner = util.TO_FROM_BLENDER_SPACE @ min_corner
        center = (max_corner + min_corner) / 2

        bpy.ops.s3o_tools.add_s3o_root(
            name=self.s3o_model_name,
            collision_radius=max(max_corner - min_corner) / 2 if self.auto_collision_radius else 20,
            height=max_corner.y if self.auto_height else 40,
            midpoint=Vector(
                (
                    center.x if self.auto_midpoint_xz else 0,
                    center.y if self.auto_midpoint_y else 20,
                    center.z if self.auto_midpoint_xz else 0,
                )
            ),
            texture_name_1="",
            texture_name_2="",
        )
        s3o_root = context.active_object

        prev_location = top_level_object.matrix_world.translation
        s3o_root.location = (prev_location.x, prev_location.y, 0)

        bpy.ops.object.select_all(action='DESELECT')
        top_level_object.select_set(True)
        s3o_root.select_set(True)
        bpy.ops.object.parent_no_inverse_set(keep_transform=True)

        for empty_child in (c for c in top_level_object.children_recursive if c.type == 'EMPTY'):
            empty_child.empty_display_type = 'SPHERE'
            empty_child.empty_display_size = 1.5

            empty_child.s3o_empty_type = 'AIM_POINT'
            empty_child.s3o_aim_point.pos = (0, 0, 0)
            empty_child.s3o_aim_point.dir = (0, 0, 1)
        
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = s3o_root
        s3o_root.select_set(True)
        
        return {'FINISHED'}


def add_ops_menu_func(menu: Menu, context: Context):
    menu.layout.operator(AddS3ORoot.bl_idname, icon='EMPTY_ARROWS')
    menu.layout.operator(AddS3OAimPoint.bl_idname, icon='EMPTY_SINGLE_ARROW')
    row = menu.layout.row()
    row.enabled = bpy.ops.s3o_tools.add_mesh_as_child.poll()
    row.operator_menu_enum(AddMeshAsChild.bl_idname, 'mesh_type', icon='OUTLINER_OB_MESH')
    menu.layout.separator()


def register():
    bpy.utils.register_class(RefreshS3OProps)
    bpy.utils.register_class(SetAllRotationModes)
    bpy.utils.register_class(AddS3ORoot)
    bpy.utils.register_class(AddS3OAimPoint)
    bpy.utils.register_class(AddMeshAsChild)
    bpy.utils.register_class(S3OifyExistingObjectHierarchy)

    bpy.types.VIEW3D_MT_add.prepend(add_ops_menu_func)


def unregister():
    bpy.utils.unregister_class(RefreshS3OProps)
    bpy.utils.unregister_class(SetAllRotationModes)
    bpy.utils.unregister_class(AddS3ORoot)
    bpy.utils.unregister_class(AddS3OAimPoint)
    bpy.utils.unregister_class(AddMeshAsChild)
    bpy.utils.unregister_class(S3OifyExistingObjectHierarchy)

    bpy.types.VIEW3D_MT_add.remove(add_ops_menu_func)
