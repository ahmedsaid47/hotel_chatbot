import os, openai

API_FALLBACK_PATH = ".openai_key"

def load_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key.strip()
    if os.path.isfile(API_FALLBACK_PATH):
        with open(API_FALLBACK_PATH, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key
    raise ValueError("OPENAI_API_KEY eksik!")

def resolve_finetuned_model(ft_job_id: str) -> str:
    openai.api_key = load_api_key()
    job = openai.fine_tuning.jobs.retrieve(ft_job_id)
    if job.status != "succeeded":
        raise RuntimeError(f"Fine-tune hâlâ {job.status}")
    return job.fine_tuned_model
