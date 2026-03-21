# backend/app/main.py
import os
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from sse_starlette.sse import EventSourceResponse
from types import SimpleNamespace
import uuid
import asyncio
import json

load_dotenv()

# We import the runner we just fixed
from app.agent import runner
from app.vector_store import process_pdf, get_unique_documents

app = FastAPI()
APP_NAME, USER_ID = "agentic_rag_assistant", "user_001"

    
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None

@app.get("/")
def read_root():
    return {"status": "Backend is running"}


@app.post("/documents/upload")
async def upload(file: UploadFile = File(...)):
    # Save and Process PDF
    file_path = f"./data/{file.filename}"
    os.makedirs("./data", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(await file.read())
    
    num_chunks = process_pdf(file_path, file.filename)
    return {"message": "Success", "chunks": num_chunks}

@app.get("/documents")
async def list_documents():
    try:
        docs = get_unique_documents()
        # Return a list of objects so it's easier to expand later (e.g., adding upload date)
        return [{"name": doc} for doc in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest):
    async def event_generator():
        try:
            # 1. Start by sending a "Processing" status to the UI
            yield {"event": "status", "data": "Agent is thinking..."}

            # --- Step 1: Determine session ID ---
            session_id = request.session_id or str(uuid.uuid4())

            # --- Step 2: Ensure session exists ---
            session = await runner.session_service.get_session(
                app_name=APP_NAME,
                user_id=USER_ID,
                session_id=session_id
            ) if request.session_id else None

            if session is None:
                # Create session if it does not exist
                await runner.session_service.create_session(
                    app_name=APP_NAME,
                    user_id=USER_ID,
                    session_id=session_id
                )
                
            # 2. Define the sync runner
            def run_sync():
                # runner.run returns a generator
                return runner.run(
                    user_id=USER_ID,
                    new_message=SimpleNamespace(role="user", parts=[{"text": request.message}]),
                    session_id=session_id
                )

            # 3. Execute in thread
            stream = await asyncio.to_thread(run_sync)

            # 4. Iterate through chunks
            for chunk in stream:
                try:
                    if hasattr(chunk, 'content') and chunk.content.parts:
                        for part in chunk.content.parts:
                            
                            # 1. Handle the LLM's Text Response
                            if hasattr(part, 'text') and part.text:
                                yield {
                                    "event": "message",
                                    "data": json.dumps({"text": part.text})
                                }
                            
                            # 2. Handle the Tool's JSON Output (the Retrieval results)
                            if hasattr(part, 'function_response') and part.function_response:
                                resp_dict = part.function_response.response
                                
                                if 'result' in resp_dict:
                                    # Since your tool returns json.dumps(), 
                                    # resp_dict['result'] is a string containing JSON.
                                    # We parse it first to ensure we send clean JSON to the UI.
                                    try:
                                        tool_data = json.loads(resp_dict['result'])
                                        yield {
                                            "event": "sources",
                                            "data": json.dumps(tool_data)
                                        }
                                    except json.JSONDecodeError:
                                        # Fallback if the tool somehow returns a plain string
                                        yield {
                                            "event": "sources",
                                            "data": json.dumps({"raw_context": resp_dict['result']})
                                        }
                except Exception as e:
                    print(f"Parsing error: {e}")

        except Exception as e:
            print(f"Streaming Error: {e}")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_generator())