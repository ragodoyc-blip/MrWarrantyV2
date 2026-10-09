"""
Prueba del ruteo por contenido: keywords solo PLM/datapacks, videos a fotos,
resto legible a IA. Conversores archivo_a_imagenes.
Ejecucion: python tests/test_clasificacion_contenido.py
"""

import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mr_warranty.adapters.salesforce_client import clasificar_adjuntos
from mr_warranty.infrastructure.blob import archivo_a_imagenes


def check(nombre: str, cond: bool, detalle: str = ""):
    estado = "OK" if cond else "FAIL"
    print(f"[{estado}] {nombre} {detalle}")
    if not cond:
        raise AssertionError(f"Fallo: {nombre} {detalle}")


def adj(title: str, file_type: str) -> dict:
    return {"id": title, "title": title, "file_type": file_type}


def test_ruteo_reglas():
    adjuntos = [
        adj("DATA PLM IV", "ZIP"),
        adj("DSC_001", "PDF"),
        adj("HT364", "MP4"),
        adj("A26000281925_INVHT", "PDF"),
        adj("PTBU", "JPG"),
        adj("TR-falla pelicano", "PDF"),
    ]
    c = clasificar_adjuntos(adjuntos)
    check("plm por nombre", c["plm"] == ["DATA PLM IV"], str(c["plm"]))
    check("datapacks por nombre", set(c["datapacks"]) == {"DATA PLM IV", "DSC_001"}, str(c["datapacks"]))
    check("video a fotos", c["fotografias"] == ["HT364"], str(c["fotografias"]))
    check("invoice sin keywords", c["purchase_invoice"] == [], str(c["purchase_invoice"]))
    check("reporte sin keywords", c["reporte_tecnico"] == [], str(c["reporte_tecnico"]))
    check("imagen a IA (no fotos)", "PTBU" not in c["fotografias"], str(c["fotografias"]))
    check("pdf generico a IA", "A26000281925_INVHT" not in c["fotografias"], str(c))


def test_conversores():
    with tempfile.TemporaryDirectory() as tmp:
        # PNG pasa directo
        png = os.path.join(tmp, "foto.png")
        from PIL import Image
        Image.new("RGB", (50, 50), "red").save(png, "PNG")
        check("png passthrough", archivo_a_imagenes(png, tmp) == [png])

        # ZIP no convertible
        zf = os.path.join(tmp, "data.zip")
        open(zf, "wb").write(b"PK\x03\x04")
        check("zip vacio", archivo_a_imagenes(zf, tmp) == [])

        # CSV -> PNG
        csv = os.path.join(tmp, "datos.csv")
        open(csv, "w").write("a,b\n1,2\n")
        out_csv = archivo_a_imagenes(csv, tmp)
        check("csv a png", len(out_csv) == 1 and out_csv[0].endswith(".png"), str(out_csv))

        # TXT -> PNG
        txt = os.path.join(tmp, "nota.txt")
        open(txt, "w").write("hola mundo\n")
        check("txt a png", len(archivo_a_imagenes(txt, tmp)) == 1)

        # DOCX -> PNG
        from docx import Document
        docx = os.path.join(tmp, "informe.docx")
        doc = Document()
        doc.add_paragraph("Contenido de prueba")
        doc.save(docx)
        check("docx a png", len(archivo_a_imagenes(docx, tmp)) == 1)

        # BMP -> PNG
        bmp = os.path.join(tmp, "img.bmp")
        Image.new("RGB", (20, 20), "blue").save(bmp, "BMP")
        out_bmp = archivo_a_imagenes(bmp, tmp)
        check("bmp a png", len(out_bmp) == 1 and out_bmp[0].endswith(".png"), str(out_bmp))


if __name__ == "__main__":
    test_ruteo_reglas()
    test_conversores()
    print("\nTodas las pruebas clasificacion contenido pasaron.")
