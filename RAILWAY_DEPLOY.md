# Railway Deployment Guide

## Environment Variables Setup

For this bot to work properly, you **must** set these environment variables in your Railway project:

1. Go to your project in Railway dashboard
2. Click on the "Variables" tab
3. Add the following variables:

```
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
```

## Common Issues

If you see this error:
```
ValueError: Missing required environment variables
```

It means you need to:
1. Double-check that you've added both environment variables
2. Make sure there are no typos in the variable names
3. Redeploy your project after adding the variables

## Steps After Changing Environment Variables

1. After adding or changing variables, click "Deploy" to restart your service
2. Check the deployment logs to verify the variables are being recognized 