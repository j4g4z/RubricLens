import uvicorn
from backend.database import init_db

if __name__ == "__main__":
    init_db()
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
