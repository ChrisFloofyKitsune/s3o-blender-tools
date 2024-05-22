import math
from collections.abc import Iterator, Callable
from contextlib import AbstractContextManager

import numpy as np
import numpy.typing as npt

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
    min_distance: FloatProperty(
        name='Min Distance',
        description="",
        default=1,
        min=0,
        soft_max=8,
        subtype='DISTANCE',
        options=set(),
    )

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


def ensure_ao_layer(obj: bpy.types.Object) -> bpy.types.FloatColorAttribute:
    mesh: bpy.types.Mesh = obj.data
    if 'ambient_occlusion' not in mesh.color_attributes:
        mesh.color_attributes.new(
            name='ambient_occlusion',
            type='FLOAT_COLOR',
            domain='CORNER',
        )

    mesh.attributes.default_color_name = 'ambient_occlusion'
    mesh.attributes.active_color_name = 'ambient_occlusion'

    return mesh.color_attributes.get('ambient_occlusion')


def ao_vals_get(obj: bpy.types.Object) -> np.ndarray:
    ao_layer = ensure_ao_layer(obj)
    colors = np.zeros(shape=len(ao_layer.data) * 4, dtype=np.single)
    ao_layer.data.foreach_get('color', colors)
    return colors.reshape((-1, 4))[:, 0:3].max(axis=1)


def ao_vals_set(obj: bpy.types.Object, values: npt.ArrayLike):
    ao_layer = ensure_ao_layer(obj)

    values = np.broadcast_to(values, len(ao_layer.data))
    values = values.clip(0, 1)

    colors = np.repeat(values, 3).reshape((-1, 3))
    colors = np.insert(colors, 3, 1, axis=1)

    ao_layer.data.foreach_set('color', colors.ravel())
    obj.update_tag()


def ao_val_foreach_get_set(
    obj: bpy.types.Object,
    func: Callable[[float], float]
):
    ao_vals = ao_vals_get(obj)
    ao_vals = np.frompyfunc(func, 1, 1)(ao_vals)
    ao_vals_set(obj, ao_vals)


def make_ao_vertex_bake_plate(context: Context) -> bpy.types.Object:
    min_corner, max_corner = util.get_world_bounds_min_max(ao_targets_iter(context))
    center = (max_corner + min_corner) / 2
    center.z = 0

    min_dist = context.scene.s3o_ao.min_distance
    ao_dist = context.scene.s3o_ao.distance
    plate_thickness = abs(min_corner.z) + max(1, min_dist, ao_dist / 64) * 2
    radius = (max_corner.xy - min_corner.xy).length / 2 + min_dist + ao_dist
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

        for obj in ao_targets_iter(context):
            ao_vals_set(obj, reset_val)

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
        prev_selection = list(context.selected_objects)
        prev_active = context.active_object

        try:
            bpy.context.scene.render.engine = 'CYCLES'
            if context.scene.s3o_ao.ground_plate:
                plate = make_ao_vertex_bake_plate(context)
                context.view_layer.objects.active = prev_active

            bpy.ops.object.select_all(action='DESELECT')

            ao_props: AOProps = context.scene.s3o_ao
            min_dist = ao_props.min_distance
            min_clamp = ao_props.min_clamp
            gain = ao_props.gain
            bias = ao_props.bias

            def ao_adjust(ao_in):
                return max(min_clamp, ao_in * gain + bias)

            with ExplodeObjectsForBake(context):
                for obj in ao_targets_iter(context):
                    if obj.hide_render:
                        continue

                    ensure_ao_layer(obj)
                    starting_mode = obj.mode

                    context.view_layer.objects.active = obj
                    obj.select_set(True)
                    bpy.ops.object.mode_set(mode='OBJECT')

                    orig_object = obj
                    bpy.ops.object.duplicate()
                    obj = context.active_object

                    orig_object.hide_render = True

                    bm = bmesh.new()
                    bm.from_mesh(obj.data)
                    bmesh.ops.split_edges(bm, edges=list(e for e in bm.edges if not e.smooth))
                    bm.to_mesh(obj.data)

                    if min_dist > 0:
                        orig_dist = ao_props.distance

                        ao_props.distance = min_dist
                        if plate is not None:
                            plate.hide_render = True
                        bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
                        min_ao_data = ao_vals_get(obj)

                        ao_props.distance = orig_dist
                        if plate is not None:
                            plate.hide_render = False
                        bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
                        ao_data = ao_vals_get(obj)

                        mesh: bpy.types.Mesh = obj.data
                        bm = bmesh.new()
                        bm.from_mesh(mesh)
                        bm.verts.ensure_lookup_table()

                        corners_to_fix = set(np.flatnonzero(np.isclose(min_ao_data, 0, atol=0.05)))
                        for corner_idx in corners_to_fix:
                            vert_idx = mesh.loops[corner_idx].vertex_index
                            bm_loop = next(l for l in bm.verts[vert_idx].link_loops if l.index == corner_idx)

                            other_loops = list(
                                l for l in {*list(bm_loop.face.loops), *list(bm_loop.link_loops)} if
                                    l.index not in corners_to_fix
                            )

                            if len(other_loops) != 0:
                                ao_data[corner_idx] = min([ao_data[l.index] for l in other_loops])

                            mesh_vert = mesh.vertices[vert_idx]
                            if mesh_vert.co.y > 0.5:
                                mesh_vert.select |= ao_data[corner_idx] <= 0.9

                        ao_data = np.interp(ao_data, [min(ao_data), max(ao_data)], [0, 1])
                        ao_data = np.frompyfunc(ao_adjust, 1, 1)(ao_data)

                        ao_vals_set(obj, ao_data)
                        bpy.ops.paint.vertex_paint_toggle()
                        mesh.use_paint_mask_vertex = True
                        bpy.ops.paint.vertex_color_smooth()
                        bpy.ops.paint.vertex_paint_toggle()
                    else:
                        bpy.ops.object.bake(type='AO', target='VERTEX_COLORS')
                        ao_val_foreach_get_set(obj, ao_adjust)
                    
                    ao_vals_set(orig_object, ao_vals_get(obj))
                    bpy.data.objects.remove(object=obj)

                    orig_object.hide_render = False
                    with context.temp_override(**{'object': orig_object, 'active_object': orig_object}):
                        bpy.ops.object.mode_set(mode=starting_mode)

        finally:
            if plate is not None:
                bpy.data.objects.remove(plate)
            bpy.context.scene.render.engine = prev_render_engine
            for obj in prev_selection:
                obj.select_set(True)
            context.view_layer.objects.active = prev_active

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
        elif context.object is not None \
            and (root_obj := obj_props.get_s3o_root_object(context.object)) is not None:
            return root_obj.s3o_root

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
            ao: np.ndarray = (pixel_vals[:, :, 0:3].max(2) * 255).astype(np.uint16)

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
