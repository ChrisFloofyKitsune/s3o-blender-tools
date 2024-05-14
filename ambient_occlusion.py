import itertools
import math
from collections.abc import Iterator, Callable

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, PointerProperty, CollectionProperty, IntProperty, EnumProperty
from bpy.types import Operator, Context, PropertyGroup


class ObjectExplodeEntry(PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object)


class AddObjExplodeEntry(Operator):
    bl_idname = 's3o_tools_ao.add_explode_entry'
    bl_label = 'Add Entry'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> set[str]:
        list_prop: bpy.types.CollectionProperty = context.scene.s3o_ao.objects_to_explode
        list_prop.add()
        return {'FINISHED'}


class RemoveObjExplodeEntry(Operator):
    bl_idname = 's3o_tools_ao.remove_explode_entry'
    bl_label = 'Remove Entry'

    def execute(self, context: Context) -> set[str]:
        list_prop: bpy.types.CollectionProperty = context.scene.s3o_ao.objects_to_explode
        list_prop.remove(len(list_prop) - 1)
        return {'FINISHED'}


class AOProps(PropertyGroup):
    def get_ao_dist(self):
        return bpy.context.scene.world.light_settings.distance

    def set_ao_dist(self, value):
        bpy.context.scene.world.light_settings.distance = value

    distance: FloatProperty(
        name='Distance',
        description='Length of rays used to check for occlusion',
        min=0,
        soft_max=64,
        get=get_ao_dist,
        set=set_ao_dist,
        subtype='DISTANCE',
        options=set(),
    )

    min_clamp: FloatProperty(
        name='Min Clamp',
        description=
        """The darkest possible level AO shading will go to.
        0 means even the darkest is allowed,
        1 means that everything will be full white. 
        0.5 is good if you dont want pieces to go too dark""",
        min=0,
        max=1,
        subtype='FACTOR',
        options=set(),
    )

    bias: FloatProperty(
        name='Bias',
        description=
        """Add this much to every vertex AO value.
        Positive values brighten, negative values darken.
        Results are still clamped to [0-1] in the end""",
        min=-1,
        max=1,
        subtype='FACTOR',
        options=set(),
    )

    gain: FloatProperty(
        name='Gain',
        description="""Multiply calculated AO terms with this value.
        A value of 2.0 would double the brightness of each value, 0.5 would half it.
        AO_out = min(1, max(min_clamp, AO_in * bias + gain))""",
        soft_min=0.1,
        soft_max=2,
        default=1,
        subtype='FACTOR',
        options=set(),
    )

    ground_plate: BoolProperty(
        name="Ground Plate",
        description="""Enable this when baking AO for ground units or buildings.
Disable for flying units.
            This puts a plane underneath the model, to make sure it is only lit from above.
            The plane will be placed at the origin (0,0,0)""",
        default=True
    )

    building_plate_size_x: IntProperty(
        name="Size X",
        min=1,
        soft_max=8,
    )

    building_plate_size_z: IntProperty(
        name="Size Z",
        min=1,
        soft_max=8,
    )

    building_plate_resolution_inner: IntProperty(
        options={"HIDDEN"}
    )

    def get_building_plate_res(self):
        return self.building_plate_resolution_inner

    def set_building_plate_res(self, value):
        log2_val = math.log2(value)
        if value < self.building_plate_resolution_inner:
            exp = math.floor(log2_val)
        else:
            exp = math.ceil(log2_val)

        self.building_plate_resolution_inner = 2 ** exp

    building_plate_resolution: IntProperty(
        name="Resolution",
        min=64,
        soft_max=1024,
        default=128,
        get=get_building_plate_res,
        set=set_building_plate_res,
    )

    objects_to_explode: CollectionProperty(
        name="Objects to Explode",
        type=ObjectExplodeEntry
    )

    selected_explode_entry: IntProperty()

    bake_target: EnumProperty(
        name='AO Bake Target',
        items=(
            ('ALL', "All Objects", "All Objects in Scene"),
            ('HIERARCHY', "Object Hierarchy", "All Objects in the Active Object's parent/child hierarchy"),
            ('ACTIVE', "Active Object Only", "Only the current Active Object"),
        )
    )

    reset_ao_value: FloatProperty(
        name="Reset AO Value",
        description="Value that the Ambient Occlusion data will be reset to",
        min=0,
        max=1,
        default=0.8,
        subtype='FACTOR',
    )


def ao_targets_iter(context: Context) -> Iterator[bpy.types.Object]:
    match context.scene.s3o_ao.bake_target:
        case 'ALL':
            for obj in context.scene.objects:
                if obj.type == 'MESH':
                    yield obj
        case 'HIERARCHY':
            if context.active_object is not None:
                parent_obj = context.active_object
                while parent_obj.parent is not None:
                    parent_obj = parent_obj.parent

            for obj in itertools.chain([parent_obj], parent_obj.children_recursive):
                if obj.type == 'MESH':
                    yield obj

        case 'ACTIVE':
            if context.active_object.type == 'MESH':
                yield context.active_object

def ao_val_each_get_set(
    input: bpy.types.Object | bmesh.types.BMesh, 
    func: Callable[[tuple[float, float, float, float]], tuple[float, float, float, float]]
):
    if isinstance(input, bmesh.types.BMesh):
        bm = input
    else:
        bm = bmesh.new(use_operators=False)
        bm.from_mesh(input.data)
    
    ao_data = bm.loops.layers.float_color.get(
        'ambient_occlusion',
        bm.loops.layers.float_color.new('ambient_occlusion')
    )

    for face in bm.faces:
        for face_corner in face.loops:
            face_corner[ao_data] = func(face_corner[ao_data])
    
    if bm is not input:
        bm.to_mesh(input.data)


class ShowAOInView(Operator):
    """Change the view settings to a preset such that AO data is visible"""
    bl_idname = "s3o_tools_ao.show_ao_in_view"
    bl_label = "To AO View"

    def execute(self, context: Context):
        context.space_data.shading.type = 'SOLID'
        context.space_data.shading.light = 'FLAT'
        context.space_data.shading.color_type = 'VERTEX'
        return {'FINISHED'}


class ResetAO(Operator):
    """ Reset Ambient Occlusion data to the value specified by 'Reset AO Value'"""
    bl_idname = "s3o_tools_ao.reset_ao_value"
    bl_label = "Reset AO"
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> set[str]:
        reset_val = (*((context.scene.s3o_ao.reset_ao_value,) * 3), 1.0)

        bpy.ops.object.select_all(action='DESELECT')
        for obj in ao_targets_iter(context):
            ao_val_each_get_set(obj, lambda _: reset_val)

        return {"FINISHED"}


reg_classes, unreg_classes = bpy.utils.register_classes_factory(
    [
        ObjectExplodeEntry,
        AddObjExplodeEntry,
        RemoveObjExplodeEntry,
        AOProps,
        ShowAOInView,
        ResetAO
    ]
)


def register():
    reg_classes()
    bpy.types.Scene.s3o_ao = PointerProperty(
        type=AOProps
    )


def unregister():
    unreg_classes()
    del bpy.types.Scene.s3o_ao
