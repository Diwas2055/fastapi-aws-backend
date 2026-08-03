"""
SNS service for pub/sub notifications.
"""
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

import aioboto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class SNSService:
    """Service for interacting with AWS SNS."""
    
    def __init__(self):
        self.session = aioboto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION,
        )
        self.topic_arn = settings.SNS_TOPIC_ARN
        self._client = None
    
    @asynccontextmanager
    async def get_client(self):
        """Get SNS client context manager."""
        async with self.session.client(
            "sns",
            endpoint_url=settings.AWS_ENDPOINT_URL,
        ) as client:
            yield client
    
    async def create_topic(self, name: str) -> Optional[str]:
        """Create an SNS topic."""
        try:
            async with self.get_client() as client:
                response = await client.create_topic(Name=name)
            topic_arn = response["TopicArn"]
            logger.info("Topic created", name=name, arn=topic_arn)
            return topic_arn
        except ClientError as e:
            logger.error("Failed to create topic", name=name, error=str(e))
            return None
    
    async def publish(
        self,
        message: str,
        subject: Optional[str] = None,
        message_attributes: Optional[Dict[str, Dict]] = None,
        topic_arn: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Publish a message to SNS topic."""
        topic = topic_arn or self.topic_arn
        if not topic:
            logger.error("No topic ARN configured")
            return None
        
        try:
            async with self.get_client() as client:
                params = {
                    "TopicArn": topic,
                    "Message": message,
                }
                
                if subject:
                    params["Subject"] = subject
                
                if message_attributes:
                    params["MessageAttributes"] = message_attributes
                
                response = await client.publish(**params)
            
            logger.debug("Message published", topic=topic, message_id=response["MessageId"])
            return {
                "message_id": response["MessageId"],
                "sequence_number": response.get("SequenceNumber"),
            }
        except ClientError as e:
            logger.error("Failed to publish message", topic=topic, error=str(e))
            return None
    
    async def publish_batch(
        self,
        messages: List[Dict[str, Any]],
        topic_arn: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Publish multiple messages (using batch if available)."""
        topic = topic_arn or self.topic_arn
        if not topic:
            return {"successful": [], "failed": []}
        
        results = {"successful": [], "failed": []}
        
        for i, msg in enumerate(messages):
            result = await self.publish(
                message=msg.get("message", ""),
                subject=msg.get("subject"),
                message_attributes=msg.get("attributes"),
                topic_arn=topic,
            )
            if result:
                results["successful"].append({"Id": str(i), **result})
            else:
                results["failed"].append({"Id": str(i)})
        
        return results
    
    async def subscribe(
        self,
        protocol: str,
        endpoint: str,
        topic_arn: Optional[str] = None,
        filter_policy: Optional[Dict] = None,
    ) -> Optional[str]:
        """Subscribe an endpoint to a topic."""
        topic = topic_arn or self.topic_arn
        if not topic:
            return None
        
        try:
            async with self.get_client() as client:
                params = {
                    "TopicArn": topic,
                    "Protocol": protocol,
                    "Endpoint": endpoint,
                }
                
                if filter_policy:
                    params["Attributes"] = {"FilterPolicy": str(filter_policy)}
                
                response = await client.subscribe(**params)
            
            subscription_arn = response["SubscriptionArn"]
            logger.info("Subscription created", protocol=protocol, endpoint=endpoint)
            return subscription_arn
        except ClientError as e:
            logger.error("Failed to subscribe", error=str(e))
            return None
    
    async def unsubscribe(self, subscription_arn: str) -> bool:
        """Unsubscribe from a topic."""
        try:
            async with self.get_client() as client:
                await client.unsubscribe(SubscriptionArn=subscription_arn)
            logger.info("Unsubscribed", subscription=subscription_arn)
            return True
        except ClientError as e:
            logger.error("Failed to unsubscribe", error=str(e))
            return False
    
    async def list_subscriptions(
        self,
        topic_arn: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List subscriptions for a topic."""
        topic = topic_arn or self.topic_arn
        if not topic:
            return []
        
        try:
            async with self.get_client() as client:
                response = await client.list_subscriptions_by_topic(TopicArn=topic)
            return response.get("Subscriptions", [])
        except ClientError as e:
            logger.error("Failed to list subscriptions", error=str(e))
            return []
    
    async def add_permission(
        self,
        label: str,
        aws_account_ids: List[str],
        actions: List[str],
        topic_arn: Optional[str] = None,
    ) -> bool:
        """Add permission for other AWS accounts to publish."""
        topic = topic_arn or self.topic_arn
        if not topic:
            return False
        
        try:
            async with self.get_client() as client:
                await client.add_permission(
                    TopicArn=topic,
                    Label=label,
                    AWSAccountId=aws_account_ids,
                    ActionName=actions,
                )
            logger.info("Permission added", label=label)
            return True
        except ClientError as e:
            logger.error("Failed to add permission", error=str(e))
            return False


# Global SNS service instance
sns_service = SNSService()