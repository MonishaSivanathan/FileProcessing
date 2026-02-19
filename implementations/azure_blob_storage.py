import os
from typing import Optional

from azure.storage.blob import BlobClient, BlobServiceClient, ContainerClient

from app.interfaces.storage_interface import IStorage


class AzureBlobStorage(IStorage):
    def __init__(self, container_name: Optional[str] = None):
        # read connection information from environment or Azure identity
        self.conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not self.conn_str:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING not set")
        self.container = container_name or os.environ.get(
            "AZURE_CONTAINER", "documents"
        )
        self._service = BlobServiceClient.from_connection_string(self.conn_str)
        self._container_client: ContainerClient = self._service.get_container_client(
            self.container
        )
        # create container if it does not exist
        try:
            self._container_client.create_container()
        except Exception:
            pass

    def save(self, name: str, data: bytes) -> str:
        """Upload bytes under the given blob name and return the blob URL."""
        blob_client: BlobClient = self._container_client.get_blob_client(name)
        blob_client.upload_blob(data, overwrite=True)
        return blob_client.url

    def get(self, name: str) -> bytes:
        """Download blob contents as bytes."""
        blob_client: BlobClient = self._container_client.get_blob_client(name)
        downloader = blob_client.download_blob()
        return downloader.readall()
