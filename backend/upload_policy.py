"""Limits for files uploaded by users."""
import os

MAX_REQUEST_BYTES = 50 * 1024 * 1024            # Flask MAX_CONTENT_LENGTH: whole request, documents included
MAX_DATASET_BYTES = 1024 * 1024                 # evaluation CSV
MAX_DATASET_QUESTIONS = 500
DOCUMENT_EXTENSIONS = frozenset({'.pdf', '.txt', '.md', '.docx', '.csv'})   # what SimpleDirectoryReader is used with
MAX_EVALUATION_EXECUTIONS = 10                  # n_exec


def is_allowed_document(filename: str) -> bool:
    return os.path.splitext(filename)[1].lower() in DOCUMENT_EXTENSIONS
