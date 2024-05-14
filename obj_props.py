import math
from enum import StrEnum
from typing import Any, Literal, ClassVar

import bpy
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, StringProperty, PointerProperty, BoolProperty
from bpy.types import PropertyGroup, Object, Context
from bpy_extras import object_utils
from mathutils import Vector, Matrix, Euler
from . import util


class S3OPropertyGroup(PropertyGroup):
    empty_type: ClassVar[Literal['ROOT', 'AIM_POINT', 'PLACEHOLDER']]
    being_updated: BoolProperty(options={'HIDDEN', 'SKIP_SAVE'}, default=False)

    def update(self, context: Context | None):
        ...

    def update_from_placeholder(self, tag: str, obj: Object):
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

    def update(self, context: Context | None):
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
            obj: Object = self.id_data
            obj_pos = obj.matrix_world.translation

            col_radius_pl = get_or_create_placeholder_empty(
                obj, context,
                S3ORootProperties.PlaceholderTag.MidpointCollisionRadius
            )
            if col_radius_pl is not None:
                col_radius_pl.empty_display_type = 'SPHERE'
                col_radius_pl.empty_display_size = self.collision_radius
                col_radius_pl.matrix_world = Matrix.LocRotScale(
                    self.midpoint @ util.TO_FROM_BLENDER_SPACE + obj_pos,
                    None,
                    None
                )

            height_pl = get_or_create_placeholder_empty(
                obj, context,
                S3ORootProperties.PlaceholderTag.Height
            )
            if height_pl is not None:
                height_pl.empty_display_type = 'CIRCLE'
                height_pl.empty_display_size = self.collision_radius / 2
                height_pl.matrix_world = Matrix.LocRotScale(
                    Vector(
                        (self.midpoint.x, self.height, self.midpoint.z)
                    ) @ util.TO_FROM_BLENDER_SPACE + obj_pos,
                    Euler((math.pi / 2, 0, 0)),
                    None
                )
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
        update=update,
        options=set(),
    )

    height: FloatProperty(
        name="Height",
        subtype="DISTANCE",
        update=update,
        options=set(),
    )

    midpoint: FloatVectorProperty(
        name='Midpoint',
        subtype="XYZ_LENGTH",
        size=3,
        update=update,
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
    placeholder_tag = 'aim_ray'

    def update(self, context: Context | None):
        if self.being_updated:
            return

        if not S3OAimPointProperties.poll(self.id_data):
            raise ValueError(
                'Object no longer meets the requirements for s3o aim point props. '
                '(Did change it from being an empty?)'
            )

        try:
            self.being_updated = True
            obj: Object = self.id_data

            if self.align_to_rotation:
                my_fwd = obj.matrix_world.normalized().col[2].xyz
                self.inner_dir = my_fwd @ util.TO_FROM_BLENDER_SPACE

            aim_pl = get_or_create_placeholder_empty(
                self.id_data, context,
                S3OAimPointProperties.placeholder_tag
            )
            if aim_pl is not None:
                aim_pl.empty_display_type = 'SINGLE_ARROW'
                aim_pl.empty_display_size = 10
                aim_pl.matrix_world = Matrix.LocRotScale(
                    self.pos @ util.TO_FROM_BLENDER_SPACE + obj.matrix_world.translation,
                    Vector((0, 0, 1)).rotation_difference(self.dir @ util.TO_FROM_BLENDER_SPACE),
                    None
                )
        finally:
            self.being_updated = False

    def update_from_placeholder(self, tag: str, obj: Object):
        if self.being_updated or tag != S3OAimPointProperties.placeholder_tag:
            return

        new_pos = util.TO_FROM_BLENDER_SPACE @ (
            obj.matrix_world.translation - self.id_data.matrix_world.translation
        )

        if not self.align_to_rotation:
            new_dir = obj.matrix_world.normalized().col[2].xyz @ util.TO_FROM_BLENDER_SPACE
            self.inner_dir = new_dir

        self.pos = new_pos

    pos: FloatVectorProperty(
        name="Aim Position",
        subtype="XYZ_LENGTH",
        size=3,
        update=update,
        options=set(),
    )

    inner_dir: FloatVectorProperty(
        size=3, options={'HIDDEN'}, default=(0, 0, 1)
    )

    def set_dir(self, new_value: tuple[float, float, float]):
        new_dir = Vector(new_value).normalized()
        if new_dir.length_squared == 0:
            self.inner_dir = Vector((0, 0, 1))
        else:
            self.inner_dir = new_dir

    def get_dir(self):
        return self.inner_dir

    dir: FloatVectorProperty(
        name="Aim Direction",
        subtype="XYZ",
        size=3,
        set=set_dir,
        get=get_dir,
        update=update,
        options=set(),
    )

    align_to_rotation: BoolProperty(
        name="Align Direction to Rotation",
        description="Force aim direction to align this object's forward direction",
        default=False,
        # update=update_from_prop, # gets covered by the depsgraph listener
        options=set()
    )


class S3OPlaceholderProperties(S3OPropertyGroup):
    empty_type = 'PLACEHOLDER'
    tag: StringProperty(name='Tag', options={'HIDDEN'})


def get_or_create_placeholder_empty(
    parent_obj: Object, context: Context | None, tag: str
) -> Object | None:
    parent_name = util.strip_suffix(parent_obj.name)

    placeholder = next(
        (
            c for c in parent_obj.children
            if S3OPlaceholderProperties.poll(c)
               and c.s3o_placeholder.tag == tag
        ),
        None
    )
    if placeholder is None and context is not None:
        placeholder = object_utils.object_data_add(context, None, name=f'{parent_name}.{tag}')
        placeholder.s3o_empty_type = 'PLACEHOLDER'
        placeholder.s3o_placeholder.tag = tag
        placeholder.rotation_mode = 'YXZ'
        placeholder.parent = parent_obj

    return placeholder


def refresh_all_s3o_props(context: Context | None = None):
    for obj in bpy.data.objects:
        for prop_name in obj.keys():
            prop = getattr(obj, prop_name)
            if isinstance(prop, S3OPropertyGroup):
                if prop.poll(obj):
                    prop.update(context)


def get_s3o_root_object(obj: Object | None) -> Object | None:
    if obj is None:
        return None
    
    while not S3ORootProperties.poll(obj) and obj.parent is not None:
        obj = obj.parent
    return obj if S3ORootProperties.poll(obj) else None


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
        options={'HIDDEN'},
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


def unregister():
    del Object.s3o_empty_type

    bpy.utils.unregister_class(S3ORootProperties)
    del Object.s3o_root

    bpy.utils.unregister_class(S3OAimPointProperties)
    del Object.s3o_aim_point

    bpy.utils.unregister_class(S3OPlaceholderProperties)
    del Object.s3o_placeholder
