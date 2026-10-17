import asyncio
from unittest.mock import AsyncMock, patch
from app.detail_director import heuristic_recommendation, recommend_detail


def test_heuristic_routes_clothing_and_damaged_surfaces():
    clothing = heuristic_recommendation('worn denim jacket and torn cloth pants')
    assert clothing['profile'] == 'clothing'
    damaged = heuristic_recommendation('rusted, cracked and weathered industrial robot')
    assert damaged['profile'] == 'damaged'


def test_ai_director_falls_back_when_local_model_is_unavailable():
    with patch('app.detail_director.select_local_model', new=AsyncMock(side_effect=RuntimeError('offline'))):
        result = asyncio.run(recommend_detail('realistic zombie with torn clothing and weathered skin'))
    assert result['profile'] in {'organic', 'skin_pores', 'clothing', 'fabric', 'damaged', 'hard_surface'}
    assert result['source'] == 'heuristic_fallback'
    assert result['free_local_only'] is True
