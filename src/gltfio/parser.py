import pathlib
import ctypes
import re
from typing import Optional, List, Dict
from .types import *


DATA_URI = re.compile(r'^data:([^;]*);base64,(.*)')


class GltfBufferReader:
    def __init__(self, gltf, path: Optional[pathlib.Path], bin: Optional[bytes]):
        self.gltf = gltf
        self.bin = bin
        self.path = path
        self.uri_cache: Dict[str, bytes] = {}

    def uri_bytes(self, uri: str) -> bytes:
        data = self.uri_cache.get(uri)
        if not data:
            if uri.startswith('data:'):
                m = DATA_URI.match(uri)
                if not m:
                    raise RuntimeError()
                import base64
                data = base64.urlsafe_b64decode(m[2])
            elif self.path:
                import urllib.parse
                path = self.path.parent / urllib.parse.unquote(uri)
                data = path.read_bytes()
            else:
                raise NotImplementedError()
        self.uri_cache[uri] = data
        return data

    def _buffer_bytes(self, buffer_index: int) -> bytes:
        if self.bin and buffer_index == 0:
            # glb bin_chunk
            return self.bin

        gltf_buffer = self.gltf['buffers'][buffer_index]
        uri = gltf_buffer['uri']
        if not isinstance(uri, str):
            raise GltfError()

        return self.uri_bytes(uri)

    def buffer_view_bytes(self, buffer_view_index: int) -> bytes:
        gltf_buffer_view = self.gltf['bufferViews'][buffer_view_index]
        bin = self._buffer_bytes(gltf_buffer_view['buffer'])
        offset = gltf_buffer_view.get('byteOffset', 0)
        length = gltf_buffer_view['byteLength']
        return bin[offset:offset+length]

    def read_accessor(self, accessor_index: int) -> TypedBytes:
        gltf_accessor = self.gltf['accessors'][accessor_index]
        offset = gltf_accessor.get('byteOffset', 0)
        count = gltf_accessor['count']
        element_type, element_count = get_accessor_type(gltf_accessor)
        length = ctypes.sizeof(element_type) * element_count*count
        match gltf_accessor:
            case {'bufferView': buffer_view_index}:
                bin = self.buffer_view_bytes(buffer_view_index)
                bin = bin[offset:offset+length]
                return TypedBytes(bin, element_type, element_count)
            case _:
                # zefo filled
                return TypedBytes(b'\0' * length, element_type, element_count)


