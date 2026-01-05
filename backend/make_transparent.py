
from PIL import Image
import sys

def remove_black_background(input_path, output_path, threshold=50):
    img = Image.open(input_path).convert("RGBA")
    datas = img.getdata()
    
    new_data = []
    for item in datas:
        # Check if pixel is black or very dark
        if item[0] < threshold and item[1] < threshold and item[2] < threshold:
            # Make it transparent
            new_data.append((0, 0, 0, 0))
        else:
            new_data.append(item)
            
    img.putdata(new_data)
    img.save(output_path, "PNG")
    print(f"Saved transparent image to {output_path}")

if __name__ == "__main__":
    input_file = r"C:\Users\USER\.gemini\antigravity\brain\2428b5a7-c0da-48dd-bd7f-7af29cd8b142\trading_maven_logo_solid_black_1766641587849.png"
    output_file = r"d:\desktop-app\frontend\src\assets\logo.png"
    # Also save to favicon
    favicon_file = r"d:\desktop-app\frontend\public\favicon.png"
    
    remove_black_background(input_file, output_file)
    remove_black_background(input_file, favicon_file)
