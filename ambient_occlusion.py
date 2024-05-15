import math
from collections.abc import Iterator, Callable
from contextlib import AbstractContextManager

import numpy as np

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, PointerProperty, CollectionProperty, IntProperty, EnumProperty, \
    StringProperty
from bpy.types import Operator, Context, PropertyGroup, Event
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix
from . import util, obj_props
from .obj_props import S3ORootProperties


class ObjectExplodeEntry(PropertyGroup):
    obj: PointerProperty(
        type=bpy.types.Object,
        name='Target Object',
        description="'Exploded' object to be moved far away from the others while baking AO"
                    " so that internally hidden objects can appear to be lit"
    )


class AddObjExplodeEntry(Operator):
    """Add slot for an object to the list"""
    bl_idname = 's3o_tools_ao.add_explode_entry'
    bl_label = 'Add Entry'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context: Context) -> set[str]:
        list_prop: bpy.types.CollectionProperty = context.scene.s3o_ao.objects_to_explode
        list_prop.add()
        return {'FINISHED'}


class RemoveObjExplodeEntry(Operator):
    """Remove the last slot"""
    bl_idname = 's3o_tools_ao.remove_explode_entry'
    bl_label = 'Remove Entry'
    bl_options = {'REGISTER', 'UNDO'}

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
        default=128,
        min=0,
        soft_max=256,
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
        default=0.05,
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
        description="Building's X size in footprint squares (8x8 units). Leave 0 for Automatic",
        min=0
    )

    building_plate_size_z: IntProperty(
        name="Size Z",
        description="Building's Z size in footprint squares  (8x8 units). Leave 0 for Automatic",
        min=0
    )

    building_plate_resolution_inner: IntProperty(
        options={"HIDDEN"},
        default=64,
        min=32
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
        description="Output AO plate image resolution in pixels",
        min=32,
        soft_max=256,
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
            ('ALL', "All Objects", "Slowest! All Objects in Scene"),
            ('HIERARCHY', "Object Hierarchy", "All Objects in the Active Object's parent/child hierarchy"),
            ('ACTIVE', "Active Object Only", "Fastest! Only the current Active Object"),
        ),
        default='HIERARCHY'
    )

    reset_ao_value: FloatProperty(
        name="Reset AO Value",
        description="Value that the Ambient Occlusion data will be reset to",
        min=0,
        max=1,
        default=0.8,
        subtype='FACTOR',
    )


class ExplodeObjectsForBake(AbstractContextManager):

    context: Context
    original_matrices: dict[bpy.types.Object, Matrix]

    def __init__(self, context: Context):
        self.context = context
        self.original_matrices = {}

    def __enter__(self):
        to_explode = set(entry.obj for entry in self.context.scene.s3o_ao.objects_to_explode)
        ao_dist = self.context.scene.s3o_ao.distance

        for obj in ao_targets_iter(self.context):
            if obj in to_explode:
                self.original_matrices[obj] = obj.matrix_world.copy()
                obj.matrix_world.translation.z += ao_dist * 3 * len(self.original_matrices)

    def __exit__(self, exc_type, exc_val, exc_tb):
        for obj, orig_matrix in self.original_matrices.items():
            obj.matrix_world = orig_matrix


def ao_targets_iter(context: Context) -> Iterator[bpy.types.Object]:
    if context.active_object is None:
        raise ValueError('Context must have an active object!')

    match context.scene.s3o_ao.bake_target:
        case 'ALL':
            parent_objs = [o for o in context.scene.objects if o.parent is None]

            for parent in parent_objs:
                for obj in util.depth_first_child_iteration(parent):
                    if obj.type == 'MESH':
                        yield obj

        case 'HIERARCHY':
            parent_obj = context.active_object
            while parent_obj.parent is not None:
                parent_obj = parent_obj.parent

            for obj in util.depth_first_child_iteration(parent_obj):
                if obj.type == 'MESH':
                    yield obj

        case 'ACTIVE':
            if context.active_object.type == 'MESH':
                yield context.active_object


def ao_val_each_get_set(
    input_data: bpy.types.Object | bmesh.types.BMesh,
    func: Callable[[float], float]
):
    if isinstance(input_data, bmesh.types.BMesh):
        bm = input_data
    else:
        bm = bmesh.new(use_operators=False)
        bm.from_mesh(input_data.data)

    ao_data = bm.loops.layers.float_color.get(
        'ambient_occlusion',
        bm.loops.layers.float_color.new('ambient_occlusion')
    )

    for face in bm.faces:
        for face_corner in face.loops:
            new_ao_val = min(1.0, max(0.0, func(max(face_corner[ao_data][0:3]))))
            face_corner[ao_data] = (*((new_ao_val,) * 3), 1)

    if bm is not input_data:
        bm.to_mesh(input_data.data)


