from flask import Blueprint

from app.controllers.document_controller import get_excel, upload_document
from app.logging_config import get_logger

document_bp = Blueprint("documents", __name__, url_prefix="/api/documents")
logger = get_logger(__name__)


def upload_document_route():
    logger.info("Received request: method=POST path=/api/documents")
    return upload_document()


def get_excel_route():
    logger.info("Received request: method=GET path=/api/documents/excel")
    return get_excel()


document_bp.add_url_rule("", view_func=upload_document_route, methods=["POST"])
document_bp.add_url_rule("/excel", view_func=get_excel_route, methods=["GET"])
