import os
import uuid

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status

from app.config import settings
from app.middleware.auth_middleware import get_current_user
from app.models.schemas import DocumentResponse, DocumentListResponse
from app.services.document_service import upload_document, list_documents, delete_document

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentResponse,
    status_code=201,
    summary="Upload a menu PDF document",
)
async def upload_document_endpoint(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """Upload a PDF menu document. It will be processed, chunked, and stored in Pinecone."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are accepted",
        )

    # Save file to disk
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    filepath = os.path.join(settings.UPLOAD_DIR, unique_filename)

    content = await file.read()
    file_size = len(content)

    with open(filepath, "wb") as f:
        f.write(content)

    try:
        result = upload_document(
            user_id=current_user.user_id,
            filename=file.filename,
            filepath=filepath,
            file_size=file_size,
        )
        return result
    except Exception as e:
        # Clean up file on failure
        if os.path.exists(filepath):
            os.remove(filepath)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}",
        )


@router.get(
    "",
    response_model=DocumentListResponse,
    summary="List all uploaded documents",
)
def list_documents_endpoint(
    current_user=Depends(get_current_user),
):
    """Get a list of all documents uploaded by the current user."""
    docs = list_documents(user_id=current_user.user_id)
    return DocumentListResponse(documents=docs, total=len(docs))


@router.delete(
    "/{document_id}",
    summary="Delete a document",
)
def delete_document_endpoint(
    document_id: int,
    current_user=Depends(get_current_user),
):
    """Delete a document and its vectors from Pinecone."""
    return delete_document(user_id=current_user.user_id, document_id=document_id)
