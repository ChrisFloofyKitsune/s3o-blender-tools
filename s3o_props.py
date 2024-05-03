from typing import Any, Literal

import bpy
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, StringProperty, PointerProperty
from bpy.types import PropertyGroup


class S3OPropertyGroup(PropertyGroup):
    empty_type: Literal['ROOT'] | Literal['AIM_POINT']

    @classmethod
    def poll(cls, obj: bpy.types.Object | Any):
        return isinstance(obj, bpy.types.Object) and obj.type == 'EMPTY' and obj.s3o_empty_type == cls.empty_type

    def _poll(self, obj: bpy.types.Object | Any):
        return self.__class__.poll(obj)


class S3ORootProperties(S3OPropertyGroup):
    empty_type = 'ROOT'

    s3o_name: StringProperty(
        name="Name"
    )

    collision_radius: FloatProperty(
        name="Collision Radius",
        subtype="DISTANCE",
        default=0
    )

    height: FloatProperty(
        name="Height",
        subtype="DISTANCE",
    )

    midpoint: FloatVectorProperty(
        name='Midpoint',
        subtype="XYZ_LENGTH",
        size=3,
    )

    texture_path_1: StringProperty(
        name='Color Texture'
    )

    texture_path_2: StringProperty(
        name='Other Texture'
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


def register():
    bpy.types.Object.s3o_empty_type = EnumProperty(
        items=[
            (
                'ROOT', 's3o root',
                'placeholder to contain the top level properties of the s3o object', 0
            ),
            (
                'AIM_POINT', 's3o aim/emit point',
                'point and direction for aiming, firing weapons, particle emissions, etc', 1
            ),
        ],
        name="S3O Empty Type",
        options=set(),
    )

    bpy.utils.register_class(S3ORootProperties)
    bpy.types.Object.s3o_root = PointerProperty(
        type=S3ORootProperties,
        poll=S3ORootProperties._poll,
        options=set(),
    )

    bpy.utils.register_class(S3OAimPointProperties)
    bpy.types.Object.s3o_aim_point = PointerProperty(
        type=S3OAimPointProperties,
        poll=S3OAimPointProperties._poll,
        options=set(),
    )


def unregister():
    bpy.utils.unregister_class(S3ORootProperties)
    bpy.utils.unregister_class(S3OAimPointProperties)