def make_ao_vertex_bake_plate(context: Context) -> bpy.types.Object:
    min_corner, max_corner = util.get_world_bounds_min_max(ao_targets_iter(context))
    center = (max_corner + min_corner) / 2
    center.z = 0

    ao_dist = context.scene.s3o_ao.distance
    plate_thickness = abs(min_corner.z) + ao_dist / 64
    radius = (max_corner.xy - min_corner.xy).length / 2 + ao_dist
    box = util.add_ground_box(context, radius, plate_thickness)
    box.location = center
    return box


class ToAOView(Operator):
    """Change the view settings to a preset such that AO data is visible"""
    bl_idname = "s3o_tools_ao.to_ao_view"
    bl_label = "To AO View"

    def execute(self, context: Context):
        context.space_data.shading.type = 'SOLID'
        context.space_data.shading.light = 'FLAT'
        context.space_data.shading.color_type = 'VERTEX'
        return {'FINISHED'}


class ToRenderView(Operator):
    """Shortcut to change to 'Rendered' viewport shading"""
    bl_idname = "s3o_tools_ao.to_rendered_view"
    bl_label = "To Rendered View"

    def execute(self, context: Context) -> set[str]:
        bpy.context.space_data.shading.type = 'RENDERED'
        return {'FINISHED'}


class ResetAO(Operator):
    """ Reset Ambient Occlusion data to the value specified by 'Reset AO Value'"""
    bl_idname = "s3o_tools_ao.reset_ao_value"
    bl_label = "Reset AO"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.scene.s3o_ao.bake_target == 'ALL' or context.active_object is not None

    def execute(self, context: Context) -> set[str]:
        reset_val = context.scene.s3o_ao.reset_ao_value

        bpy.ops.object.select_all(action='DESELECT')
        for obj in ao_targets_iter(context):
            ao_val_each_get_set(obj, lambda _: reset_val)

        return {"FINISHED"}


class BakeVertexAO(Operator):
    """ Bake vertex AO for the model """
    bl_idname = "s3o_tools_ao.bake_vertex_ao"
    bl_label = "Bake Vertex AO"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.scene.s3o_ao.bake_target == 'ALL' or context.active_object is not None

    def execute(self, context: Context) -> set[str]:
        prev_render_engine = context.scene.render.engine
        plate = None

        try:
            bpy.context.scene.render.engine = 'CYCLES'
            if context.scene.s3o_ao.ground_plate:
                prev_active = context.active_object
                plate = make_ao_vertex_bake_plate(context)
                context.view_layer.objects.active = prev_active

            bpy.ops.object.select_all(action='DESELECT')

            min_clamp = context.scene.s3o_ao.min_clamp
            gain = context.scene.s3o_ao.gain
            bias = context.scene.s3o_ao.bias

            with ExplodeObjectsForBake(context):
                for obj in ao_targets_iter(context):
                    context.view_layer.objects.active = obj
                    obj.select_set(True)

                    mesh: bpy.types.Mesh = obj.data
                    if mesh.color_attributes.get('ambient_occlusion', None) is None:
                        mesh.color_attributes.new(
                            name='ambient_occlusion',
                            type='FLOAT_COLOR',
                            domain='CORNER',
                        )
                        mesh.attributes.default_color_name = 'ambient_occlusion'
                        mesh.attributes.active_color_name = 'ambient_occlusion'

                    bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
                    ao_val_each_get_set(obj, lambda ao_in: max(min_clamp, ao_in * gain + bias))
                    obj.select_set(False)

        finally:
            if plate is not None:
                bpy.data.objects.remove(plate)
            bpy.context.scene.render.engine = prev_render_engine

        return {'FINISHED'}


