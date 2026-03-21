import os
from typing import List
from dotenv import load_dotenv
from google import genai

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings
from langchain_community.vectorstores import FAISS
from flashrank import Ranker, RerankRequest

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
INDEX_PATH = "faiss_index"

# --- 1. Custom Embedder ---
class GeminiEmbedder(Embeddings):
    def __init__(self, api_key: str, model: str = "models/gemini-embedding-001"):
        self.client = genai.Client(api_key=api_key)
        self.model = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        response = self.client.models.embed_content(model=self.model, contents=texts)
        return [e.values for e in response.embeddings]

    def embed_query(self, text: str) -> List[float]:
        response = self.client.models.embed_content(model=self.model, contents=text)
        return response.embeddings[0].values

custom_embeddings = GeminiEmbedder(api_key=api_key)

# Initialize ranker (this will download a small model ~40MB on first run)
ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir="/tmp/flashrank")

def rerank_documents(query: str, search_results: list):
    """
    Refines the search results using a Cross-Encoder.
    Requirement 3: Apply reranking on retrieved chunks.
    """
    if not search_results:
        return []

    # Format for FlashRank
    passages = [
        {"id": i, "text": r["content"], "meta": {"source": r["source"]}} 
        for i, r in enumerate(search_results)
    ]

    rerank_request = RerankRequest(query=query, passages=passages)
    results = ranker.rerank(rerank_request)

    # Return top 3 highest scoring chunks
    return [
        {"content": r["text"], "source": r["meta"]["source"], "score": r["score"]} 
        for r in results[:3]
    ]
    
# --- 2. Load Existing Index on Startup ---
def load_local_vector_db():
    if os.path.exists(INDEX_PATH):
        try:
            # allow_dangerous_deserialization is required for loading local FAISS files
            return FAISS.load_local(INDEX_PATH, custom_embeddings, allow_dangerous_deserialization=True)
        except Exception as e:
            print(f"Error loading index: {e}")
            return None
    return None

# Initialize the global variable
vector_db = load_local_vector_db()

# --- 3. Core Functions ---

def process_pdf(file_path: str, filename: str):
    global vector_db
    
    loader = PyPDFLoader(file_path)
    docs = loader.load()
    
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)
    chunks = text_splitter.split_documents(docs)
    
    for chunk in chunks:
        chunk.metadata["source"] = filename
    
    if vector_db is None:
        vector_db = FAISS.from_documents(chunks, custom_embeddings)
    else:
        vector_db.add_documents(chunks)
        
    # SAVE to disk immediately after updating
    vector_db.save_local(INDEX_PATH)
    
    return len(chunks)

def search_docs(query: str, k: int = 10):
    global vector_db
    if vector_db is None:
        vector_db = load_local_vector_db()
        
    if vector_db is None:
        return []
    
    # Retrieve more documents than we actually need for the final answer
    docs = vector_db.similarity_search(query, k=k)
    return [{"content": d.page_content, "source": d.metadata.get("source")} for d in docs]

def get_unique_documents():
    global vector_db
    if vector_db is None:
        vector_db = load_local_vector_db()
    
    if vector_db is None:
        return []

    # FAISS stores documents in a dictionary-like docstore
    # We iterate through them to find all unique 'source' metadata tags
    unique_sources = set()
    
    # docstore is a private attribute in LangChain's FAISS wrapper
    # we can access the values which are the Document objects
    for doc in vector_db.docstore._dict.values():
        source = doc.metadata.get("source")
        if source:
            unique_sources.add(source)
            
    return sorted(list(unique_sources))