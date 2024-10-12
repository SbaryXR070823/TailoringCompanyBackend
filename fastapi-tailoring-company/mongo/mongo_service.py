import motor.motor_asyncio
from pymongo import ReturnDocument 
import logging
from bson import ObjectId


logger = logging.getLogger(__name__)

class MongoDBService:
    def __init__(self, connection_string: str):
        self.client = motor.motor_asyncio.AsyncIOMotorClient(connection_string)
        self.db = self.client.get_default_database()  

    async def insert_one(self, collection_name: str, document: dict):
        logger.info(f"Inserting document into {collection_name}: {document}")
        result = await self.db[collection_name].insert_one(document)
        return str(result.inserted_id)

    async def find_one(self, collection_name: str, query: dict):
        logger.info(f"Finding one document in {collection_name} with query: {query}")
        document = await self.db[collection_name].find_one(query)
        if document:
            document['_id'] = str(document['_id']) 
        return document

    async def find_all(self, collection_name: str):
        logger.info(f"Finding all documents in {collection_name}")
        documents = []
        try:
            cursor = self.db[collection_name].find().limit(0) 
            async for document in cursor:
                document['_id'] = str(document['_id'])  
                documents.append(document)
                logger.debug(f"Retrieved document: {document['_id']}")
            
            logger.info(f"Retrieved {len(documents)} documents from {collection_name}")
        except Exception as e:
            logger.error(f"Error retrieving documents from {collection_name}: {str(e)}")
        
        return documents

    async def update_one(self, collection_name: str, query: dict, update: dict):
        logger.info(f"Updating document in {collection_name} with query: {query} and update: {update}")
        updated_document = await self.db[collection_name].find_one_and_update(
            query,
            {"$set": update},
            return_document=ReturnDocument.AFTER
        )
        if updated_document:
            updated_document['_id'] = str(updated_document['_id'])  
        return updated_document

    async def delete_one(self, collection_name: str, query: dict):
        logger.info(f"Deleting document from {collection_name} with query: {query}")
        result = await self.db[collection_name].delete_one(query)
        return result.deleted_count
