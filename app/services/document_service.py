import os
import time
from typing import Optional

from fastapi import HTTPException, status
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_ollama import OllamaEmbeddings

from app.config import settings
from app.database.pinecone import get_pinecone_index, delete_vectors_by_ids
from app.database.postgres import get_db_cursor
from app.models.schemas import DocumentResponse


def _get_embeddings() -> OllamaEmbeddings:
    return OllamaEmbeddings(
        model=settings.OLLAMA_EMBEDDING_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
    )


def _generate_document_id(user_id: int, doc_db_id: int, chunk_index: int) -> str:
    return f"user_{user_id}_doc_{doc_db_id}_chunk_{chunk_index}"


def upload_document(user_id: int, filename: str, filepath: str, file_size: int):
    """Process a PDF document: extract text, chunk, embed, and store in Pinecone."""

    # ── Step 1: Load PDF ──────────────────────────────────────────────────
    try:
        loader = PyPDFLoader(filepath)
        pages = loader.load()
        page_count = len(pages)
        full_text = "\n\n".join(page.page_content for page in pages)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process PDF: {str(e)}",
        )

    # ── Step 2: Split into chunks ─────────────────────────────────────────
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=150,
        chunk_overlap=20,
        separators=["\n\n", "\n", ".", " ", ""],
    )
    chunks = text_splitter.split_text(full_text)
    print(f"DEBUG: Total chunks created: {len(chunks)}")

    # ── Step 3: Save document record in DB ────────────────────────────────
    with get_db_cursor(auto_commit=True) as cur:
        cur.execute(
            """INSERT INTO documents (user_id, filename, filepath, file_size, page_count, status)
               VALUES (%s, %s, %s, %s, %s, %s)
               RETURNING id, created_at""",
            (user_id, filename, filepath, file_size, page_count, "processing"),
        )
        doc_record = cur.fetchone()
        doc_id = doc_record["id"]
        doc_created_at = doc_record["created_at"]

    # ── Step 4: Generate embeddings ───────────────────────────────────────
    embeddings = _get_embeddings()
    index = get_pinecone_index()

    pinecone_ids = []
    vectors = []

    for i, chunk in enumerate(chunks):
        vec_id = _generate_document_id(user_id, doc_id, i)
        pinecone_ids.append(vec_id)

        # Retry embedding up to 3 times
        for attempt in range(3):
            try:
                embedding_vector = embeddings.embed_query(chunk)
                break
            except Exception as e:
                if attempt < 2:
                    time.sleep(2)
                else:
                    raise HTTPException(
                        status_code=503,
                        detail=f"Embedding service unavailable: {str(e)}"
                    )

        vectors.append({
            "id": vec_id,
            "values": embedding_vector,
            "metadata": {
                "user_id": str(user_id),
                "document_id": str(doc_id),
                "chunk_index": i,
                "text": chunk,
                "source": filename,
            },
        })

    # ── Step 5: Upsert to Pinecone ────────────────────────────────────────
    print(f"DEBUG: Total vectors to upsert: {len(vectors)}")
    batch_size = 100
    for start in range(0, len(vectors), batch_size):
        batch = vectors[start: start + batch_size]
        print(f"DEBUG: Upserting batch {start} - {start + len(batch)}")
        index.upsert(vectors=batch)
        print(f"DEBUG: Batch upserted successfully!")

    print(f"DEBUG: All vectors upserted to Pinecone!")

    # ── Step 6: Update document status ───────────────────────────────────
    with get_db_cursor(auto_commit=True) as cur:
        cur.execute(
            """UPDATE documents SET status = %s, pinecone_ids = %s WHERE id = %s""",
            ("completed", pinecone_ids, doc_id),
        )

    return DocumentResponse(
        id=doc_id,
        user_id=user_id,
        filename=filename,
        file_size=file_size,
        page_count=page_count,
        status="completed",
        created_at=doc_created_at,
    )


def list_documents(user_id: int) -> list[DocumentResponse]:
    """List all documents for a user."""
    with get_db_cursor() as cur:
        cur.execute(
            """SELECT id, user_id, filename, file_size, page_count, status, created_at
               FROM documents WHERE user_id = %s
               ORDER BY created_at DESC""",
            (user_id,),
        )
        rows = cur.fetchall()

    return [
        DocumentResponse(
            id=row["id"],
            user_id=row["user_id"],
            filename=row["filename"],
            file_size=row["file_size"],
            page_count=row["page_count"],
            status=row["status"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def delete_document(user_id: int, document_id: int):
    """Delete a document and its vectors from Pinecone."""
    with get_db_cursor() as cur:
        cur.execute(
            "SELECT id, pinecone_ids FROM documents WHERE id = %s AND user_id = %s",
            (document_id, user_id),
        )
        doc = cur.fetchone()

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Delete vectors from Pinecone
    pinecone_ids = doc["pinecone_ids"]
    if pinecone_ids:
        delete_vectors_by_ids(pinecone_ids)

    # Delete file from disk
    with get_db_cursor(auto_commit=True) as cur:
        cur.execute(
            "SELECT filepath FROM documents WHERE id = %s",
            (document_id,),
        )
        file_record = cur.fetchone()
        if file_record and os.path.exists(file_record["filepath"]):
            os.remove(file_record["filepath"])

        cur.execute(
            "DELETE FROM documents WHERE id = %s AND user_id = %s",
            (document_id, user_id),
        )

    return {"message": "Document deleted successfully"}