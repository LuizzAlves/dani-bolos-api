"""
Testes do repositório de pedidos.
"""

from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.orders import create_draft_order


@pytest.mark.asyncio
async def test_create_draft_order_generates_order_number():
    db = AsyncMock()
    lock_result = MagicMock()
    number_result = MagicMock()
    number_result.scalar_one.return_value = 1548
    db.execute.side_effect = [lock_result, number_result]
    db.add = MagicMock()

    order = await create_draft_order(db, uuid4(), uuid4())

    assert order.order_number == 1548
    assert db.execute.call_count == 2
    db.add.assert_called_once()
    db.flush.assert_awaited_once()
    db.refresh.assert_awaited_once_with(order)
