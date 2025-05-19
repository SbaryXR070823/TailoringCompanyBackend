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
    async def update_one(self, collection_name: str, query: dict, update: dict, array_filters=None):
        logger.info(f"Updating document in {collection_name} with query: {query} and update: {update}")
        options = {
            "return_document": ReturnDocument.AFTER
        }
        
        if array_filters:
            options["array_filters"] = array_filters
            
        if update.get("$set"):
            update_doc = update
        else:
            update_doc = {"$set": update}
            
        updated_document = await self.db[collection_name].find_one_and_update(
            query,
            update_doc,
            **options
        )
        if updated_document:
            updated_document['_id'] = str(updated_document['_id'])  
        return updated_document

    async def delete_one(self, collection_name: str, query: dict):
        logger.info(f"Deleting document from {collection_name} with query: {query}")
        result = await self.db[collection_name].delete_one(query)
        return result.deleted_count

    async def find_with_conditions(self, collection_name: str, conditions: dict):
        logger.info(f"Finding documents in {collection_name} with conditions: {conditions}")
        documents = []
        try:
            cursor = self.db[collection_name].find(conditions)
            async for document in cursor:
                document['_id'] = str(document['_id'])
                documents.append(document)
                logger.debug(f"Retrieved document: {document['_id']}")
            
            logger.info(f"Retrieved {len(documents)} documents matching conditions from {collection_name}")
        except Exception as e:
            logger.error(f"Error retrieving documents with conditions from {collection_name}: {str(e)}")
        
        return documents

    async def find_by_id(self, collection_name: str, id: str):
        from bson import ObjectId
        logger.info(f"Finding document in {collection_name} by _id: {id}")
        try:
            document = await self.find_one(collection_name, {"_id": ObjectId(id)})
            return document
        except Exception as e:
            logger.error(f"Error finding document by id in {collection_name}: {str(e)}")
            return None