"""
DynamoDB service for NoSQL operations.
"""
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4

import aioboto3
from botocore.exceptions import ClientError
from boto3.dynamodb.conditions import Key, Attr

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class DynamoDBService:
    """Service for interacting with AWS DynamoDB."""
    
    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.table_name = settings.DYNAMODB_TABLE
        self._table = None
    
    @asynccontextmanager
    async def get_table(self):
        """Get DynamoDB table resource."""
        async with self.session.resource(
            "dynamodb",
            endpoint_url=settings.DYNAMODB_ENDPOINT_URL or settings.AWS_ENDPOINT_URL,
        ) as dynamodb:
            yield await dynamodb.Table(self.table_name)
    
    async def create_table(self) -> bool:
        """Create DynamoDB table if it doesn't exist."""
        try:
            async with self.session.resource(
                "dynamodb",
                endpoint_url=settings.DYNAMODB_ENDPOINT_URL or settings.AWS_ENDPOINT_URL,
            ) as dynamodb:
                # Check if table exists
                existing_tables = []
                async for table in dynamodb.tables.all():
                    existing_tables.append(table.name)
                
                if self.table_name in existing_tables:
                    logger.info("Table already exists", table=self.table_name)
                    return True
                
                # Create table with PK/SK pattern
                table = await dynamodb.create_table(
                    TableName=self.table_name,
                    KeySchema=[
                        {"AttributeName": "pk", "KeyType": "HASH"},
                        {"AttributeName": "sk", "KeyType": "RANGE"},
                    ],
                    AttributeDefinitions=[
                        {"AttributeName": "pk", "AttributeType": "S"},
                        {"AttributeName": "sk", "AttributeType": "S"},
                        {"AttributeName": "gsi1pk", "AttributeType": "S"},
                        {"AttributeName": "gsi1sk", "AttributeType": "S"},
                    ],
                    GlobalSecondaryIndexes=[
                        {
                            "IndexName": "GSI1",
                            "KeySchema": [
                                {"AttributeName": "gsi1pk", "KeyType": "HASH"},
                                {"AttributeName": "gsi1sk", "KeyType": "RANGE"},
                            ],
                            "Projection": {"ProjectionType": "ALL"},
                            "ProvisionedThroughput": {
                                "ReadCapacityUnits": 5,
                                "WriteCapacityUnits": 5,
                            },
                        }
                    ],
                    BillingMode="PAY_PER_REQUEST",
                )
                
                await table.wait_until_exists()
                logger.info("Table created", table=self.table_name)
                return True
                
        except ClientError as e:
            logger.error("Failed to create table", error=str(e))
            return False
    
    async def put_item(
        self,
        pk: str,
        sk: str,
        data: Dict[str, Any],
        gsi1pk: Optional[str] = None,
        gsi1sk: Optional[str] = None,
    ) -> bool:
        """Put an item in DynamoDB."""
        item = {
            "pk": pk,
            "sk": sk,
            "data": data,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        if gsi1pk:
            item["gsi1pk"] = gsi1pk
        if gsi1sk:
            item["gsi1sk"] = gsi1sk
        
        try:
            async with self.get_table() as table:
                await table.put_item(Item=item)
            logger.debug("Item put", pk=pk, sk=sk)
            return True
        except ClientError as e:
            logger.error("Failed to put item", pk=pk, sk=sk, error=str(e))
            return False
    
    async def get_item(self, pk: str, sk: str) -> Optional[Dict[str, Any]]:
        """Get an item from DynamoDB."""
        try:
            async with self.get_table() as table:
                response = await table.get_item(Key={"pk": pk, "sk": sk})
                return response.get("Item")
        except ClientError as e:
            logger.error("Failed to get item", pk=pk, sk=sk, error=str(e))
            return None
    
    async def update_item(
        self,
        pk: str,
        sk: str,
        data: Dict[str, Any],
    ) -> bool:
        """Update an item in DynamoDB."""
        try:
            async with self.get_table() as table:
                await table.update_item(
                    Key={"pk": pk, "sk": sk},
                    UpdateExpression="SET #data = :data, updated_at = :updated",
                    ExpressionAttributeNames={"#data": "data"},
                    ExpressionAttributeValues={
                        ":data": data,
                        ":updated": datetime.utcnow().isoformat(),
                    },
                )
            logger.debug("Item updated", pk=pk, sk=sk)
            return True
        except ClientError as e:
            logger.error("Failed to update item", pk=pk, sk=sk, error=str(e))
            return False
    
    async def delete_item(self, pk: str, sk: str) -> bool:
        """Delete an item from DynamoDB."""
        try:
            async with self.get_table() as table:
                await table.delete_item(Key={"pk": pk, "sk": sk})
            logger.debug("Item deleted", pk=pk, sk=sk)
            return True
        except ClientError as e:
            logger.error("Failed to delete item", pk=pk, sk=sk, error=str(e))
            return False
    
    async def query_items(
        self,
        pk: str,
        sk_prefix: Optional[str] = None,
        limit: int = 100,
        last_evaluated_key: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Query items by partition key."""
        try:
            async with self.get_table() as table:
                key_condition = Key("pk").eq(pk)
                if sk_prefix:
                    key_condition &= Key("sk").begins_with(sk_prefix)
                
                params = {
                    "KeyConditionExpression": key_condition,
                    "Limit": limit,
                    "ScanIndexForward": True,
                }
                
                if last_evaluated_key:
                    params["ExclusiveStartKey"] = last_evaluated_key
                
                response = await table.query(**params)
                
                return {
                    "items": response.get("Items", []),
                    "last_evaluated_key": response.get("LastEvaluatedKey"),
                    "count": response.get("Count", 0),
                }
        except ClientError as e:
            logger.error("Failed to query items", pk=pk, error=str(e))
            return {"items": [], "last_evaluated_key": None, "count": 0}
    
    async def query_gsi1(
        self,
        gsi1pk: str,
        gsi1sk_prefix: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query items using GSI1."""
        try:
            async with self.get_table() as table:
                key_condition = Key("gsi1pk").eq(gsi1pk)
                if gsi1sk_prefix:
                    key_condition &= Key("gsi1sk").begins_with(gsi1sk_prefix)
                
                response = await table.query(
                    IndexName="GSI1",
                    KeyConditionExpression=key_condition,
                    Limit=limit,
                    ScanIndexForward=True,
                )
                
                return response.get("Items", [])
        except ClientError as e:
            logger.error("Failed to query GSI1", gsi1pk=gsi1pk, error=str(e))
            return []
    
    async def scan_items(
        self,
        filter_expression: Optional[Any] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Scan items with optional filter."""
        try:
            async with self.get_table() as table:
                params = {"Limit": limit}
                if filter_expression:
                    params["FilterExpression"] = filter_expression
                
                response = await table.scan(**params)
                return response.get("Items", [])
        except ClientError as e:
            logger.error("Failed to scan items", error=str(e))
            return []
    
    async def batch_write(self, items: List[Dict[str, Any]]) -> bool:
        """Batch write items to DynamoDB."""
        if not items:
            return True
        
        try:
            async with self.get_table() as table:
                async with table.batch_writer() as batch:
                    for item in items:
                        await batch.put_item(Item=item)
            logger.info("Batch write completed", count=len(items))
            return True
        except ClientError as e:
            logger.error("Failed batch write", error=str(e))
            return False


# Global DynamoDB service instance
dynamodb_service = DynamoDBService()