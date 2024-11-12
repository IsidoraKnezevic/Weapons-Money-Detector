import glob
import sys
import os
from ultralytics import YOLO

model = YOLO('./model/best.pt')

if len(sys.argv) > 1:
    DATA_PATH = sys.argv[1]
else:
    DATA_PATH = '.' + os.path.sep + 'images' + os.path.sep

if not os.path.exists(DATA_PATH):
    print(f"Error: Folder '{DATA_PATH}' does not exist.")
    sys.exit(1)


if len(sys.argv) > 2:
    OUTPUT_PATH = sys.argv[2]
else:
    OUTPUT_PATH = '.' + os.path.sep + 'output' + os.path.sep

if not os.path.exists(OUTPUT_PATH):
    os.makedirs(OUTPUT_PATH)

image_extensions = ["*.jpg", "*.png", "*.jpeg", "*.gif", "*.bmp", "*.tiff", "*.webp"]
images = []
for ext in image_extensions:
    images.extend(glob.glob(DATA_PATH + ext))

images = sorted(images)
image_count = len(images)

object_classes = ['pistol', 'bill', 'knife', 'card']

result_file_contents = f"Total number of images: {image_count} \n"


for i, image_path in enumerate(images, start=1):
    results = model(image_path)
    detected_classes = set()

    for result in results:
        for box in result.boxes:
            cls = int(box.cls[0])
            conf = box.conf[0]
            if cls < len(object_classes) and conf >= 0.5:
                detected_classes.add(object_classes[cls])

    image_directory, image_name = os.path.split(image_path)
    tags = ", ".join(detected_classes) if detected_classes else "No objects detected"
    result_file_contents += f"Image {i}: {image_name}, Tags: {tags} \n"



with open(os.path.join(OUTPUT_PATH, 'report.txt'), 'w') as output_file:
    output_file.write(result_file_contents)
