import os
import re
import sys
import argparse
import json
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


	@property
	def json_path(self) -> str:
		return f"{self.root}\\{self.name}.json"


class SourceImage(PathedImage):
	def __init__(self, root : str, file : str, region : Rect = None, bitmap : Image = None):
		super().__init__(root, file)
		self.image : Image = Image.open(self.full).convert("RGBA")
		self.bitmap : Image = bitmap

		if region == None:
			region = Rect(0, 0, self.image.width, self.image.height)

		self.source_region = region
		self.target_offset = (0, 0)
		self.target_match = None

	@property
	def image_cropped(self) -> Image:
		if self.bitmap == None: return self.image

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
	def json_data(self) -> dict:
		return {
			"name": self.name,
			"source_offset": {
				"x": self.source_region.left,
				"y": self.source_region.top,
			},
			"target_region": {
				"x": int(self.target_offset[0]),
				"y": int(self.target_offset[1]),
				"w": self.source_region.width,
				"h": self.source_region.height,
			},
		}


	@property
	def target_region(self) -> Rect:
		return Rect(self.target_offset, self.source_region.size)
	

	def add_to_target(self):
		print(f"Added {self.name} to '{self.target}'")
		self.target.add(self)

	
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
	def __init__(self, root, file, format, margin):
		super().__init__(root, file)

		self.sources = []
		self.margin = (margin, margin)
		self.snaps = [ self.margin ]

		self.image : Image = Image.new(format, [1, 1])
		self.full_rect : Rect = Rect(0, 0, 1, 1)


	def expand(self, size):
		new_size = (size[0] + self.margin[0], size[1] + self.margin[1])
		delta = (0, 0, new_size[0] - self.full_rect.size[0], new_size[1] - self.full_rect.size[1])
		self.full_rect.size = new_size
		self.image = ImageOps.expand(self.image, delta)

	
	def add(self, source: SourceImage):
		size = source.source_region.size
		snap = self.get_snap_for(size)
		rect = Rect(snap[0], snap[1], size[0], size[1])

		if not self.full_rect.contains(rect):
			self.expand(self.full_rect.union(rect).size)

		self.image.paste(source.image_cropped, (rect.x, rect.y))
		source.target_offset = (rect.x, rect.y)

		self.sources.append(source)

		try:
			self.snaps.remove(source.target_offset)
		except ValueError: pass
		snap1 = (source.target_offset[0] + source.source_region.width + self.margin[0], source.target_offset[1])
		try:
			_ = self.snaps.index(snap1)
		except ValueError:
			self.snaps.append(snap1)
		snap2 = (source.target_offset[0], source.target_offset[1] + source.source_region.height + self.margin[1])
		try:
			_ = self.snaps.index(snap2)
		except ValueError:
			self.snaps.append(snap2)


	def get_snap_for(self, size: tuple[int, int]) -> tuple[int, int]:
		candidates = []
		for snap in self.snaps:
			query = Rect(snap[0], snap[1], size[0], size[1])
			intersects = False
			for source in self.sources:
				if source.target_region.colliderect(query):
					intersects = True
					break
			if not intersects:
				candidates.append(query)

		if len(candidates) == 0: return self.snaps[0]
		candidates.sort(key=lambda rect: not self.full_rect.contains(rect))
		return (candidates[0][0], candidates[0][1])

	
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


def assign_image_sources(args):
	result = []
	pattern = re.compile(args.regex_restrict)
	for root, dirs, files, in os.walk(args.source_folder):
		for file in files:			
			if re.search(pattern, file) == None: continue
			source = SourceImage(root, file)
			result.append(source)
	return result


def assign_image_targets(sources, args):
	result = []
	pattern = re.compile(args.regex_separate)
	targets_dict = dict()
	for source in sources:
		match_string = re.search(pattern, source.name).group()
		if targets_dict.get(match_string) == None:
			name, ext = os.path.splitext(args.target_path)
			path = f"{name}{match_string}{ext}"
			targets_dict[match_string] = TargetImage(args.target_folder, path, args.target_format, args.island_margin)
		source.target_match = match_string
	return (sources, targets_dict)


