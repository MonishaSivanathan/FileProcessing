import os


class Config:
    AZURE_STORAGE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    AZURE_CONTAINER = os.environ.get("AZURE_CONTAINER", "documents")
    EXCEL_PATH = os.environ.get("EXCEL_PATH", "./data/data.xlsx")
