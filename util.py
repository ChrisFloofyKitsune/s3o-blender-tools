import functools
import math
import os.path
from collections.abc import Iterable, Generator
from enum import StrEnum
from itertools import islice
from typing import TypeVar, ContextManager

import numpy as np
import numpy.typing as npt

import bmesh
import bpy
import bpy_extras.object_utils
from bpy.utils.previews import ImagePreviewCollection
from mathutils import Matrix, Vector

TO_FROM_BLENDER_SPACE = Matrix(
    (
        (-1, 0, 0, 0),
        (0, 0, 1, 0),
        (0, 1, 0, 0),
        (0, 0, 0, 1),
    )
).freeze()
""" Ends up being just a couple of rotations. Also is it's own inverse! """

T = TypeVar('T')

custom_icons: ImagePreviewCollection


class S3OIcon(StrEnum):
    LOGO = 'logo'
    LOGO_TRANSPARENT = 'logo_transparent'

    @property
    def icon_id(self) -> int:
        global custom_icons
        return custom_icons[self].icon_id


def batched(iterable: Iterable[T], n) -> Generator[tuple[T]]:
    """
    Batch data into tuples of length n. The last batch may be shorter.
    batched('ABCDEFG', 3) --> ABC DEF G

    https://docs.python.org/3.11/library/itertools.html#itertools-recipes
    """

    if n < 1:
        raise ValueError('n must be at least one')
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch


def extract_null_terminated_string(data: bytes, offset: int) -> str:
    """
    :param data: raw bytes
    :param offset: offset into bytes
    :return: bytes up to (not including) '\0' decoded as utf8 string
    """
    if offset == 0:
        return b"".decode()
    else:
        return data[offset:data.index(b'\x00', offset)].decode()


def make_duplicates_mapping(
    values: dict[int, npt.ArrayLike] | npt.ArrayLike,
    tolerance=0.001,
) -> npt.NDArray[int]:
    np_array: npt.NDArray
    try:
        if type(values) is dict:
            if len(values) == 0:
                return np.array([], dtype=int)
            example_array = np.array(next(iter(values.values()), ()))
            np_array = np.full_like(
                example_array, fill_value=np.nan, shape=(max(values.keys()) + 1, *example_array.shape)
            )
            np_array[np.array(list(values.keys()), dtype=int)] = [np.array(v) for v in values.values()]
        else:
            np_array = np.array(values)
            if np_array.size == 0:
                return np.array([], dtype=int)

        idx_to_orig_idx = np.arange(len(np_array), dtype=int)

        for idx in range(len(np_array) - 1):
            current_value = np_array[idx]

            # skip if value is "empty" or if this value was already marked as a duplicate
            if np.all(np.isnan(current_value)):
                continue
            if idx_to_orig_idx[idx] < idx:
                continue

            slice_compare_results = np.isclose(np_array[idx + 1:], current_value, atol=tolerance, rtol=0)
            # exclude first axis
            slice_compare_results = np.all(slice_compare_results, axis=tuple(range(1, np_array.ndim)))
            np.copyto(idx_to_orig_idx[idx + 1:], idx, where=slice_compare_results)
        return idx_to_orig_idx

    except Exception as err:
        print("WARNING could not find dupes!", err)
    return {}


def strip_suffix(blender_name: str):
    if "." not in blender_name:
        return blender_name

    head, tail = blender_name.rsplit(".", 1)
    if tail.isnumeric():
        return head
    return blender_name


def library_load_addon_assets() -> ContextManager:
    dirname = os.path.dirname(os.path.abspath(__file__))
    return bpy.data.libraries.load(
        filepath=os.path.join(dirname, 'SpringModelingTemplate.blend'),
        assets_only=True,
        link=True,
        create_liboverrides=True,
        reuse_liboverrides=True,
    )


def select_active_in_outliner(context: bpy.types.Context):
    area = next((area for area in bpy.data.screens[context.screen.name].areas if area.type == 'OUTLINER'), None)
    if area is not None:
        region = next(region for region in area.regions if region.type == 'WINDOW')
        if region is not None:

            # the Outliner has not been updated yet, so we must wait a moment
            def temp_outliner_select(**kwargs):
                with context.temp_override(**kwargs):
                    bpy.ops.outliner.show_active()

            bpy.app.timers.register(
                functools.partial(temp_outliner_select, window=context.window, area=area, region=region),
                first_interval=0.01
            )


def get_world_bounds_min_max(objects: Iterable[bpy.types.Object]) -> tuple[Vector, Vector]:
    max_corner = Vector((-math.inf,) * 3)
    min_corner = Vector((math.inf,) * 3)

    for obj in objects:
        world_space_corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        max_corner.x = max(max_corner.x, *[corner.x for corner in world_space_corners])
        max_corner.y = max(max_corner.y, *[corner.y for corner in world_space_corners])
        max_corner.z = max(max_corner.z, *[corner.z for corner in world_space_corners])

        min_corner.x = min(min_corner.x, *[corner.x for corner in world_space_corners])
        min_corner.y = min(min_corner.y, *[corner.y for corner in world_space_corners])
        min_corner.z = min(min_corner.z, *[corner.z for corner in world_space_corners])

    return min_corner, max_corner


def add_ground_box(context: bpy.types.Context, radius: float, depth: float) -> bpy.types.Object:
    """
    This function takes inputs and returns vertex and face arrays.
    no actual mesh data creation is done here.
    """

    verts = [
        (+1.0, +1.0, -1.0),
        (+1.0, -1.0, -1.0),
        (-1.0, -1.0, -1.0),
        (-1.0, +1.0, -1.0),
        (+1.0, +1.0, 0),
        (+1.0, -1.0, 0),
        (-1.0, -1.0, 0),
        (-1.0, +1.0, 0),
    ]

    faces = [
        (0, 1, 2, 3),
        (4, 7, 6, 5),
        (0, 4, 5, 1),
        (1, 5, 6, 2),
        (2, 6, 7, 3),
        (4, 0, 3, 7),
    ]

    # apply size
    for i, v in enumerate(verts):
        verts[i] = v[0] * radius, v[1] * radius, v[2] * depth

    mesh = bpy.data.meshes.new("Box")

    bm = bmesh.new()

    for v_co in verts:
        bm.verts.new(v_co)

    bm.verts.ensure_lookup_table()
    for f_idx in faces:
        bm.faces.new([bm.verts[i] for i in f_idx])

    bm.to_mesh(mesh)
    mesh.update()

    return bpy_extras.object_utils.object_data_add(context, mesh)


def depth_first_child_iteration(parent_object: bpy.types.Object) -> Iterable[bpy.types.Object]:
    traversal_stack = [parent_object]

    while len(traversal_stack) != 0:
        current_object = traversal_stack.pop()
        yield current_object
        traversal_stack.extend(reversed(current_object.children))


def register():
    global custom_icons
    custom_icons = bpy.utils.previews.new()
    dirname = os.path.dirname(os.path.abspath(__file__))
    custom_icons.load('logo', os.path.join(dirname, 'logo.png'), 'IMAGE')
    custom_icons.load('logo_transparent', os.path.join(dirname, 'logo_transparent.png'), 'IMAGE')


def unregister():
    global custom_icons
    bpy.utils.previews.remove(custom_icons)
