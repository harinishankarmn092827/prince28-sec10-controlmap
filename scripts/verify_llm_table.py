"""Verify that the LLM usage table exists in PostgreSQL."""

import asyncio

from sqlalchemy import text

from app.database.connection import engine


async def main() -> None:
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT column_name "
                    "FROM information_schema.columns "
                    "WHERE table_schema = current_schema() "
                    "AND table_name = 'llm_calls' "
                    "ORDER BY ordinal_position"
                )
            )
            columns = [row[0] for row in result.fetchall()]

        print("llm_calls exists:", bool(columns))
        print("Columns:", ", ".join(columns))

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
