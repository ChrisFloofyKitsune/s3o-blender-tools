import traceback
import warnings
from enum import StrEnum
from typing import Any, Literal, ClassVar

import bpy
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, StringProperty, PointerProperty, BoolProperty
from bpy.types import PropertyGroup, Object, Context
from bpy_extras import object_utils
from mathutils import Vector
from . import util


class S3OPropertyGroup(PropertyGroup):
    empty_type: ClassVar[Literal['ROOT', 'AIM_POINT', 'PLACEHOLDER']]
    being_updated: BoolProperty(options={'HIDDEN', 'SKIP_SAVE'}, default=False)

    def update_from_prop(self, context: Context):
        ...

    def update_from_placeholder(self, tag: str, placeholder_obj: Object):
        ...

    @classmethod
    def poll(cls, obj: bpy.types.Object | Any):
        return isinstance(obj, bpy.types.Object) and obj.type == 'EMPTY' and obj.s3o_empty_type == cls.empty_type

    def _poll(self, obj: bpy.types.Object | Any):
        return self.__class__.poll(obj)


class S3ORootProperties(S3OPropertyGroup):
    class PlaceholderTag(StrEnum):
        MidpointCollisionRadius = 'midpoint_and_collision_radius'
        Height = 'height'

    empty_type = 'ROOT'

    def update_from_prop(self, context: Context):
        # no infinite recursion via the depsgraph listener thank you very much
        if self.being_updated:
            return

        if not S3ORootProperties.poll(self.id_data):
            raise ValueError(
                'Object no longer meets the requirements for s3o root props. '
                '(Did change it from being an empty?)'
            )

        try:
            self.being_updated = True
            obj: bpy.types.Object = self.id_data

            col_radius_pl = get_or_create_placeholder_empty(
                obj, context,
                S3ORootProperties.PlaceholderTag.MidpointCollisionRadius
            )
            col_radius_pl.empty_display_type = 'SPHERE'
            col_radius_pl.empty_display_size = self.collision_radius
            col_radius_pl.scale = (1, 1, 1)
            col_radius_pl.location = self.midpoint @ util.TO_FROM_BLENDER_SPACE @ obj.matrix_basis

            height_pl = get_or_create_placeholder_empty(
                obj, context,
                S3ORootProperties.PlaceholderTag.Height
            )
            height_pl.empty_display_type = 'CIRCLE'
            height_pl.empty_display_size = self.collision_radius / 2
            height_pl.scale = (1, 1, 1)
            height_pl.location = Vector((self.midpoint.x, self.height, self.midpoint.z))
            height_pl.location = height_pl.location @ util.TO_FROM_BLENDER_SPACE @ obj.matrix_basis
            height_pl.rotation_quaternion = obj.matrix_basis.col[2].xyz.rotation_difference((0, 1, 0))
        finally:
            self.being_updated = False

    last_scale_change: FloatProperty(options={'HIDDEN', 'SKIP_SAVE'}, default=1)

    def update_from_placeholder(self, tag: str, obj: Object):
        if self.being_updated:
            return

        new_pos = util.TO_FROM_BLENDER_SPACE @ (
            obj.matrix_world.translation - self.id_data.matrix_world.translation
        )

        match tag:
            case S3ORootProperties.PlaceholderTag.MidpointCollisionRadius:
                if abs(1 - (scale := obj.matrix_basis.median_scale)) >= 0.01:
                    scale_delta = scale - self.last_scale_change
                    self.last_scale_change = scale
                    self.collision_radius *= 1 + scale_delta
                else:
                    self.last_scale_change = 1.0

                self.midpoint = new_pos
            case S3ORootProperties.PlaceholderTag.Height:
                self.height = new_pos.y

    s3o_name: StringProperty(
        name="Name"
    )
    collision_radius: FloatProperty(
        name="Collision Radius",
        subtype="DISTANCE",
        default=10,
        update=update_from_prop,
        options=set(),
    )

    height: FloatProperty(
        name="Height",
        subtype="DISTANCE",
        update=update_from_prop,
        options=set(),
    )

    midpoint: FloatVectorProperty(
        name='Midpoint',
        subtype="XYZ_LENGTH",
        size=3,
        update=update_from_prop,
        options=set(),
    )

    texture_path_1: StringProperty(
        name='Color Texture',
        options=set(),
    )

    texture_path_2: StringProperty(
        name='Other Texture',
        options=set(),
    )


