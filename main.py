import asyncio
import json
import os
import tempfile

import redis.asyncio as redis
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import AsyncOpenAI
from pydantic import BaseModel

load_dotenv()
API_KEY = os.getenv('OPENAI_API_KEY')
client = AsyncOpenAI(api_key=API_KEY)

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


class SSEMessage(BaseModel):
    event: str
    data: dict


async def event_stream(session_id: str):
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(session_id)

    try:
        while True:
            message = await pubsub.get_message(
                ignore_subscribe_messages=True, timeout=30
            )
            if message and message['type'] == 'message':
                data = json.loads(message['data'])
                payload = f"event: {data['event']}\ndata: {json.dumps(data['data'])}\n\n"
                yield payload
            else:
                yield ': keep-alive\n\n'
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(session_id)
        await pubsub.aclose()


@app.get('/stream-events/{session_id}')
async def stream_events(session_id: str):
    return StreamingResponse(
        event_stream(session_id), media_type='text/event-stream'
    )


@app.post('/upload-audio/')
async def upload_audio(request: Request):
    session_id = request.query_params.get('session_id')
    from_lang = request.query_params.get('from_lang', 'ru')
    to_lang = request.query_params.get('to_lang', 'English')

    if not session_id:
        return {'error': 'Invalid session'}

    audio_bytes = await request.body()

    with tempfile.TemporaryDirectory() as tmpdir:
        # audio_path = os.path.join(tmpdir, "chunk.webm")
        audio_path = os.path.join('audio', 'chunk.webm')
        with open(audio_path, 'wb') as f:
            f.write(audio_bytes)

        with open(audio_path, 'rb') as f:
            try:
                # Распознавание речи
                transcript_response = await client.audio.transcriptions.create(
                    model='whisper-1', file=f, language=from_lang
                )
                transcript = transcript_response.text

                await redis_client.publish(
                    session_id,
                    json.dumps(
                        {'event': 'transcribed', 'data': {'text': transcript}}
                    ),
                )

                # Перевод
                prompt = f'Translate text to {to_lang}.'
                translation = await client.chat.completions.create(
                    model='gpt-4o',
                    messages=[
                        {'role': 'system', 'content': prompt},
                        {'role': 'user', 'content': transcript},
                    ],
                )
                translated_text = translation.choices[0].message.content

                await redis_client.publish(
                    session_id,
                    json.dumps(
                        {
                            'event': 'translated',
                            'data': {'translated_text': translated_text},
                        }
                    ),
                )

            except Exception as e:
                await redis_client.publish(
                    session_id,
                    json.dumps({'event': 'error', 'data': {'error': str(e)}}),
                )

    return {'status': 'ok'}


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host='0.0.0.0', port=8000)
