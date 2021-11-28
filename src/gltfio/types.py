'''
https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/
'''
from ctypes.wintypes import RGB
from typing import NamedTuple, Optional, Tuple, List, Dict, Type
import ctypes
from enum import Enum
import pathlib
from dataclasses import dataclass


class GltfError(RuntimeError):
    pass


class Mat4(NamedTuple):
    m11: float
    m12: float
    m13: float
    m14: float
    m21: float
    m22: float
    m23: float
    m24: float
    m31: float
    m32: float
    m33: float
    m34: float
    m41: float
    m42: float
    m43: float
    m44: float


class Vec3(NamedTuple):
    x: float
    y: float
    z: float


class Vec4(NamedTuple):
    x: float
    y: float
    z: float
    w: float


CTYPES_FORMAT_MAP: Dict[Type[ctypes._SimpleCData], str] = {
    ctypes.c_byte: 'b',
    ctypes.c_ubyte: 'B',
    ctypes.c_short: 'h',
    ctypes.c_ushort: 'H',
    ctypes.c_uint: 'I',
    ctypes.c_float: 'f',
}


class TypedBytes(NamedTuple):
    data: bytes
    element_type: Type[ctypes._SimpleCData]
    element_count: int = 1

    def get_stride(self) -> int:
        return ctypes.sizeof(self.element_type) * self.element_count

    def get_count(self) -> int:
        return len(self.data) // self.get_stride()

    def get_item(self, i: int):
        begin = i * self.element_count
        return memoryview(self.data).cast(CTYPES_FORMAT_MAP[self.element_type])[begin:begin+self.element_count]


COMPONENT_TYPE_TO_ELEMENT_TYPE = {
    5120: ctypes.c_char,
    5121: ctypes.c_byte,
    5122: ctypes.c_short,
    5123: ctypes.c_ushort,
    5125: ctypes.c_uint,
    5126: ctypes.c_float,
}

TYPE_TO_ELEMENT_COUNT = {
    'SCALAR': 1,
    'VEC2': 2,
    'VEC3': 3,
    'VEC4': 4,
    'MAT2': 4,
    'MAT3': 9,
    'MAT4': 16,
}


def get_accessor_type(gltf_accessor) -> Tuple[Type[ctypes._SimpleCData], int]:
    return COMPONENT_TYPE_TO_ELEMENT_TYPE[gltf_accessor['componentType']], TYPE_TO_ELEMENT_COUNT[gltf_accessor['type']]


class MimeType(Enum):
    Jpg = "image/jpeg"
    Png = "image/png"
    Ktx2 = "image/ktx2"

    @staticmethod
    def from_name(name: str):
        match pathlib.Path(name).suffix.lower():
            case ".png":
                return MimeType.Png
            case ".jpg":
                return MimeType.Jpg
            case ".ktx2":
                return MimeType.Ktx2
            case _:
                raise GltfError(f'unknown image: {name}')


class GltfImage(NamedTuple):
    name: str
    data: bytes
    mime: MimeType


class GltfTexture(NamedTuple):
    name: str
    image: GltfImage


class RGB(NamedTuple):
    r: float
    g: float
    b: float


class RGBA(NamedTuple):
    r: float
    g: float
    b: float
    a: float


class AlphaMode(Enum):
    OPAQUE = 'OPAQUE'
    MASK = 'MASK'
    BLEND = 'BLEND'


class GltfMaterial(NamedTuple):
    name: str
    base_color_texture: Optional[GltfTexture]
    base_color_factor: RGBA
    metallic_roughness_texture: Optional[GltfTexture]
    metallic_factor: float
    roughness_factor: float
    emissive_texture: Optional[GltfTexture]
    emissive_factor: RGB
    normal_texture: Optional[GltfTexture]
    occlusion_texture: Optional[GltfTexture]
    alpha_mode: AlphaMode
    alpha_cutoff: float
    double_sided: bool

    @staticmethod
    def default() -> 'GltfMaterial':
        return GltfMaterial('__default__', None, RGBA(1, 1, 1, 1), None, 0, 1, None, RGB(0, 0, 0), None, None, AlphaMode.OPAQUE, 0.5, False)


class GltfPrimitive(NamedTuple):
    material: GltfMaterial
    position: TypedBytes
    position_min: Vec3
    position_max: Vec3
    normal: Optional[TypedBytes]
    uv0: Optional[TypedBytes]
    uv1: Optional[TypedBytes]
    uv2: Optional[TypedBytes]
    tangent: Optional[TypedBytes]
    color: Optional[TypedBytes]
    joints: Optional[TypedBytes]
    weights: Optional[TypedBytes]
    indices: Optional[TypedBytes]


class GltfMesh(NamedTuple):
    name: str
    primitives: Tuple[GltfPrimitive, ...]


@dataclass
class GltfNode:
    name: str
    children: List['GltfNode']
    mesh: Optional[GltfMesh] = None
    matrix: Optional[Mat4] = None
    translation: Optional[Vec3] = Vec3(0, 0, 0)
    rotation: Optional[Vec4] = Vec4(0, 0, 0, 1)
    scale: Optional[Vec3] = Vec3(1, 1, 1)
