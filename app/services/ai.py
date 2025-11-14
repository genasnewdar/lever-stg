import backoff
from openai import AsyncOpenAI, RateLimitError
import json
from typing import List
from aiolimiter import AsyncLimiter
import os

OPENAI_RATE_LIMIT = 10000
async_openai = AsyncOpenAI()
api_rate_limiter = AsyncLimiter(OPENAI_RATE_LIMIT, 60)



YESH_GRADER_ASSISTANT = "asst_LmZYVlO3RyVHuK2Amwo0KvWX"


@backoff.on_exception(backoff.expo, RateLimitError)
async def grade_yesh(input: str):
    async with api_rate_limiter:
        thread = await async_openai.beta.threads.create()

        await async_openai.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=input
        )
        run = await async_openai.beta.threads.runs.create_and_poll(
            thread_id=thread.id,
            assistant_id=YESH_GRADER_ASSISTANT
        )

        if run.status == 'completed': 
            messages = await async_openai.beta.threads.messages.list(
                thread_id=thread.id
            )
            return messages.data[0].content[0].text.value
        else:
            raise Exception(run.status)