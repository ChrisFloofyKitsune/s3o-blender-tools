import dataclasses
from typing import Self

import numpy

import bmesh
import bpy.types
import bpy_extras.object_utils
from bpy_extras import object_utils
from mathutils import Vector
from . import util, vertex_cache
from .props import S3ORootProperties, S3OAimPointProperties
from .s3o import S3O, S3OPiece, S3OVertex
from .util import batched, TO_FROM_BLENDER_SPACE


def s3o_to_blender_obj(
    s3o: S3O,
    *,
    name="loaded_s3o",
    merge_vertices=True,
) -> bpy.types.Object:
    if bpy.context.object:
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

    bpy.ops.s3o_tools.add_s3o_root(
        name=name,
        collision_radius=s3o.collision_radius,
        height=s3o.height,
        midpoint=s3o.midpoint,
        texture_path_1=s3o.texture_path_1,
        texture_path_2=s3o.texture_path_2,
    )
    root = bpy.context.object

    recurse_add_s3o_piece_as_child(
        s3o.root_piece, root, merge_vertices=merge_vertices
    )

    bpy.ops.s3o_tools.refresh_s3o_props()

    return root


def recurse_add_s3o_piece_as_child(
    piece: S3OPiece,
    obj: bpy.types.Object,
    *,
    merge_vertices=True
):
    new_obj: bpy.types.Object
    # 0-1 triangle pieces are emit pieces
    if len(piece.indices) < 4:
        new_obj = make_aim_point_from_s3o_empty(piece)
    else:
        new_obj = make_bl_obj_from_s3o_mesh(
            piece,
            merge_vertices=merge_vertices
        )

    new_obj.rotation_mode = 'YXZ'
    new_obj.location = piece.parent_offset
    new_obj.parent = obj

    for child in piece.children:
        recurse_add_s3o_piece_as_child(
            child, new_obj,
            merge_vertices=merge_vertices
        )

    return new_obj


def make_aim_point_from_s3o_empty(s3o_piece: S3OPiece) -> bpy.types.Object:
    aim_position = (0, 0, 0)
    aim_dir = (0, 0, 0)

    match (len(s3o_piece.vertices)):
        case 0:
            aim_dir = (0, 0, 1)
        case 1:
            aim_dir = s3o_piece.vertices[0][0]
        case 2:
            aim_position = s3o_piece.vertices[0].position
            aim_dir = (s3o_piece.vertices[1].position - aim_position).normalized()
        case _:
            pass

    bpy.ops.object.empty_add(type='SPHERE', radius=1.5)
    aim_point = bpy.context.object
    aim_point.name = s3o_piece.name
    set_aim_point_props(aim_point, aim_position, aim_dir)

    return aim_point


def set_aim_point_props(obj: bpy.types.Object, position: Vector, direction: Vector):
    obj.s3o_empty_type = 'AIM_POINT'
    obj.s3o_aim_point.pos = position
    obj.s3o_aim_point.dir = direction


