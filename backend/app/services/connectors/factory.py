from app.models.connector import Connector
from app.services.connectors.base import DocumentConnector
from app.services.connectors.google_drive import GoogleDriveConnector
from app.services.connectors.local import LocalConnector
from app.services.connectors.notion import NotionConnector
from app.services.connectors.sharepoint import SharePointConnector


def build_connector(connector: Connector) -> DocumentConnector:
    config = connector.config or {}

    if connector.type == "local":
        root_path = config.get("root_path") or "./sample_docs"
        return LocalConnector(root_path=root_path)

    if connector.type == "sharepoint":
        return SharePointConnector(config=config)

    if connector.type == "google_drive":
        return GoogleDriveConnector(config=config)

    if connector.type == "notion":
        return NotionConnector(config=config)

    raise ValueError(f"Unsupported connector type: {connector.type!r}")
