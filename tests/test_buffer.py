import unittest
import ctypes
import array
from gltfio.types import GltfAccessorSlice


class TestBuffer(unittest.TestCase):

    def test_bytearray(self):
        abc = bytearray(b'abc')
        c_abc = (ctypes.c_ubyte * 3).from_buffer(abc)
        abc[0] = 123
        self.assertEqual(123, c_abc[0])

    def test_bytes(self):
        abc = memoryview(b'abc')
        self.assertTrue(abc.readonly)
        # TypeError: underlying buffer is not writable
        # c_abc = (ctypes.c_ubyte * 3).from_buffer(abc)
        # abc[0] = 123
        # self.assertEqual(123, c_abc[0])

    def test_array(self):
        abc = array.array('f', (1, 2, 3))
        c_abc = (ctypes.c_float * 3).from_buffer(abc)
        abc[0] = 123
        self.assertEqual(123, c_abc[0])

    def test_memoryview(self):
        abc = memoryview(array.array('f', (1, 2, 3)))
        self.assertFalse(abc.readonly)
        c_abc = (ctypes.c_float * 3).from_buffer(abc)
        abc[0] = 123
        self.assertEqual(123, c_abc[0])

    def test_typedbytes(self):
        value = array.array('f', (1, 2, 3, 4, 5, 6, 7, 8, 9))
        tb = GltfAccessorSlice(memoryview(value), 3)
        value_slice = tb.get_item(1)
        self.assertEqual(array.array('f', (4, 5, 6)), value_slice)
