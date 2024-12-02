import glob
import os
import sys
from ultralytics import YOLO

def process_images(model_path, data_path, output_path):
    # Load model
    model = YOLO(model_path)

    # Check if data_path exists
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"Error: Folder '{data_path}' does not exist.")

    # Create output_path if it doesn't exist
    if not os.path.exists(output_path):
        os.makedirs(output_path)

    # Supported image extensions
    image_extensions = ["*.jpg", "*.png", "*.jpeg", "*.gif", "*.bmp", "*.tiff", "*.webp"]

    # Collect all images
    images = []
    for ext in image_extensions:
        images.extend(glob.glob(os.path.join(data_path, ext)))

    images = sorted(images)
    image_count = len(images)

    # Define object classes
    object_classes = ['pistol', 'bill', 'knife', 'card']

    # Initialize result content
    result_file_contents = ""

    for i, image_path in enumerate(images, start=1):
        results = model(image_path)
        detected_classes = set()

        for result in results:
            for box in result.boxes:
                cls = int(box.cls[0])
                conf = box.conf[0]
                if cls < len(object_classes) and conf >= 0.5:
                    detected_classes.add(object_classes[cls])

        # Extract image name
        _, image_name = os.path.split(image_path)
        tags = ", ".join(detected_classes) if detected_classes else "No objects detected"
        result_file_contents += f"{image_name}, Tags: {tags} \n"

    # Save results to a file
    with open(os.path.join(output_path, 'report.txt'), 'w') as output_file:
        output_file.write(result_file_contents)

if __name__ == "__main__":
    
    model_path = sys.argv[1]
    data_path = sys.argv[2] 
    output_path = sys.argv[3] 

    try:
        process_images(model_path, data_path, output_path)
        print(f"Processing completed. Results saved in '{output_path}'.")
    except Exception as e:
        print(f"Error: {e}")