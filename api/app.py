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

# Création de l'app Flask
app = Flask(
    __name__,
    static_folder='../static',
    template_folder='../templates'
)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB

# S’assure que le dossier uploads existe
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def detect_panels(image_path):
    """Détecte les cases rectangulaires sur la planche."""
    try:
        img = cv2.imread(image_path)
        if img is None:
            return []
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150, apertureSize=3)
        kernel = np.ones((3,3), np.uint8)
        edges = cv2.dilate(edges, kernel, iterations=1)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        panels = []
        for cnt in contours:
            epsilon = 0.02 * cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, epsilon, True)
            area = cv2.contourArea(cnt)
            if len(approx) == 4 and area > 1000:
                x, y, w, h = cv2.boundingRect(approx)
                ratio = w / h if h else 0
                if 0.2 < ratio < 5.0:
                    panels.append({'x': x, 'y': y, 'width': w, 'height': h})
        panels.sort(key=lambda p: (p['y'], p['x']))
        return panels
    except Exception:
        return []

@app.route('/', methods=['GET'])
def index():
    """Affiche la page principale."""
    return render_template('index.html',
                           template_image=session.get('template_image'),
                           panel_images=session.get('panel_images', []),
                           panel_coordinates=session.get('panel_coordinates', []))

@app.route('/upload_template', methods=['POST'])
def upload_template():
    """Reçoit la planche, détecte les cases et stocke en session."""
    file = request.files.get('template_file')
    if not file or file.filename == '' or not allowed_file(file.filename):
        return redirect(url_for('index'))
    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

    panels = detect_panels(filepath)
    session['template_image'] = filename
    session['panel_coordinates'] = panels
    return redirect(url_for('index'))

@app.route('/upload_panels', methods=['POST'])
def upload_panels():
    """Reçoit les images à placer dans les cases."""
    files = request.files.getlist('panel_files[]')
    panel_images = session.get('panel_images', [])
    for file in files:
        if file and allowed_file(file.filename):
            fn = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], fn)
            file.save(path)
            panel_images.append(fn)
    session['panel_images'] = panel_images
    return redirect(url_for('index'))

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Service pour renvoyer les fichiers uploadés."""
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/generate', methods=['POST'])
def generate_comic():
    """Génère la planche finale avec les images collées."""
    data = request.get_json() or {}
    images_data = data.get('images', [])
    template_image = session.get('template_image')
    if not template_image:
        return jsonify({'error': 'Aucune planche template'}), 400

    template_path = os.path.join(app.config['UPLOAD_FOLDER'], template_image)
    template = Image.open(template_path).convert('RGB')
    result = template.copy()

    for img_data in images_data:
        try:
            img_path = os.path.join(app.config['UPLOAD_FOLDER'], img_data['src'])
            panel_img = Image.open(img_path).convert('RGB')
            w = int(img_data['img_w'])
            h = int(w * (panel_img.height / panel_img.width))
            panel_img = panel_img.resize((w, h), Image.Resampling.LANCZOS)
            x = int(img_data['panel_x'] + img_data['img_left'])
            y = int(img_data['panel_y'] + img_data['img_top'])
            result.paste(panel_img, (x, y))
        except Exception:
            continue

    buf = io.BytesIO()
    result.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png', as_attachment=True, download_name='planche.png')

# Point d’entrée pour Vercel : exporte l’app
handler = app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
