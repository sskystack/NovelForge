import os

import uvicorn

from novelforge.database import Base, create_database_engine
from novelforge.projects import models_registry  # noqa: F401
from novelforge.main import app

if __name__ == "__main__":
    database_url = os.environ.get("DATABASE_URL", "sqlite:///novelforge.db")
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()
    uvicorn.run(app, host="127.0.0.1", port=8765, log_config=None, access_log=False)
