# 🤖 Agentic RAG Assistant

A production-grade, full-stack Retrieval-Augmented Generation (RAG) system. This application allows users to upload internal PDF documents, index them into a vector store, and interact with a **Gemini-powered Agent** that provides grounded answers with real-time source citations.

---

## 🏗 System Architecture

The system is built on a modern decoupled stack:
1.  **Frontend (Angular v17+):** A reactive UI that supports PDF uploads, real-time message streaming (SSE), and an "Evidence Found" sidebar to display source snippets.
2.  **Backend (FastAPI):** A high-performance server that handles document processing, vector storage, and streams agent responses using Server-Sent Events (SSE).
3.  **Agent Logic (Google ADK):** An autonomous agent that follows a multi-step reasoning pipeline.

---

## 🚀 How to Run the Project

The easiest way to run the assistant is via **Docker Compose**, which orchestrates the Python environment, the Angular build, and the vector database.

### 1. Prerequisites
* [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
* A Google Gemini API Key from [Google AI Studio](https://aistudio.google.com/)

### 2. Setup & Installation
```bash
# 1. Clone the repository
git clone [https://github.com/ronak-makwana-dev/agentic-rag-assistant.git](https://github.com/ronak-makwana-dev/agentic-rag-assistant.git)
cd agentic-rag-assistant

# 2. Configure Environment Variables
echo "GOOGLE_API_KEY=your_gemini_api_key_here" > .env

# Install dependencies
pip install -r requirements.txt
```


### 4. Execution
To start the agent in interactive mode:

```bash
docker-compose up --build
```

Access the Frontend at http://localhost:4200 and the Backend API at http://localhost:8000



## 🏗 Design Decisions

The architecture of this assistant was guided by the need for **high factual accuracy** and **real-time interactivity**. Below are the core technical choices made during development:

### 1. Agentic Workflow
Instead of a simple "one-shot" retrieval, we implemented a **ReAct (Reason + Act)** pattern using the Google ADK.
* **Decision:** The agent utilizes LlmAgent to autonomously call tools (retrieve_documents -> rerank_results -> summarize_context) in sequence to ensure the final answer is grounded in the latest retrieved data.

### 2. Hybrid Retrieval & Reranking Pipeline
To solve the "Lost in the Middle" problem common in LLMs, we utilize a two-stage retrieval process:
1.  **Stage 1 (FAISS):** Performs high-speed similarity search for the top 10 candidate chunks.
2.  **Stage 2 (FlashRank):** A lightweight Cross-Encoder reranks these candidates to ensure the 3 most relevant snippets are at the very top of the context window.

### 3. Reactive UI with Server-Sent Events (SSE)
FastAPI's EventSourceResponse pushes tokens and metadata (sources) to the frontend. This allows the "Evidence Found" sidebar to update as soon as the agent identifies sources, even before the text response is finished.

### 5. Frontend State Management with Angular Signals
In the Angular v17+ frontend, we utilized **Signals** to manage the chat state and source snippets.
* **Decision:** Signals provide fine-grained reactivity, meaning the UI only re-renders the specific message component or source card that changed, ensuring 60fps performance even during high-volume streaming.

---


## 🔍 RAG Pipeline Details

The system follows a multi-stage **Retrieval-Augmented Generation** pipeline designed to eliminate hallucinations and ensure every response is backed by uploaded evidence.



### 1. Data Ingestion & Pre-processing
When a file is uploaded via the Angular dashboard, the following occurs:
* **Parsing:** The `PyPDFLoader` extracts raw text while preserving structural metadata (page numbers, filenames).
* **Recursive Splitting:** Documents are broken into chunks of 1,000 characters with a 100-character overlap via RecursiveCharacterTextSplitter.

### 2. Semantic Indexing
* **Embedding Model:** e utilize models/gemini-embedding-001 (as defined in vector_store.py).
* **Vector Store:** Chunks are indexed in FAISS. The index is persisted locally in the faiss_index/ directory.

### 3. Two-Tier Retrieval Strategy
To ensure the most relevant information is fed to the LLM, we use a "Coarse-to-Fine" approach:
1.  **Candidate Retrieval:** The system fetches the top $10$ most similar chunks from FAISS based on the user's query vector.
2.  **Semantic Reranking:** We pass these $10$ chunks through **FlashRank** (using the `ms-marco-MiniLM-L-12-v2` model). This cross-encoder evaluates the actual semantic relationship between the query and the text, re-ordering them to put the "perfect match" at position #1.

### 4. Grounded Generation (The "Augmentation")
The agent uses gemini-3-flash-preview with a specific system instruction to act as a "Precise Research Assistant," ensuring it only answers based on the provided context or responds with "Information not found.":
* **Context Injection:** The top $3$ reranked snippets are injected into the system prompt.
* **Source Attribution:** The model is instructed to append the source filename (e.g., `[test.pdf]`) to every factual claim.
* **Safety Guardrails:** If the retrieved context does not contain the answer, the agent is programmed to respond with *"Information not found"* rather than guessing.

---
