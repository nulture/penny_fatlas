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
	## Includes all islands as a single region; trims excess transparent pixels outside this region.
	CROP_FULL = "crop_full"
	## Includes only the largest island found in the image.
	CROP_SINGLE = "crop_single"
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
	def __init__(self, root : str, file : str, region : Rect = None):
		super().__init__(root, file)
		self.image : Image = Image.open(self.full).convert("RGBA")

		if region == None:
			region = Rect(0, 0, self.image.width, self.image.height)

		self.source_region = region
		self.target_offset = Vec2(0, 0)

	@property
	def image_cropped(self) -> Image:
		return self.image.crop((self.source_region.left, self.source_region.top, self.source_region.right, self.source_region.bottom))


	@property
	def target_region(self) -> Rect:
		return Rect(self.target_offset, self.source_region.size)

	
	def crop_islands(self, mode : IslandMode, threshold : int = 16):
		bitmap = self.get_opacity_bitmap(threshold)
		pixels = bitmap.load()
		w, h = self.image.size
		visited = set()
		rects = []

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
		
		for x in range(w):
			for y in range(h):
				if (x, y) not in visited and pixels[x, y] == 1:
					island = flood_fill(x, y)
					if island:
						min_x = min(p[0] for p in island)
						max_x = max(p[0] for p in island)
						min_y = min(p[1] for p in island)
						max_y = max(p[1] for p in island)
						rects.append(Rect(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1))
		
		if not rects: return self
		match mode:
			case IslandMode.CROP_FULL: 
				while len(rects) > 1:
					rects.insert(0, rects.pop().union(rects.pop()))
				self.source_region = rects[0]
				return self

			case IslandMode.CROP_SINGLE:
				rects.sort(key=lambda rect: rect.w * rect.h, reverse=True)
				self.source_region = rects[0]
				return self				
				
			case IslandMode.CROP_MANY:
				pass

		print(f"Found islands: {rects}")

		return self
	
		
	def get_opacity_bitmap(self, threshold: int = 16):
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
		print(f"Cropped image to {self.image.size}")

	
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
		snap1 = source.target_offset + Vec2(source.image.width, 0)
		try:
			_ = self.snaps.index(snap1)
		except ValueError:
			self.snaps.append(snap1)
		snap2 = source.target_offset + Vec2(0, source.image.height)
		try:
			_ = self.snaps.index(snap2)
		except ValueError:
			self.snaps.append(snap2)

		print(f"Added image at {source.target_offset}")


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
	parser.add_argument("--island-crop", "-ic", type=island_mode, required=False, default=IslandMode.NO_CROP, help=f"Defines how/if to separate pixel islands. Options: {[e.value for e in IslandMode]}")
	parser.add_argument("--island-margin", "-im", type=int, required=False, default=1, help="Islands above this threshold will have their regions expanded by this margin to include any surrounding pixels.")
	parser.add_argument("--island-opacity", "-io", type=int, required=False, default=16, help="Pixels with an opacity above this threshold will be considered part of a contiguous island.")
	parser.add_argument("--island-size", "-is", type=int, required=False, default=1, help="Islands with an area smaller than this will be discarded.")
	args = parser.parse_args()

	sources = aggregate_image_sources(args.source_folder, args.regex_restrict)
	
	print(f"Found {len(sources)} images to compile.")

	# if args.island_crop != IslandMode.NO_CROP:
	# 	new_sources = []
	# 	for source in sources: 
	# 		new_sources.append(source.crop_islands(args.island_crop))
	# 	sources = new_sources
	sources[0] = sources[0].crop_islands(args.island_crop)

	target = TargetImage(args.target_folder, args.target_path, args.target_format)

	i = 0
	limit = 1
	for source in sources:
		i += 1
		if i > limit: break
		
		target.add(source)
		
	print(f"Final image size: {target.image.size}")
	target.image.show()
	target.save()

	# img = sources[0]
	# img.get_opacity_bitmap()
	# # img.get_bitmap().save(target.full)


if __name__ == "__main__":
	main()