def make_bl_obj_from_s3o_mesh(
    piece: S3OPiece,
    *,
    merge_vertices=True
) -> bpy.types.Object:
    for vertex in piece.vertices:
        vertex.normal.normalize()

    p_vertices = piece.vertices
    p_indices: list[tuple[int, int]] = [(idx, idx) for idx in piece.indices]
    """ vertex index, ao index """

    # store this now so that values are not overlooked as a result of the de-duplication steps
    v_ambient_occlusion: list[float] = [v.ambient_occlusion for v in p_vertices]

    duplicate_verts = []

    if merge_vertices:
        duplicate_verts = util.make_duplicates_mapping(p_vertices, 0.001)

        for i, current_vert_index in enumerate(idx_pair[0] for idx_pair in p_indices):
            if current_vert_index in duplicate_verts:
                p_indices[i] = (duplicate_verts[current_vert_index], p_indices[i][1])

    type_face_indices = list[tuple[int, int, int, int]]

    face_indices_list: list[type_face_indices] = [
        [
            (pair1[0], pair1[0], pair1[0], pair1[1]),
            (pair2[0], pair2[0], pair2[0], pair2[1]),
            (pair3[0], pair3[0], pair3[0], pair3[1]),
        ]
        for pair1, pair2, pair3 in util.batched(p_indices, 3)
    ]

    # unpack all the vertices into their separate components
    # vertexes can share the values of these
    v_positions: dict[int, Vector] = {}
    v_normals: dict[int, Vector] = {}

    # tex_coords are always considered unique per vertex
    v_tex_coords: dict[int, Vector] = {}

    for i, vertex in ((i, v) for i, v in enumerate(p_vertices) if i not in duplicate_verts):
        (v_positions[i], v_normals[i], v_tex_coords[i]) = vertex

    if merge_vertices:
        duplicate_positions = util.make_duplicates_mapping(v_positions, 0.002)
        norms_to_check = {i: v_normals[i] for i in duplicate_positions.keys()}
        duplicate_normals = util.make_duplicates_mapping(norms_to_check, 0.01)

        for face_indices in face_indices_list:
            for i, (pos_idx, norm_idx, tex_coord_idx, ao_idx) in enumerate(face_indices):
                face_indices[i] = (
                    duplicate_positions[pos_idx] if pos_idx in duplicate_positions else pos_idx,
                    duplicate_normals[norm_idx] if norm_idx in duplicate_normals else norm_idx,
                    tex_coord_idx,
                    ao_idx
                )
    # endif merge_vertices

    bm = bmesh.new()
    bmesh_vert_lookup: dict[int, dict[int, bmesh.types.BMVert]] = {}
    for face_indices in face_indices_list:
        for (pos_idx, norm_idx, _, _) in face_indices:
            if pos_idx not in bmesh_vert_lookup:
                bmesh_vert_lookup[pos_idx] = {}

            if norm_idx not in bmesh_vert_lookup[pos_idx]:
                vert = bm.verts.new(v_positions[pos_idx])
                vert.normal = v_normals[norm_idx]
                bmesh_vert_lookup[pos_idx][norm_idx] = vert

    uv_layer = bm.loops.layers.uv.new("UVMap")
    ao_layer = bm.loops.layers.float_color.new("ambient_occlusion")

    for face_indices in face_indices_list:
        face_verts = [bmesh_vert_lookup[pos_idx][norm_idx] for pos_idx, norm_idx, _, _ in face_indices]
        try:
            face = bm.faces.new(face_verts)
            face.smooth = True

            for i, loop in enumerate(face.loops):
                _, _, tex_coord_idx, ao_idx = face_indices[i]
                loop[uv_layer].uv = v_tex_coords[tex_coord_idx]
                loop[ao_layer] = (*((v_ambient_occlusion[ao_idx],) * 3), 1)
        except Exception as err:
            print(err)

    if merge_vertices:
        for edge in bm.edges:
            edge.smooth = not edge.is_boundary
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)

    mesh = bpy.data.meshes.new(piece.name)
    bm.to_mesh(mesh)
    mesh.attributes.default_color_name = "ambient_occlusion"
    mesh.attributes.active_color_name = "ambient_occlusion"

    new_obj = object_utils.object_data_add(bpy.context, mesh)
    new_obj.name = piece.name

    if len(mesh.polygons) == 1:
        print(f'{piece.name} looks like it is an emit piece')

    return new_obj


def blender_obj_to_s3o(obj: bpy.types.Object) -> S3O:
    if not S3ORootProperties.poll(obj):
        raise ValueError('Object to export must have s3o root properties')

    if (count := sum(1 for c in obj.children if c.type == 'MESH' or S3OAimPointProperties.poll(c))) != 1:
        raise ValueError(f'Expected only ONE non-placeholder child of the root object, found {count}')

    props: S3ORootProperties = obj.s3o_root

    s3o = S3O()

    s3o.collision_radius = props.collision_radius
    s3o.height = props.height
    s3o.midpoint = props.midpoint

    s3o.texture_path_1 = props.texture_path_1
    s3o.texture_path_2 = props.texture_path_2

    s3o.root_piece = blender_obj_to_piece(
        next(c for c in obj.children if c.type == 'MESH' or S3OAimPointProperties.poll(c))
    )

    return s3o


