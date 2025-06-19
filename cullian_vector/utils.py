import os, json, openai
API_FALLBACK_PATH = ".openai_key"  # Dosya adı dilediğiniz gibi değişebilir


def load_api_key() -> str:
    """
    Önce ortam değişkeninden, bulamazsa yedek dosyadan OPENAI API anahtarını okur.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        return api_key.strip()

    if os.path.isfile(API_FALLBACK_PATH):
        with open(API_FALLBACK_PATH, "r", encoding="utf-8") as f:
            key = f.read().strip()
            if key:
                return key

    raise ValueError(
        "OPENAI_API_KEY bulunamadı. Ortam değişkeni atayın veya "
        f"{API_FALLBACK_PATH} dosyasına anahtarı yazın."
    )


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