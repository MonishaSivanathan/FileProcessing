import os

from dotenv import load_dotenv
from flask import Flask

from app.controllers.document_controller import document_bp

# load environment variables from a .env file if present
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def create_app():
    app = Flask(__name__)
    app.register_blueprint(document_bp)
    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True)
