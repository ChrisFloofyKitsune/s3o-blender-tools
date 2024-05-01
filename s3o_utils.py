import math
from copy import copy

import bmesh
import bpy.types
from bpy_extras import object_utils
from mathutils import Vector, Matrix
from mathutils.geometry import normal
from . import util, vertex_cache
from .s3o import S3O, S3OPiece, S3OVertex
from .util import batched

TO_BLENDER_SPACE = Matrix(
    (
        (-1, 0, 0, 0),
        (0, 0, 1, 0),
        (0, 1, 0, 0),
        (0, 0, 0, 1),
    )
).freeze()
FROM_BLENDER_SPACE = TO_BLENDER_SPACE.inverted().freeze()


def closest_vertex(vtable: list[S3OVertex], q: int, tolerance: float):  # returns the index of the closest vertex pos
    v = vtable[q].position
    for i in range(len(vtable)):
        v2 = vtable[i].position
        if abs(v2[0] - v[0]) < tolerance and abs(v2[1] - v[1]) < tolerance and abs(v2[2] - v[2]) < tolerance:
            return i
    print('[WARN] No matching vertex for', v, ' not even self!')
    return q


def in_smoothing_group(piece: S3OPiece, face_a: int, face_b: int, tolerance: float, step: int):
    """ returns whether the two primitives share a smoothed edge """
    shared = 0
    for va in range(face_a, face_a + step):
        for vb in range(face_b, face_b + step):
            v = piece.vertices[piece.indices[va]]
            v2 = piece.vertices[piece.indices[vb]]
            if abs(v2[0][0] - v[0][0]) < tolerance and abs(v2[0][1] - v[0][1]) < tolerance and abs(
                v2[0][2] - v[0][2]
            ) < tolerance:
                if abs(v2[1][0] - v[1][0]) < tolerance and abs(v2[1][1] - v[1][1]) < tolerance and abs(
                    v2[1][2] - v[1][2]
                ) < tolerance:
                    shared += 1
    if shared >= 3:
        print('[WARN]', shared, 'shared and normal matching vertices faces', face_a, face_b, piece.name)
    return shared == 2


def create_blender_obj(
    s3o: S3O,
    *,
    name="loaded_s3o",
    merge_vertices=True,
) -> bpy.types.Object:
    if bpy.context.object:
        bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.select_all(action='DESELECT')

    bpy.ops.object.empty_add(type='ARROWS', radius=s3o.collision_radius / 4)
    root = bpy.context.object
    root.name = name

    bpy.ops.object.empty_add(type='SPHERE', location=s3o.midpoint, radius=s3o.collision_radius)
    radius_empty = bpy.context.object
    radius_empty.name = f'{name}.collision_radius'
    radius_empty.parent = root

    bpy.ops.object.empty_add(type='SINGLE_ARROW', location=(0, s3o.height, 0), radius=s3o.collision_radius / 2)
    height_empty = bpy.context.object
    height_empty.name = f'{name}.height'
    height_empty.rotation_euler = Vector((0, 0, 1)).rotation_difference((0, 1, 0)).to_euler()
    height_empty.parent = root

    recurse_add_s3o_piece_as_child(
        s3o.root_piece, root, merge_vertices=merge_vertices
    )

    bpy.ops.object.select_all(action='DESELECT')
    root.select_set(True)

    root.matrix_basis = TO_BLENDER_SPACE @ root.matrix_basis
    root.location = (0, 0, 0)
    # bpy.ops.object.transform_apply(location=False)

    return root


def recurse_add_s3o_piece_as_child(
    piece: S3OPiece,
    obj: bpy.types.Object,
    *,
    merge_vertices=True
):
    new_obj: bpy.types.Object
    if len(piece.indices) < 3:
        new_obj = make_obj_from_s3o_empty(piece)
    else:
        new_obj = make_obj_from_s3o_mesh(
            piece,
            merge_vertices=merge_vertices
        )

    new_obj.location = piece.parent_offset
    new_obj.parent = obj

    for child in piece.children:
        recurse_add_s3o_piece_as_child(
            child, new_obj,
            merge_vertices=merge_vertices
        )

    return new_obj


def make_obj_from_s3o_empty(s3o_piece: S3OPiece) -> bpy.types.Object:
    emit_position = (0, 0, 0)
    emit_dir = (0, 0, 0)

    match (len(s3o_piece.vertices)):
        case 0:
            emit_dir = (0, 0, 1)
        case 1:
            emit_dir = s3o_piece.vertices[0][0]
        case 2:
            emit_position = s3o_piece.vertices[0].position
            emit_dir = s3o_piece.vertices[1].position - emit_position
        case _:
            pass

    rotation = Vector((0, 0, 1)).rotation_difference(emit_dir).to_euler()

    bpy.ops.object.empty_add(type='SPHERE', radius=0.5)
    empty_obj = bpy.context.object
    empty_obj.name = s3o_piece.name

    bpy.ops.object.empty_add(
        type='SINGLE_ARROW', radius=5,
        location=emit_position, rotation=rotation
    )
    aim_point = bpy.context.object
    aim_point.name = empty_obj.name + ".emit_ray"
    aim_point.parent = empty_obj

    return empty_obj


