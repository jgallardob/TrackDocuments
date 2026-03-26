import io
import datetime
import fitz  # PyMuPDF

def apply_forensic_watermark(pdf_bytes: bytes, user_id: str) -> bytes:
    """
    Toma un PDF en memoria (bytes) e inyecta una capa de marca de agua forense.
    La marca de agua es un patrón estilo microtexto casi transparente que incluye
    el ID del usuario (user_id) y una marca de tiempo UTC.
    Retorna el PDF alterado en formato de bytes.
    """
    pdf_document = fitz.open("pdf", pdf_bytes)
    
    current_time_utc = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    watermark_text = f"USER_ID:{user_id} TIMESTAMP:{current_time_utc}    " * 5
    
    # Iteramos sobre cada página del documento original
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        rect = page.rect
        
        # Inyectamos el microtexto esteganográfico invisible 
        # Usamos técnica de Yellow Dots (amarillo puro) a 3% opacidad
        # Virtualmente invisible al ojo humano sobre blanco, pero revelable al alterar contraste.
        font_size = 12
        y_pos = 50
        while y_pos < rect.height:
            page.insert_text(
                fitz.Point(10, y_pos), 
                watermark_text * 10, # Repetimos para extender la línea a lo ancho
                fontsize=font_size,
                color=(1, 1, 0), # Amarillo puro
                fill_opacity=0.03 # 3% opacidad
            )
            y_pos += 45 # Espaciado 
            
        # Marca Forense Primaria Latente (Anticapturas / RRSS)
        # Ocultamos la firma gigante en gris ínfimo
        page.insert_text(
            fitz.Point(30, rect.height / 2),
            f"RESPONSABLE: {user_id}",
            fontsize=28,
            color=(0.5, 0.5, 0.5), # Gris
            fill_opacity=0.02 # 2% opacidad, indetectable a simple vista
        )
        
        # Segunda inyección de texto como pie de página seguro
        footer_text = f"CONFIDENTIAL | DOWLOADED BY: {user_id} | DATE: {current_time_utc}"
        page.insert_text(
            fitz.Point(30, rect.height - 30),
            footer_text,
            fontsize=10,
            color=(0.8, 0, 0), # Color oscuro (rojo) para contraste
            fill_opacity=0.5
        )

    # Convertimos los cambios a bytes puramente en memoria
    output_buffer = io.BytesIO()
    pdf_document.save(output_buffer)
    pdf_document.close()
    
    return output_buffer.getvalue()
