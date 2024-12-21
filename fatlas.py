import os
import re
import sys
import argparse
from PIL import Image, ImageOps
from enum import Enum
from pygame import Rect
from pygame import Vector2 as Vec2

class IslandMode(Enum):
	## Performs no internal cropping on the images.
	NO_CROP = "no_crop"
	## Includes all islands as a single region; trims excess transparent pixels.
	CROP_FULL = "crop_full"
	## Includes only the largest island found in the image.
	CROP_LARGEST = "crop_largest"
	## Includes all islands found as individual regions. Good for spritesheets.
	CROP_MANY = "crop_many"


class PathedImage:
	def __init__(self, root, file):
		self.root = root
		self.file = file
		self.full = os.path.join(root, file)
		self.name, self.ext = os.path.splitext(file)

	
	def __str__(self):
		return self.file

	
	def crop(self, size):
		pass


class SourceImage(PathedImage):
	def __init__(self, root : str, file : str, region : Rect = None, bitmap : Image = None):
		super().__init__(root, file)
		self.image : Image = Image.open(self.full).convert("RGBA")
		self.bitmap : Image = bitmap

		if region == None:
			region = Rect(0, 0, self.image.width, self.image.height)

		self.source_region = region
		self.target_offset = (0, 0)

	@property
	def image_cropped(self) -> Image:
		result : Image = self.image.crop((self.source_region.left, self.source_region.top, self.source_region.right, self.source_region.bottom))
		r, g, b, a = result.split()
		mask = self.bitmap.convert("L")
		mask_pixels = mask.load()
		alpha_pixels = a.load()

		for x in range(result.width):
			for y in range(result.height):
				alpha_pixels[x, y] = min(mask_pixels[x, y], alpha_pixels[x, y])

		result = Image.merge("RGBA", (r, g, b, a))
		# self.bitmap.show()
		return result


	@property
	def target_region(self) -> Rect:
		return Rect(self.target_offset, self.source_region.size)

	
	def crop_islands(self, args):
		bitmap = self.get_opacity_bitmap(args.island_opacity)
		pixels = bitmap.load()
		w, h = self.image.size
		visited = set()
		news = []

		def flood_fill(x, y):
			stack = [(x, y)]
			island_pixels = []

			while stack:
				px, py = stack.pop()
				if (px, py) in visited or px < 0 or py < 0 or px >= w or py >= h:
					continue
				if pixels[px, py] == 0:
					continue
			
				visited.add((px, py))
				island_pixels.append((px, py))

				stack.extend([(px + 1, py), (px - 1, py), (px, py + 1), (px, py - 1)])
			return island_pixels

		def crop_islands_many():
			result = []
			for x in range(w):
				for y in range(h):
					if (x, y) not in visited and pixels[x, y] == 1:
						island_pixels = flood_fill(x, y)
						if island_pixels:
							min_x = min(p[0] for p in island_pixels)
							max_x = max(p[0] for p in island_pixels)
							min_y = min(p[1] for p in island_pixels)
							max_y = max(p[1] for p in island_pixels)
							island_rect = Rect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)

							if island_rect.w * island_rect.h < args.island_size: continue
							
							island_bitmap = Image.new("1", island_rect.size, color=0)
							island_bitmap_pixels = island_bitmap.load()
							island_pixels_set = set(island_pixels)
							for px, py in island_pixels_set:
								island_bitmap_pixels[px - min_x, py - min_y] = 1
							result.append(SourceImage(self.root, self.file, island_rect, island_bitmap))
			return result
		
		def crop_islands_accumulate():
			rects = None
			bitms = set()
			for x in range(w):
				for y in range(h):
					if (x, y) not in visited and pixels[x, y] == 1:
						island_pixels = flood_fill(x, y)
						if island_pixels:
							min_x = min(p[0] for p in island_pixels)
							max_x = max(p[0] for p in island_pixels)
							min_y = min(p[1] for p in island_pixels)
							max_y = max(p[1] for p in island_pixels)
							island_rect = Rect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)

							if island_rect.w * island_rect.h < args.island_size: continue

							if rects == None:
								rects = island_rect
							else:
								rects = rects.union(island_rect)
							bitms = bitms.union(island_pixels)

			full_rect = rects
			full_bitmap = Image.new("1", full_rect.size, color=0)
			full_bitmap_pixels = full_bitmap.load()

			for px, py in bitms:
				full_bitmap_pixels[px - full_rect.left, py - full_rect.top] = 1
			return SourceImage(self.root, self.file, full_rect, full_bitmap)

		match args.island_mode:
			case IslandMode.CROP_FULL:
				return crop_islands_accumulate()
			case IslandMode.CROP_MANY:
				return crop_islands_many()
			case IslandMode.CROP_LARGEST:
				result = crop_islands_many()
				result.sort(key=lambda image: image.source_region.w * image.source_region.h, reverse=True)
				return result[0]
		return self
	
		
	def get_opacity_bitmap(self, threshold: int = 1):
		bitmap = Image.new("1", self.image.size)
		pixels = bitmap.load()

		for x in range(bitmap.width):
			for y in range(bitmap.height):
				_, _, _, a = self.image.getpixel((x, y))
				pixels[x, y] = 0 if a < threshold else 1
				
		return bitmap


