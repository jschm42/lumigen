
from app.db.engine import SessionLocal
from app.db.models import ModelConfig, EnhancementConfig
from sqlalchemy import select

def check():
    with SessionLocal() as session:
        print("--- Enhancement Config ---")
        cfg = session.scalar(select(EnhancementConfig))
        if cfg:
            print(f"ID: {cfg.id}")
            print(f"Provider: {cfg.provider}")
            print(f"Model: {cfg.model}")
            print(f"Prompt: {cfg.default_enhancement_prompt}")
        else:
            print("No global enhancement config.")

        print("\n--- Model Configs ---")
        models = session.scalars(select(ModelConfig)).all()
        for m in models:
            print(f"ID: {m.id}, Name: {m.name}, Prompt: {m.enhancement_prompt}")

if __name__ == "__main__":
    check()
