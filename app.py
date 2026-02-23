import os

from dotenv import load_dotenv
from flask import Flask

from app.logging_config import get_logger, setup_logging

# load environment variables from a .env file if present
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
setup_logging()
logger = get_logger(__name__)


def create_app():
    app = Flask(__name__)
    from app.routers.document_router import document_bp

    app.register_blueprint(document_bp)
    logger.info(
        "Application initialization complete: registered blueprint='%s'",
        document_bp.name,
    )
    return app


if __name__ == "__main__":
    app = create_app()
    logger.info("Starting Flask development server with debug=%s", True)
    app.run(debug=True)
