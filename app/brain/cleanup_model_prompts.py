
from app.db.engine import SessionLocal
from app.db.models import ModelConfig
from sqlalchemy import select, update

def cleanup():
    with SessionLocal() as session:
        # Find all model configs with the specific placeholder prompt
        # and set it to None so the global config takes over.
        placeholder = "Enhance prompt."
        
        stmt = select(ModelConfig).where(ModelConfig.enhancement_prompt == placeholder)
        models = session.scalars(stmt).all()
        
        if not models:
            print("No models found with the placeholder prompt.")
            return

        print(f"Found {len(models)} models with placeholder prompt. Cleaning up...")
        
        for model in models:
            print(f"Cleaning up model: {model.name} (ID: {model.id})")
            model.enhancement_prompt = None
            
        session.commit()
        print("Cleanup complete.")

if __name__ == "__main__":
    cleanup()
