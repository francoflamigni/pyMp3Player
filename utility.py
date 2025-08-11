from PIL import Image, ImageQt
import io
import sys
from pathlib import Path

def qpixmap_to_bytes(pixmap):
    """Converte un QPixmap in dati binari."""
    # Converte QPixmap in PIL Image
    qimage = pixmap.toImage()
    pil_image = ImageQt.fromqimage(qimage)

    # Salva in un buffer
    buffer = io.BytesIO()
    pil_image.save(buffer, format='PNG')
    return buffer.getvalue()

def resize_image_data(image_data, target_size=(400, 400), quality=85):
    """
    Ridimensiona i dati dell'immagine mantenendo le proporzioni.

    Args:
        image_data: Dati binari dell'immagine
        target_size: Tuple (width, height) della dimensione target
        quality: Qualità JPEG (1-100)

    Returns:
        bytes: Dati dell'immagine ridimensionata in formato JPEG
    """
    try:
        # Carica l'immagine dai dati binari
        image = Image.open(io.BytesIO(image_data))

        # Converte in RGB se necessario (per PNG con trasparenza, etc.)
        if image.mode in ('RGBA', 'LA', 'P'):
            # Crea uno sfondo bianco per le immagini con trasparenza
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('RGBA')
            background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
            image = background
        elif image.mode != 'RGB':
            image = image.convert('RGB')

        # Calcola le nuove dimensioni mantenendo le proporzioni
        original_width, original_height = image.size
        target_width, target_height = target_size

        # Calcola il rapporto per mantenere le proporzioni
        ratio = min(target_width / original_width, target_height / original_height)

        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)

        # Ridimensiona l'immagine con un filtro di alta qualità
        resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

        # Salva in un buffer come JPEG
        output_buffer = io.BytesIO()
        resized_image.save(output_buffer, format='JPEG', quality=quality, optimize=True)

        return output_buffer.getvalue()

    except Exception as e:
        raise Exception(f"Errore nel ridimensionamento dell'immagine: {e}")

def get_resource_path_pathlib(relative_path):
    """
    Versione con pathlib per percorsi più robusti
    """
    try:
        base_path = Path(sys._MEIPASS)
    except AttributeError:
        base_path = Path(__file__).parent

    return base_path / relative_path