def make_obj_from_s3o_mesh(
    piece: S3OPiece,
    *,
    merge_vertices=True
) -> bpy.types.Object:

    for vertex in piece.vertices:
        vertex.normal.normalize()

    p_vertices = copy(piece.vertices)
    p_indices = copy(piece.indices)

    close_pos = util.close_to_comparator(threshold=0.002)
    close_norm = util.close_to_comparator(threshold=0.01)
    close_tex_coord = util.close_to_comparator(threshold=0.01)

    # always combine all exact duplicates
    duplicate_verts = util.duplicates_by_predicate(
        p_vertices,
        lambda v1, v2: (
            close_pos(v1.position, v2.position)
            and close_norm(v1.normal, v2.normal)
            and close_tex_coord(v1.tex_coords, v2.tex_coords)
        )
    )

    for i, current_vert_index in enumerate(p_indices):
        if current_vert_index in duplicate_verts:
            p_indices[i] = duplicate_verts[current_vert_index]

    type_face_indices = list[tuple[int, int, int]]

    face_indices_list: list[type_face_indices] = [
        [(v0,) * 3, (v1,) * 3, (v2,) * 3]
        for v0, v1, v2 in util.batched(p_indices, 3)
    ]

    # unpack all the vertices into their separate components
    # vertexes can share the values of these
    v_positions: dict[int, Vector] = {}
    v_normals: dict[int, Vector] = {}

    # tex_coords (and the ambient occlusion packed in them) are always considered unique per vertex
    v_tex_coords: dict[int, Vector] = {}
    v_ambient_occlusion: dict[int, float] = {}

    for i, vertex in ((i, v) for i, v in enumerate(p_vertices) if i not in duplicate_verts):
        (v_positions[i], v_normals[i], v_tex_coords[i]) = vertex
        v_ambient_occlusion[i] = vertex.ambient_occlusion

    if merge_vertices:
        duplicate_positions = util.duplicates_by_predicate(v_positions, close_pos)
        duplicate_normals = util.duplicates_by_predicate(v_normals, close_norm)

        for face_indices in face_indices_list:
            for i, (pos_idx, norm_idx, tex_coord_idx) in enumerate(face_indices):
                face_indices[i] = (
                    duplicate_positions[pos_idx] if pos_idx in duplicate_positions else pos_idx,
                    duplicate_normals[norm_idx] if norm_idx in duplicate_normals else norm_idx,
                    tex_coord_idx
                )
    # endif merge_vertices

    bm = bmesh.new()
    bmesh_vert_lookup: dict[int, dict[int, bmesh.types.BMVert]] = {}
    for face_indices in face_indices_list:
        for (pos_idx, norm_idx, _) in face_indices:
            if pos_idx not in bmesh_vert_lookup:
                bmesh_vert_lookup[pos_idx] = {}

            if norm_idx not in bmesh_vert_lookup[pos_idx]:
                vert = bm.verts.new(v_positions[pos_idx])
                vert.normal = v_normals[norm_idx]
                bmesh_vert_lookup[pos_idx][norm_idx] = vert

    uv_layer = bm.loops.layers.uv.new("UVMap")
    ao_layer = bm.loops.layers.float.new("ambient_occlusion")

    for face_indices in face_indices_list:
        face_verts = [bmesh_vert_lookup[pos_idx][norm_idx] for pos_idx, norm_idx, _ in face_indices]
        try:
            face = bm.faces.new(face_verts)
            face.smooth = True

            for i, loop in enumerate(face.loops):
                _, _, tex_coord_idx = face_indices[i]
                loop[uv_layer].uv = v_tex_coords[tex_coord_idx]
                loop[ao_layer] = v_ambient_occlusion[tex_coord_idx]
        except Exception as err:
            print(err)

    if merge_vertices:
        for edge in bm.edges:
            edge.smooth = not edge.is_boundary
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.002)
    
    mesh = bpy.data.meshes.new(piece.name)
    bm.to_mesh(mesh)

    new_obj = object_utils.object_data_add(bpy.context, mesh)
    new_obj.name = piece.name

    return new_obj


