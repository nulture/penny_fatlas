import argparse
from PIL import Image as Pillow

def main():
    print("Main")
    
    parser = argparse.ArgumentParser(description="Something")
    parser.add_argument("source", help="Source help")
    parser.add_argument("target", help="Target help")

if __name__ == "__main__":
    main()