def blender_obj_to_piece(obj: bpy.types.Object) -> S3OPiece | None:

    if not ((is_ap := S3OAimPointProperties.poll(obj)) or obj.type == 'MESH') or obj.parent is None:
        return None

    piece = S3OPiece()
    piece.primitive_type = S3OPiece.PrimitiveType.Triangles

    piece.name = util.strip_suffix(obj.name)

    offset = obj.matrix_world.translation - obj.parent.matrix_world.translation
    piece.parent_offset = offset @ TO_FROM_BLENDER_SPACE

    to_world_space = obj.matrix_world.inverted_safe()
    to_world_space.translation = (0, 0, 0)

    if is_ap:
        ap_props: S3OAimPointProperties = obj.s3o_aim_point
        position = ap_props.pos
        direction = ap_props.dir.normalized()

        verts: list[S3OVertex] = []
        if not numpy.allclose(position, (0, 0, 0)):
            verts.append(S3OVertex(position))
            verts.append(S3OVertex(position + direction))
        elif not numpy.allclose(direction, (0, 0, 1)):
            verts.append(S3OVertex(direction))

        piece.vertices = verts

    else:  # is mesh
        tmp_obj: bpy.types.Object | None = None
        tmp_mesh: bpy.types.Mesh | None = None
        try:
            tmp_mesh: bpy.types.Mesh = obj.data.copy()
            tmp_obj = bpy_extras.object_utils.object_data_add(bpy.context, tmp_mesh)
            bpy.ops.object.select_all(action='DESELECT')
            tmp_obj.select_set(True)

            tmp_obj.matrix_world = obj.matrix_world
            bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)

            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.quads_convert_to_tris()
            bpy.ops.mesh.delete_loose()
            bpy.ops.object.mode_set(mode='OBJECT')

            tmp_mesh.transform(TO_FROM_BLENDER_SPACE)

            uv_layer: bpy.types.MeshUVLoopLayer = tmp_mesh.uv_layers.active
            ao_layer: bpy.types.FloatColorAttribute = tmp_mesh.color_attributes.get('ambient_occlusion', None)

            # face corner (aka loop) walking based on the .ply export implementation at:
            # https://github.com/blender/blender/blob/main/source/blender/io/ply/exporter/ply_export_load_plydata.cc
            @dataclasses.dataclass(eq=True, frozen=True, slots=True)
            class FaceCornerData:
                uv: (float, float)
                ao: float
                norm: (float, float, float)
                v_idx: int

                @classmethod
                def from_loop_index(cls, l_idx: int) -> Self:
                    uv = tuple(uv_layer.uv[l_idx].vector)
                    ao = ao_layer.data[l_idx].color[0]
                    norm = tuple(tmp_mesh.corner_normals[l_idx].vector)
                    v_idx = tmp_mesh.loops[l_idx].vertex_index
                    return FaceCornerData(uv, ao, norm, v_idx)

            vertex_map: dict[FaceCornerData, int] = {}

            loop_to_s3o_idx: list[int] = []
            s3o_idx_to_data: list[FaceCornerData] = []

            for loop_index in range(len(tmp_mesh.loops)):
                fc_data = FaceCornerData.from_loop_index(loop_index)
                s3o_index = vertex_map.setdefault(fc_data, len(vertex_map))
                loop_to_s3o_idx.append(s3o_index)
                while len(s3o_idx_to_data) <= s3o_index:
                    s3o_idx_to_data.append(fc_data)

            for data in s3o_idx_to_data:
                new_vert = S3OVertex(
                    tmp_mesh.vertices[data.v_idx].co.copy(),
                    Vector(data.norm),
                    Vector(data.uv)
                )
                new_vert.ambient_occlusion = data.ao
                new_vert.freeze()
                piece.vertices.append(new_vert)

            for loop_idx in range(len(tmp_mesh.loops)):
                idx = loop_to_s3o_idx[loop_idx]
                assert 0 <= idx < len(piece.vertices)
                piece.indices.append(idx)

            optimize_piece(piece)
        except Exception as err:
            print("!!! ERROR exporting mesh!!!")
            print(f"{obj.name} --> {piece.name}")
            raise err

        if tmp_mesh is not None:
            bpy.data.meshes.remove(tmp_mesh)

    piece.children = [
        p for p in (blender_obj_to_piece(c) for c in obj.children) if p is not None
    ]

    return piece


def optimize_piece(piece: S3OPiece):
    remap = {}
    new_indices = []
    print('[INFO]', 'Optimizing:', piece.name)
    for index in piece.indices:
        vertex = piece.vertices[index]
        vertex.freeze()
        if vertex not in remap:
            remap[vertex] = len(remap)
        new_indices.append(remap[vertex])

    new_vertices = [(index, vertex) for vertex, index in remap.items()]
    new_vertices.sort()
    new_vertices = [vertex for _, vertex in new_vertices]

    if piece.primitive_type == "triangles" and len(new_indices) > 0:
        tris = list(batched(new_indices, 3))
        acmr = vertex_cache.average_transform_to_vertex_ratio(tris)

        tmp = vertex_cache.get_cache_optimized_triangles(tris)
        acmr_new = vertex_cache.average_transform_to_vertex_ratio(tmp)
        if acmr_new < acmr:
            new_indices = []
            for tri in tmp:
                new_indices.extend(tri)

    vertex_map = []
    remapped_indices = []
    for index in new_indices:
        try:
            new_index = vertex_map.index(index)
        except ValueError:
            new_index = len(vertex_map)
            vertex_map.append(index)

        remapped_indices.append(new_index)

    new_vertices = [new_vertices[index] for index in vertex_map]
    new_indices = remapped_indices

    piece.indices = new_indices
    piece.vertices = new_vertices
