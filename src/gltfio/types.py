'''
https://github.com/KhronosGroup/glTF/blob/main/specification/2.0/
'''
from ctypes.wintypes import RGB
from typing import NamedTuple, Optional, Tuple, List, Type
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


class GltfAccessorSlice(NamedTuple):
    # float3 の場合 memoryview.format == 'f'
    # ushort1 の場合 memoryview.format == 'H'
    scalar_view: memoryview
    # float3 の場合 3
    # ushort1 の場合 1
    element_count: int = 1

    def get_stride(self) -> int:
        return self.scalar_view.itemsize * self.element_count

    def get_count(self) -> int:
        # return self.scalar_array.nbytes // self.get_stride()
        return len(self.scalar_view) // self.element_count

    def get_item(self, i: int) -> memoryview:
        begin = i * self.element_count
        return self.scalar_view[begin:begin+self.element_count]


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
    index: int
    name: str
    data: bytes
    mime: MimeType
    extensions: Optional[dict]
    extras: Optional[dict]


class GltfTexture(NamedTuple):
    index: int
    name: str
    image: GltfImage
    extensions: Optional[dict]
    extras: Optional[dict]


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
    index: int
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
    extensions: Optional[dict]
    extras: Optional[dict]

    @staticmethod
    def default() -> 'GltfMaterial':
        return GltfMaterial(-1, '__default__', None, RGBA(1, 1, 1, 1), None, 0, 1, None, RGB(0, 0, 0), None, None, AlphaMode.OPAQUE, 0.5, False, None, None)


class GltfPrimitive(NamedTuple):
    material: GltfMaterial
    position: GltfAccessorSlice
    position_min: Vec3
    position_max: Vec3
    normal: Optional[GltfAccessorSlice]
    uv0: Optional[GltfAccessorSlice]
    uv1: Optional[GltfAccessorSlice]
    uv2: Optional[GltfAccessorSlice]
    tangent: Optional[GltfAccessorSlice]
    color: Optional[GltfAccessorSlice]
    joints: Optional[GltfAccessorSlice]
    weights: Optional[GltfAccessorSlice]
    indices: Optional[GltfAccessorSlice]


class GltfMesh(NamedTuple):
    index: int
    name: str
    primitives: Tuple[GltfPrimitive, ...]
    extensions: Optional[dict]
    extras: Optional[dict]


@dataclass
class GltfNode:
    index: int
    name: str
    children: List['GltfNode']
    mesh: Optional[GltfMesh] = None
    matrix: Optional[Mat4] = None
    translation: Optional[Vec3] = Vec3(0, 0, 0)
    rotation: Optional[Vec4] = Vec4(0, 0, 0, 1)
    scale: Optional[Vec3] = Vec3(1, 1, 1)
    extensions: Optional[dict] = None
    extras: Optional[dict] = None
    skin: Optional['GltfSkin'] = None


class GltfSkin(NamedTuple):
    index: int
    name: str
    inverse_bind_matrices: Optional[GltfAccessorSlice]
    skeleton: Optional[GltfNode]
    joints: List[GltfNode]
    extensions: Optional[dict] = None
    extras: Optional[dict] = None


class GltfAnimationInterpolation(Enum):
    Linear = 'LINEAR'
    Step = 'STEP'
    Cubicspline = 'CUBICSPLINE'


class GltfAnimationSampler(NamedTuple):
    # time
    input: GltfAccessorSlice
    # values
    output: GltfAccessorSlice
    #
    interpolation: GltfAnimationInterpolation = GltfAnimationInterpolation.Linear


class GltfAnimationTargetPath(Enum):
    Translation = 'translation'
    Rotation = 'rotation'
    Scale = 'scale'
    Weights = 'weights'


class GltfAnimationTarget(NamedTuple):
    path: GltfAnimationTargetPath
    node_index: GltfNode


class GltfAnimationChannel(NamedTuple):
    sampler: int
    target: GltfAnimationTarget


class GltfAnimation(NamedTuple):
    index: int
    name: str
    channels: List[GltfAnimationChannel]
    samplers: List[GltfAnimationSampler]
    extensions: Optional[dict] = None
    extras: Optional[dict] = None
