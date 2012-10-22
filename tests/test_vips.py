import unittest

from gdal2mbtiles.constants import TILE_SIDE
from gdal2mbtiles.storages import Storage
from gdal2mbtiles.types import XY
from gdal2mbtiles.vips import LibVips, TmsTiles, VImage, VIPS


class TestLibVips(unittest.TestCase):
    def setUp(self):
        self.version = 15

    def tearDown(self):
        VIPS.set_concurrency(processes=0)  # Auto-detect

    def test_create(self):
        self.assertTrue(LibVips(version=self.version))
        self.assertRaises(OSError, LibVips, version=999)

    def test_concurrency(self):
        concurrency = 42
        vips = LibVips(version=self.version)
        self.assertRaises(ValueError, vips.set_concurrency, processes=1.1)
        self.assertRaises(ValueError, vips.set_concurrency, processes=-1)
        self.assertEqual(vips.set_concurrency(processes=concurrency), None)
        self.assertEqual(vips.get_concurrency(), concurrency)


class TestVImage(unittest.TestCase):
    def test_new_rgba(self):
        image = VImage.new_rgba(width=1, height=2)
        self.assertEqual(image.Xsize(), 1)
        self.assertEqual(image.Ysize(), 2)
        self.assertEqual(image.Bands(), 4)

    def test_from_vimage(self):
        image = VImage.new_rgba(width=1, height=1)
        self.assertEqual(VImage.from_vimage(image).tostring(),
                         image.tostring())

    def test_stretch(self):
        image = VImage.new_rgba(width=16, height=16)

        # No stretch
        stretched = image.stretch(xscale=1.0, yscale=1.0)
        self.assertEqual(stretched.Xsize(), image.Xsize())
        self.assertEqual(stretched.Ysize(), image.Ysize())

        # X direction
        stretched = image.stretch(xscale=2.0, yscale=1.0)
        self.assertEqual(stretched.Xsize(), image.Xsize() * 2.0)
        self.assertEqual(stretched.Ysize(), image.Ysize())

        # Y direction
        stretched = image.stretch(xscale=1.0, yscale=4.0)
        self.assertEqual(stretched.Xsize(), image.Xsize())
        self.assertEqual(stretched.Ysize(), image.Ysize() * 4.0)

        # Both directions
        stretched = image.stretch(xscale=2.0, yscale=4.0)
        self.assertEqual(stretched.Xsize(), image.Xsize() * 2.0)
        self.assertEqual(stretched.Ysize(), image.Ysize() * 4.0)

        # Not a power of 2
        stretched = image.stretch(xscale=3.0, yscale=5.0)
        self.assertEqual(stretched.Xsize(), image.Xsize() * 3.0)
        self.assertEqual(stretched.Ysize(), image.Ysize() * 5.0)

        # Out of bounds
        self.assertRaises(ValueError,
                          image.stretch, xscale=0.5, yscale=1.0)
        self.assertRaises(ValueError,
                          image.stretch, xscale=1.0, yscale=0.5)

    def test_shrink(self):
        image = VImage.new_rgba(width=16, height=16)

        # No shrink
        shrunk = image.shrink(xscale=1.0, yscale=1.0)
        self.assertEqual(shrunk.Xsize(), image.Xsize())
        self.assertEqual(shrunk.Ysize(), image.Ysize())

        # X direction
        shrunk = image.shrink(xscale=0.25, yscale=1.0)
        self.assertEqual(shrunk.Xsize(), image.Xsize() * 0.25)
        self.assertEqual(shrunk.Ysize(), image.Ysize())

        # Y direction
        shrunk = image.shrink(xscale=1.0, yscale=0.5)
        self.assertEqual(shrunk.Xsize(), image.Xsize())
        self.assertEqual(shrunk.Ysize(), image.Ysize() * 0.5)

        # Both directions
        shrunk = image.shrink(xscale=0.25, yscale=0.5)
        self.assertEqual(shrunk.Xsize(), image.Xsize() * 0.25)
        self.assertEqual(shrunk.Ysize(), image.Ysize() * 0.5)

        # Not a power of 2
        shrunk = image.shrink(xscale=0.1, yscale=0.2)
        self.assertEqual(shrunk.Xsize(), int(image.Xsize() * 0.1))
        self.assertEqual(shrunk.Ysize(), int(image.Ysize() * 0.2))

        # Out of bounds
        self.assertRaises(ValueError,
                          image.shrink, xscale=0.0, yscale=1.0)
        self.assertRaises(ValueError,
                          image.shrink, xscale=2.0, yscale=1.0)
        self.assertRaises(ValueError,
                          image.shrink, xscale=1.0, yscale=0.0)
        self.assertRaises(ValueError,
                          image.shrink, xscale=1.0, yscale=2.0)

    def test_tms_align(self):
        image = VImage.new_rgba(width=16, height=16)

        # Already aligned to integer offsets
        result = image.tms_align(tile_width=16, tile_height=16,
                                 offset=XY(1, 1))
        self.assertEqual(result.Xsize(), image.Xsize())
        self.assertEqual(result.Ysize(), image.Ysize())

        # Spanning by half tiles in both X and Y directions
        result = image.tms_align(tile_width=16, tile_height=16,
                                 offset=XY(1.5, 1.5))
        self.assertEqual(result.Xsize(), image.Xsize() * 2)
        self.assertEqual(result.Ysize(), image.Ysize() * 2)

        # Image is quarter tile
        result = image.tms_align(tile_width=32, tile_height=32,
                                 offset=XY(1, 1))
        self.assertEqual(result.Xsize(), image.Xsize() * 2)
        self.assertEqual(result.Ysize(), image.Ysize() * 2)


