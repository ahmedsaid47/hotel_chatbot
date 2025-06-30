import openai
from config import load_api_key

def resolve_finetuned_model(ft_job_id: str) -> str:
    openai.api_key = load_api_key()
    job = openai.fine_tuning.jobs.retrieve(ft_job_id)
    if job.status != "succeeded":
        raise RuntimeError(f"Fine-tune hâlâ {job.status}")
    return job.fine_tuned_model