class BakePlateAO(Operator, ExportHelper):
    """ Bake alpha-channel AO plate for building """
    bl_idname = "s3o_tools_ao.bake_building_plate"
    bl_label = "Bake Ground Plate AO"
    bl_options = {'REGISTER'}

    filename_ext = ".png"

    filter_glob: StringProperty(
        default="*.png",
        options={'HIDDEN'},
        maxlen=255,
    )

    @staticmethod
    def get_s3o_to_export(context: Context) -> S3ORootProperties:
        s3o_roots_in_scene = [o.s3o_root for o in context.scene.objects if S3ORootProperties.poll(o)]
        if len(s3o_roots_in_scene) == 1:
            return s3o_roots_in_scene[0]
        elif context.object is not None:
            return obj_props.get_s3o_root_object(context.object).s3o_root

    @classmethod
    def poll(cls, context: Context) -> bool:
        return context.scene.s3o_ao.bake_target == 'ALL' or context.active_object is not None

    def invoke(self, context: Context, event: Event) -> set[str]:
        if (s3o := self.get_s3o_to_export(context)) is not None:
            self.filepath = s3o.s3o_name + '_aoplane' + self.filename_ext
        return super().invoke(context, event)

    def execute(self, context: Context) -> set[str]:
        prev_render_engine = context.scene.render.engine
        plane = None

        temp_image = None
        temp_material = None

        try:
            bpy.context.scene.render.engine = "CYCLES"
            min_corner, max_corner = util.get_world_bounds_min_max(ao_targets_iter(context))

            size_x = context.scene.s3o_ao.building_plate_size_x
            size_z = context.scene.s3o_ao.building_plate_size_z

            if size_x <= 0 or size_z <= 0:
                if size_x == 0:
                    size_x = abs(max_corner.x - min_corner.x + 32) // 8
                if size_z == 0:
                    size_z = abs(max_corner.y - min_corner.y + 32) // 8

            center = (max_corner + min_corner) / 2
            center.z = 0

            resolution = context.scene.s3o_ao.building_plate_resolution

            bpy.ops.mesh.primitive_plane_add(location=center, size=8, calc_uvs=True)
            plane = context.active_object
            plane.scale = (size_x, size_z, 1)

            temp_image = bpy.data.images.new(
                name='ao_temp_image',
                width=resolution,
                height=resolution,
                is_data=True,
                alpha=True
            )
            temp_material = bpy.data.materials.new(name='ao_temp_mat')
            temp_material.use_nodes = True

            img_node = temp_material.node_tree.nodes.new('ShaderNodeTexImage')
            img_node.image = temp_image

            plane.active_material = temp_material

            bpy.ops.object.bake(
                type="AO",
                target='IMAGE_TEXTURES',
            )

            pixel_vals = np.reshape(temp_image.pixels, (resolution, resolution, temp_image.channels))
            # pixel values are going to be 0-1 in rgb and 1 in a
            # extract the rgb vals and remap to [0, 255]
            ao: np.ndarray = (pixel_vals.min(2) * 255).astype(np.uint16)

            # #BlameBeherith, for I merely ported his code
            modifier = 255 - min(ao[0, 0], ao[0, -1], ao[-1, 0], ao[-1, -1]) - 3
            max_darkness = 32

            ao = np.fmin(ao + modifier, 255)  # clamp upper
            ao = ao - ((255 - ao) // 8)  # Beherith: some darkening? hell if i remember
            ao = np.fmax(ao, max_darkness)  # clamp lower
            ao = 255 - ao  # invert for use as alpha channel

            x_threshold = resolution / (size_x * 0.5)
            y_threshold = resolution / (size_z * 0.5)

            # non-linear smoothing because perceived brightness is non-linear
            def smoothing(coord, threshold):
                return 1 - (1 - (coord / threshold) ** math.e)

            # fade to 0 near edges
            # I cannot spot a visible difference between
            # val = min(val, val * smooth) and val = val * smooth
            for (y, x), val in np.ndenumerate(ao):
                if x < x_threshold:
                    val = min(val, val * smoothing(x, x_threshold))
                    # val *= smoothing(x, x_threshold)
                if x > resolution - x_threshold:
                    val = min(val, val * smoothing(resolution - x - 1, x_threshold))
                    # val *= smoothing(resolution - x - 1, x_threshold)

                if y < y_threshold:
                    val = min(val, val * smoothing(y, y_threshold))
                    # val *= smoothing(y, y_threshold)
                if y > resolution - y_threshold:
                    val = min(val, val * smoothing(resolution - y - 1, y_threshold))
                    # val *= smoothing(resolution - y - 1, y_threshold)

                ao[y, x] = int(val)

            new_pixels = []
            for val in ao.ravel():
                new_pixels.extend([0, 0, 0, val / 255])

            temp_image.pixels = new_pixels
            temp_image.file_format = 'PNG'
            temp_image.save(filepath=self.filepath, quality=100)
        finally:
            if plane is not None:
                bpy.data.objects.remove(plane)

            if temp_image is not None:
                bpy.data.images.remove(temp_image)

            if temp_material is not None:
                bpy.data.materials.remove(temp_material)

            bpy.context.scene.render.engine = prev_render_engine
        return {'FINISHED'}


reg_classes, unreg_classes = bpy.utils.register_classes_factory(
    [
        ObjectExplodeEntry,
        AddObjExplodeEntry,
        RemoveObjExplodeEntry,
        AOProps,
        ToAOView,
        ToRenderView,
        ResetAO,
        BakeVertexAO,
        BakePlateAO
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
