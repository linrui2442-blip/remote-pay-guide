from fastapi import FastAPI

app = FastAPI(title="Remote Pay Guide OS")


@app.get("/")
def root():
    return {
        "system": "Remote Pay Guide OS",
        "status": "running",
        "phase": "15.1",
        "modules": [
            "production",
            "publish",
            "analytics"
        ]
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }
