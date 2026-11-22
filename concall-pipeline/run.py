"""One command: python run.py  -> watcher + API + UI + WebSocket on http://localhost:8000"""
import uvicorn
if __name__ == "__main__":
    uvicorn.run("server.app:app", host="0.0.0.0", port=8000)
