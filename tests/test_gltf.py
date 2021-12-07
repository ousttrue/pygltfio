import unittest
import pathlib
import gltfio
import gltfio.glb
import gltfio.types


def get_path(key: str) -> pathlib.Path:
    import os
    value = os.environ.get(key)
    if not value:
        import sys
        sys.exit()
    return pathlib.Path(value)


GLTF_SAMPLE_MODELS = get_path('GLTF_SAMPLE_MODELS')


class TestGltf(unittest.TestCase):

    def test_gltf(self):
        path = GLTF_SAMPLE_MODELS / '2.0/Box/glTF/Box.gltf'
        gltf_data = gltfio.parse_path(path)
        self.assertEqual(1, len(gltf_data.materials))
        self.assertEqual(1, len(gltf_data.meshes))
        self.assertEqual(
            24, gltf_data.meshes[0].primitives[0].position.get_count())
        self.assertEqual(
            24, gltf_data.meshes[0].primitives[0].normal.get_count())  # type: ignore
        self.assertEqual(
            36, gltf_data.meshes[0].primitives[0].indices.get_count())  # type: ignore
        self.assertEqual(
            'Red', gltf_data.meshes[0].primitives[0].material.name)
        self.assertEqual(2, len(gltf_data.nodes))

    def test_glb(self):
        path = GLTF_SAMPLE_MODELS / '2.0/BoxTextured/glTF-Binary/BoxTextured.glb'
        gltf_data = gltfio.parse_path(path)
        self.assertEqual(1, len(gltf_data.materials))
        self.assertEqual(1, len(gltf_data.meshes))
        self.assertEqual(
            24, gltf_data.meshes[0].primitives[0].position.get_count())
        self.assertEqual(
            24, gltf_data.meshes[0].primitives[0].normal.get_count())  # type: ignore
        self.assertEqual(24, gltf_data.meshes[0].primitives[0].uv0.get_count()  # type: ignore
                         )
        self.assertEqual(
            36, gltf_data.meshes[0].primitives[0].indices.get_count())  # type: ignore
        self.assertEqual(
            'Texture', gltf_data.meshes[0].primitives[0].material.name)
        self.assertEqual('CesiumLogoFlat.png',
                         gltf_data.textures[0].image.name)
        self.assertEqual(gltfio.types.MimeType.Png,
                         gltf_data.textures[0].image.mime)
        self.assertEqual(2, len(gltf_data.nodes))

    def test_skin_animation(self):
        path = GLTF_SAMPLE_MODELS / '2.0/CesiumMan/glTF-Binary/CesiumMan.glb'
        gltf_data = gltfio.parse_path(path)
        self.assertEqual(1, len(gltf_data.skins))
        self.assertEqual(gltf_data.skins[0], gltf_data.nodes[2].skin)
        self.assertEqual(1, len(gltf_data.animations))

    def test_all(self):
        dir = GLTF_SAMPLE_MODELS / '2.0'
        for model in dir.iterdir():
            if not model.is_dir():
                continue
            for kind in model.iterdir():
                if not kind.is_dir():
                    continue
                for path in kind.iterdir():
                    match path.suffix:
                        case '.gltf' | '.glb':
                            gltf_data = gltfio.parse_path(path)


if __name__ == '__main__':
    unittest.main()
