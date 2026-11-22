# WORKBENCH-CARD: Робоче місце Unity-розробника JarLight

## Ідентифікація
- **Автор:** Світенко Софія Миколаївна, група ПЗПІ-23-3, `sofiia.svitenko@nure.ua`
- **Репозиторій GitHub:** https://github.com/NureSvitenkoSofiia/lab04-workbench
- **Посилання на архів:** https://drive.google.com/drive/folders/1k8GXOSL3zOE6G7XA6qtZOdR0EipGEnlV

## 1. Мета й аудиторія
- **Етап ЖЦ ПЗ:** 4 — Конструювання ПЗ (*Implementation / Construction*).
- **Роль користувача:** Unity C# розробник 2D-головоломки **«JarLight»** (Unity ECS / Burst, `ScriptableObjects`, `EventBus`, гексагональна сітка, оптичні закони Снелла й спектр RGB).
- **Задача, яку прискорює робоче місце:** перетворення текстової задачі з GDD/беклогу на узгоджений пакет конструювання для Unity — оцінку готовності вимог, архітектурний план, C# ECS/Burst-сніпети, демонстраційний `level_preset.json`, автотести **Unity Test Framework (`FeatureTests.cs`)** та результати паралельного рев'ю оптики/балансу і Burst QA.
- **Очікуваний ефект:** швидке підхоплення оптичних інваріантів із бази знань `jarlight-kb`, відсіювання антипатернів Burst (`GameObject.Find`, `Resources.Load`, невалідний JSON) на ранніх гейтах та безпечний експорт артефактів до наступного етапу (PR Review / Unity QA).

## 2. Архітектура та шари
Застосунок побудовано за 4-шаровою архітектурою з повним відокремленням інтерфейсу від агентів та векторного сховища:

| Шар | Модуль(і) | Відповідальність |
| --- | --- | --- |
| Інтерфейс користувача | `streamlit_app.py` | 3 вкладки (`Питання до бази знань`, `Команда агентів`, `Історія і метрики`), живий лог із часом `[t с]` у `st.status`, `@st.cache_resource`, форми, ліміт `MAX_TEAM_RUNS = 10`, шлюз `Human-in-the-loop`. Не імпортує `app.*` чи `kb.*` напряму. |
| Сервісний шар | `workbench/service.py` (`WorkbenchService`), `workbench/runner.py` | Єдиний фасад бізнес-сценаріїв (`ask()`, `run_team()`, `save_result()`, `rate()`, `obsidian_url()`), переклад `[[Нотатка#Розділ]]` у `obsidian://`, виявлення непідтверджених цитат, синхронний міст до ADK (`run_agent()`). |
| Агенти та інтеграція БЗ | `app/kb_assistant.py`, `app/agent.py`, `app/nodes.py`, `app/agents.py`, `app/schemas.py` | Чат-асистент БЗ (`search_knowledge`, `read_note`) та МАС `jarlight_feature_sdlc` з детермінованим вузлом `retrieve_context`. |
| Дані, індекс та експорт | `kb/*`, `workbench/exporters.py`, `workbench/storage.py` | Векторний індекс ChromaDB (`jarlight_kb`, 50 фрагментів із 16 нотаток Obsidian), журнал SQLite (`workbench.db`), експорт `draft_pr.md`, `FeatureTests.cs`, `preset.json` та збереження в `Inbox/`. |

## 3. Інтеграція бази знань та МАС
- **Точка входу БЗ у МАС:** вузол-функція `retrieve_context` у `app/agent.py` (параметр `use_kb_agent=False` у `build_service()`), що шукає в `ChromaDB` (`gemini-embedding-001`, поріг `KB_MAX_DISTANCE = 0.35`, із фільтром чернеток `skip_inbox=True`) та передає `<fragment source="[[...]]" path="...">` у стан `kb_context`.
- **Повернення результатів (Human-in-the-loop):** погоджений Draft Feature PR може бути збережений у підпапку `Inbox/` сховища Obsidian лише через `WorkbenchService.save_result()` після заповнення імені рецензента та підтвердження чекбоксом. Існуючі нотатки ніколи не перезаписуються (`(2)`, `(3)`, ...), а вихід за межі сховища блокується (`ValueError`).
- **Перевірка джерел у чаті:** `WorkbenchService.ask()` звіряє всі згадки `[[Нотатка#Розділ]]` у відповіді моделі з тегами `source="[[...]]"` у реальних виводах інструментів (`invalid_citations`).

