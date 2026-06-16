"""
Testes para o repositório de bolos pronta entrega (ReadyCake).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

from app.models import ReadyCake
from app.repositories.ready_cakes import (
    get_available_ready_cakes,
    get_all_ready_cakes,
    get_ready_cake_by_id,
    create_ready_cake,
    update_ready_cake,
    delete_ready_cake,
)


@pytest.mark.asyncio
async def test_get_available_ready_cakes():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_cakes = [
        ReadyCake(id=1, flavor="Bolo 1", available=True),
        ReadyCake(id=2, flavor="Bolo 2", available=True),
    ]
    mock_result.scalars.return_value.all.return_value = mock_cakes
    db.execute.return_value = mock_result

    result = await get_available_ready_cakes(db)

    assert len(result) == 2
    assert result[0].flavor == "Bolo 1"
    assert result[1].flavor == "Bolo 2"
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_all_ready_cakes():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_cakes = [
        ReadyCake(id=2, flavor="Bolo 2", available=False),
        ReadyCake(id=1, flavor="Bolo 1", available=True),
    ]
    mock_result.scalars.return_value.all.return_value = mock_cakes
    db.execute.return_value = mock_result

    result = await get_all_ready_cakes(db)

    assert len(result) == 2
    assert result[0].flavor == "Bolo 2"
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_ready_cake_by_id():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_cake = ReadyCake(id=1, flavor="Bolo 1", available=True)
    mock_result.scalar_one_or_none.return_value = mock_cake
    db.execute.return_value = mock_result

    result = await get_ready_cake_by_id(db, 1)

    assert result is not None
    assert result.flavor == "Bolo 1"
    db.execute.assert_called_once()


@pytest.mark.asyncio
async def test_create_ready_cake():
    db = AsyncMock()
    db.add = MagicMock()

    cake = await create_ready_cake(db, "Chocolate", "Descrição", 85.00)

    assert cake.flavor == "Chocolate"
    assert cake.description == "Descrição"
    assert cake.price == Decimal("85")
    db.add.assert_called_once_with(cake)
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_update_ready_cake():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    db.execute.return_value = mock_result

    success = await update_ready_cake(db, 1, {"flavor": "Novo Chocolate", "price": 90.00})

    assert success is True
    db.execute.assert_called_once()
    db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_ready_cake():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.rowcount = 1
    db.execute.return_value = mock_result

    success = await delete_ready_cake(db, 1)

    assert success is True
    db.execute.assert_called_once()
    db.flush.assert_awaited_once()
