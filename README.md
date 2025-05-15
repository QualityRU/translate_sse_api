# Live Bidirectional Speech Translation
Веб-приложение для двустороннего перевода речи в реальном времени между двумя пользователями. Поддерживает распознавание речи, перевод и отображение результатов для обеих сторон через микрофон, WebSocket/HTTP и Server-Sent Events (SSE).

## Возможности
- Двусторонняя передача речи: A ↔ B
- Распознавание речи с помощью Whisper
- Перевод с помощью OpenAI GPT / OpenAI Translate
- Интерфейс с двумя независимыми потоками
- Поддержка различных языков (например, ru, en, и др.)
## Стек
- Frontend: HTML + JavaScript (MediaRecorder + SSE)
- Backend: FastAPI, Whisper, OpenAI, uvicorn
- Протоколы: SSE, POST (audio/webm)