class TestTmsTiles(unittest.TestCase):
    def test_dimensions(self):
        # Very small WGS84 map. :-)
        image = VImage.new_rgba(width=2, height=1)
        tiles = TmsTiles(image=image,
                         storage=Storage(renderer=None),
                         tile_width=1, tile_height=1,
                         offset=XY(0, 0), resolution=0)
        self.assertEqual(tiles.image_width, 2)
        self.assertEqual(tiles.image_height, 1)

    def test_downsample(self):
        resolution = 2
        image = VImage.new_rgba(width=TILE_SIDE * 2 ** resolution,
                                height=TILE_SIDE * 2 ** resolution)
        tiles = TmsTiles(image=image,
                         storage=Storage(renderer=None),
                         tile_width=TILE_SIDE, tile_height=TILE_SIDE,
                         offset=XY(0, 0),
                         resolution=resolution)

        # Zero levels - invalid
        self.assertRaises(AssertionError,
                          tiles.downsample, levels=0)

        # One level
        tiles1a = tiles.downsample()
        self.assertEqual(tiles1a.image_width,
                         TILE_SIDE * 2 ** (resolution - 1))
        self.assertEqual(tiles1a.image_height,
                         TILE_SIDE * 2 ** (resolution - 1))
        self.assertEqual(tiles1a.resolution,
                         resolution - 1)

        tiles1b = tiles.downsample(levels=1)
        self.assertEqual(tiles1b.image_width,
                         TILE_SIDE * 2 ** (resolution - 1))
        self.assertEqual(tiles1b.image_height,
                         TILE_SIDE * 2 ** (resolution - 1))
        self.assertEqual(tiles1b.resolution,
                         resolution - 1)

        # Two levels
        tiles2 = tiles.downsample(levels=2)
        self.assertEqual(tiles2.image_width,
                         TILE_SIDE * 2 ** (resolution - 2))
        self.assertEqual(tiles2.image_height,
                         TILE_SIDE * 2 ** (resolution - 2))
        self.assertEqual(tiles2.resolution,
                         resolution - 2)

        # Three levels - invalid since resolution is 2
        self.assertRaises(AssertionError,
                          tiles.downsample, levels=3)

    def test_upsample(self):
        resolution = 0
        image = VImage.new_rgba(width=TILE_SIDE * 2 ** resolution,
                                height=TILE_SIDE * 2 ** resolution)
        tiles = TmsTiles(image=image,
                         storage=Storage(renderer=None),
                         tile_width=TILE_SIDE, tile_height=TILE_SIDE,
                         offset=XY(0, 0), resolution=resolution)

        # Zero levels
        self.assertRaises(AssertionError,
                          tiles.upsample, levels=0)

        # One level
        tiles1a = tiles.upsample()
        self.assertEqual(tiles1a.image_width,
                         TILE_SIDE * 2 ** (resolution + 1))
        self.assertEqual(tiles1a.image_height,
                         TILE_SIDE * 2 ** (resolution + 1))
        self.assertEqual(tiles1a.resolution,
                         resolution + 1)

        tiles1b = tiles.upsample(levels=1)
        self.assertEqual(tiles1b.image_width,
                         TILE_SIDE * 2 ** (resolution + 1))
        self.assertEqual(tiles1b.image_height,
                         TILE_SIDE * 2 ** (resolution + 1))
        self.assertEqual(tiles1b.resolution,
                         resolution + 1)

        # Two levels
        tiles2 = tiles.upsample(levels=2)
        self.assertEqual(tiles2.image_width,
                         TILE_SIDE * 2 ** (resolution + 2))
        self.assertEqual(tiles2.image_height,
                         TILE_SIDE * 2 ** (resolution + 2))
        self.assertEqual(tiles2.resolution,
                         resolution + 2)