class GltfData:
    def __init__(self, gltf, path: Optional[pathlib.Path], bin: Optional[bytes]):
        self.gltf = gltf
        self.path = path
        self.bin = bin
        self.images: List[GltfImage] = []
        self.textures: List[GltfTexture] = []
        self.materials: List[GltfMaterial] = []
        self.meshes: List[GltfMesh] = []
        self.nodes: List[GltfNode] = []
        self.scene: List[GltfNode] = []
        self.buffer_reader = GltfBufferReader(gltf, path, bin)

    def __str__(self) -> str:
        return f'{len(self.materials)} materials, {len(self.meshes)} meshes, {len(self.nodes)} nodes'

    def _parse_image(self, i: int, gltf_image) -> GltfImage:
        name = gltf_image.get('name')
        match gltf_image:
            case {'bufferView': buffer_view_index, 'mimeType': mime}:
                return GltfImage(name or f'{i}', self.buffer_reader.buffer_view_bytes(buffer_view_index), MimeType(mime))
            case {'uri': uri}:
                if uri.startswith('data:'):
                    m = DATA_URI.match(uri)
                    if not m:
                        raise RuntimeError()
                    return GltfImage(uri, self.buffer_reader.uri_bytes(uri), MimeType(m[1]))
                else:
                    return GltfImage(uri, self.buffer_reader.uri_bytes(uri), MimeType.from_name(uri))
            case _:
                raise GltfError()

    def _parse_texture(self, i: int, gltf_texture) -> GltfTexture:
        match gltf_texture:
            case {'source': image_index}:
                texture = GltfTexture(gltf_texture.get(
                    'name', f'{i}'), self.images[image_index])
                return texture
            case {'extensions': {
                'KHR_texture_basisu': {'source': image_index}
            }}:
                texture = GltfTexture(gltf_texture.get(
                    'name', f'{i}'), self.images[image_index])
                return texture
            case _:
                raise Exception()

    def _parse_material(self, i: int, gltf_material) -> GltfMaterial:
        name = f'{i}'
        base_color_texture = None
        base_color_factor = RGBA(1, 1, 1, 1)
        metallic_roughness_texture = None
        metallic_factor = 0.0
        roughness_factor = 0.0
        emissive_texture = None
        emissive_factor = RGB(0, 0, 0)
        normal_texture = None
        occlusion_texture = None
        alpha_mode = AlphaMode.OPAQUE
        alpha_cutoff = 0.5
        double_sided = False
        for k, v in gltf_material.items():
            match k:
                case 'name':
                    name = v
                case 'pbrMetallicRoughness':
                    for kk, vv in v.items():
                        match kk:
                            case 'baseColorTexture':
                                match vv:
                                    case {'index': texture_index}:
                                        base_color_texture = self.textures[texture_index]
                                    case _:
                                        raise GltfError()
                            case 'baseColorFactor':
                                base_color_factor = RGBA(*vv)
                            case 'metallicFactor':
                                metallic_factor = vv
                            case 'roughnessFactor':
                                roughness_factor = vv
                            case 'metallicRoughnessTexture':
                                match vv:
                                    case {'index': texture_index}:
                                        metallic_roughness_texture = self.textures[texture_index]
                            case _:
                                raise NotImplementedError()
                        pass
                case 'emissiveTexture':
                    match v:
                        case {'index': texture_index}:
                            emissive_texture = self.textures[texture_index]
                case 'emissiveFactor':
                    emissive_factor = RGB(*v)
                case 'alphaMode':
                    alpha_mode = AlphaMode(v)
                case 'alphaCutoff':
                    alpha_cutoff = v
                case 'doubleSided':
                    double_sided = v
                case 'normalTexture':
                    match v:
                        case {'index': texture_index}:
                            normal_texture = self.textures[texture_index]
                        case _:
                            raise GltfError()
                case 'occlusionTexture':
                    match v:
                        case {'index': texture_index}:
                            occlusion_texture = self.textures[texture_index]
                        case _:
                            raise GltfError()

                case 'extensions':
                    # TODO:
                    pass

                case _:
                    raise NotImplementedError()
        material = GltfMaterial(name, base_color_texture,
                                base_color_factor, metallic_roughness_texture, metallic_factor, roughness_factor,
                                emissive_texture, emissive_factor, normal_texture, occlusion_texture, alpha_mode, alpha_cutoff, double_sided)
        return material

    def _parse_mesh(self, i: int, gltf_mesh) -> GltfMesh:
        primitives = []
        for gltf_prim in gltf_mesh['primitives']:
            gltf_attributes = gltf_prim['attributes']
            positions = None
            normal = None
            uv0 = None
            uv1 = None
            uv2 = None
            tangent = None
            color = None
            joints = None
            weights = None
            for k, v in gltf_attributes.items():
                match k:
                    case 'POSITION':
                        positions = self.buffer_reader.read_accessor(v)
                    case 'NORMAL':
                        normal = self.buffer_reader.read_accessor(v)
                    case 'TEXCOORD_0':
                        uv0 = self.buffer_reader.read_accessor(v)
                    case 'TEXCOORD_1':
                        uv1 = self.buffer_reader.read_accessor(v)
                    case 'TEXCOORD_2':
                        uv2 = self.buffer_reader.read_accessor(v)
                    case 'TANGENT':
                        tangent = self.buffer_reader.read_accessor(v)
                    case 'COLOR_0':
                        color = self.buffer_reader.read_accessor(v)
                    case 'JOINTS_0':
                        joints = self.buffer_reader.read_accessor(v)
                    case 'WEIGHTS_0':
                        weights = self.buffer_reader.read_accessor(v)
                    case _:
                        raise NotImplementedError()
            if not positions:
                raise GltfError('no POSITIONS')

            indices = None
            match gltf_prim:
                case {'indices': accessor}:
                    indices = self.buffer_reader.read_accessor(accessor)

            match gltf_prim:
                case {'material': material_index}:
                    material = self.materials[material_index]
                case _:
                    # use default material
                    material = GltfMaterial.default()
            prim = GltfPrimitive(material, positions, normal,
                                 uv0, uv1, uv2,
                                 tangent, color,
                                 joints, weights,
                                 indices)
            primitives.append(prim)

        mesh = GltfMesh(gltf_mesh.get('name', f'{i}'), tuple(primitives))
        return mesh

    def _parse_node(self, i: int, gltf_node) -> GltfNode:
        node = GltfNode(f'{i}', [])
        for k, v in gltf_node.items():
            match k:
                case 'name':
                    node.name = v
                case 'mesh':
                    node.mesh = self.meshes[v]
                case 'children':
                    pass
                case 'matrix':
                    node.matrix = v
                case 'translation':
                    node.translation = Vec3(*v)
                case 'rotation':
                    node.rotation = Vec4(*v)
                case 'scale':
                    node.scale = Vec3(*v)
                case 'skin':
                    # TODO:
                    pass
                case 'camera':
                    # TODO:
                    pass
                case 'extensions':
                    # TODO:
                    pass
                case 'extras':
                    # TODO
                    pass
                case _:
                    raise NotImplementedError()
        return node

    def parse(self):
        # image
        for i, gltf_image in enumerate(self.gltf.get('images', [])):
            image = self._parse_image(i, gltf_image)
            self.images.append(image)

        # texture
        for i, gltf_texture in enumerate(self.gltf.get('textures', [])):
            texture = self._parse_texture(i, gltf_texture)
            self.textures.append(texture)

        # material
        maetrials = self.gltf.get('materials')
        if maetrials:
            for i, gltf_material in enumerate(maetrials):
                material = self._parse_material(i, gltf_material)
                self.materials.append(material)
        else:
            NotImplementedError('no material')

        # mesh
        for i, gltf_mesh in enumerate(self.gltf.get('meshes', [])):
            mesh = self._parse_mesh(i, gltf_mesh)
            self.meshes.append(mesh)

        # node
        for i, gltf_node in enumerate(self.gltf.get('nodes', [])):
            node = self._parse_node(i, gltf_node)
            self.nodes.append(node)
        for i, gltf_node in enumerate(self.gltf.get('nodes', [])):
            match gltf_node.get('children'):
                case [*children]:
                    for child_index in children:
                        self.nodes[i].children.append(self.nodes[child_index])

        # skinning
        for i, gltf_skin in enumerate(self.gltf.get('skins', [])):
            pass

        # scene
        self.scene += [self.nodes[node_index]
                       for node_index in self.gltf['scenes'][self.gltf.get('scene', 0)]['nodes']]


def parse_gltf(json_chunk: bytes, *, path: Optional[pathlib.Path] = None, bin: Optional[bytes] = None) -> GltfData:
    import json
    gltf = json.loads(json_chunk)
    data = GltfData(gltf, path, bin)
    data.parse()

    return data
