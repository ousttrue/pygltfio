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

    def read_accessor(self, accessor_index: int) -> GltfAccessorSlice:
        gltf_accessor = self.gltf['accessors'][accessor_index]
        offset = gltf_accessor.get('byteOffset', 0)
        count = gltf_accessor['count']
        element_type, element_count = get_accessor_type(gltf_accessor)
        scalar_format = element_type._type_  # type: ignore
        length = ctypes.sizeof(element_type) * element_count*count
        match gltf_accessor:
            case {'bufferView': buffer_view_index}:
                bin = self.buffer_view_bytes(buffer_view_index)
                bin = bin[offset:offset+length]
                return GltfAccessorSlice(memoryview(bin).cast(scalar_format), element_count)
            case _:
                # zero filled
                return GltfAccessorSlice(memoryview(b'\0' * length).cast(scalar_format), element_count)


class GltfData:
    def __init__(self, gltf, path: Optional[pathlib.Path], bin: Optional[bytes]):
        self.gltf = gltf
        self.path = path
        self.bin = bin
        self.buffer_reader = GltfBufferReader(gltf, path, bin)
        self.images: List[GltfImage] = []
        self.textures: List[GltfTexture] = []
        self.materials: List[GltfMaterial] = []
        self.meshes: List[GltfMesh] = []
        self.skins: List[GltfSkin] = []
        self.nodes: List[GltfNode] = []
        self.scene: List[GltfNode] = []
        self.animations: List[GltfAnimation] = []

    def __str__(self) -> str:
        return f'{len(self.materials)} materials, {len(self.meshes)} meshes, {len(self.nodes)} nodes'

    def _parse_image(self, i: int, gltf_image) -> GltfImage:
        name = gltf_image.get('name')
        extensions = gltf_image.get('extensions')
        extras = gltf_image.get('extras')
        match gltf_image:
            case {'bufferView': buffer_view_index, 'mimeType': mime}:
                return GltfImage(i, name or f'{i}', self.buffer_reader.buffer_view_bytes(buffer_view_index), MimeType(mime), extensions, extras)
            case {'uri': uri}:
                if uri.startswith('data:'):
                    m = DATA_URI.match(uri)
                    if not m:
                        raise RuntimeError()
                    return GltfImage(i, uri, self.buffer_reader.uri_bytes(uri), MimeType(m[1]), extensions, extras)
                else:
                    return GltfImage(i, uri, self.buffer_reader.uri_bytes(uri), MimeType.from_name(uri), extensions, extras)
            case _:
                raise GltfError()

    def _parse_texture(self, i: int, gltf_texture) -> GltfTexture:
        extensions = gltf_texture.get('extensions')
        extras = gltf_texture.get('extras')
        match gltf_texture:
            case {'source': image_index}:
                texture = GltfTexture(i, gltf_texture.get(
                    'name', f'{i}'), self.images[image_index], extensions, extras)
                return texture
            case {'extensions': {
                'KHR_texture_basisu': {'source': image_index}
            }}:
                texture = GltfTexture(i, gltf_texture.get(
                    'name', f'{i}'), self.images[image_index], extensions, extras)
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
        extensions = None
        extras = None
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
                    extensions = v
                case 'extras':
                    extras = v

                case _:
                    raise NotImplementedError()
        material = GltfMaterial(i, name, base_color_texture,
                                base_color_factor, metallic_roughness_texture, metallic_factor, roughness_factor,
                                emissive_texture, emissive_factor, normal_texture, occlusion_texture, alpha_mode, alpha_cutoff, double_sided, extensions, extras)
        return material

    def _parse_mesh(self, i: int, gltf_mesh) -> GltfMesh:
        primitives = []
        for gltf_prim in gltf_mesh['primitives']:
            gltf_attributes = gltf_prim['attributes']
            positions = None
            position_min = Vec3(float('inf'), float('inf'), float('inf'))
            position_max = Vec3(-float('inf'), -float('inf'), -float('inf'))
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
                        match self.gltf['accessors'][v]:
                            case {
                                'min': min_list,
                                'max': max_list
                            }:
                                position_min = Vec3(*min_list)
                                position_max = Vec3(*max_list)
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
            prim = GltfPrimitive(material, positions, position_min, position_max,
                                 normal, uv0, uv1, uv2,
                                 tangent, color,
                                 joints, weights,
                                 indices)
            primitives.append(prim)

        mesh = GltfMesh(i, gltf_mesh.get('name', f'{i}'), tuple(
            primitives), gltf_mesh.get('extensions'), gltf_mesh.get('extras'))
        return mesh

    def _parse_node(self, i: int, gltf_node) -> GltfNode:
        node = GltfNode(i, f'{i}', [])
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
                    node.extensions = v
                case 'extras':
                    node.extras = v
                case _:
                    raise NotImplementedError()
        return node

    def _parse_skin(self, i: int, gltf_skin) -> GltfSkin:
        matrices = None
        match gltf_skin:
            case {'inverseBindMatrices': accessor}:
                matrices = self.buffer_reader.read_accessor(accessor)
        skeleton = None
        match gltf_skin:
            case {'skeleton': skeleton_index}:
                skeleton = self.nodes[skeleton_index]

        skin = GltfSkin(i, gltf_skin.get('name', f'{i}'),
                        matrices, skeleton,
                        [self.nodes[joint] for joint in gltf_skin['joints']],
                        gltf_skin.get('extensions'),
                        gltf_skin.get('extras'))
        return skin

    def _parse_animation_channel(self, gltf_animation_channel) -> GltfAnimationChannel:
        match gltf_animation_channel:
            case {'sampler': sampler, 'target': {'node': target_node, 'path': target_path}}:
                target = GltfAnimationTarget(GltfAnimationTargetPath(
                    target_path), self.nodes[target_node])
                return GltfAnimationChannel(sampler, target)
            case _:
                raise GltfError()

    def _parse_animation_sampler(self, gltf_animation_sampler) -> GltfAnimationSampler:
        match gltf_animation_sampler:
            case {'input': input, 'output': output}:
                interpolation = gltf_animation_sampler.get(
                    'interpolation', 'LINEAR')
                return GltfAnimationSampler(
                    self.buffer_reader.read_accessor(input),
                    self.buffer_reader.read_accessor(output),
                    GltfAnimationInterpolation(interpolation))
            case _:
                raise GltfError()

    def _parse_animation(self, i: int, gltf_animation) -> GltfAnimation:
        channels = [self._parse_animation_channel(
            ch) for ch in gltf_animation['channels']]
        samplers = [self._parse_animation_sampler(
            s) for s in gltf_animation['samplers']]
        animation = GltfAnimation(i, gltf_animation.get(
            'name', f'{i}'), channels, samplers)
        return animation

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

        # skinning
        for i, gltf_skin in enumerate(self.gltf.get('skins', [])):
            skin = self._parse_skin(i, gltf_skin)
            self.skins.append(skin)

        # node 2 pass
        for i, gltf_node in enumerate(self.gltf.get('nodes', [])):
            match gltf_node.get('children'):
                case [*children]:
                    for child_index in children:
                        self.nodes[i].children.append(self.nodes[child_index])
            match gltf_node:
                case {'skin': skin_index}:
                    self.nodes[i].skin = self.skins[skin_index]

        # scene
        self.scene += [self.nodes[node_index]
                       for node_index in self.gltf['scenes'][self.gltf.get('scene', 0)]['nodes']]

        # animation
        for i, gltf_animation in enumerate(self.gltf.get('animations', [])):
            animation = self._parse_animation(i, gltf_animation)
            self.animations.append(animation)


def parse_gltf(json_chunk: bytes, *, path: Optional[pathlib.Path] = None, bin: Optional[bytes] = None) -> GltfData:
    import json
    gltf = json.loads(json_chunk)
    data = GltfData(gltf, path, bin)
    data.parse()

    return data
