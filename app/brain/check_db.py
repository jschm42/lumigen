
import sys
import os
sys.path.append(os.getcwd())

from sqlalchemy import select
from app.db.engine import SessionLocal
from app.db.models import EnhancementConfig

def check_config():
    with SessionLocal() as session:
        stmt = select(EnhancementConfig)
        results = session.scalars(stmt).all()
        print(f"Total enhancement configs: {len(results)}")
        for i, config in enumerate(results):
            print(f"Config {i}:")
            print(f"  ID: {config.id}")
            print(f"  Provider: {config.provider}")
            print(f"  Model: {config.model}")
            print(f"  Prompt length: {len(config.default_enhancement_prompt) if config.default_enhancement_prompt else 'None'}")
            print(f"  Prompt snippet: {config.default_enhancement_prompt[:50] if config.default_enhancement_prompt else 'None'}...")

if __name__ == "__main__":
    check_config()
