<div align="center">

# 🍽️ RestoBot — AI Restaurant PDF Chatbot API

[![FastAPI](https://img.shields.io/badge/FastAPI-0.138-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.14%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![LangChain](https://img.shields.io/badge/LangChain-1.3-1C3D5A?logo=langchain&logoColor=white)](https://langchain.com)
[![Ollama](https://img.shields.io/badge/Ollama-llama3.1-000?logo=ollama&logoColor=white)](https://ollama.ai)
[![Pinecone](https://img.shields.io/badge/Pinecone-6.0-000?logo=pinecone&logoColor=white)](https://pinecone.io)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-psycopg2-4169E1?logo=postgresql&logoColor=white)](https://postgresql.org)
[![JWT](https://img.shields.io/badge/Auth-JWT-000?logo=jsonwebtokens&logoColor=white)](https://jwt.io)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**RestoBot** is a friendly AI restaurant assistant API that understands menu PDFs, answers questions, suggests dishes, places orders automatically, and generates bills — all powered by local LLMs via Ollama.

</div>

---

## ✨ Features

- 🤖 **AI-Powered Chat** — Conversational assistant powered by Llama 3.1 via Ollama
- 📄 **PDF Menu Ingestion** — Upload restaurant menu PDFs, automatically chunked & vectorised
- 🔍 **Semantic Menu Search** — Find dishes by description, ingredients, or preferences
- 🛒 **Automatic Order Placement** — Place orders via natural language; prices fetched from menu automatically
- 🧾 **Bill Generation** — Generate itemised bills with subtotal, tax (8%), and total
- 📜 **Chat History** — Persistent per-user conversation history
- 🔐 **JWT Authentication** — Secure user registration & login with bcrypt password hashing
- 🏥 **Health Monitoring** — Health check endpoint for all downstream services

---

## 🏗 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        FastAPI Server                        │
│  ┌───────────┐ ┌──────────┐ ┌──────────┐ ┌───────────────┐ │
│  │ Auth API  │ │ Chat API │ │ Menu API │ │ Orders / Bill │ │
│  └─────┬─────┘ └────┬─────┘ └────┬─────┘ └───────┬───────┘ │
│        │             │            │                │         │
│  ┌─────┴─────────────┴────────────┴────────────────┴───────┐│
│  │              LangChain RAG Pipeline                     ││
│  └─────┬────────────────────────────────────────┬──────────┘│
│        │                                        │            │
│  ┌─────┴──────────┐                    ┌───────┴──────────┐ │
│  │   Pinecone     │                    │    PostgreSQL     │ │
│  │  (Vector DB)   │                    │  (Relational DB)  │ │
│  │  Menu chunks   │                    │  Users, Orders    │ │
│  │  Embeddings    │                    │  Chat History     │ │
│  └────────────────┘                    │  Documents meta   │ │
│                                        └───────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐│
│  │               Ollama (llama3.1:latest)                   ││
│  │         Local LLM + Embeddings (qwen3-embedding)        ││
│  └──────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

---

## 🛠 Tech Stack

| Component              | Technology                                   |
|------------------------|----------------------------------------------|
| **Framework**          | FastAPI + Uvicorn                            |
| **AI/LLM**             | Ollama (llama3.1:latest)                     |
| **Embeddings**         | Ollama (qwen3-embedding:latest)              |
| **Vector Database**    | Pinecone (cosine similarity, dim 4096)       |
| **Relational Database**| PostgreSQL (via psycopg2 connection pool)    |
| **Authentication**     | JWT (python-jose) + bcrypt (passlib)         |
| **PDF Processing**     | PyPDFLoader + RecursiveCharacterTextSplitter |
| **Orchestration**      | LangChain RAG pipeline                       |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.14+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- PostgreSQL database
- [Ollama](https://ollama.ai) running with `llama3.1:latest` and `qwen3-embedding:latest`
- Pinecone account and API key

### Setup

```bash
# 1. Clone the repository
git clone https://github.com/your-org/restobot.git
cd restobot

# 2. Create environment file
cp .env.example .env
# Edit .env with your credentials

# 3. Install dependencies
uv sync

# 4. Start the server
uv run python -m app.main
```

The API will be available at **http://localhost:8000** with interactive docs at **http://localhost:8000/docs**.

---

## 🔐 Authentication

All endpoints except `/auth/register`, `/auth/login`, and `/health` require a **Bearer JWT token** in the `Authorization` header.

```
Authorization: Bearer <your_access_token>
```

---

## 📡 API Reference

### 🔑 Authentication

| Method | Endpoint             | Description                          | Auth Required |
|--------|----------------------|--------------------------------------|:-------------:|
| POST   | `/auth/register`     | Register a new user                  | ❌            |
| POST   | `/auth/login`        | Login and receive JWT token          | ❌            |

#### `POST /auth/register`

**Request:**
```json
{
  "username": "john_doe",
  "email": "john@example.com",
  "password": "securepass123",
  "full_name": "John Doe"
}
```

**Response `201 Created`:**
```json
{
  "id": 1,
  "username": "john_doe",
  "email": "john@example.com",
  "full_name": "John Doe",
  "created_at": "2026-06-29T12:00:00Z"
}
```

#### `POST /auth/login`

**Request:**
```json
{
  "username": "john_doe",
  "password": "securepass123"
}
```

**Response `200 OK`:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "id": 1,
    "username": "john_doe",
    "email": "john@example.com",
    "full_name": "John Doe",
    "created_at": "2026-06-29T12:00:00Z"
  }
}
```

---

### 📄 Documents

| Method | Endpoint                  | Description                                      | Auth Required |
|--------|---------------------------|--------------------------------------------------|:-------------:|
| POST   | `/documents/upload`       | Upload a PDF menu document                       | ✅            |
| GET    | `/documents`              | List all uploaded documents for current user     | ✅            |
| DELETE | `/documents/{id}`         | Delete a document and its Pinecone vectors       | ✅            |

#### `POST /documents/upload`

**Request:** `multipart/form-data` with `file` field (PDF only)

```
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer <token>" \
  -F "file=@menu.pdf"
```

**Response `201 Created`:**
```json
{
  "id": 1,
  "user_id": 1,
  "filename": "menu.pdf",
  "file_size": 245760,
  "page_count": 8,
  "status": "completed",
  "created_at": "2026-06-29T12:05:00Z"
}
```

#### `GET /documents`

**Response `200 OK`:**
```json
{
  "documents": [
    {
      "id": 1,
      "user_id": 1,
      "filename": "menu.pdf",
      "file_size": 245760,
      "page_count": 8,
      "status": "completed",
      "created_at": "2026-06-29T12:05:00Z"
    }
  ],
  "total": 1
}
```

#### `DELETE /documents/1`

**Response `200 OK`:**
```json
{
  "message": "Document deleted successfully"
}
```

---

### 💬 Chat

| Method | Endpoint    | Description                                    | Auth Required |
|--------|-------------|------------------------------------------------|:-------------:|
| POST   | `/chat`     | Send a message to RestoBot                     | ✅            |

#### `POST /chat`

**Request:**
```json
{
  "message": "What appetizers do you have?"
}
```

**Response `200 OK` (question):**
```json
{
  "reply": "Here are our appetizers:\n\n🍽️ Spring Rolls — Rs. 350\n   Crispy vegetable spring rolls with sweet chili dip\n\n🍽️ Chicken Wings — Rs. 550\n   Spicy grilled chicken wings with garlic mayo\n\nWould you like to order any of these? 😊",
  "user_id": 1,
  "order_placed": false,
  "order_id": null
}
```

**Response `200 OK` (automatic order placement):**
```json
{
  "reply": "Great choice! I've placed your order for Chicken Biryani and Garlic Naan.\n\n✅ **Order #5 placed successfully!** Your order has been confirmed and is being prepared. Thank you for dining with us! 🍽️",
  "user_id": 1,
  "order_placed": true,
  "order_id": 5
}
```

---

### 🛒 Orders

| Method | Endpoint                    | Description                              | Auth Required |
|--------|-----------------------------|------------------------------------------|:-------------:|
| POST   | `/orders`                   | Create a new order                       | ✅            |
| GET    | `/orders`                   | List current user's orders               | ✅            |
| GET    | `/orders/{id}`              | Get order by ID                          | ✅            |
| PATCH  | `/orders/{id}/status`       | Update order status                      | ✅            |
| DELETE | `/orders/{id}`              | Delete/cancel an order                   | ✅            |
| GET    | `/orders/{id}/bill`         | Generate bill for an order               | ✅            |
| GET    | `/users/{user_id}/orders`   | Get orders for a specific user           | ✅            |

#### `POST /orders`

**Request:**
```json
{
  "items": [
    {"menu_item": "Chicken Biryani", "quantity": 2},
    {"menu_item": "Garlic Naan", "quantity": 1}
  ],
  "special_instructions": "Extra spicy please"
}
```

> **Note:** Prices are fetched automatically from the menu via Pinecone — no need to include them.

**Response `201 Created`:**
```json
{
  "id": 5,
  "user_id": 1,
  "items": [
    {
      "menu_item": "Chicken Biryani",
      "quantity": 2,
      "price": 450.0,
      "subtotal": 900.0
    },
    {
      "menu_item": "Garlic Naan",
      "quantity": 1,
      "price": 80.0,
      "subtotal": 80.0
    }
  ],
  "total_amount": 980.0,
  "status": "pending",
  "special_instructions": "Extra spicy please",
  "created_at": "2026-06-29T12:10:00Z",
  "updated_at": "2026-06-29T12:10:00Z"
}
```

#### `GET /orders`

**Response `200 OK`:**
```json
{
  "orders": [
    {
      "id": 5,
      "user_id": 1,
      "items": [
        {"menu_item": "Chicken Biryani", "quantity": 2, "price": 450.0, "subtotal": 900.0},
        {"menu_item": "Garlic Naan", "quantity": 1, "price": 80.0, "subtotal": 80.0}
      ],
      "total_amount": 980.0,
      "status": "confirmed",
      "special_instructions": "Extra spicy please",
      "created_at": "2026-06-29T12:10:00Z",
      "updated_at": "2026-06-29T12:11:00Z"
    }
  ],
  "total": 1
}
```

#### `PATCH /orders/5/status`

**Request:**
```json
{
  "status": "confirmed"
}
```

**Valid statuses:** `pending`, `confirmed`, `preparing`, `ready`, `delivered`, `cancelled`

**Response `200 OK`:**
```json
{
  "id": 5,
  "user_id": 1,
  "items": [...],
  "total_amount": 980.0,
  "status": "confirmed",
  "special_instructions": "Extra spicy please",
  "created_at": "2026-06-29T12:10:00Z",
  "updated_at": "2026-06-29T12:11:00Z"
}
```

#### `GET /orders/5/bill`

**Response `200 OK`:**
```json
{
  "order_id": 5,
  "items": [
    {"menu_item": "Chicken Biryani", "quantity": 2, "price": 450.0, "subtotal": 900.0},
    {"menu_item": "Garlic Naan", "quantity": 1, "price": 80.0, "subtotal": 80.0}
  ],
  "subtotal": 980.0,
  "tax": 78.4,
  "total": 1058.4,
  "status": "confirmed",
  "generated_at": "2026-06-29T12:15:00Z"
}
```

---

### 📜 History

| Method | Endpoint                               | Description                          | Auth Required |
|--------|----------------------------------------|--------------------------------------|:-------------:|
| GET    | `/users/{user_id}/history`             | Get chat history for a user          | ✅            |
| DELETE | `/users/{user_id}/history`             | Delete chat history for a user       | ✅            |

#### `GET /users/1/history`

**Response `200 OK`:**
```json
{
  "messages": [
    {
      "role": "user",
      "content": "What appetizers do you have?",
      "created_at": "2026-06-29T12:00:00Z"
    },
    {
      "role": "assistant",
      "content": "Here are our appetizers:...",
      "created_at": "2026-06-29T12:00:05Z"
    }
  ],
  "total": 2
}
```

---

### 🍽️ Menu / Smart Search

| Method | Endpoint                        | Description                                      | Auth Required |
|--------|---------------------------------|--------------------------------------------------|:-------------:|
| GET    | `/menu/search`                  | Semantic search menu items                       | ✅            |
| GET    | `/menu/recommendations`         | Get personalised menu recommendations            | ✅            |

#### `GET /menu/search?q=spicy+chicken&top_k=5`

**Response `200 OK`:**
```json
{
  "query": "spicy chicken",
  "results": [
    {
      "id": "search_result",
      "text": "🍽️ Chicken Wings — Rs. 550\n   Spicy grilled chicken wings with garlic mayo\n\n🍽️ Spicy Chicken Tikka — Rs. 650\n   Marinated chicken with traditional spices...",
      "score": 1.0,
      "source": "AI formatted result"
    }
  ],
  "total": 1
}
```

#### `GET /menu/recommendations?preferences=vegetarian+and+healthy&top_k=3`

**Response `200 OK`:**
```json
{
  "recommendations": [
    {
      "id": "recommendation_result",
      "text": "🌟 Recommended for you:\n\n🍽️ Garden Salad — Rs. 350\n   Why we recommend it: Fresh and healthy option perfect for vegetarian preferences\n\n🍽️ Vegetable Stir Fry — Rs. 420\n   Why we recommend it: Light, nutritious vegetarian dish...",
      "score": 1.0,
      "source": "AI recommendation"
    }
  ],
  "based_on": "vegetarian and healthy"
}
```

---

### 🏥 Health

| Method | Endpoint    | Description                          | Auth Required |
|--------|-------------|--------------------------------------|:-------------:|
| GET    | `/health`   | Health check for all services        | ❌            |

#### `GET /health`

**Response `200 OK`:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "healthy",
  "pinecone": "healthy",
  "ollama": "healthy"
}
```

If any service is down, `status` will be `"degraded"` and the individual status will show `"unhealthy"`.

---

## 🗄 Database Schema

### PostgreSQL (Relational)

```sql
-- Users table
CREATE TABLE users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(100) UNIQUE NOT NULL,
    email           VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    full_name       VARCHAR(255),
    created_at      TIMESTAMP DEFAULT NOW(),
    updated_at      TIMESTAMP DEFAULT NOW()
);

-- Chat history
CREATE TABLE chat_history (
    id          SERIAL PRIMARY KEY,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        VARCHAR(20) NOT NULL,         -- 'user' or 'assistant'
    content     TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_chat_history_user_id ON chat_history(user_id);

-- Documents metadata
CREATE TABLE documents (
    id              SERIAL PRIMARY KEY,
    user_id         INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename        VARCHAR(500) NOT NULL,
    filepath        TEXT NOT NULL,
    file_size       INTEGER DEFAULT 0,
    page_count      INTEGER DEFAULT 0,
    status          VARCHAR(50) DEFAULT 'pending',  -- pending, processing, completed
    pinecone_ids    TEXT[] DEFAULT '{}',             -- references to vectors in Pinecone
    created_at      TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_documents_user_id ON documents(user_id);

-- Orders
CREATE TABLE orders (
    id                  SERIAL PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    items               JSONB NOT NULL DEFAULT '[]',     -- [{menu_item, quantity, price, subtotal}]
    total_amount        DECIMAL(10, 2) DEFAULT 0.00,
    status              VARCHAR(50) DEFAULT 'pending',   -- pending, confirmed, preparing, ready, delivered, cancelled
    special_instructions TEXT,
    created_at          TIMESTAMP DEFAULT NOW(),
    updated_at          TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_orders_user_id ON orders(user_id);
```

### Pinecone (Vector Database)

**Index Configuration:**

| Parameter            | Value                       |
|----------------------|-----------------------------|
| **Index Name**       | `restaurant-menu`           |
| **Dimension**        | 4096                        |
| **Metric**           | `cosine`                    |
| **Cloud**            | AWS                         |
| **Region**           | `us-east-1` (configurable)  |

**Vector Metadata Schema:**

| Field          | Type   | Description                          |
|----------------|--------|--------------------------------------|
| `user_id`      | string | Owner of the document                |
| `document_id`  | string | FK to PostgreSQL `documents.id`      |
| `chunk_index`  | int    | Position of chunk within the document|
| `text`         | string | Raw text content of the chunk        |
| `source`       | string | Original filename                    |

**Vector ID Format:**
```
user_{user_id}_doc_{doc_id}_chunk_{chunk_index}
```

Each PDF document is split into chunks of **~150 characters** (20 character overlap) using `RecursiveCharacterTextSplitter`, embedded via Ollama's `qwen3-embedding:latest` model (4096 dimensions), and upserted to Pinecone in batches of 100.

---

## 🔧 Environment Variables

| Variable                      | Default                                      | Description                            |
|-------------------------------|----------------------------------------------|----------------------------------------|
| `DEBUG`                       | `false`                                      | Enable debug mode & auto-reload        |
| `DATABASE_URL`                | `postgresql://postgres:postgres@localhost:5432/restaurant_chatbot` | PostgreSQL connection string |
| `DATABASE_HOST`               | `localhost`                                  | PostgreSQL host                        |
| `DATABASE_PORT`               | `5432`                                       | PostgreSQL port                        |
| `DATABASE_NAME`               | `restaurant_chatbot`                         | PostgreSQL database name               |
| `DATABASE_USER`               | `postgres`                                   | PostgreSQL user                        |
| `DATABASE_PASSWORD`           | `postgres`                                   | PostgreSQL password                    |
| `JWT_SECRET`                  | `change-me-in-production`                    | Secret key for JWT signing             |
| `JWT_ALGORITHM`               | `HS256`                                      | JWT signing algorithm (hardcoded)      |
| `JWT_EXPIRATION_HOURS`        | `24`                                         | JWT token expiry (hours)               |
| `OLLAMA_BASE_URL`             | `http://154.57.212.236:11434`                | Ollama server URL                      |
| `OLLAMA_LLM_MODEL`            | `llama3.1:latest`                            | LLM model for chat                     |
| `OLLAMA_EMBEDDING_MODEL`      | `qwen3-embedding:latest`                     | Embedding model for vectors            |
| `PINECONE_API_KEY`            | *(required)*                                 | Pinecone API key                       |
| `PINECONE_ENVIRONMENT`        | `us-east-1`                                  | Pinecone region                        |
| `PINECONE_INDEX_NAME`         | `restaurant-menu`                            | Pinecone index name                    |
| `PINECONE_EMBEDDING_DIMENSION`| `4096`                                       | Embedding vector dimension             |
| `UPLOAD_DIR`                  | `static/uploads`                             | Directory for uploaded PDFs            |

---

## 🗺 Dual-Database Architecture

RestoBot uses **two distinct databases** for different purposes:

### 🐘 PostgreSQL — Relational Data
- **Stores:** Users, documents metadata, chat history, orders, and bills
- **Why:** Relational data with strong consistency, complex queries (JOINs), and transactions
- **Access:** Connection pool via `psycopg2` with `ThreadedConnectionPool` (1–10 connections)
- **Schema:** Auto-initialised on startup via `init_db()` — tables created if they don't exist

### 🌲 Pinecone — Vector Data
- **Stores:** Menu PDF text chunks as embeddings (4096-dimension vectors)
- **Why:** Efficient similarity search across menu items for RAG (Retrieval-Augmented Generation)
- **Access:** Serverless index with cosine similarity metric
- **Indexing:** Documents are chunked, embedded via Ollama, and upserted automatically on upload

> **How they work together:** When a user asks a question, the query is embedded and searched against Pinecone to find relevant menu items. The retrieved context is passed to the LLM (via LangChain) to generate a response. Orders, user accounts, and conversation history are stored in PostgreSQL. When a document is deleted, both the database record and its Pinecone vectors are removed.

---

## 📁 Project Structure

```
restobot/
├── app/
│   ├── main.py                  # FastAPI app entry point
│   ├── config.py                # Settings from environment variables
│   ├── database/
│   │   ├── __init__.py
│   │   ├── postgres.py          # PostgreSQL connection pool & init
│   │   └── pinecone.py          # Pinecone client & index management
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py           # Pydantic request/response models
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth.py              # /auth endpoints
│   │   ├── chat.py              # /chat endpoints
│   │   ├── documents.py         # /documents endpoints
│   │   ├── health.py            # /health endpoint
│   │   ├── history.py           # /users/{id}/history endpoints
│   │   ├── menu.py              # /menu endpoints
│   │   └── orders.py            # /orders endpoints
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py      # Registration & login logic
│   │   ├── chat_service.py      # RAG pipeline & order parsing
│   │   ├── document_service.py  # PDF processing & vector indexing
│   │   ├── menu_service.py      # Semantic search & recommendations
│   │   └── order_service.py     # Order CRUD & bill generation
│   └── middleware/
│       ├── __init__.py
│       └── auth_middleware.py    # JWT creation & verification
├── pyproject.toml               # Dependencies & project metadata
├── uv.lock                      # Locked dependency versions
└── README.md                    # This file
```

---

## 🧪 Running Tests

```bash
# Coming soon
uv run pytest
```

---

## 📖 Interactive API Docs

Once the server is running, visit:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<div align="center">
Built with ❤️ using FastAPI, LangChain & Ollama
</div>
