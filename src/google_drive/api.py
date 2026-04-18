"""Low-level Google Drive and Docs API wrappers."""

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


def get_drive_service(creds: Credentials):
    """Build Google Drive API service.

    Args:
        creds: Google OAuth credentials.

    Returns:
        Google Drive API service.
    """
    return build("drive", "v3", credentials=creds)


def get_docs_service(creds: Credentials):
    """Build Google Docs API service.

    Args:
        creds: Google OAuth credentials.

    Returns:
        Google Docs API service.
    """
    return build("docs", "v1", credentials=creds)


def list_files_in_folder(service, folder_id: str) -> list[dict]:
    """List files in a Google Drive folder.

    Args:
        service: Google Drive API service.
        folder_id: The folder ID.

    Returns:
        List of file metadata dicts.
    """
    query = f"'{folder_id}' in parents and trashed = false"
    results = service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
        pageSize=100,
    ).execute()
    return results.get("files", [])


def export_google_doc(service, doc_id: str, mime_type: str = "text/plain") -> str:
    """Export Google Doc content.

    Args:
        service: Google Drive API service.
        doc_id: The document ID.
        mime_type: Export MIME type.

    Returns:
        Document content as string.
    """
    content = service.files().export(
        fileId=doc_id,
        mimeType=mime_type,
    ).execute()
    return content.decode("utf-8") if isinstance(content, bytes) else content


def download_file(service, file_id: str) -> str:
    """Download file content.

    Args:
        service: Google Drive API service.
        file_id: The file ID.

    Returns:
        File content as string.
    """
    content = service.files().get_media(fileId=file_id).execute()
    return content.decode("utf-8") if isinstance(content, bytes) else content


def create_google_doc(
    docs_service,
    drive_service,
    name: str,
    content: str,
    parent_id: str | None,
) -> dict:
    """Create a new Google Doc with content.

    Args:
        docs_service: Google Docs API service.
        drive_service: Google Drive API service.
        name: Document name.
        content: Initial content.
        parent_id: Optional parent folder ID.

    Returns:
        Dict with 'id' and 'url' of created document.
    """
    # Create empty doc
    doc = docs_service.documents().create(body={"title": name}).execute()
    doc_id = doc["documentId"]

    # Move to folder if specified
    if parent_id:
        drive_service.files().update(
            fileId=doc_id,
            addParents=parent_id,
            fields="id, parents",
        ).execute()

    # Insert content
    if content:
        docs_service.documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [{
                    "insertText": {
                        "location": {"index": 1},
                        "text": content,
                    }
                }]
            },
        ).execute()

    return {
        "id": doc_id,
        "url": f"https://docs.google.com/document/d/{doc_id}/edit",
    }


def format_paragraph(
    docs_service,
    doc_id: str,
    start_index: int,
    end_index: int,
    style: dict,
) -> None:
    """Apply paragraph formatting.

    Args:
        docs_service: Google Docs API service.
        doc_id: The document ID.
        start_index: Start index in document.
        end_index: End index in document.
        style: Paragraph style dict.
    """
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [{
                "updateParagraphStyle": {
                    "range": {"startIndex": start_index, "endIndex": end_index},
                    "paragraphStyle": style,
                    "fields": ",".join(style.keys()),
                }
            }]
        },
    ).execute()


def format_text(
    docs_service,
    doc_id: str,
    start_index: int,
    end_index: int,
    style: dict,
) -> None:
    """Apply text formatting.

    Args:
        docs_service: Google Docs API service.
        doc_id: The document ID.
        start_index: Start index in document.
        end_index: End index in document.
        style: Text style dict.
    """
    docs_service.documents().batchUpdate(
        documentId=doc_id,
        body={
            "requests": [{
                "updateTextStyle": {
                    "range": {"startIndex": start_index, "endIndex": end_index},
                    "textStyle": style,
                    "fields": ",".join(style.keys()),
                }
            }]
        },
    ).execute()


def get_document(docs_service, doc_id: str) -> dict:
    """Get full document structure.

    Args:
        docs_service: Google Docs API service.
        doc_id: The document ID.

    Returns:
        Document structure dict.
    """
    return docs_service.documents().get(documentId=doc_id).execute()
