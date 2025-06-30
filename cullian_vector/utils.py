import json, openai
from config import load_api_key


def resolve_finetuned_model(ft_job_id: str) -> str:
    """
    Fine-tune işi tamamlandıysa, nihai model adını döndürür.
    openai>=1.0.0+ sürümleriyle uyumlu.
    """
    openai.api_key = load_api_key()

    # Yeni API: fine_tuning.jobs.retrieve
    job = openai.fine_tuning.jobs.retrieve(ft_job_id)

    if job.status != "succeeded":
        raise RuntimeError(f"Fine-tune işi henüz tamamlanmamış: {job.status}")

    return job.fine_tuned_model
