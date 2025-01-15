import os
import re
import sys
import argparse
import numpy as np
from PIL import Image, ImageOps


def main():
	print("\n\n")

	parser = argparse.ArgumentParser(description="Something")
	parser.add_argument("source_folder", type=str, help="All .png files in this folder will have normal created.")
	parser.add_argument("target_folder", type=str, help="Destination for normal images.")
	parser.add_argument("")

	pass

if __name__ == "__main__":
	main()