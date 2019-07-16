import weasyprint
import pdfkit
import logging

logger = logging.getLogger(__name__)


def download_url_wkhtmltopdf(url, out_file):
    pdfkit.from_url(url, out_file)


def download_url_weasyprint(url, out_file):
    weasyprint.HTML(url).write_pdf(out_file)

