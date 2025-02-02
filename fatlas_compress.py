import os
import sys
import subprocess


def compress_folder(input_folder, output_path):
	for file_name in os.listdir(input_folder):
		if os.path.isdir(os.path.join(input_folder, file_name)):
			compress_folder(os.path.join(input_folder, file_name), os.path.join(output_path, file_name))
		elif file_name.lower().endswith(".png"):
			input_file = os.path.join(input_folder, file_name)
			compress_png_lossless(input_file, output_path)


def compress_png_lossless(input_path, output_path):
	try:
		if not os.path.exists(output_path):
			os.makedirs(output_path)

		output_file = os.path.join(output_path, os.path.basename(input_path))
		subprocess.run(["optipng.exe", "-o7", "-out", output_file, input_path], check=True)
		print(f"Compressed: {input_path} -> {output_file}")
	except Exception as e:
		print(f"Error compressing {input_path}: {e}")

if __name__ == "__main__":
	if len(sys.argv) < 2:
		print("Usage: python compress_png.py <input_folder> <output_folder>")
		sys.exit(1)

	input_folder = sys.argv[1]

	if os.path.exists(input_folder):
		output_folder = input_folder if len(sys.argv) == 2 else sys.argv[2]

		if not os.path.exists(output_folder):
			os.makedirs(output_folder)

		compress_folder(input_folder, output_folder)

		print("Lossless compression completed.")
