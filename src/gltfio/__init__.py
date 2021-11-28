import pathlib
from .glb import GlbError, parse_glb
from .parser import GltfData, parse_gltf


def parse_path(path: pathlib.Path) -> GltfData:
    '''
    parse glb or gltf
    '''
    data = path.read_bytes()
    try:
        # first, try glb
        json, bin = parse_glb(data)
        if json and bin:
            return parse_gltf(json, path=path, bin=bin)
    except GlbError:
        pass

    # fallback to gltf
    return parse_gltf(data, path=path)
