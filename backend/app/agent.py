import os
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.vector_store import search_docs, rerank_documents
import json

# --- Tool 1: Retrieve ---
def retrieve_documents(query: str):
    """Retrieves top-k relevant chunks from the vector database."""
    initial_chunks = search_docs(query, k=10)
    
    res = json.dumps(initial_chunks)
    print(f"retrive_documents: {res}")
    return res

# --- Tool 2: Rerank ---
def rerank_results(query: str, retrieved_chunks: str):
    """Applies semantic reranking to the retrieved chunks."""
    chunks = json.loads(retrieved_chunks)
    best_chunks = rerank_documents(query, chunks)
    
    results = []
    seen_content = set()
    for chunk in best_chunks:
        score = float(chunk.get('score', 0.0))
        content_snippet = chunk['content'].strip()
        if score > 0.20 and content_snippet not in seen_content:
            results.append({
                "source": chunk['source'],
                "content": chunk['content'],
                "relevance_score": score
            })
            seen_content.add(content_snippet)
    data = json.dumps({"results": results})
    print(f"rerank_results: {data}")
    return data

# --- Tool 3: Summarize ---
def summarize_context(reranked_data: str):
    """Summarizes the reranked snippets to prepare for final generation."""
    data = json.loads(reranked_data)
    results = data.get("results", [])
    if not results:
        return "No relevant context found."
    context_text = "\n".join([f"[{r['source']}]: {r['content']}" for r in results])
    # Returns a condensed version for the agent to process
    print(context_text)
    print(f"summarize_context: {context_text}")
    return context_text

# --- Tool 4: Generate ---
def generate_answer(query: str, summarized_context: str):
    """Generates the final grounded response based on the context."""
    # This acts as the final decision point for the agent
    answer = f"Based on the provided documents for '{query}': {summarized_context}"
    print(f"generate_answer: {answer}")

# --- Agent Configuration ---
rag_agent = LlmAgent(
    name="RAG_Assistant",
    model="gemini-3-flash-preview", 
    tools=[retrieve_documents, rerank_results, summarize_context, generate_answer], 
    instruction="""You are a precise Research Assistant. 
    Your goal is to answer questions as concisely as possible based ONLY on the provided context.
    
    RULES:
    1. If the user asks for a specific number or date, provide ONLY that information and the source.
    2. Do not summarize the entire document if a specific detail was requested.
    3. Use the tools in order: Retrieve -> Rerank -> Summarize -> Generate.
    4. Example: If asked 'What is the amount?', respond with '$1,200 USD [Source: manual.pdf]' instead of a paragraph.
    5. If the information is missing, simply say 'Information not found.'"""
)

# 3. Create the Runner
session_service = InMemorySessionService()
runner = Runner(
    agent=rag_agent,
    session_service=session_service,
    app_name="agentic_rag_assistant"
)