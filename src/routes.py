from datetime import datetime
from typing import Annotated, Optional

from fastapi import APIRouter, FastAPI, Depends, HTTPException
from fastapi.security import APIKeyHeader
from rewire import simple_plugin
from rewire_fastapi import Dependable
from rewire_sqlmodel import transaction

from src import redis
from src.bot import parse_init_data
from src.models import User, ChallengeResponse, ChallengeElementResponse, CompleteChallengeRequest, CompleteChallengeResponse

plugin = simple_plugin()
router = APIRouter()


@Dependable
@transaction(1)
async def user_dependency(init_data_str: Annotated[str, Depends(APIKeyHeader(name='X-Init-Data'))]) -> Optional[User]:
    init_data = parse_init_data(init_data_str)
    if not init_data.user:
        raise HTTPException(status_code=401, detail='No user in the init data!')

    user = await User.get(init_data.user.id)
    if not user:
        raise HTTPException(status_code=401, detail='No user found for this init data!')

    return user


@router.get('/api/challenges', response_model=ChallengeResponse)
@transaction(1)
async def get_challenge(user: user_dependency.Result) -> ChallengeResponse:
    if not user.current_challenge:
        raise HTTPException(status_code=400, detail='No current challenge available!')

    return ChallengeResponse(
        **user.current_challenge.model_dump(),
        elements=[
            ChallengeElementResponse(**element.model_dump())
            for element in user.current_challenge.elements
        ]
    )


@router.post('/api/challenges/complete', response_model=CompleteChallengeResponse)
@transaction(1)
async def complete_challenge(request: CompleteChallengeRequest, user: user_dependency.Result):
    if not user.current_challenge:
        raise HTTPException(status_code=400, detail='No current challenge available!')

    placed_elements = {element.id: element for element in request.placed_elements}
    total_distance = 0.0

    for element in user.current_challenge.elements:
        if element.id not in placed_elements:
            continue

        user_element = placed_elements[element.id]
        distance_x = abs(user_element.x - element.target_x)
        distance_y = abs(user_element.y - element.target_y)
        total_distance += distance_x + distance_y

    MAX_ERROR = 1000
    error_rate = min(total_distance / MAX_ERROR, 1.0)
    success_rate = 1 - error_rate
    final_score = round(success_rate * 100, 1)

    last_score = await redis.get_user_challenge_score(user.id, user.current_challenge_id)
    if not last_score:
        user.last_completed_at = datetime.now()

    await redis.set_user_challenge_score(
        user_id=user.id,
        challenge_id=user.current_challenge_id,
        score=final_score
    )

    average_score = await redis.get_user_average_score(user.id)
    await redis.set_user_score(user.id, average_score)

    user.average_score = average_score
    user.add()

    return CompleteChallengeResponse(ok=True)


@plugin.setup()
def include_router(app: FastAPI):
    app.include_router(router)
