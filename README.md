# JarLight Unity Developer Workbench (ЛР 4)

Робоче місце Unity-розробника головоломки **JarLight** для 4 етапу ЖЦ ПЗ («Конструювання ПЗ»): поєднує векторну базу знань `jarlight-kb` (ЛР 2) та мультиагентну систему `jarlight-feature-sdlc` (ЛР 3) у веб-інтерфейсі Streamlit.

## Швидкий старт

```bash
uv sync --dev
cp .env.example .env   # вкажіть GEMINI_API_KEY і шляхи до сховища та ChromaDB
uv run pytest -v       # 13+ офлайн-тестів (без API)
uv run streamlit run streamlit_app.py
```

## Контейнерний запуск (крок 15)

```bash
docker build -t jarlight-workbench .
docker run -p 8501:8501 --env-file .env \
  -v /path/to/kb-vault:/vault \
  -v /path/to/chroma_data:/chroma_data \
  jarlight-workbench
```
