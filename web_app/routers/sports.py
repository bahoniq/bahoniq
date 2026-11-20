"""FastAPI-роутер для модуля «BahonIQ Sports»."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from starlette.concurrency import run_in_threadpool

from web_app.modules.sports.service import SportsService

router = APIRouter(prefix="/api/sports", tags=["sports"])
_service = SportsService()


@router.get("/overview")
async def sports_overview(force: bool = Query(False)):
    """Возвращает сводку для главного экрана Sports Hub."""
    return await run_in_threadpool(_service.get_overview, force)


@router.get("/football/{club_id}")
async def sports_football_club(club_id: str, force: bool = Query(False)):
    """Возвращает расписание, таблицу, состав и новости по выбранному клубу."""
    try:
        return await run_in_threadpool(_service.get_football_club, club_id, force)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/f1")
async def sports_f1(force: bool = Query(False)):
    """Возвращает календарь, зачёты и результаты Formula 1."""
    return await run_in_threadpool(_service.get_f1_overview, force)


@router.get("/ufc")
async def sports_ufc(force: bool = Query(False)):
    """Возвращает турнир UFC, кард, рейтинги и новости."""
    return await run_in_threadpool(_service.get_ufc_overview, force)


@router.get("/news")
async def sports_news(force: bool = Query(False)):
    """Возвращает агрегированный русскоязычный новостной центр BahonIQ Sports."""
    return await run_in_threadpool(_service.get_news_center, force)


@router.get("/profile")
async def sports_profile(name: str = Query(..., min_length=2), force: bool = Query(False)):
    """Возвращает профиль спортсмена или команды из Wikipedia REST API."""
    return await run_in_threadpool(_service.get_profile, name, force)


@router.get("/football/{club_id}/match/{event_id}")
async def sports_football_match(club_id: str, event_id: str, force: bool = Query(False)):
    """Возвращает детальную карточку футбольного матча (составы, события, статистика)."""
    try:
        return await run_in_threadpool(_service.get_match_detail, club_id, event_id, force)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/football/{club_id}/player/{player_id}")
async def sports_football_player(club_id: str, player_id: str, force: bool = Query(False)):
    """Возвращает профиль футболиста (статистика сезона + фото/биография)."""
    try:
        return await run_in_threadpool(_service.get_football_player_profile, club_id, player_id, force)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/f1/round/{round_num}")
async def sports_f1_round(round_num: int, force: bool = Query(False)):
    """Возвращает результаты гонки, квалификации и спринта для этапа Formula 1."""
    return await run_in_threadpool(_service.get_f1_round, round_num, force)


@router.get("/f1/driver/{driver_id}")
async def sports_f1_driver(driver_id: str, force: bool = Query(False)):
    """Возвращает профиль гонщика Formula 1."""
    return await run_in_threadpool(_service.get_f1_driver, driver_id, force)


@router.get("/f1/constructor/{constructor_id}")
async def sports_f1_constructor(constructor_id: str, force: bool = Query(False)):
    """Возвращает профиль команды Formula 1."""
    return await run_in_threadpool(_service.get_f1_constructor, constructor_id, force)


@router.get("/ufc/fighter")
async def sports_ufc_fighter(
    fighter_id: str = Query(""),
    name: str = Query(""),
    force: bool = Query(False),
):
    """Возвращает профиль бойца UFC."""
    if not fighter_id and not name:
        raise HTTPException(status_code=400, detail="Укажите fighter_id или name")
    return await run_in_threadpool(_service.get_ufc_fighter, fighter_id, name, force)
