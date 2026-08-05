def handler(event, context):
    """Sample Lambda function for FastAPI AWS Backend."""
    import json

    # Log the incoming event
    print(f"Received event: {json.dumps(event)}")

    # Extract request details
    body = event.get("body", {})
    if isinstance(body, str):
        body = json.loads(body)

    action = body.get("action", "unknown")

    # Handle different actions
    if action == "process":
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "message": "Processing complete",
                "data": body.get("data", {}),
                "request_id": context.aws_request_id if context else "local"
            })
        }

    elif action == "health":
        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "healthy",
                "service": "fastapi-aws-backend-lambda",
                "version": "1.0.0"
            })
        }

    else:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": f"Unknown action: {action}",
                "valid_actions": ["process", "health"]
            })
        }
