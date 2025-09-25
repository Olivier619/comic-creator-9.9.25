document.addEventListener('DOMContentLoaded', () => {
    console.log("Le DOM est chargé. Le script main.js est en cours d'exécution.");

    // Variable globale pour le fallback de drag-drop
    let draggedSrc = null;

    // --- Initialisation de l'éditeur ---
    function initializeEditor() {
        const editorArea = document.getElementById('editor-area');
        const templateImage = editorArea.querySelector('img[alt="Planche de BD"]');

        if (!templateImage || !window.panelCoordinates || window.panelCoordinates.length === 0) {
            return;
        }

        const setupDropZones = () => {
            const scale = templateImage.clientWidth / templateImage.naturalWidth;

            editorArea.querySelectorAll('.panel-drop-zone').forEach(zone => zone.remove());

            window.panelCoordinates.forEach(coords => {
                const zone = document.createElement('div');
                zone.className = 'panel-drop-zone';
                zone.style.left = `${coords.x * scale}px`;
                zone.style.top = `${coords.y * scale}px`;
                zone.style.width = `${coords.width * scale}px`;
                zone.style.height = `${coords.height * scale}px`;
                zone.dataset.originalX = coords.x;
                zone.dataset.originalY = coords.y;
                zone.dataset.originalW = coords.width;
                zone.dataset.originalH = coords.height;

                zone.addEventListener('dragover', handleDragOver);
                zone.addEventListener('drop', handleDrop);

                editorArea.appendChild(zone);
            });

            attachSaveHandler();
        };

        if (templateImage.complete) {
            setupDropZones();
        } else {
            templateImage.onload = setupDropZones;
        }

        window.addEventListener('resize', setupDropZones);
    }

    // --- Logique de Drag and Drop ---
    function handleDragStart(e) {
        e.dataTransfer.setData('text/plain', e.target.src);
        draggedSrc = e.target.src;
    }

    function handleDragOver(e) {
        e.preventDefault();
    }

    function handleDrop(e) {
        e.preventDefault();
        let imgSrc = e.dataTransfer.getData('text/plain') || draggedSrc;
        if (!imgSrc) return;

        const dropZone = e.currentTarget;
        dropZone.innerHTML = '';

        const newImg = document.createElement('img');
        newImg.src = imgSrc;

        // Positionnement initial simple
        newImg.style.width = '100%';
        newImg.style.height = 'auto';
        newImg.style.left = '0px';
        newImg.style.top = '0px';
        newImg.style.position = 'absolute';

        newImg.onload = () => {
            const imgHeight = newImg.clientHeight;
            const zoneHeight = dropZone.clientHeight;
            // Centrage vertical initial si l'image est plus petite que la zone
            if (imgHeight < zoneHeight) {
                newImg.style.top = `${(zoneHeight - imgHeight) / 2}px`;
            }
        };

        dropZone.appendChild(newImg);
        makeImageInteractive(newImg);
    }

    // --- Fonction pour contraindre l'image dans les limites (CORRIGÉE) ---
    function constrainImageToBounds(img) {
        const dropZone = img.parentElement;

        // Récupérer les dimensions réelles de la zone (qui inclut déjà le padding CSS)
        const zoneWidth = dropZone.clientWidth;
        const zoneHeight = dropZone.clientHeight;

        // Position et taille actuelles de l'image
        let left = parseFloat(img.style.left) || 0;
        let top = parseFloat(img.style.top) || 0;
        const imgWidth = img.clientWidth;
        const imgHeight = img.clientHeight;

        // Contraintes simples : l'image doit rester dans la zone
        // Mais on laisse un petit padding pour que les bordures restent visibles
        const minLeft = -imgWidth + 20; // peut sortir à gauche mais garde 20px visible
        const maxLeft = zoneWidth - 20;  // peut sortir à droite mais garde 20px visible
        const minTop = -imgHeight + 20;  // peut sortir en haut mais garde 20px visible
        const maxTop = zoneHeight - 20;  // peut sortir en bas mais garde 20px visible

        // Appliquer les contraintes
        left = Math.max(minLeft, Math.min(maxLeft, left));
        top = Math.max(minTop, Math.min(maxTop, top));

        img.style.left = `${left}px`;
        img.style.top = `${top}px`;
    }

    // --- Logique d'interactivité de l'image (Pan & Zoom) ---
    function makeImageInteractive(img) {
        let isPanning = false;
        let startX, startY, startLeft, startTop;

        const startPan = (e) => {
            e.preventDefault();
            isPanning = true;
            startX = e.clientX;
            startY = e.clientY;
            startLeft = img.offsetLeft;
            startTop = img.offsetTop;
            img.style.cursor = 'grabbing';
            document.addEventListener('mousemove', doPan);
            document.addEventListener('mouseup', stopPan);
        };

        const doPan = (e) => {
            if (!isPanning) return;
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
            img.style.left = `${startLeft + dx}px`;
            img.style.top = `${startTop + dy}px`;

            // Contraindre pendant le déplacement
            constrainImageToBounds(img);
        };

        const stopPan = () => {
            isPanning = false;
            img.style.cursor = 'move';
            document.removeEventListener('mousemove', doPan);
            document.removeEventListener('mouseup', stopPan);
        };

        const handleZoom = (e) => {
            e.preventDefault();
            const scaleFactor = 1.1;
            const rect = img.getBoundingClientRect();
            const currentWidth = img.clientWidth;
            const newWidth = e.deltaY < 0 ? currentWidth * scaleFactor : currentWidth / scaleFactor;

            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;

            const newLeft = img.offsetLeft + (mouseX - mouseX * (newWidth / currentWidth));
            const newTop = img.offsetTop + (mouseY - mouseY * (newWidth / currentWidth));

            img.style.width = `${newWidth}px`;
            img.style.height = 'auto';
            img.style.left = `${newLeft}px`;
            img.style.top = `${newTop}px`;

            // Contraindre après le zoom
            constrainImageToBounds(img);
        };

        img.addEventListener('mousedown', startPan);
        img.addEventListener('wheel', handleZoom);
    }

    // --- Logique de Sauvegarde ---
    function attachSaveHandler() {
        const saveButton = document.getElementById('save-button');
        const dropZones = document.querySelectorAll('.panel-drop-zone');

        if (saveButton) {
            saveButton.onclick = () => handleSave(dropZones);
        }
    }

    async function handleSave(dropZones) {
        const imagesData = [];
        const templateImage = document.querySelector('#editor-area img[alt="Planche de BD"]');

        if (!templateImage || !templateImage.naturalWidth) {
            alert("Erreur : Impossible de trouver l'image de la planche ou ses dimensions originales.");
            return;
        }

        const scale = templateImage.clientWidth / templateImage.naturalWidth;

        dropZones.forEach(zone => {
            const img = zone.querySelector('img');

            if (img) {
                const url = new URL(img.src);

                // Convertir les coordonnées de l'écran en coordonnées de l'image originale
                // Le padding CSS de 2px est automatiquement pris en compte par les coordonnées de la zone
                const final_img_left = (parseFloat(img.style.left) || 0) / scale;
                const final_img_top = (parseFloat(img.style.top) || 0) / scale;
                const final_img_w = img.clientWidth / scale;

                imagesData.push({
                    src: url.pathname.split('/').pop(),
                    panel_x: parseInt(zone.dataset.originalX, 10),
                    panel_y: parseInt(zone.dataset.originalY, 10),
                    panel_w: parseInt(zone.dataset.originalW, 10),
                    panel_h: parseInt(zone.dataset.originalH, 10),
                    img_left: final_img_left,
                    img_top: final_img_top,
                    img_w: final_img_w,
                });
            }
        });

        const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ images: imagesData })
        });

        if (response.ok) {
            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = downloadUrl;
            a.download = 'ma_planche_de_bd.png';
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            a.remove();
        } else {
            alert('Une erreur est survenue lors de la génération de l\'image.');
        }
    }

    // --- Point d'entrée du script ---
    initializeEditor();

    document.querySelectorAll('#panel-thumbnails img').forEach(thumb => {
        thumb.setAttribute('draggable', 'true');
        thumb.addEventListener('dragstart', handleDragStart);
    });
});