import math

from mathutils import Vector
from mathutils.geometry import normal
from . import vertex_cache
from .s3o import S3O, S3OPiece, S3OVertex
from .util import batched


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


def s3o_to_obj(s3o_object: "S3O", filename, optimize_for_wings3d=True):
    print("[INFO] Wings3d optimization:", optimize_for_wings3d)
    obj_file = open(filename, 'w')
    obj_file.write('# Spring Unit export, Created by Beherith mysterme@gmail.com with the help of Muon \n')
    obj_file.write(
        '# arguments of an object \'o\' piecename:\n# Mxyz = midpoint of an s3o\n# r = unit radius\n# h = height\n#\
         t1 t2 = textures 1 and 2\n# Oxyz = piece offset\n# p = parent\n'
    )
    header = 'mx=%.2f,my=%.2f,mz=%.2f,r=%.2f,h=%.2f,t1=%s,t2=%s' % (
        s3o_object.midpoint[0],
        s3o_object.midpoint[1],
        s3o_object.midpoint[2],
        s3o_object.collision_radius,
        s3o_object.height,
        s3o_object.texture_paths[0],
        s3o_object.texture_paths[1],
    )
    obj_vert_index = 0
    obj_normal_uv_index = 0  # obj indexes vertices from 1

    recurse_s3o_to_obj(
        s3o_object.root_piece, obj_file, header, obj_vert_index, obj_normal_uv_index, 0, (0, 0, 0),
        optimize_for_wings3d
    )


