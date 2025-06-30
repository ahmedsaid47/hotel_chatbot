# fine_tune.py

import os
import time
from openai import OpenAI
from config import load_api_key


def main() -> None:
    api_key = load_api_key()
    client = OpenAI(api_key=api_key)

    # 1) Eğitim dosyasını yükle
    train_path = "train.jsonl"
    if not os.path.isfile(train_path):
        raise FileNotFoundError(
            f"Eğitim dosyası '{train_path}' bulunamadı. "
            "Doğru dizinde misiniz?"
        )

    print("📤 Eğitim dosyası yükleniyor...")
    train = client.files.create(
        file=open(train_path, "rb"),
        purpose="fine-tune"
    )
    print(f"✅ Eğitim dosyası yüklendi: {train.id}, boyut: {train.bytes} bayt")

    # (İsteğe bağlı) Doğrulama seti
    # valid = client.files.create(
    #     file=open("validation.jsonl", "rb"),
    #     purpose="fine-tune"
    # )
    # print(f"Validation file: {valid.id}")

    # 2) Fine-tune işlemini başlat
    print("🎯 Fine-tune başlatılıyor...")
    job = client.fine_tuning.jobs.create(
        training_file=train.id,
        model="gpt-4o-mini-2024-07-18",
        n_epochs=4
        # learning_rate_multiplier=0.1,
        # batch_size=8
    )
    job_id = job.id
    print(f"✅ Fine-tune job oluşturuldu: {job_id}")

    # 3) Durumu takip et
    status = job.status
    print("Durum:", status)
    while status not in ("succeeded", "failed", "cancelled"):
        time.sleep(5)
        job = client.fine_tuning.jobs.retrieve(job_id)
        status = job.status
        print("Güncel durum:", status)

    if status != "succeeded":
        print("❌ Fine-tune başarısız oldu:", job)
        return

    ft_model = job.fine_tuned_model
    print(f"🎉 Fine-tune tamamlandı. Model adı: **{ft_model}**")

    # 4) Basit model kullanım örneği
    resp = client.chat.completions.create(
        model=ft_model,
        messages=[
            {"role": "system", "content": "Cullinan Belek konusunda bir asistansın."},
            {"role": "user", "content": "Lagoon odaları ne sunar?"}
        ],
        temperature=0.2
    )
    print("👁️ Demo yanıt:", resp.choices[0].message.content)


if __name__ == "__main__":
    main()
