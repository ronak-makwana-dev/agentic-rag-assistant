import os
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.vector_store import search_docs, rerank_documents
import json

def retrieve_and_rerank_knowledge(query: str):
    """
    Use this tool to find information in uploaded documents. 
    It performs a vector search followed by a semantic reranking pass.
    """
    # 1. Retrieve
    initial_chunks = search_docs(query, k=10)
    
    if not initial_chunks:
        return json.dumps({"error": "No relevant documents found", "results": []})

    # 2. Rerank
    best_chunks = rerank_documents(query, initial_chunks)
    
    # 3. Create a structured list
    results = []
    seen_content = set()

    for chunk in best_chunks:
        score = float(chunk.get('score', 0.0))
        content_snippet = chunk['content'].strip()

        # ONLY include results with a meaningful relevance score (e.g., > 20%)
        # and ignore duplicates
        if score > 0.20 and content_snippet not in seen_content:
            results.append({
                "source": chunk['source'],
                "content": chunk['content'],
                "relevance_score": score
            })
            seen_content.add(content_snippet)
    
    # Return as a JSON string
    return json.dumps({"results": results}, indent=2)

rag_agent = LlmAgent(
    name="RAG_Assistant",
    model="gemini-3-flash-preview", 
    tools=[retrieve_and_rerank_knowledge], 
    instruction="""You are a professional research assistant. 
    1. Always use retrieve_and_rerank_knowledge to find facts.
    2. The tool returns a JSON object with a list of 'results'. 
    3. Answer ONLY based on the 'content' field within those results.
    4. Cite your sources by mentioning the 'source' field (e.g., [Source: filename.pdf]).
    5. If the answer isn't in the provided JSON, say you don't know."""
)

# 3. Create the Runner
session_service = InMemorySessionService()
runner = Runner(
    agent=rag_agent,
    session_service=session_service,
    app_name="agentic_rag_assistant"
)