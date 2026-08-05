const AWS = require('aws-sdk');

// Initialize AWS services
const s3 = new AWS.S3();
const dynamodb = new AWS.DynamoDB.DocumentClient();
const sqs = new AWS.SQS();
const sns = new AWS.SNS();

// Environment variables
const TABLE_NAME = process.env.DYNAMODB_TABLE || '';
const S3_BUCKET = process.env.S3_BUCKET || '';
const SQS_QUEUE_URL = process.env.SQS_QUEUE_URL || '';
const SNS_TOPIC_ARN = process.env.SNS_TOPIC_ARN || '';

/**
 * Health check endpoint
 */
exports.health = async (event) => {
  return {
    statusCode: 200,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*',
    },
    body: JSON.stringify({
      status: 'healthy',
      service: 'fastapi-aws-backend-serverless',
      timestamp: new Date().toISOString(),
    }),
  };
};

/**
 * Webhook handler for incoming HTTP requests
 */
exports.webhook = async (event) => {
  try {
    const body = JSON.parse(event.body || '{}');
    
    // Log the webhook
    console.log('Webhook received:', JSON.stringify(body));

    // Process webhook based on type
    const { type, payload } = body;

    if (type === 'item.created') {
      // Handle item creation event
      await dynamodb.put({
        TableName: TABLE_NAME,
        Item: {
          pk: `WEBHOOK#${Date.now()}`,
          sk: `EVENT#${type}`,
          ...payload,
          created_at: new Date().toISOString(),
        },
      }).promise();
    }

    return {
      statusCode: 200,
      headers: {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
      },
      body: JSON.stringify({
        message: 'Webhook processed successfully',
        type,
      }),
    };
  } catch (error) {
    console.error('Webhook processing error:', error);
    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Internal server error' }),
    };
  }
};

/**
 * Process S3 object creation events
 */
exports.processS3Event = async (event) => {
  try {
    const records = event.Records || [];
    const results = [];

    for (const record of records) {
      const bucket = record.s3.bucket.name;
      const key = decodeURIComponent(record.s3.object.key.replace(/\+/g, ' '));

      console.log(`Processing S3 object: s3://${bucket}/${key}`);

      // Get object metadata
      const headResponse = await s3.headObject({
        Bucket: bucket,
        Key: key,
      }).promise();

      // Store metadata in DynamoDB
      await dynamodb.put({
        TableName: TABLE_NAME,
        Item: {
          pk: `S3#${bucket}`,
          sk: `OBJECT#${key}`,
          size: headResponse.ContentLength,
          content_type: headResponse.ContentType,
          last_modified: headResponse.LastModified,
          created_at: new Date().toISOString(),
        },
      }).promise();

      results.push({ bucket, key, size: headResponse.ContentLength });
    }

    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'S3 events processed',
        count: results.length,
        results,
      }),
    };
  } catch (error) {
    console.error('S3 event processing error:', error);
    throw error;
  }
};

/**
 * Process SQS messages
 */
exports.processSQSMessage = async (event) => {
  try {
    const records = event.Records || [];
    const results = [];

    for (const record of records) {
      const messageId = record.messageId;
      const body = JSON.parse(record.body);

      console.log(`Processing SQS message ${messageId}:`, JSON.stringify(body));

      // Process message based on action
      if (body.action === 'process') {
        // Do processing...
        console.log('Processing action:', body.action);
      }

      results.push({ messageId, status: 'processed' });
    }

    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'SQS messages processed',
        count: results.length,
        results,
      }),
    };
  } catch (error) {
    console.error('SQS processing error:', error);
    throw error;
  }
};

/**
 * Process SNS notifications
 */
exports.processSNSMessage = async (event) => {
  try {
    const records = event.Records || [];
    const results = [];

    for (const record of records) {
      const message = JSON.parse(record.Sns.Message);
      const subject = record.Sns.Subject;
      const messageId = record.Sns.MessageId;

      console.log(`Processing SNS message ${messageId}:`, JSON.stringify(message));

      // Handle notification
      if (message.event === 'item.created') {
        // Trigger downstream processing
        await sqs.sendMessage({
          QueueUrl: SQS_QUEUE_URL,
          MessageBody: JSON.stringify({
            action: 'process_item',
            data: message,
          }),
        }).promise();
      }

      results.push({ messageId, subject, status: 'processed' });
    }

    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'SNS messages processed',
        count: results.length,
        results,
      }),
    };
  } catch (error) {
    console.error('SNS processing error:', error);
    throw error;
  }
};

/**
 * Scheduled cleanup job
 */
exports.scheduledCleanup = async (event) => {
  try {
    console.log('Running scheduled cleanup');

    // Example: Clean up old S3 objects
    const listResponse = await s3.listObjectsV2({
      Bucket: S3_BUCKET,
      Prefix: 'temp/',
    }).promise();

    const objectsToDelete = listResponse Contents?.filter(obj => 
      obj.LastModified < new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) // 7 days old
    ) || [];

    if (objectsToDelete.length > 0) {
      await s3.deleteObjects({
        Bucket: S3_BUCKET,
        Delete: {
          Objects: objectsToDelete.map(obj => ({ Key: obj.Key })),
        },
      }).promise();

      console.log(`Deleted ${objectsToDelete.length} old objects`);
    }

    return {
      statusCode: 200,
      body: JSON.stringify({
        message: 'Cleanup completed',
        deleted: objectsToDelete.length,
      }),
    };
  } catch (error) {
    console.error('Cleanup error:', error);
    throw error;
  }
};
