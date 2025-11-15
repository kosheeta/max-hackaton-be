from typing import Dict, Optional, List

from pydantic import BaseModel
from redis.asyncio import Redis
from rewire import simple_plugin, DependenciesModule, config

plugin = simple_plugin()


@config
class Config(BaseModel):
    url: str


@plugin.setup()
async def create_redis() -> Redis:
    return Redis.from_url(Config.url, decode_responses=True)


def get_redis() -> Redis:
    return DependenciesModule.get().resolve(Redis)


async def set_user_score(user_id: int, score: float):
    redis = get_redis()
    await redis.zadd('user:ratings', {str(user_id): score})


async def get_user_place(user_id: int) -> Optional[int]:
    redis = get_redis()
    return await redis.zrevrank('user:ratings', user_id)


async def get_scores_leaderboard(limit: int = 10) -> Dict[int, float]:
    redis = get_redis()
    user_scores = await redis.zrevrange('user:ratings', 0, limit - 1, withscores=True)
    return {int(user_id): float(score) for user_id, score in user_scores}


async def set_user_challenge_score(user_id: int, challenge_id: str, score: float):
    redis = get_redis()
    await redis.hset(f'user:{user_id}:ratings', challenge_id, str(score))


async def get_user_challenge_score(user_id: int, challenge_id: str) -> Optional[float]:
    redis = get_redis()
    score = await redis.hget(f'user:{user_id}:ratings', challenge_id)
    return float(score) if score else None


async def get_user_completed_challenges(user_id: int) -> List[str]:
    redis = get_redis()
    return await redis.hkeys(f'user:{user_id}:ratings')


async def get_user_average_score(user_id: int) -> float:
    redis = get_redis()
    user_scores = await redis.hvals(f'user:{user_id}:ratings')

    scores = [float(score) for score in user_scores]
    return round(sum(scores) / len(scores), 1) if user_scores else 0.0


async def set_user_mailing_sent(user_id: int, mailing_id: int) -> bool:
    redis = get_redis()
    was_sent = await redis.set(f'user:{user_id}:mailing:{mailing_id}', '1', get=True)
    return was_sent == '1'
