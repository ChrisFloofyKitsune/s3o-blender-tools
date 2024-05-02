from typing import Any

import bpy
from bpy.props import EnumProperty, FloatProperty, FloatVectorProperty, StringProperty, PointerProperty
from bpy.types import PropertyGroup


class S3OProperties(PropertyGroup):
    s3o_empty_type: EnumProperty(
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

    root__name: StringProperty(
        name="s3o_name"
    )

    root__collision_radius: FloatProperty(
        name="collision_radius",
        subtype="DISTANCE",
        default=0
    )

    root__height: FloatProperty(
        name="height",
        subtype="DISTANCE",
    )

    root__midpoint: FloatVectorProperty(
        name='midpoint',
        subtype="XYZ_LENGTH",
        size=3,
    )

    root__texture_path_1: StringProperty(
        name='texture_path_1'
    )

    root__texture_path_2: StringProperty(
        name='texture_path_2'
    )

    aim_point__pos: FloatVectorProperty(
        name="aim_pos",
        subtype="XYZ_LENGTH",
        size=3
    )

    aim_point__dir: FloatVectorProperty(
        name="aim_dir",
        subtype="XYZ",
        size=3,
        default=(0, 0, 1)
    )

    def poll(self, obj: bpy.types.Object | Any):
        return isinstance(obj, bpy.types.Object) and obj.type == 'EMPTY'


def register():
    bpy.utils.register_class(S3OProperties)
    bpy.types.Object.s3o_props = PointerProperty(
        type=S3OProperties,
        poll=S3OProperties.poll,
        options=set(),
    )

def unregister():
    bpy.utils.unregister_class(S3OProperties)