class S3OAimPointProperties(S3OPropertyGroup):
    empty_type = 'AIM_POINT'

    pos: FloatVectorProperty(
        name="Aim Position",
        subtype="XYZ_LENGTH",
        size=3
    )

    dir: FloatVectorProperty(
        name="Aim Direction",
        subtype="XYZ",
        size=3,
        default=(0, 0, 1)
    )


class S3OPlaceholderProperties(S3OPropertyGroup):
    empty_type = 'PLACEHOLDER'
    tag: StringProperty(options={'HIDDEN'})


def get_or_create_placeholder_empty(
    parent_obj: Object, context: Context, tag: str
) -> Object:
    parent_name = util.strip_suffix(parent_obj.name)

    placeholder = next(
        (
            c for c in parent_obj.children
            if S3OPlaceholderProperties.poll(c)
               and c.s3o_placeholder.tag == tag
        ),
        None
    )
    if placeholder is None:
        print(parent_obj)
        traceback.print_stack()
        placeholder = object_utils.object_data_add(context, None, name=f'{parent_name}.{tag}')
        placeholder.s3o_empty_type = 'PLACEHOLDER'
        placeholder.s3o_placeholder.tag = tag
        placeholder.parent = parent_obj
        placeholder.rotation_mode = 'QUATERNION'

    return placeholder


responding_to_depsgraph = False
insanity_counter = 0


@bpy.app.handlers.persistent
def s3o_placeholder_depsgraph_listener(*_):
    depsgraph = bpy.context.evaluated_depsgraph_get()

    global insanity_counter
    global responding_to_depsgraph
    if responding_to_depsgraph:
        return

    # we only care of the updates started with a placeholder object
    update = next(iter(depsgraph.updates), None)
    if update is None or not S3OPlaceholderProperties.poll(update.id):
        return

    try:
        if insanity_counter != 0:
            warnings.warn_explicit(f's3o props depsgraph listener has looped {insanity_counter} times!!')
        insanity_counter += 1

        responding_to_depsgraph = True
        obj = update.id.original
        parent = obj.parent
        tag = obj.s3o_placeholder.tag

        if S3ORootProperties.poll(parent) and not parent.s3o_root.being_updated:
            parent.s3o_root.update_from_placeholder(tag, obj)
        elif S3OAimPointProperties.poll(parent):
            parent.s3o_aim_point.update_from_placeholder(tag, obj)
    finally:
        insanity_counter -= 1
        responding_to_depsgraph = False


def register():
    Object.s3o_empty_type = EnumProperty(
        items=[
            (
                'ROOT', 's3o root',
                'placeholder to contain the top level properties of the s3o object', 0
            ),
            (
                'AIM_POINT', 's3o aim/emit point',
                'point and direction for aiming, firing weapons, particle emissions, etc', 1
            ),
            (
                'PLACEHOLDER', 'empty object visual placeholder',
                'placeholder to visually show a s3o prop and allow manipulation of it'
            )
        ],
        name="S3O Empty Type",
        options=set(),
    )

    bpy.utils.register_class(S3ORootProperties)
    Object.s3o_root = PointerProperty(
        type=S3ORootProperties,
        poll=S3ORootProperties._poll,
        options=set(),
    )

    bpy.utils.register_class(S3OAimPointProperties)
    Object.s3o_aim_point = PointerProperty(
        type=S3OAimPointProperties,
        poll=S3OAimPointProperties._poll,
        options=set(),
    )

    bpy.utils.register_class(S3OPlaceholderProperties)
    Object.s3o_placeholder = PointerProperty(
        type=S3OPlaceholderProperties,
        poll=S3OPlaceholderProperties._poll,
        options=set()
    )

    bpy.app.handlers.depsgraph_update_post.append(s3o_placeholder_depsgraph_listener)


def unregister():
    bpy.app.handlers.depsgraph_update_post.remove(s3o_placeholder_depsgraph_listener)

    del Object.s3o_empty_type

    bpy.utils.unregister_class(S3ORootProperties)
    del Object.s3o_root

    bpy.utils.unregister_class(S3OAimPointProperties)
    del Object.s3o_aim_point

    bpy.utils.unregister_class(S3OPlaceholderProperties)
    del Object.s3o_placeholder
