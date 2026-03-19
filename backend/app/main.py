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

load_dotenv()

# We import the runner we just fixed
from app.agent import runner
from app.vector_store import process_pdf

app = FastAPI()
APP_NAME, USER_ID = "agentic_rag_assistant", "user_001"

    
# Enable CORS so your Angular frontend (4200) can talk to FastAPI (8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, change this to your frontend URL
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
                # 1. Extract FINAL ANSWER Text
                # Path: chunk -> content -> parts -> [0] -> text
                try:
                    if hasattr(chunk, 'content') and chunk.content.parts:
                        for part in chunk.content.parts:
                            if hasattr(part, 'text') and part.text:
                                yield {
                                    "event": "message",
                                    "data": part.text
                                }
                            
                    # 2. Extract TRACEABILITY (Requirement 8)
                    # Path: chunk -> content -> parts -> [0] -> function_response
                    if hasattr(part, 'function_response') and part.function_response:
                        resp_dict = part.function_response.response
                        # If your tool returned the string context, we send it to the UI
                        if 'result' in resp_dict:
                            yield {
                                "event": "sources",
                                "data": resp_dict['result']
                            }
                except Exception as e:
                    print(f"Parsing error: {e}")

        except Exception as e:
            print(f"Streaming Error: {e}")
            yield {"event": "error", "data": str(e)}

    return EventSourceResponse(event_generator())

# @app.post("/chat")
# async def chat(request: ChatRequest):
    # async def event_generator():
    #     try:
    #         # --- Step 1: Determine session ID ---
    #         session_id = request.session_id or str(uuid.uuid4())

    #         # --- Step 2: Ensure session exists ---
    #         session = await runner.session_service.get_session(
    #             app_name=APP_NAME,
    #             user_id=USER_ID,
    #             session_id=session_id
    #         ) if request.session_id else None

    #         if session is None:
    #             # Create session if it does not exist
    #             await runner.session_service.create_session(
    #                 app_name=APP_NAME,
    #                 user_id=USER_ID,
    #                 session_id=session_id
    #             )

    #         # --- Step 3: Build the message object ---
    #         new_message = SimpleNamespace(
    #             role="user",
    #             parts=[{"text": request.message}]
    #         )

    #         # --- Step 4: Run the blocking runner.run() safely in a thread ---
    #         def run_sync():
    #             return runner.run(
    #                 user_id=USER_ID,
    #                 new_message=new_message,
    #                 session_id=session_id
    #             )

    #         stream = await asyncio.to_thread(run_sync)

    #         # --- Step 5: Yield each chunk for SSE ---
    #         for chunk in stream:
    #             if hasattr(chunk, "text") and chunk.text:
    #                 yield f"data: {chunk.text}\n\n"

    #     except Exception as e:
    #         print(f"Streaming Error: {e}")
    #         yield f"data: [ERROR]: {str(e)}\n\n"

    # return EventSourceResponse(event_generator())