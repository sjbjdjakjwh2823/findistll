def handler(request):
    """
    Pure Vercel Python Function (No dependencies)
    """
    return {
        "statusCode": 200,
        "headers": { "Content-Type": "text/plain" },
        "body": "Hello from Pure Python! Deployment is working."
    }