## 4. Експлуатаційні заходи безпеки
- **Мережева ізоляція:** `.streamlit/config.toml` фіксує `server.address = "localhost"`, `browser.gatherUsageStats = false`, `maxUploadSize = 5`, `client.toolbarMode = "viewer"`.
- **Захист від Prompt Injection:** інструкції `app/kb_assistant.py` явно наказують ігнорувати директиви всередині `<fragment>`/`<note>`; вхід і код проходять детермінований лінт `unity_policy_lint()`.
- **Обмеження ресурсів:** максимум 10 командних запусків за сесію (`MAX_TEAM_RUNS = 10`), максимум 3 чернетки в МАС (`MAX_ROUNDS = 3`), обмеження довжини коду (`MAX_CODE_LEN = 3800`) і відсутність перезапису файлів поза `Inbox/`.
- **Безпека секретів і контейнера:** `.env`, `workbench.db` та `eval/real_runs.csv` виключено в `.gitignore`; `Dockerfile` працює під непривілейованим `appuser` з окремими томами `/vault`, `/chroma_data`, `/data`.

## 5. Артефакти експорту та їх передача
1. **`{task_key}_draft_pr.md`** — повний звіт Draft Feature PR (прив'язка до систем Unity, C# ECS/ScriptableObject, результати лінту та рев'ю) для Stage 5 (PR Review / Tech Lead).
2. **`{task_key}_FeatureTests.cs`** — набір NUnit-тестів (`using NUnit.Framework;`, `[Test]`/`[UnityTest]`) для миттєвого перенесення в Unity Test Framework.
3. **`{task_key}_preset.json`** — валідний JSON пресет рівня або ScriptableObject для перевірки механіки в Unity Editor / QA.
4. **Нотатка в Obsidian `Inbox/`** — документація прийнятої фічі з YAML frontmatter (`status: draft`, `approved_by`, `source: "workbench run ..."`).

## 6. Результати перевірки та 10 реальних сесій
- **Автотести (`uv run pytest -v`):** `13 passed, 1 skipped` (`2.46 с`, усі 13 модульних, сервісних та `AppTest` UI-тестів пройдено без API через `ScriptedLlm` і `ToolCallingLlm`; Playwright у голому WSL пропущено через відсутність `libnspr4.so`).
- **Наскрізний Playwright E2E (`tests/e2e/test_playwright_demo.py`, крок 14):** пройдено (`1 passed in 4.13s`) із браузера Windows Chrome проти живого стенда `tests/demo_app.py`.
- **10 реальних запусків (`eval/run_real_sessions.py` на моделі `gemini-3.1-flash-lite`):**
  - 5 запитів до БЗ (`ask`) + 5 запусків команди (`run_team`: `JL-24`, `JL-27`, `JL-29`, `JL-31`, `JL-35`);
  - зведені метрики: `4.5` виклики LLM у середньому за запуск, `58.16 с` середній час, `73 412` токенів сумарно, частка позитивних оцінок `80%` (`8/10`; у 2 запитах до БЗ сервіс виявив `invalid_citations` при підстановці шляхів файлів замість назв нотаток; у командних запусках `JL-24` і `JL-27` — `approved`, `JL-31` і `JL-35` — `max_drafts`, `JL-29` зупинено на `needs_clarification`);
  - результати збережено у `eval/real_summary.json` (та `eval/real_runs.csv` локально поза git).

## 7. Юзабіліті-оцінювання (SUS)
- Утиліта розрахунку `eval/sus.py` перевірена модульним тестом `tests/unit/test_sus.py`.
- Проведено оцінювання за 3 сценаріями (`UC1`, `UC2`, `UC4`) серед 3 учасників (`eval/my_sus.csv`):
  - `R1`: `UC1 = 12.4 с`, `UC2 = 34.8 с`, `UC4 = 8.2 с`, **SUS = 100.0**;
  - `R2`: `UC1 = 15.1 с`, `UC2 = 41.2 с`, `UC4 = 11.5 с`, **SUS = 90.0**;
  - `R3`: `UC1 = 10.8 с`, `UC2 = 29.5 с`, `UC4 = 9.0 с`, **SUS = 97.5**;
  - **Середні показники:** `UC1 = 12.77 с`, `UC2 = 35.17 с`, `UC4 = 9.57 с`, **SUS mean = 95.8** (`uv run python -m eval.sus eval/my_sus.csv`).
- **Внесені UI-покращення за результатами оцінювання (`R1`, `R2`):**
  - додано кнопку **«Завантажити все (ZIP)»** (`workbench/exporters.py::to_bundle_zip()`), щоб вивантажувати `draft_pr.md`, `FeatureTests.cs` та `preset.json` одним кліком (`R1`);
  - додано візуальну шкалу прогресу `st.progress` за вузлами МАС усередині `st.status` (`R2`).

## 8. Запуск і відтворення
```bash
uv sync --dev
uv run streamlit run streamlit_app.py
uv run pytest -v
```
Контейнерний запуск (крок 15, non-root `appuser`):
```bash
docker build -t jarlight-workbench .
docker run -p 8501:8501 --env-file .env \
  -v /path/to/kb-vault:/vault \
  -v /path/to/chroma_data:/chroma_data \
  jarlight-workbench
```
