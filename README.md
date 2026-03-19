cd Documents/Techo/Assignments/agentic-rag-assistant/backend
source venv/bin/activate
uvicorn app.main:app --reload

python3.11 -m venv venv
pip freeze > requirements.txt
pip install chromadb
pip install python-dotenv
 

