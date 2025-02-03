import os
import re
import sys
import argparse
import numpy as np
from PIL import Image, ImageFilter
from scipy.ndimage import sobel, prewitt
from scipy.ndimage import distance_transform_edt, gaussian_filter

class TargetImage:
	def __init__(self, root, file, src_path):
		self.root = root
		self.file = file
		self.full = os.path.join(root, file)
		self.name, self.ext = os.path.splitext(file)

		self.source : Image = Image.open(src_path)


	def __str__(self):
		return self.file


	def generate(self, args):
		if args.smoothness > 1:
			smoothsource = self.source.filter(ImageFilter.GaussianBlur(args.smoothness))
		else:
			smoothsource = self.source

		gray = np.array(smoothsource.convert("L"), dtype=np.float32)


		# binary_mask = np.array(self.source.getchannel("A"), dtype=np.float32) > 0
		binary_mask = gray > 0
		distance_map = distance_transform_edt(binary_mask)
		distance_map = np.clip(distance_map / args.heightmap_distance, 0, 1)

		height_map = (1.0 - np.exp(-distance_map)) * args.heightmap_height
		height_map = gaussian_filter(height_map, sigma=args.heightmap_softness)
		height_map += gray.copy()

		# Image.fromarray(height_map).show()
		# preview = Image.fromarray(height_map).convert("RGBA")
		# preview = preview.filter(ImageFilter.GaussianBlur(args.heightmap_softness))
		# preview.show()

		# height_map = np.array(preview.convert("L"), dtype=np.float32)

		if args.method == "sobel":
			gradient_x = sobel(gray, axis=1)
			gradient_y = sobel(gray, axis=0)
		elif args.method == "prewitt":
			gradient_x = prewitt(gray, axis=1)
			gradient_y = prewitt(gray, axis=0)
		else:
			gradient_x, gradient_y = np.gradient(gray)

		gradient_x *= args.intensity * -1 if args.flipx else 1
		gradient_y *= args.intensity * -1 if args.flipy else 1

		normal_x = -gradient_x
		normal_y = -gradient_y
		normal_z = np.ones_like(height_map) * 255.0

		magnitude = np.sqrt(normal_x**2 + normal_y**2 + normal_z**2)
		normal_x = (normal_x / magnitude) * 127.5 + 127.5
		normal_y = (normal_y / magnitude) * 127.5 + 127.5
		normal_z = (normal_z / magnitude) * 127.5 + 127.5

		normal_map = np.stack((normal_x, normal_y, normal_z), axis=-1).astype(np.uint8)

		self.image = Image.fromarray(normal_map, mode="RGB")
		self.image = self.image.convert("RGBA")
		self.image.putalpha(self.source.getchannel("A"))

		self.image.show()



	def save(self):
		os.makedirs(os.path.dirname(self.full), exist_ok=True)
		print(f"Saving image to {self.full} ...")
		self.image.save(self.full)
		print(f"Saved image!")


def assign_image_sources(args):
	result = []
	pattern = re.compile(args.regex_restrict)
	for _, _, files in os.walk(args.source_folder):
		for file in files:
			if re.search(pattern, file) == None: continue
			result.append(file)
	return result


def assign_image_targets(sources, args):
	result = []
	for source in sources:
		name, ext = os.path.splitext(source)
		path = f"{name}{args.suffix}{ext}"
		result.append(TargetImage(args.target_folder, path, os.path.join(args.source_folder, source)))
	return result


def main():
	print("\n\n")

	parser = argparse.ArgumentParser(description="Something")
	parser.add_argument("source_folder", type=str, help="All files in this folder will have normal created.")
	parser.add_argument("target_folder", type=str, help="Destination for normal images.")
	parser.add_argument("--regex_restrict", type=str, required=False, default=r".*?\.(?:png)$", help="Only file paths that match this regex will be included (considers extensions).")
	parser.add_argument("--suffix", type=str, required=False, default="_n", help="Suffix to append to the end of the image file name.")
	parser.add_argument("--smoothness", type=int, required=False, default=1, help="Applies a smoothing filter to the target image at the start of the operation.")
	parser.add_argument("--intensity", type=float, required=False, default=1.0, help="Gradient scalar.")
	parser.add_argument("--method", type=str, required=False, default="sobel", help="Normal algorithm to use. Options include 'sobel', 'prewitt'.")
	parser.add_argument("--flipx", type=bool, required=False, default=False, help="Flip the x normals.")
	parser.add_argument("--flipy", type=bool, required=False, default=True, help="Flip the y normals.")
	parser.add_argument("--heightmap-height", "-hh", type=float, required=False, default=1.0, help="Strength of the elevation effect.")
	parser.add_argument("--heightmap-distance", "-hd", type=float, required=False, default=1.0, help="Distance of the heightmap from transparent pixels.")
	parser.add_argument("--heightmap-softness", "-hs", type=float, required=False, default=1.0, help="Smoothness of the heightmap.")



	args = parser.parse_args()

	source_paths = assign_image_sources(args)
	targets = assign_image_targets(source_paths, args)

	for target in targets:
		target.generate(args)
		target.save()
		break



if __name__ == "__main__":
	main()