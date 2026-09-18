import pytest


def requerir_weasyprint():
    """WeasyPrint falla con OSError (no ImportError) cuando faltan Pango/Cairo; se omite la prueba."""
    try:
        import weasyprint  # noqa: F401
    except (ImportError, OSError) as error:
        pytest.skip(f"WeasyPrint no disponible en este entorno: {str(error)[:80]}")
    return weasyprint
