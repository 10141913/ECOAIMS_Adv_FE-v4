import logging
import os
import sys

from flask import Flask, jsonify

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ecoaims_backend.precooling.api import precooling_bp


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def create_backend_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(precooling_bp)

    @app.get("/health")
    def health():
        return jsonify({"ok": True})

    return app


app = create_backend_app()


if __name__ == "__main__":
    host = os.getenv("BACKEND_HOST", "127.0.0.1")
    port = int(os.getenv("BACKEND_PORT", "5000"))
    logger.info("Starting ECOAIMS Precooling Backend (LEGACY Flask) on http://%s:%s", host, port)
    app.run(host=host, port=port, debug=True)
