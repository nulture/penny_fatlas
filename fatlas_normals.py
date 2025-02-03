import os
import re
import subprocess
import argparse
from PIL import Image

class TargetImage:
	def __init__(self, root, file, src_root, src_file):
		self.root = root
		self.file = file
		self.full = os.path.join(root, file)
		self.name, self.ext = os.path.splitext(file)

		self.src_root = src_root
		self.src_file = src_file
		self.src_full = os.path.join(src_root, src_file)


	def __str__(self):
		return self.file


	def generate(self, args):
		print(f"Generating normal map for {self.file} ...")

		os.makedirs(os.path.dirname(self.full), exist_ok=True)

		sub_args = [args.laigter_path, "--no-gui", "-d", self.src_full, "-n"]
		if args.laigter_preset:
			sub_args.append("-r")
			sub_args.append(args.laigter_preset)
		subprocess.run(args=sub_args, shell=True)

		result_path = os.path.join(self.src_root, f"{self.name}{self.ext}")
		image = Image.open(result_path)

		source : Image = Image.open(self.src_full).convert("RGBA")
		image.putalpha(source.getchannel("A"))
		image.save(self.full)
		os.remove(result_path)

		print(f"Saved image to {self.full}")


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
		path = f"{name}_n{ext}"
		result.append(TargetImage(args.target_folder, path, args.source_folder, source))
	return result


def main():
	print("\n\n")

	parser = argparse.ArgumentParser(description="Something")
	parser.add_argument("laigter_path", type=str, help="Path to Laigter.")
	parser.add_argument("source_folder", type=str, help="All files in this folder will have normal created.")
	parser.add_argument("target_folder", type=str, help="Destination for normal images.")
	parser.add_argument("--regex_restrict", type=str, required=False, default=r".+(?<!_n)\.png$", help="Only file paths that match this regex will be included (considers extensions).")
	parser.add_argument("--laigter-preset", "-r", type=str, required=False, default=None, help="Path to laigter preset file")

	args = parser.parse_args()

	source_paths = assign_image_sources(args)
	targets = assign_image_targets(source_paths, args)

	for target in targets:
		target.generate(args)


if __name__ == "__main__":
	main()