def adjust_obj_to_s3o_offsets(piece, curx, cury, curz):
    # print 'adjusting offsets of',piece.name,': current:',curx,cury,curz,'parent offsets:',piece.parent_offset
    for i in range(len(piece.vertices)):
        v = piece.vertices[i]

        v = ((v[0][0] - curx - piece.parent_offset[0], v[0][1] - cury - piece.parent_offset[1],
        v[0][2] - curz - piece.parent_offset[2]), v[1], v[2])
        # print 'offset:',v[0],piece.vertices[0][0]
        piece.vertices[i] = v
    for child in piece.children:
        adjust_obj_to_s3o_offsets(
            child,
            curx + piece.parent_offset[0],
            cury + piece.parent_offset[1],
            curz + piece.parent_offset[2]
        )


def recursively_optimize_pieces(piece):
    if piece.indices is list and len(piece.indices) > 4:
        optimize_piece(piece)
        fix_zero_normals_piece(piece)

    for child in piece.children:
        recursively_optimize_pieces(child)


def optimize_piece(piece: S3OPiece):
    remap = {}
    new_indices = []
    print('[INFO]', 'Optimizing:', piece.name)
    for index in piece.indices:
        vertex = piece.vertices[index]
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


# if there are zero vertices, the emit direction is 0,0,1, the emit position is the origin of the piece
# if there is 1 vertex, the emit dir is the vector from the origin to the the position of the first vertex
#    the emit position is the origin of the piece
# if there is more than one, then the emit vector is the vector pointing from v[0] to v[1],
#    and the emit position is v[0]
def fix_zero_normals_piece(piece: S3OPiece):
    if len(piece.indices) == 0:
        return

    badnormals = 0
    fixednormals = 0
    nonunitnormals = 0

    DEFAULT_NORMAL = Vector((0, 1, 0))

    piece.triangulate_faces()

    verts = piece.vertices
    idxs = piece.indices

    for v_idx in range(len(verts)):
        vertex = verts[v_idx]
        normal_length = vertex.normal.length
        if normal_length < 0.01:  # nearly 0 normal
            badnormals += 1
            if v_idx not in idxs:
                # this is some sort of degenerate vertex, just replace it's normal with [0,1,0]
                verts[v_idx] = vertex.with_normal(DEFAULT_NORMAL.copy())
                fixednormals += 1
            else:
                for f_idx in range(0, len(idxs), 3):
                    if v_idx in idxs[f_idx:min(len(idxs), f_idx + 3)]:
                        new_normal = Vector.cross(
                            verts[idxs[f_idx + 1]].position - verts[idxs[f_idx]].position,
                            verts[idxs[f_idx + 2]].position - verts[idxs[f_idx]].position
                        )

                        if new_normal.length < 0.001:
                            piece.vertices[v_idx] = vertex.with_normal(DEFAULT_NORMAL.copy())
                        else:
                            piece.vertices[v_idx] = vertex.with_normal(vertex.normal.normalized())
                        fixednormals += 1
                        break
        elif normal_length < 0.9 or normal_length > 1.1:
            nonunitnormals += 1
            piece.vertices[v_idx] = vertex.with_normal(vertex.normal.normalized())

    if badnormals > 0:
        print('[WARN]', 'Bad normals:', badnormals, 'Fixed:', fixednormals)
        if badnormals != fixednormals:
            print('[WARN]', 'NOT ALL ZERO NORMALS fixed!!!!!')  # this isn't possible with above code anyway :/

    if nonunitnormals > 0:
        print('[WARN]', nonunitnormals, 'fixed to unit length')


def recalculate_normals(piece: S3OPiece, smooth_angle: float, recursive=False):
    piece.triangulate_faces()

    # build a list of vertices, each with their list of faces:
    if len(piece.indices) > 4:
        # explode vertices uniquely
        new_vertices = []
        new_indices = []
        for i, vi in enumerate(piece.indices):
            new_vertices.append(piece.vertices[vi])
            new_indices.append(i)
        piece.vertices = new_vertices
        piece.indices = new_indices

        faces_per_vertex = []
        for i, v1 in enumerate(piece.vertices):
            faces_per_vertex.append([])
            for j, v2 in enumerate(piece.vertices):
                if (v1.position - v2.position).length < 0.05:
                    faces_per_vertex[i].append(j)

        for i, v1 in enumerate(piece.vertices):
            if len(faces_per_vertex[i]) > 0:
                face_index = int(math.floor(i / 3) * 3)
                my_normal = normal(piece.vertices[face_index:face_index + 2])

                mixed_norm = Vector((0, 0, 0))
                for face_vertex in faces_per_vertex[i]:
                    # get face:
                    face_index = int(math.floor(face_vertex / 3) * 3)
                    mixed_norm += normal(piece.vertices[face_index:face_index + 2])
                mixed_norm.normalize()

                if my_normal.angle(mixed_norm) <= smooth_angle:
                    piece.vertices[i] = piece.vertices[i].with_normal(mixed_norm)
                else:
                    piece.vertices[i] = piece.vertices[i].with_normal(my_normal)

    if recursive:
        for child in piece.children:
            recalculate_normals(child, smooth_angle, recursive)
