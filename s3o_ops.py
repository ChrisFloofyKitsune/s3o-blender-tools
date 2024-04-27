from .s3o import S3O, S3OPiece, S3OVertex


def closest_vertex(vtable: list[S3OVertex], q: int, tolerance: float):  # returns the index of the closest vertex pos
    v = vtable[q][0]
    for i in range(len(vtable)):
        v2 = vtable[i][0]
        if abs(v2[0] - v[0]) < tolerance and abs(v2[1] - v[1]) < tolerance and abs(v2[2] - v[2]) < tolerance:
            # if i!=q:
            # print i,'matches',q
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
    objfile = open(filename, 'w')
    objfile.write('# Spring Unit export, Created by Beherith mysterme@gmail.com with the help of Muon \n')
    objfile.write(
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
    obj_vertindex = 0
    obj_normal_uv_index = 0  # obj indexes vertices from 1

    recurse_s3o_to_obj(
        s3o_object.root_piece, objfile, header, obj_vertindex, obj_normal_uv_index, 0, (0, 0, 0),
        optimize_for_wings3d
    )


def recurse_s3o_to_obj(
    piece, objfile, extraargs, vi, nti, groups, offset,
    optimize_for_wings3d=True
):  # vi is our current vertex index counter, nti is the normal/texcoord index counter
    # If we don't use shared vertices in a OBJ file in wings, it won't be able to merge vertices,
    # so we need a mapping to remove redundant vertices, normals and texture indices are separate
    parent = ''
    oldnti = nti

    if piece.parent != None:
        parent = piece.parent.name
        print('[INFO] parentname=', piece.parent.name)
    # objfile.write('o %s,ox=%.2f,oy=%.2f,oz=%.2f,p=%s,%s\n'%(
    # piece.name,
    # piece.parent_offset[0],
    # piece.parent_offset[1],
    # piece.parent_offset[2],
    # parent,
    # extraargs))

    vdata_obj = []  # vertex, normal and UV in the piece
    fdata_obj = []  # holds the faces in the piece
    hash = {}
    vcount = 0
    step = 3  # todo: fix for not just triangles
    if piece.primitive_type == 'triangles':
        step = 3
    elif piece.primitive_type == 'quads':
        step = 4
    print('[INFO]', piece.name, 'has', piece.primitive_type, step)
    if len(piece.indices) >= step and piece.primitive_type != "triangle strips":
        objfile.write(
            'o %s,ox=%.2f,oy=%.2f,oz=%.2f,p=%s,%s\n' % (
                piece.name.decode(),
                piece.parent_offset[0],
                piece.parent_offset[1],
                piece.parent_offset[2],
                '' if parent == '' else parent.decode(),
                extraargs)
        )
        print('[INFO]', 'Piece', piece.name, 'has more than 3 vert indices')
        for k in range(0, len(piece.indices), step):  # iterate over faces
            facestr = 'f'
            for i in range(step):
                v = piece.vertices[piece.indices[k + i]]
                # sanity check normals:
                for j in range(3):
                    if v[1][j] < 1000000 and v[1][j] > -1000000:
                        pass  # any comparison of NaN is always false
                    else:
                        v = (v[0], (0.0, 0.0, 0.0), v[2])
                        print('[WARN]', 'NAN normal encountered in piece', piece.name, 'replacing with 0')
                if float('nan') in v[1]:
                    print('[WARN]', 'NAN normal encountered in piece', piece.name)
                if optimize_for_wings3d:
                    closest = closest_vertex(piece.vertices, piece.indices[k + i], 0.002)
                    if closest not in hash:
                        # print 'closest',closest,'not in hash',hash
                        vcount += 1
                        hash[closest] = vcount
                        vdata_obj.append(
                            'v %f %f %f\n' % (
                                v[0][0] + offset[0] + piece.parent_offset[0],
                                v[0][1] + offset[1] + piece.parent_offset[1],
                                v[0][2] + offset[2] + piece.parent_offset[2])
                        )
                    vdata_obj.append('vn %f %f %f\n' % (v[1][0], v[1][1], v[1][2]))
                    vdata_obj.append('vt %.9f %.9f\n' % (v[2][0], v[2][1]))
                    nti += 1
                    facestr += ' %i/%i/%i' % (vi + hash[closest], nti, nti)

                else:
                    closest = piece.indices[k + i]

                    if closest not in hash:
                        # print 'closest',closest,'not in hash',hash
                        vcount += 1
                        hash[closest] = vcount
                        vdata_obj.append(
                            'v %f %f %f\n' % (
                                v[0][0] + offset[0] + piece.parent_offset[0],
                                v[0][1] + offset[1] + piece.parent_offset[1],
                                v[0][2] + offset[2] + piece.parent_offset[2])
                        )
                    vdata_obj.append('vn %f %f %f\n' % (v[1][0], v[1][1], v[1][2]))
                    vdata_obj.append('vt %.9f %.9f\n' % (v[2][0], v[2][1]))
                    nti += 1
                    # if 1==1: #closest>=piece.indices[k+i]: #no matching vert

                    facestr += ' %i/%i/%i' % (vi + hash[closest], nti, nti)

            fdata_obj.append(facestr + '\n')
        for l in vdata_obj:
            objfile.write(l)
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
                                # print '[INFO]', 'Conflicting smoothing groups!', f1, f2, faces[f1], faces[
                                #	f2], 'resolving with merge!'
                                greater = max(faces[f2], faces[f1])
                                lesser = min(faces[f2], faces[f1])
                                for faceindex in faces.keys():
                                    if faces[faceindex] == greater:
                                        faces[faceindex] = lesser
                                    elif faces[faceindex] > greater:
                                        faces[faceindex] -= 1
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
        groupids = set(faces.values())
        print('[INFO]', 'Sets of smoothing groups in piece', piece.name, 'are', groupids, groups)

        nonsmooth_faces = False
        for l in range(len(fdata_obj)):
            if l not in faces:
                nonsmooth_faces = True
        if nonsmooth_faces:
            objfile.write('s off\n')
        for l in range(len(fdata_obj)):
            if l not in faces:
                objfile.write(fdata_obj[l])
        for k in groupids:
            objfile.write('s ' + str(k) + '\n')
            for l in range(len(fdata_obj)):
                if l in faces and faces[l] == k:
                    objfile.write(fdata_obj[l])
        print('[INFO]', 'Optimized vertex count=', vcount, 'unoptimized count=', nti - oldnti)
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
            objfile.write(
                'o %s,ox=%.2f,oy=%.2f,oz=%.2f,p=%s,%s,e=%i\n' % (
                    piece.name.decode(),
                    piece.parent_offset[0],
                    piece.parent_offset[1],
                    piece.parent_offset[2],
                    '' if parent == '' else parent.decode(),
                    '' if extraargs == '' else extraargs.encode().decode(),
                    len(piece.vertices))
            )
            if len(piece.vertices) == 0:
                objfile.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                objfile.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        4 + offset[2] + piece.parent_offset[2])
                )
                objfile.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], 2 + offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                # objfile.write('v 0 0 0\n')
                # objfile.write('v 0 0 1\n')
                objfile.write('f %i/1/1 %i/2/2 %i/3/3\n' % (vi + 1, vi + 2, vi + 3))
                vcount += 3
            elif len(piece.vertices) == 1:
                print(
                    '[INFO]', 'Emit vertices:', piece.vertices, 'offset:  %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                v = piece.vertices[0]
                objfile.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                objfile.write(
                    'v %f %f %f\n' % (
                        v[0][0] + offset[0] + piece.parent_offset[0],
                        v[0][1] + offset[1] + piece.parent_offset[1],
                        v[0][2] + offset[2] + piece.parent_offset[2])
                )
                objfile.write(
                    'v %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], 2 + offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                # objfile.write('v 0 0 0\n')
                # objfile.write('v 0 0 1\n')
                objfile.write('f %i/1/1 %i/2/2 %i/3/3\n' % (vi + 1, vi + 2, vi + 3))
                vcount += 3
            elif len(piece.vertices) == 2:
                print(
                    '[INFO]', 'Emit vertices:', piece.vertices, 'offset:  %f %f %f\n' % (
                        offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                        offset[2] + piece.parent_offset[2])
                )
                v = piece.vertices[0]
                objfile.write(
                    'v %f %f %f\n' % (
                        v[0][0] + offset[0] + piece.parent_offset[0],
                        v[0][1] + offset[1] + piece.parent_offset[1],
                        v[0][2] + offset[2] + piece.parent_offset[2])
                )
                v = piece.vertices[1]
                objfile.write(
                    'v %f %f %f\n' % (
                        v[0][0] + offset[0] + piece.parent_offset[0],
                        v[0][1] + offset[1] + piece.parent_offset[1],
                        v[0][2] + offset[2] + piece.parent_offset[2])
                )
                v = piece.vertices[0]
                objfile.write(
                    'v %f %f %f\n' % (
                        v[0][0] + offset[0] + piece.parent_offset[0],
                        2 + v[0][1] + offset[1] + piece.parent_offset[1],
                        v[0][2] + offset[2] + piece.parent_offset[2])
                )

                # objfile.write('v 0 0 0\n')
                # objfile.write('v 0 0 1\n')
                objfile.write('f %i/1/1 %i/2/2 %i/3/3\n' % (vi + 1, vi + 2, vi + 3))
                vcount += 3
            else:
                print('[ERROR]', 'Piece', piece.name, ': failed to write as it looks invalid')
        # print 'empty piece',piece.name,'writing placeholder face with primitive type',piece.primitive_type
    vi = vi + vcount
    for child in piece.children:
        vi, nti = recurse_s3o_to_obj(
            child, objfile, '', vi, nti, groups, (
                offset[0] + piece.parent_offset[0], offset[1] + piece.parent_offset[1],
                offset[2] + piece.parent_offset[2]),
            optimize_for_wings3d
        )
    return vi, nti


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
