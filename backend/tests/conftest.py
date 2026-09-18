import pytest

from app.servicios.render_pdf import _preparar_gtk_en_windows


def requerir_weasyprint():
    """WeasyPrint falla con OSError (no ImportError) cuando faltan Pango/Cairo; se omite la prueba."""
    _preparar_gtk_en_windows()
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError) as error:
        pytest.skip(f"WeasyPrint no disponible en este entorno: {str(error)[:80]}")
    return weasyprint
