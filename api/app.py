import os
import io
import cv2
import numpy as np
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, session, jsonify, send_file
from werkzeug.utils import secure_filename
from PIL import Image

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max upload size
app.secret_key = 'super-secret-key'  # Necessary for session management

# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def detect_panels(image_path):
    """
    Detects rectangular panels in an image using OpenCV.
    Returns a list of dictionaries, each containing the x, y, width, and height of a panel.
    """
    try:
        img = cv2.imread(image_path)
        if img is None:
            print(f"Error: Image not loaded from {image_path}")
            return []

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # Invert the image so the black borders become white objects
        thresh = cv2.threshold(gray, 240, 255, cv2.THRESH_BINARY_INV)[1]

        # Find contours
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        panels = []
        img_height, img_width, _ = img.shape
        min_area = (img_width * img_height) * 0.005 # Panels must be at least 0.5% of the image area

        for contour in contours:
            area = cv2.contourArea(contour)
            if area > min_area:
                peri = cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
                
                # Assume panels are rectangular (4 vertices)
                if len(approx) == 4:
                    x, y, w, h = cv2.boundingRect(approx)
                    panels.append({'x': x, 'y': y, 'width': w, 'height': h})
        
        # Sort panels from top-to-bottom, then left-to-right
        panels.sort(key=lambda p: (p['y'], p['x']))
        
        return panels
    except Exception as e:
        print(f"An error occurred during panel detection: {e}")
        return []

@app.route('/')
def index():
    template_image = session.get('template_image', None)
    panel_images = session.get('panel_images', None)
    panel_coordinates = session.get('panel_coordinates', None)
    return render_template('index.html', 
                           template_image=template_image, 
                           panel_images=panel_images, 
                           panel_coordinates=panel_coordinates)

@app.route('/upload_template', methods=['POST'])
def upload_template():
    if 'template_file' not in request.files:
        return redirect(request.url)
    file = request.files['template_file']
    if file.filename == '':
        return redirect(request.url)
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        session['template_image'] = filename
        
        # Detect panels and store coordinates in session
        panel_coords = detect_panels(file_path)
        session['panel_coordinates'] = panel_coords
        
        # Clear old panel images when a new template is uploaded
        session.pop('panel_images', None)
    return redirect(url_for('index'))

@app.route('/upload_panels', methods=['POST'])
def upload_panels():
    files = request.files.getlist('panel_files[]')
    panel_filenames = session.get('panel_images', [])
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            if filename not in panel_filenames:
                panel_filenames.append(filename)
    
    session['panel_images'] = panel_filenames
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/generate', methods=['POST'])
def generate_image():
    data = request.json
    template_image_name = session.get('template_image')

    if not template_image_name:
        return jsonify({'error': 'No template image found'}), 400

    base_path = os.path.join(app.config['UPLOAD_FOLDER'], template_image_name)
    base_image = Image.open(base_path).convert('RGBA')
    # Créer une copie pour ne pas modifier l'original en mémoire
    final_image = base_image.copy()

    for img_data in data.get('images', []):
        print(f"DEBUG: Received image data: {img_data}")
        # Créer une toile vierge pour la case
        panel_canvas = Image.new('RGBA', (img_data['panel_w'], img_data['panel_h']), (0, 0, 0, 0))
        
        # Ouvrir l'image source
        panel_path = os.path.join(app.config['UPLOAD_FOLDER'], img_data['src'])
        source_img = Image.open(panel_path).convert('RGBA')
        
        # Redimensionner l'image source en fonction du zoom
        # On calcule la nouvelle hauteur en conservant le ratio
        original_w, original_h = source_img.size
        new_w = img_data['img_w']
        new_h = int(original_h * (new_w / original_w))
        resized_img = source_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Coller l'image zoomée/pannér sur la toile de la case
        paste_position = (int(img_data['img_left']), int(img_data['img_top']))
        panel_canvas.paste(resized_img, paste_position)
        
        # Coller la case complétée sur l'image finale
        final_image.paste(panel_canvas, (img_data['panel_x'], img_data['panel_y']), panel_canvas)

    # Save to a bytes buffer
    img_io = io.BytesIO()
    final_image.save(img_io, 'PNG')
    img_io.seek(0)

    return send_file(img_io, mimetype='image/png', as_attachment=True, download_name='ma_planche_de_bd.png')

if __name__ == '__main__':
    app.run(debug=True, port=5004) # Using a different port to avoid conflicts
