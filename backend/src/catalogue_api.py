import json
import logging
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

from catalogue import DEFAULT_CATALOGUE_PATH, CatalogueUnavailableError, load_catalogue
from escalation import EscalationStore

logger = logging.getLogger("catalogue-api")


def _escalation_store() -> EscalationStore:
    database_path = os.getenv("CALLER_MEMORY_DB")
    return EscalationStore(database_path) if database_path else EscalationStore()


class CatalogueRequestHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: object) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/health":
            self._send_json(200, {"status": "ok"})
            return
        if path == "/escalations":
            records = [item.to_dict() for item in _escalation_store().list()]
            self._send_json(200, {"escalations": records})
            return
        if path.startswith("/escalations/"):
            reference_id = unquote(path.removeprefix("/escalations/"))
            record = _escalation_store().get(reference_id)
            if record is None:
                self._send_json(404, {"error": "Escalation not found"})
                return
            self._send_json(200, record.to_dict())
            return
        if path != "/catalogue":
            self._send_json(404, {"error": "Not found"})
            return
        try:
            catalogue = load_catalogue(DEFAULT_CATALOGUE_PATH)
        except CatalogueUnavailableError as exc:
            self._send_json(503, {"error": str(exc)})
            return
        self._send_json(
            200,
            {
                "updated_at": catalogue.updated_at,
                "products": [
                    {
                        "product_id": product.product_id,
                        "name": product.name,
                        "seller": product.seller,
                        "location": product.location,
                        "category": product.category,
                        "price_inr": product.price_inr,
                        "stock_quantity": product.stock_quantity,
                        "unit": product.unit,
                    }
                    for product in catalogue.products
                ],
            },
        )

    def _read_json(self) -> dict[str, object]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length < 1 or content_length > 50_000:
            raise ValueError("Invalid request body")
        payload = json.loads(self.rfile.read(content_length))
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        return payload

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/escalations":
            self._send_json(404, {"error": "Not found"})
            return
        try:
            payload = self._read_json()
            if payload.get("consent_given") is not True:
                self._send_json(403, {"error": "Explicit permission is required"})
                return
            record, created = _escalation_store().create_or_update(
                customer_id=str(payload.get("customer_id", "dashboard")),
                customer_name=str(payload.get("customer_name", "")),
                issue_type=str(payload.get("issue_type", "")),
                summary=str(payload.get("summary", "")),
                checked_information=str(payload.get("checked_information", "")),
                urgency=str(payload.get("urgency", "")),
                language=str(payload.get("language", "")),
                preferred_followup=str(payload.get("preferred_followup", "")),
                consent_given=True,
            )
        except (json.JSONDecodeError, ValueError) as error:
            self._send_json(400, {"error": str(error)})
            return
        logger.info(
            "%s escalation %s",
            "Created" if created else "Updated duplicate",
            record.reference_id,
        )
        self._send_json(201 if created else 200, record.to_dict())

    def do_PATCH(self) -> None:
        path = urlparse(self.path).path
        if not path.startswith("/escalations/"):
            self._send_json(404, {"error": "Not found"})
            return
        try:
            payload = self._read_json()
            reference_id = unquote(path.removeprefix("/escalations/"))
            record = _escalation_store().update_status(
                reference_id, str(payload.get("status", ""))
            )
        except (json.JSONDecodeError, ValueError) as error:
            self._send_json(400, {"error": str(error)})
            return
        if record is None:
            self._send_json(404, {"error": "Escalation not found"})
            return
        logger.info("Escalation status changed: %s -> %s", reference_id, record.status)
        self._send_json(200, record.to_dict())

    def log_message(self, message: str, *args: object) -> None:
        logger.info("%s - %s", self.client_address[0], message % args)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    host = os.getenv("CATALOGUE_API_HOST", "127.0.0.1")
    port = int(os.getenv("CATALOGUE_API_PORT", "8001"))
    server = ThreadingHTTPServer((host, port), CatalogueRequestHandler)
    logger.info("Catalogue API listening on http://%s:%s", host, port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Catalogue API stopped")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
