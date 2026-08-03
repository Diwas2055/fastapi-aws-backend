"""
SQS service for message queue operations.
"""
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any
import json

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SQSService:
    """Service for interacting with AWS SQS."""
    
    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.queue_url = settings.SQS_QUEUE_URL
        self._client = None
    
    @asynccontextmanager
    async def get_client(self):
        """Get SQS client context manager."""
        async with self.session.client(
            "sqs",
            endpoint_url=settings.AWS_ENDPOINT_URL,
        ) as client:
            yield client
    
    async def create_queue(self, queue_name: str) -> Optional[str]:
        """Create an SQS queue."""
        try:
            async with self.get_client() as client:
                response = await client.create_queue(
                    QueueName=queue_name,
                    Attributes={
                        "VisibilityTimeout": str(settings.SQS_VISIBILITY_TIMEOUT),
                        "MessageRetentionPeriod": "1209600",  # 14 days
                        "ReceiveMessageWaitTimeSeconds": "20",  # Long polling
                    },
                )
            queue_url = response["QueueUrl"]
            logger.info("Queue created", queue=queue_name, url=queue_url)
            return queue_url
        except ClientError as e:
            logger.error("Failed to create queue", queue=queue_name, error=str(e))
            return None
    
    async def send_message(
        self,
        message_body: Dict[str, Any],
        delay_seconds: int = 0,
        message_attributes: Optional[Dict[str, Dict]] = None,
        queue_url: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Send a message to SQS queue."""
        queue = queue_url or self.queue_url
        if not queue:
            logger.error("No queue URL configured")
            return None
        
        try:
            async with self.get_client() as client:
                params = {
                    "QueueUrl": queue,
                    "MessageBody": json.dumps(message_body),
                }
                
                if delay_seconds > 0:
                    params["DelaySeconds"] = min(delay_seconds, 900)
                
                if message_attributes:
                    params["MessageAttributes"] = message_attributes
                
                response = await client.send_message(**params)
            
            logger.debug("Message sent", queue=queue, message_id=response["MessageId"])
            return {
                "message_id": response["MessageId"],
                "md5_of_body": response["MD5OfBody"],
                "sequence_number": response.get("SequenceNumber"),
            }
        except ClientError as e:
            logger.error("Failed to send message", queue=queue, error=str(e))
            return None
    
    async def send_batch(
        self,
        messages: List[Dict[str, Any]],
        queue_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send multiple messages in a batch (max 10)."""
        queue = queue_url or self.queue_url
        if not queue:
            logger.error("No queue URL configured")
            return {"successful": [], "failed": []}
        
        if len(messages) > 10:
            logger.warning("Batch size exceeds 10, truncating", count=len(messages))
            messages = messages[:10]
        
        entries = [
            {
                "Id": str(i),
                "MessageBody": json.dumps(msg.get("body", {})),
                "DelaySeconds": msg.get("delay", 0),
                "MessageAttributes": msg.get("attributes", {}),
            }
            for i, msg in enumerate(messages)
        ]
        
        try:
            async with self.get_client() as client:
                response = await client.send_message_batch(
                    QueueUrl=queue,
                    Entries=entries,
                )
            
            successful = len(response.get("Successful", []))
            failed = len(response.get("Failed", []))
            
            logger.info("Batch sent", queue=queue, successful=successful, failed=failed)
            return {
                "successful": response.get("Successful", []),
                "failed": response.get("Failed", []),
            }
        except ClientError as e:
            logger.error("Failed to send batch", queue=queue, error=str(e))
            return {"successful": [], "failed": []}
    
    async def receive_messages(
        self,
        max_messages: int = 10,
        wait_time_seconds: int = 20,
        queue_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Receive messages from SQS queue."""
        queue = queue_url or self.queue_url
        if not queue:
            logger.error("No queue URL configured")
            return []
        
        try:
            async with self.get_client() as client:
                response = await client.receive_message(
                    QueueUrl=queue,
                    MaxNumberOfMessages=min(max_messages, 10),
                    WaitTimeSeconds=wait_time_seconds,
                    MessageAttributeNames=["All"],
                )
            
            messages = response.get("Messages", [])
            logger.debug("Messages received", queue=queue, count=len(messages))
            return messages
        except ClientError as e:
            logger.error("Failed to receive messages", queue=queue, error=str(e))
            return []
    
    async def delete_message(
        self,
        receipt_handle: str,
        queue_url: Optional[str] = None,
    ) -> bool:
        """Delete a message from SQS queue."""
        queue = queue_url or self.queue_url
        if not queue:
            logger.error("No queue URL configured")
            return False
        
        try:
            async with self.get_client() as client:
                await client.delete_message(
                    QueueUrl=queue,
                    ReceiptHandle=receipt_handle,
                )
            logger.debug("Message deleted", queue=queue)
            return True
        except ClientError as e:
            logger.error("Failed to delete message", queue=queue, error=str(e))
            return False
    
    async def delete_messages_batch(
        self,
        receipt_handles: List[str],
        queue_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Delete multiple messages in a batch."""
        queue = queue_url or self.queue_url
        if not queue:
            logger.error("No queue URL configured")
            return {"successful": [], "failed": []}
        
        entries = [
            {"Id": str(i), "ReceiptHandle": handle}
            for i, handle in enumerate(receipt_handles)
        ]
        
        try:
            async with self.get_client() as client:
                response = await client.delete_message_batch(
                    QueueUrl=queue,
                    Entries=entries,
                )
            
            successful = len(response.get("Successful", []))
            failed = len(response.get("Failed", []))
            
            logger.debug("Batch deleted", queue=queue, successful=successful, failed=failed)
            return {
                "successful": response.get("Successful", []),
                "failed": response.get("Failed", []),
            }
        except ClientError as e:
            logger.error("Failed to delete batch", queue=queue, error=str(e))
            return {"successful": [], "failed": []}
    
    async def change_visibility(
        self,
        receipt_handle: str,
        visibility_timeout: int,
        queue_url: Optional[str] = None,
    ) -> bool:
        """Change message visibility timeout."""
        queue = queue_url or self.queue_url
        if not queue:
            return False
        
        try:
            async with self.get_client() as client:
                await client.change_message_visibility(
                    QueueUrl=queue,
                    ReceiptHandle=receipt_handle,
                    VisibilityTimeout=visibility_timeout,
                )
            return True
        except ClientError as e:
            logger.error("Failed to change visibility", error=str(e))
            return False
    
    async def get_queue_attributes(
        self,
        queue_url: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Get queue attributes."""
        queue = queue_url or self.queue_url
        if not queue:
            return None
        
        try:
            async with self.get_client() as client:
                response = await client.get_queue_attributes(
                    QueueUrl=queue,
                    AttributeNames=["All"],
                )
            return response.get("Attributes", {})
        except ClientError as e:
            logger.error("Failed to get queue attributes", error=str(e))
            return None


# Global SQS service instance
sqs_service = SQSService()