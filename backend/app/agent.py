import os
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from app.vector_store import search_docs, rerank_documents

def retrieve_and_rerank_knowledge(query: str):
    """
    Use this tool to find information in uploaded documents. 
    It performs a vector search followed by a semantic reranking pass 
    to ensure the most relevant context is found.
    """
    # 1. Retrieve (Broad)
    initial_chunks = search_docs(query, k=10)
    
    if not initial_chunks:
        return "No relevant documents found."

    # 2. Rerank (Deep)
    best_chunks = rerank_documents(query, initial_chunks)
    
    # 3. Format context for the LLM
    context_block = "Relevant Snippets found in documents:\n"
    for i, chunk in enumerate(best_chunks):
        context_block += f"\n--- SNIPPET {i+1} (Source: {chunk['source']}) ---\n"
        context_block += f"{chunk['content']}\n"
    
    return context_block

rag_agent = LlmAgent(
    name="RAG_Assistant",
    model="gemini-3-flash-preview", 
    tools=[retrieve_and_rerank_knowledge], 
    instruction="""You are a professional research assistant. 
    1. Always use retrieve_and_rerank_knowledge to find facts.
    2. Answer ONLY based on the provided snippets.
    3. If the answer isn't in the snippets, say you don't know.
    4. Cite your sources clearly by mentioning the [Source: filename]."""
)

# 3. Create the Runner
session_service = InMemorySessionService()
runner = Runner(
    agent=rag_agent,
    session_service=session_service,
    app_name="agentic_rag_assistant"
)