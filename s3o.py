import math
import struct
from enum import Enum
from typing import NamedTuple

from .util import extract_null_terminated_string
from mathutils import Vector


_S3OHeader_struct = struct.Struct("< 12s i 5f 4i")
"""
* magic bytes "Spring unit\\\\0"
* version
* radius, height, mid.x, mid.y, mid.z
* root_piece_offset, collision_data_offset (0, unimplemented), texture1_offset, texture2_offset
"""

_S3OPiece_struct = struct.Struct("< 10i 3f")
"""
* name_offset, num_children, num_vertices, vertices_offset, vertex_type (0, unimplemented),
  primitive_type, num_face_indices, face_indices_offset, collision_data_offset (0, unimplemented)
* offset.x, offset.y, offset.z

primitive_type
    * 0: triangles
    * 1: triangle strips (end of current strip marked with 0xffffffff)
    * 2: quads
"""

_S3OVertex_struct = struct.Struct("< 3f 3f 2f")
"""
* position
* normal
* tex_coord
"""

_S3OChildOffset_struct = struct.Struct("< i")
_S3OIndex_struct = struct.Struct("< i")


class S3OVertex(NamedTuple):
    position: Vector
    normal: Vector
    tex_coords: Vector

    def with_position(self, position: Vector):
        return S3OVertex(position, self.normal, self.tex_coords)

    def with_normal(self, normal: Vector):
        return S3OVertex(self.position, normal, self.tex_coords)

    @property
    def ambient_occlusion(self) -> float:
        # ao is packed into the last ~7-8 bits of the texture U coordinate as a miniscule fractional value
        # #BlameBeherith for this fractional float value abuse
        return (self.tex_coords[0] * 2 ** 14) % 1.0

    @ambient_occlusion.setter
    def ambient_occlusion(self, value) -> None:
        # don't use full range so that rounding errors don't eat the packed in ao
        value = min(0.98, max(0.02, value))

        self.tex_coords[0] = (math.floor(self.tex_coords[0] * (2 ** 14)) / 2 ** 14) + (value / (2 ** 14))


