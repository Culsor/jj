import time
import logging
from motor.motor_asyncio import AsyncIOMotorClient

import config

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, uri: str, db_name: str):
        self._client = AsyncIOMotorClient(uri)
        self.db = self._client[db_name]
        self.users = self.db.users
        self.stats = self.db.stats

    async def ensure_indexes(self):
        await self.users.create_index("user_id", unique=True)

    async def add_user(self, user_id: int, first_name: str = "", username: str = ""):
        existing = await self.users.find_one({"user_id": user_id})
        if existing:
            return False
        await self.users.insert_one({
            "user_id": user_id,
            "first_name": first_name,
            "username": username,
            "joined_at": time.time(),
            "conversions": 0,
        })
        return True

    async def is_user_exist(self, user_id: int) -> bool:
        return await self.users.find_one({"user_id": user_id}) is not None

    async def total_users_count(self) -> int:
        return await self.users.count_documents({})

    async def get_all_user_ids(self):
        cursor = self.users.find({}, {"user_id": 1})
        return [doc["user_id"] async for doc in cursor]

    async def remove_user(self, user_id: int):
        await self.users.delete_one({"user_id": user_id})

    async def increment_conversion(self, user_id: int, kind: str):
        await self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"conversions": 1, f"conversions_{kind}": 1}},
        )
        await self.stats.update_one(
            {"_id": "global"},
            {"$inc": {"total_conversions": 1, f"total_{kind}": 1}},
            upsert=True,
        )

    async def get_stats(self):
        doc = await self.stats.find_one({"_id": "global"})
        return doc or {"total_conversions": 0, "total_sticker_to_video": 0, "total_video_to_sticker": 0}


db = Database(config.MONGO_URI, config.MONGO_DB_NAME)
