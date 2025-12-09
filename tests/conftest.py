"""Fixtures compartidas para tests."""

import pytest
from unittest.mock import MagicMock, Mock

from src.schemas.database_schema import ColumnSchema, DatabaseSchema, TableSchema


@pytest.fixture
def sample_schema():
    """Crea un schema de ejemplo para tests."""
    return DatabaseSchema(
        tables={
            "sales": TableSchema(
                name="sales",
                columns=[
                    ColumnSchema(name="id", type="INTEGER", nullable=False),
                    ColumnSchema(name="date", type="DATE", nullable=False),
                    ColumnSchema(name="revenue", type="DECIMAL(10,2)", nullable=False),
                ],
                primary_key=["id"],
            ),
            "products": TableSchema(
                name="products",
                columns=[
                    ColumnSchema(name="id", type="INTEGER", nullable=False),
                    ColumnSchema(name="name", type="VARCHAR(200)", nullable=False),
                ],
                primary_key=["id"],
            ),
        }
    )


@pytest.fixture
def mock_engine():
    """Crea un mock del SQLAlchemy Engine."""
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value.execute.return_value.fetchall.return_value = [
        ("1", "2024-01-01", "100.00"),
    ]
    return engine


@pytest.fixture
def mock_llm():
    """Crea un mock del ChatOpenAI."""
    llm = MagicMock()
    llm.invoke.return_value.content = "Respuesta del LLM"
    return llm


@pytest.fixture
def mock_agent():
    """Crea un mock del agente LangChain."""
    agent = MagicMock()
    agent.invoke.return_value = {
        "messages": [
            MagicMock(content="Respuesta del agente", role="assistant"),
        ]
    }
    return agent