class S3OPiece:
    class PrimitiveType(Enum):
        Triangles = 0,
        TriangleStrips = 1,
        Quads = 2,

    name: str

    parent: 'S3OPiece | None'
    parent_offset: Vector

    children: list['S3OPiece']

    vertices: list[S3OVertex]
    indices: list[int]
    primitive_type: PrimitiveType

    def __init__(self, data: bytes, offset: int, parent: 'S3OPiece | None' = None, name='base'):
        if data == b'':
            self.parent = None
            self.name = name
            self.primitive_type = S3OPiece.PrimitiveType.Triangles
            self.parent_offset = Vector((0.0, 0.0, 0.0))
            self.vertices = []
            self.indices = []
            self.children = []
            return

        name_offset, num_children, children_offset, num_vertices, \
            vertex_offset, vertex_type, primitive_type, num_indices, \
            index_offset, collision_data_offset, \
            x_offset, y_offset, z_offset = _S3OPiece_struct.unpack_from(data, offset)

        self.name = extract_null_terminated_string(data, name_offset)

        self.parent = parent
        self.parent_offset = Vector((x_offset, y_offset, z_offset))

        self.primitive_type = primitive_type

        self.vertices = []
        for i in range(num_vertices):
            current_offset = vertex_offset + _S3OVertex_struct.size * i
            vertex = _S3OVertex_struct.unpack_from(data, current_offset)

            position = Vector(vertex[:3])
            normal = Vector(vertex[3:6])
            tex_coords = Vector(vertex[6:])

            self.vertices.append(S3OVertex(position, normal, tex_coords))

        self.indices = []
        for i in range(num_indices):
            current_offset = index_offset + _S3OIndex_struct.size * i
            index, = _S3OIndex_struct.unpack_from(data, current_offset)
            self.indices.append(index)

        self.children = []
        for i in range(num_children):
            cur_offset = children_offset + _S3OChildOffset_struct.size * i
            child_offset, = _S3OChildOffset_struct.unpack_from(data, cur_offset)
            self.children.append(S3OPiece(data, child_offset, self))

    def mergechildren(self):
        for child in self.children:
            child.mergechildren()

        new_verts = self.vertices
        new_indices = self.indices
        index_offset = len(self.vertices)
        for child in self.children:
            for v in child.vertices:
                new_verts.append(
                    v.with_position(
                        Vector(
                            (
                                v[0][0] + child.parent_offset[0],
                                v[0][1] + child.parent_offset[1],
                                v[0][2] + child.parent_offset[2]
                            )
                        )
                    )
                )
            for index in child.indices:
                new_indices.append(index + index_offset)
            index_offset += len(child.vertices)
        self.vertices = new_verts
        self.indices = new_indices
        self.children = []

    def rescale(self, scale):
        self.parent_offset = Vector(
            (
                self.parent_offset[0] * scale,
                self.parent_offset[1] * scale,
                self.parent_offset[2] * scale
            )
        )

        for i, v in enumerate(self.vertices):
            self.vertices[i] = v.with_position(v.position * scale)

        for child in self.children:
            child.rescale(scale)

    def triangulate_faces(self):
        idx_len = len(self.indices)

        match self.primitive_type:
            case S3OPiece.PrimitiveType.Triangles:
                pass
            case S3OPiece.PrimitiveType.TriangleStrips:
                if idx_len < 3:
                    self.primitive_type = S3OPiece.PrimitiveType.Triangles
                    self.indices.clear()
                    return

                new_idx: list[int] = []

                for i in range(idx_len - 2):
                    # indices can instead be end-of-strip markers (-1)
                    if all(idx != -1 for idx in self.indices[i:i + 2]):
                        new_idx.extend(self.indices[i:i + 2])

                self.primitive_type = S3OPiece.primitive_type.Triangles
                self.indices = new_idx

            case S3OPiece.PrimitiveType.Quads:
                if len(self.indices) % 4 != 0:
                    self.primitive_type = S3OPiece.PrimitiveType.Triangles
                    self.indices.clear()
                    return

                new_idx: list[int] = []
                for i in range(0, idx_len, 4):
                    new_idx.extend(self.indices[i:i + 2])
                    new_idx.extend(self.indices[i + n] for n in [0, 2, 3])

                self.primitive_type = S3OPiece.PrimitiveType.Triangles
                self.indices = new_idx

    def serialize(self, offset):
        name_offset = _S3OPiece_struct.size + offset
        encoded_name = self.name.encode() + b'\x00'

        children_offset = name_offset + len(encoded_name)
        child_data = b''
        for _ in range(len(self.children)):
            # the true positions of children are unknown (they have yet to be serialized)
            # so fill child_data with placeholder bytes for now
            child_data += _S3OChildOffset_struct.pack(0)

        vertex_offset = children_offset + len(child_data)
        vertex_data = b''
        for pos, nor, uv in self.vertices:
            vertex_data += _S3OVertex_struct.pack(
                pos[0], pos[1], pos[2],
                nor[0], nor[1], nor[2],
                uv[0], uv[1]
            )

        index_offset = vertex_offset + len(vertex_data)
        index_data = b''
        for index in self.indices:
            vertex_data += _S3OIndex_struct.pack(index)

        primitive_type = self.primitive_type.value

        # NASTY HACK
        # if there are no children, vertices or primitives, point one back to avoid pointing outside of file!
        # if len(self.children) == 0:
        #     children_offset = children_offset - 1
        # if len(self.vertices) == 0:
        #     vertex_offset = vertex_offset - 1
        # if len(self.indices) == 0:
        #     index_offset = index_offset - 1

        args = (
            name_offset,
            len(self.children), children_offset,
            len(self.vertices), vertex_offset, 0, primitive_type,
            len(self.indices), index_offset, 0,
            self.parent_offset.x, self.parent_offset.y, self.parent_offset.z,
        )

        piece_header = _S3OPiece_struct.pack(*args)
        data = piece_header + encoded_name + child_data + vertex_data + index_data

        # serialize children and write down the child offsets for real this time
        child_offsets = []
        serialized_child_data = b''
        for child in self.children:
            child_offset = offset + len(data) + len(serialized_child_data)
            child_offsets.append(child_offset)
            serialized_child_data += child.serialize(child_offset)

        child_data = b''
        for child_offset in child_offsets:
            child_data += _S3OChildOffset_struct.pack(child_offset)

        data = piece_header + encoded_name + child_data + vertex_data + index_data + serialized_child_data

        return data


class S3O:
    collision_radius: float
    height: float
    midpoint: Vector
    texture_paths = [str]
    root_piece = S3OPiece

    def __init__(self, data: bytes):
        header = _S3OHeader_struct.unpack_from(data, 0)

        magic, version, radius, height, mid_x, mid_y, mid_z, \
            root_piece_offset, collision_data_offset, tex1_offset, \
            tex2_offset = header

        assert (magic == b'Spring unit\x00')
        assert (version == 0)
        assert (collision_data_offset == 0)

        self.collision_radius = radius
        self.height = height
        self.midpoint = Vector((mid_x, mid_y, mid_z))

        self.texture_paths = (
            extract_null_terminated_string(data, tex1_offset),
            extract_null_terminated_string(data, tex2_offset)
        )
        self.root_piece = S3OPiece(data, root_piece_offset)

    def triangulate_faces(self):
        self.root_piece.triangulate_faces()

    def serialize(self):
        # encoded_texpath1 = b"".join([bytes(self.texture_paths[0],'utf-8') , b'\x00'])
        encoded_texpath1 = self.texture_paths[0].encode() + b'\x00'
        encoded_texpath2 = self.texture_paths[1].encode() + b'\x00'

        tex1_offset = _S3OHeader_struct.size
        tex2_offset = tex1_offset + len(encoded_texpath1)
        root_offset = tex2_offset + len(encoded_texpath2)

        args = (
            b'Spring unit\x00', 0, self.collision_radius, self.height,
            self.midpoint.x, self.midpoint.y, self.midpoint.z,
            root_offset, 0, tex1_offset, tex2_offset
        )

        header = _S3OHeader_struct.pack(*args)

        data = header + encoded_texpath1 + encoded_texpath2
        data += self.root_piece.serialize(len(data))

        return data
