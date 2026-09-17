from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession as SQLModelAsyncSession

from src.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)

# Schema is owned by Alembic migrations (see migrations/) - run
# `alembic upgrade head` to create/update tables. The app no longer
# creates tables on startup; a schema drift between the migrations and
# what create_all() would produce could otherwise go unnoticed.


async def get_session() -> AsyncSession:
    # expire_on_commit=False: without this, committing anywhere mid-request
    # (e.g. saving a payment reference before calling out to Paystack) expires
    # every object the session is holding, and a later attribute access tries
    # to lazy-load it - which async SQLAlchemy cannot do outside a greenlet
    # and raises MissingGreenlet.
    async with SQLModelAsyncSession(engine, expire_on_commit=False) as session:
        yield session