class TargetImage(PathedImage):
	def __init__(self, root, file, format):
		super().__init__(root, file)

		self.sources = []
		self.snaps = [ (0, 0) ]

		self.image : Image = Image.new(format, [1, 1])
		self.full_rect : Rect = Rect(0, 0, 1, 1)


	def crop(self, size):
		self.full_rect.size = size
		self.image = ImageOps.pad(self.image, size, centering=(0,0))

	
	def add(self, source: SourceImage):
		size = source.source_region.size
		rect = Rect(self.get_snap_for(size), size)

		if not self.full_rect.contains(rect):
			self.crop(self.full_rect.union(rect).size)

		self.image.paste(source.image_cropped, (rect.x, rect.y))
		source.target_offset = Vec2(rect.x, rect.y)

		self.sources.append(source)

		try:
			self.snaps.remove(source.target_offset)
		except ValueError: pass
		snap1 = source.target_offset + Vec2(source.source_region.width, 0)
		try:
			_ = self.snaps.index(snap1)
		except ValueError:
			self.snaps.append(snap1)
		snap2 = source.target_offset + Vec2(0, source.source_region.height)
		try:
			_ = self.snaps.index(snap2)
		except ValueError:
			self.snaps.append(snap2)


	def get_snap_for(self, size: tuple[int, int]) -> tuple[int, int]:
		candidates = []
		for snap in self.snaps:
			query = Rect(snap, size)
			intersects = False
			for source in self.sources:
				if source.target_region.colliderect(query):
					intersects = True
					break
			if not intersects:
				candidates.append(query)

		if len(candidates) == 0: return self.snaps[0]
		candidates.sort(key=lambda rect: not self.full_rect.contains(rect))
		return [candidates[0].x, candidates[0].y]

	
	def save(self):
		# os.makedirs(os.path.dirname(self.full), exist_ok=True)
		print(f"Saving image to {self.full} ...")
		self.image.save(self.full)
		print(f"Saved image!")


def island_mode(value):
	try:
		return IslandMode(value.lower())
	except ValueError:
		argparse.ArgumentTypeError(f"Invalid mode. Choose from {[e.value for e in IslandMode]}.")


def aggregate_image_sources(source, restrict):
	result = []
	pattern = re.compile(restrict)
	for root, dirs, files, in os.walk(source):
		for file in files:			
			if re.search(pattern, file) == None: continue
			source = SourceImage(root, file)
			result.append(source)
	return result


def main():
	print("\n\n")

	# print(sys.argv[1:])
	parser = argparse.ArgumentParser(description="Something")
	parser.add_argument("source_folder", type=str, help="Source folder to compile images from.")
	parser.add_argument("target_folder", type=str, help="Target folder to export atlases to.")
	parser.add_argument("target_path", type=str, help="Target template path for each atlas.")
	parser.add_argument("--target-format", type=str, required=False, default="RGBA", help="Image format.")
	parser.add_argument("--regex-restrict", "-r", type=str, required=False, default=r".*?\.(?:png)", help="Only file paths that match this regex will be included (considers extensions)." )
	parser.add_argument("--regex-separate", "-s", type=str, required=False, default=r"", help="File names (not including extension) that match this regex will be separated into different images.")
	parser.add_argument("--island-mode", "-ic", type=island_mode, required=False, default=IslandMode.NO_CROP, help=f"Defines how/if to separate pixel islands. Options: {[e.value for e in IslandMode]}")
	parser.add_argument("--island-margin", "-im", type=int, required=False, default=1, help="Islands above this threshold will have their regions expanded by this margin to include any surrounding pixels.")
	parser.add_argument("--island-opacity", "-io", type=int, required=False, default=1, help="Pixels with an opacity above this threshold will be considered part of a contiguous island.")
	parser.add_argument("--island-size", "-is", type=int, required=False, default=1, help="Islands with an area smaller than this will be discarded.")
	args = parser.parse_args()

	sources = aggregate_image_sources(args.source_folder, args.regex_restrict)
	
	print(f"Found {len(sources)} images to compile.")

	limit = 1000
	print(f"Cropping images...")
	new_sources = []
	i = 0
	for source in sources: 
		i += 1
		if i > limit: break
		print(f"Cropping image '{source.name}' ({i}/{len(sources)})...")
		new_sources.append(source.crop_islands(args))
	sources = new_sources
	print(f"Cropping complete.")

	target = TargetImage(args.target_folder, args.target_path, args.target_format)

	print(f"Appending images...")
	i = 0
	for source in new_sources:
		i += 1
		print(f"Adding image ({i}/{len(new_sources)})...")
		target.add(source)
	print(f"Appending complete.")
		
	print(f"Final image size: {target.image.size}")
	target.image.show()
	target.save()


if __name__ == "__main__":
	main()