def recurse_s3o_to_obj(
    piece, obj_file, extra_args, v_idx, nt_idx, groups, offset,
    optimize_for_wings3d=True
):
    # If we don't use shared vertices in a OBJ file in wings, it won't be able to merge vertices,
    # so we need a mapping to remove redundant vertices, normals and texture indices are separate
    parent = ''
    old_nt_idx = nt_idx

    if piece.parent is not None:
        parent = piece.parent.name
        print('[INFO] parentname=', piece.parent.name)

    vdata_obj = []  # vertex, normal and UV in the piece
    fdata_obj = []  # holds the faces in the piece
    v_hash = {}
    v_count = 0
    step = 3  # todo: fix for not just triangles
    if piece.primitive_type == 'triangles':
        step = 3
    elif piece.primitive_type == 'quads':
        step = 4
    print('[INFO]', piece.name, 'has', piece.primitive_type, step)
    if len(piece.indices) >= step and piece.primitive_type != "triangle strips":
        obj_file.write(
            'o %s,ox=%.2f,oy=%.2f,oz=%.2f,p=%s,%s\n' % (
                piece.name.decode(),
                piece.parent_offset[0],
                piece.parent_offset[1],
                piece.parent_offset[2],
                '' if parent == '' else parent.decode(),
                extra_args)
        )
        print('[INFO]', 'Piece', piece.name, 'has more than 3 vert indices')
        for k in range(0, len(piece.indices), step):  # iterate over faces
            facestr = 'f'
            for i in range(step):
                v = piece.vertices[piece.indices[k + i]]
                # sanity check normals:
                for j in range(3):
                    if 1000000 > v[1][j] > -1000000:
                        pass  # any comparison of NaN is always false
                    else:
                        v = S3OVertex(v[0], Vector((0.0, 0.0, 0.0)), v[2])
                        print('[WARN]', 'NAN normal encountered in piece', piece.name, 'replacing with 0')

                if float('nan') in v[1]:
                    print('[WARN]', 'NAN normal encountered in piece', piece.name)

                if optimize_for_wings3d:
                    closest = closest_vertex(piece.vertices, piece.indices[k + i], 0.002)
                    if closest not in v_hash:
                        # print 'closest',closest,'not in hash',hash
                        v_count += 1
                        v_hash[closest] = v_count
                        vdata_obj.append(
                            'v %f %f %f\n' % (
                                v[0][0] + offset[0] + piece.parent_offset[0],
                                v[0][1] + offset[1] + piece.parent_offset[1],
                                v[0][2] + offset[2] + piece.parent_offset[2])
                        )
                    vdata_obj.append('vn %f %f %f\n' % (v[1][0], v[1][1], v[1][2]))
                    vdata_obj.append('vt %.9f %.9f\n' % (v[2][0], v[2][1]))
                    nt_idx += 1
                    facestr += ' %i/%i/%i' % (v_idx + v_hash[closest], nt_idx, nt_idx)

                else:
                    closest = piece.indices[k + i]

                    if closest not in v_hash:
                        # print 'closest',closest,'not in hash',hash
                        v_count += 1
                        v_hash[closest] = v_count
                        vdata_obj.append(
                            'v %f %f %f\n' % (
                                v[0][0] + offset[0] + piece.parent_offset[0],
                                v[0][1] + offset[1] + piece.parent_offset[1],
                                v[0][2] + offset[2] + piece.parent_offset[2])
                        )
                    vdata_obj.append('vn %f %f %f\n' % (v[1][0], v[1][1], v[1][2]))
                    vdata_obj.append('vt %.9f %.9f\n' % (v[2][0], v[2][1]))
                    nt_idx += 1
                    # if 1==1: #closest>=piece.indices[k+i]: #no matching vert

                    facestr += ' %i/%i/%i' % (v_idx + v_hash[closest], nt_idx, nt_idx)

            fdata_obj.append(facestr + '\n')
        for line in vdata_obj:
            obj_file.write(line)
        # now it's time to smooth this bitch!
        # how wings3d processes obj meshes:
        # if no normals are specified, it merges edges correctly, but all edges are soft
        # if normals are specified, but there are no smoothing groups,
        # it will treat each smoothed group as a separate mesh in an object
        # if normals AND smoothing groups are specified, it works as it should

        faces = {}
        if optimize_for_wings3d:
            for face1 in range(0, len(piece.indices), step):
                # for f2 in range(f1+step,len(piece.indices),step):
                for face2 in range(0, len(piece.indices), step):
                    if face1 != face2 and in_smoothing_group(piece, face1, face2, 0.001, step):
                        f1 = face1 / step
                        f2 = face2 / step
                        if f1 in faces and f2 in faces:
                            if faces[f2] != faces[f1]:
                                greater = max(faces[f2], faces[f1])
                                lesser = min(faces[f2], faces[f1])
                                for face_index in faces.keys():
                                    if faces[face_index] == greater:
                                        faces[face_index] = lesser
                                    elif faces[face_index] > greater:
                                        faces[face_index] -= 1
                                groups -= 1
                        # else:
                        # print 'already in same group, yay!',f1,f2,faces[f1],faces[f2]
                        elif f1 in faces:
                            faces[f2] = faces[f1]
                        elif f2 in faces:
                            faces[f1] = faces[f2]
                        else:
                            groups += 1
                            faces[f1] = groups
                            faces[f2] = groups
                    # if a face shares any two optimized position vertices and has equal normals on that,
                    # it is in one smoothing group.
                    # does it work for any 1
        group_ids = set(faces.values())
        print('[INFO]', 'Sets of smoothing groups in piece', piece.name, 'are', group_ids, groups)

        non_smooth_faces = False
        for line in range(len(fdata_obj)):
            if line not in faces:
                non_smooth_faces = True
        if non_smooth_faces:
            obj_file.write('s off\n')
        for line in range(len(fdata_obj)):
            if line not in faces:
                obj_file.write(fdata_obj[line])
        for k in group_ids:
            obj_file.write('s ' + str(k) + '\n')
            for line in range(len(fdata_obj)):
                if line in faces and faces[line] == k:
                    obj_file.write(fdata_obj[line])
        print('[INFO]', 'Optimized vertex count=', v_count, 'unoptimized count=', nt_idx - old_nt_idx)
    elif piece.primitive_type == "triangle strips":
        print(
            '[WARN]', piece.name,
            'has a triangle strip type, this is unsupported by this application, skipping piece!'
        )
    else:
        if not optimize_for_wings3d:
            print('[WARN]', 'Skipping empty emit piece', piece.name, 'because wings3d optimization is off!')
        else:
            print(
                '[INFO]', 'Empty piece', piece.name, 'writing placeholder face with primitive type',
                piece.primitive_type, '#vertices=', len(piece.vertices), '#indices=', len(piece.indices)
            )
            obj_file.write(
                'o %s,ox=%.2f,oy=%.2f,oz=%.2f,p=%s,%s,e=%i\n' % (
                    piece.name.decode(),
                    piece.parent_offset[0],
                    piece.parent_offset[1],
                    piece.parent_offset[2],
                    '' if parent == '' else parent.decode(),
                    '' if extra_args == '' else extra_args.encode().decode(),
                    len(piece.vertices))
            )
            if len(piece.vertices) == 0:
                obj_file.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                obj_file.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        4 + offset[2] + piece.parent_offset[2])
                )
                obj_file.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], 2 + offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                # objfile.write('v 0 0 0\n')
                # objfile.write('v 0 0 1\n')
                obj_file.write('f %i/1/1 %i/2/2 %i/3/3\n' % (v_idx + 1, v_idx + 2, v_idx + 3))
                v_count += 3
            elif len(piece.vertices) == 1:
                print(
                    '[INFO]', 'Emit vertices:', piece.vertices, 'offset:  %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                v = piece.vertices[0]
                obj_file.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                obj_file.write(
                    'v %f %f %f\n' % (
                        v[0][0] + offset[0] + piece.parent_offset[0],
                        v[0][1] + offset[1] + piece.parent_offset[1],
                        v[0][2] + offset[2] + piece.parent_offset[2])
                )
                obj_file.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], 2 + offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                # objfile.write('v 0 0 0\n')
                # objfile.write('v 0 0 1\n')
                obj_file.write('f %i/1/1 %i/2/2 %i/3/3\n' % (v_idx + 1, v_idx + 2, v_idx + 3))
                v_count += 3
            elif len(piece.vertices) == 2:
                print(
                    '[INFO]', 'Emit vertices:', piece.vertices, 'offset:  %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                v = piece.vertices[0]
                obj_file.write(
                    'v %f %f %f\n' % (
                        v[0][0] + offset[0] + piece.parent_offset[0],
                        v[0][1] + offset[1] + piece.parent_offset[1],
                        v[0][2] + offset[2] + piece.parent_offset[2])
                )
                v = piece.vertices[1]
                obj_file.write(
                    'v %f %f %f\n' % (
                        v[0][0] + offset[0] + piece.parent_offset[0],
                        v[0][1] + offset[1] + piece.parent_offset[1],
                        v[0][2] + offset[2] + piece.parent_offset[2])
                )
                v = piece.vertices[0]
                obj_file.write(
                    'v %f %f %f\n' % (
                        v[0][0] + offset[0] + piece.parent_offset[0],
                        2 + v[0][1] + offset[1] + piece.parent_offset[1],
                        v[0][2] + offset[2] + piece.parent_offset[2])
                )

                # objfile.write('v 0 0 0\n')
                # objfile.write('v 0 0 1\n')
                obj_file.write('f %i/1/1 %i/2/2 %i/3/3\n' % (v_idx + 1, v_idx + 2, v_idx + 3))
                v_count += 3
            else:
                print('[ERROR]', 'Piece', piece.name, ': failed to write as it looks invalid')
        # print 'empty piece',piece.name,'writing placeholder face with primitive type',piece.primitive_type
    v_idx = v_idx + v_count
    for child in piece.children:
        v_idx, nt_idx = recurse_s3o_to_obj(
            child, obj_file, '', v_idx, nt_idx, groups, (
                offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                offset[2] + piece.parent_offset[2]),
            optimize_for_wings3d
        )
    return v_idx, nt_idx


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


def optimize_piece(piece: "S3OPiece"):
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
