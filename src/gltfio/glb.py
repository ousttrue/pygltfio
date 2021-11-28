import struct
from typing import Tuple, Optional


class GlbError(RuntimeError):
    pass


class BytesReader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def is_end(self) -> bool:
        return self.pos >= len(self.data)

    def read(self, size: int) -> bytes:
        if (self.pos + size) > len(self.data):
            raise IOError()
        data = self.data[self.pos:self.pos+size]
        self.pos += size
        return data

    def read_int(self) -> int:
        data = self.read(4)
        return struct.unpack('i', data)[0]


def parse_glb(data: bytes) -> Tuple[Optional[bytes], Optional[bytes]]:
    '''
    https://www.khronos.org/registry/glTF/specs/2.0/glTF-2.0.html#glb-file-format-specification
    '''
    r = BytesReader(data)
    if r.read_int() != 0x46546C67:
        raise GlbError('invalid magic')

    version = r.read_int()
    if version != 2:
        raise GlbError(f'unknown version: {version}')

    length = r.read_int()

    json_chunk = None
    bin_chunk = None
    while r.pos < length:
        chunk_length = r.read_int()
        chunk_type = r.read_int()
        chunk_data = r.read(chunk_length)
        match chunk_type:
            case 0x4E4F534A:
                json_chunk = chunk_data
            case 0x004E4942:
                bin_chunk = chunk_data
            case _:
                raise NotImplementedError(f'unknown chunk: {chunk_type}')

    return json_chunk, bin_chunk
