#!/usr/bin/env python3
"""
Startup script for the Wikidata Fetch Microservice.
"""
import uvicorn

from api.config import config

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=config.UVICORN_HOST,
        port=config.UVICORN_PORT,
        reload=True,
        log_level="info",
    )