def assign_comp_data(maps : dict) -> dict:
	result = dict()
	available = list()
	components = set()
	pattern = re.compile(r"((.+?)(?:_(\d+))?)_([lr])_(.)")
	for k in maps.keys():
		for entry in maps[k]:
			available.append(entry["name"])
			match = re.search(pattern, entry["name"])
			
			if not match:
				print("One or more matches were not found in the regex; double check your pattern!")
				return dict()

			components.add(match.group(5))
			if result.get(match.group(1)) == None:
				is_latter_index = match.group(3) != None and int(match.group(3)) != 0

				if is_latter_index: result[match.group(1)] = f"{match.group(2)}_{"0".zfill(len(match.group(3)))}"
				else: result[match.group(1)] = None
				
	for k in result.keys():
		comp = dict()
		index_base_entry = result[k]

		for c in components:
			r_suffix = f"_r_{c}"
			r_name = k + r_suffix
			l_suffix = f"_l_{c}"
			l_name = k + l_suffix
			
			i = 0
			for m in maps.keys():
				if i == 2: break
				for entry in maps[m]:
					if i == 2: break
					if entry["name"] == r_name:
						comp[r_suffix] = r_name
						i += 1
					elif entry["name"] == l_name:
						comp[l_suffix] = l_name
						i += 1

			if index_base_entry != None and comp.get(r_suffix) == None and result[index_base_entry].get(r_suffix) != None:
				comp[r_suffix] = result[index_base_entry][r_suffix]

			if comp.get(l_suffix) == None and comp.get(r_suffix) != None:
				comp[l_suffix] = comp[r_suffix]

						
		result[k] = comp
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
	parser.add_argument("--regex-separate", "-s", type=str, required=False, default=r"^", help="File names (not including extension) that match this regex will be separated into different images.")
	parser.add_argument("--island-mode", "-ic", type=island_mode, required=False, default=IslandMode.CROP_FULL, help=f"Defines how/if to separate pixel islands. Options: {[e.value for e in IslandMode]}")
	parser.add_argument("--island-margin", "-im", type=int, required=False, default=1, help="Islands above this threshold will have their regions expanded by this margin to include any surrounding pixels.")
	parser.add_argument("--island-opacity", "-io", type=int, required=False, default=1, help="Pixels with an opacity above this threshold will be considered part of a contiguous island.")
	parser.add_argument("--island-size", "-is", type=int, required=False, default=1, help="Islands with an area smaller than this will be discarded.")
	parser.add_argument("--test-limit", "-l", type=int, required=False, default=-1, help="If set, the program will only process this many images. Helpful for testing.")
	args = parser.parse_args()

	sources = assign_image_sources(args)
	sources, targets = assign_image_targets(sources, args)

	target = TargetImage(args.target_folder, args.target_path, args.target_format, args.island_margin)
	maps_data = dict()

	print(f"Found {len(sources)} images to compile.")

	print(f"Cropping images...")
	i = 0
	for source in sources: 
		i += 1
		if args.test_limit > -1 and i > args.test_limit: break
		print(f"Cropping image '{source.name}' ({i}/{len(sources)}) ...")
		subsources = []
		subsources.append(source.crop_islands(args))
		j = 0
		for subsource in subsources:
			j += 1
			target_file = targets[source.target_match].file
			print(f"Appending image '{source.name}' to '{target_file}' ({j}/{len(subsources)}) ...")
			targets[source.target_match].add(subsource)

			if maps_data.get(target_file) == None:
				maps_data[target_file] = []
			maps_data[target_file].append(subsource.json_data)
	print(f"Conglomeration complete.")

	comp_data = assign_comp_data(maps_data)

	json_data = {"maps": maps_data, "composites": comp_data}

	with open(target.json_path, "w") as file:
		json.dump(json_data, file)

	for k in targets.keys():
		target = targets[k]
		target.save()


if __name__ == "__main__":
	main()