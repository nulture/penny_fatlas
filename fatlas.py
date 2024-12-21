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
	def __init__(self, root, file):
		super().__init__(root, file)

		self.image = Image.open(self.full)
		self.source_region = Rect(0, 0, self.image.width, self.image.height)
		self.target_offset = Vec2(0, 0)


	@property
	def target_region(self) -> Rect:
		return Rect(self.target_offset, self.source_region.size)

	
	def crop_to_new(self, mode):
		return self


	def get_size(self) -> Vec2:
		return Vec2(self.source_region.width, self.source_region.height)


class TargetImage(PathedImage):
	def __init__(self, root, file, format):
		super().__init__(root, file)

		self.sources = []
		self.snaps = [ Vec2(0, 0) ]

		self.image = Image.new(format, [1, 1])
		self.full_rect : Rect = Rect(0, 0, 1, 1)


	def crop(self, size):
		self.full_rect.size = size
		self.image = ImageOps.pad(self.image, size, centering=(0,0))
		print(f"Cropped image to {self.image.size}")

	
	def add(self, source: SourceImage):
		size = source.get_size()
		rect = Rect(self.get_snap_for(size), size)

		if not self.full_rect.contains(rect):
			self.crop(self.full_rect.union(rect).size)

		self.image.paste(source.image, [rect.x, rect.y])
		# self.image.pa
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



	def get_snap_for(self, size) -> tuple[int, int]:
		candidates = []
		for snap in self.snaps:
			query = Rect(snap, size)
			intersects = False
			for source in self.sources:
				# print(source.target_region)
				# print(query)
				# print(source.target_region.colliderect(query))
				if source.target_region.colliderect(query):
					intersects = True
					break
			if not intersects:
				candidates.append(query)

		if len(candidates) == 0: return self.snaps[0]
		candidates.sort(key=lambda a: not self.full_rect.contains(a))
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


def crop(image, offset):
	pass
	

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
	parser.add_argument("--island-opacity", "-io", type=float, required=False, default=0.1, help="Pixels with an opacity above this threshold will be considered part of a contiguous island.")
	args = parser.parse_args()

	sources = aggregate_image_sources(args.source_folder, args.regex_restrict)
	
	print(f"Found {len(sources)} images to compile.")

	if args.island_crop != IslandMode.NO_CROP:
		new_sources = []
		for source in sources: 
			new_sources.append(source.crop_to_new(args.island_crop))
		sources = new_sources

	target = TargetImage(args.target_folder, args.target_path, args.target_format)

	# i = 0
	# limit = 8
	for source in sources:
		# i += 1
		# if i > limit: break
		
		target.add(source)
		


	print(f"Final image size: {target.image.size}")

	target.save()


if __name__ == "__main__":
	main()