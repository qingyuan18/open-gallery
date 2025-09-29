# AWS Bedrock Integration Setup

This document explains how to set up and use AWS Bedrock models in the Jaaz application.

## Prerequisites

1. **AWS Account**: You need an AWS account with access to Amazon Bedrock
2. **AWS Credentials**: Configure AWS credentials on your system
3. **Model Access**: Request access to the Bedrock models you want to use

## AWS Credentials Setup

### Option 1: AWS CLI Configuration
```bash
aws configure
```
Enter your AWS Access Key ID, Secret Access Key, and default region.

### Option 2: Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_DEFAULT_REGION=us-east-1
```

### Option 3: IAM Roles (for EC2/ECS)
If running on AWS infrastructure, use IAM roles for secure access.

## Required AWS Permissions

Your AWS user/role needs the following permissions:
```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": [
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream",
                "bedrock:Converse",
                "bedrock:ConverseStream",
                "bedrock:ListFoundationModels"
            ],
            "Resource": "*"
        }
    ]
}
```

## Model Access Request

1. Go to the AWS Bedrock console
2. Navigate to "Model access" in the left sidebar
3. Request access to the models you want to use:
   - **Claude 3.5 Sonnet**: `anthropic.claude-3-5-sonnet-20241022-v2:0`
   - **Claude 3.5 Haiku**: `anthropic.claude-3-5-haiku-20241022-v1:0`
   - **Claude 3 Opus**: `anthropic.claude-3-opus-20240229-v1:0`
   - **Titan Text**: `amazon.titan-text-premier-v1:0`
   - **Llama models**: Various Meta Llama models
   - **Mistral models**: Various Mistral models

## Application Configuration

### 1. Install Dependencies
```bash
cd server
pip install boto3 botocore
```

### 2. Configure Bedrock in the Application

Create or update your `user_data/config.toml` file:

```toml
[bedrock]
region = "us-west-2"  # Your preferred AWS region
# api_key is not needed for Bedrock - uses AWS credentials

[bedrock.models]
"us.anthropic.claude-3-7-sonnet-20250219-v1:0" = { type = "text" }
"us.anthropic.claude-3-5-sonnet-20241022-v2:0" = { type = "text" }
"us.anthropic.claude-3-5-haiku-20241022-v1:0" = { type = "text" }
"us.anthropic.claude-3-opus-20240229-v1:0" = { type = "text" }
"us.amazon.titan-text-premier-v1:0" = { type = "text" }
"us.meta.llama3-2-90b-instruct-v1:0" = { type = "text" }
```

### 3. Start the Application

```bash
# Start the backend
cd server
python main.py --port 57988

# Start the frontend (in another terminal)
cd react
npm run dev
```

The application will now listen on `0.0.0.0:57988` for the backend and `0.0.0.0:5174` for the frontend.

## Available Models

The integration includes support for the following model families:

### Anthropic Claude Models
- `anthropic.claude-3-5-sonnet-20241022-v2:0` - Latest Claude 3.5 Sonnet
- `anthropic.claude-3-5-sonnet-20240620-v1:0` - Previous Claude 3.5 Sonnet
- `anthropic.claude-3-5-haiku-20241022-v1:0` - Claude 3.5 Haiku
- `anthropic.claude-3-opus-20240229-v1:0` - Claude 3 Opus
- `anthropic.claude-3-sonnet-20240229-v1:0` - Claude 3 Sonnet
- `anthropic.claude-3-haiku-20240307-v1:0` - Claude 3 Haiku

### Amazon Titan Models
- `amazon.titan-text-premier-v1:0` - Titan Text Premier
- `amazon.titan-text-express-v1` - Titan Text Express
- `amazon.titan-text-lite-v1` - Titan Text Lite

### Meta Llama Models
- `meta.llama3-2-90b-instruct-v1:0` - Llama 3.2 90B
- `meta.llama3-2-11b-instruct-v1:0` - Llama 3.2 11B
- `meta.llama3-2-3b-instruct-v1:0` - Llama 3.2 3B
- `meta.llama3-2-1b-instruct-v1:0` - Llama 3.2 1B
- `meta.llama3-1-70b-instruct-v1:0` - Llama 3.1 70B
- `meta.llama3-1-8b-instruct-v1:0` - Llama 3.1 8B

### Mistral Models
- `mistral.mistral-large-2407-v1:0` - Mistral Large
- `mistral.mistral-small-2402-v1:0` - Mistral Small

### Cohere Models
- `cohere.command-r-plus-v1:0` - Command R+
- `cohere.command-r-v1:0` - Command R

## Features Supported

### ✅ Implemented Features
- **Text Generation**: All models support text generation
- **Streaming Responses**: Real-time streaming of model responses
- **Tool Calling**: Support for function calling with compatible models
- **Multi-Agent Support**: Works with the LangGraph multi-agent system
- **System Prompts**: Support for system-level instructions
- **Context Management**: Proper handling of conversation context

### 🔧 Tool Integration
The Bedrock integration supports the application's existing tools:
- **Image Generation**: `generate_image` tool for creating images
- **Plan Writing**: `write_plan_tool` for creating execution plans
- **Agent Handoffs**: Transfer between different specialized agents

## Usage Examples

### Basic Chat
Select a Bedrock model from the model selector in the UI and start chatting.

### Image Generation
```
User: "Generate an image of a sunset over mountains"
Assistant: [Uses the generate_image tool to create the image]
```

### Planning Tasks
```
User: "Create a marketing campaign for a new product"
Assistant: [Uses write_plan_tool to create a structured plan, then hands off to appropriate agents]
```

## Troubleshooting

### Common Issues

1. **"Access Denied" Error**
   - Ensure you have requested access to the model in the Bedrock console
   - Check your AWS credentials and permissions

2. **"Region Not Supported" Error**
   - Verify the model is available in your selected region
   - Try switching to `us-east-1` or `us-west-2`

3. **"Model Not Found" Error**
   - Check the exact model ID in the Bedrock console
   - Ensure the model is enabled for your account

4. **Connection Timeout**
   - Check your internet connection
   - Verify AWS service status

### Debug Mode
Set environment variable for detailed logging:
```bash
export AWS_LOG_LEVEL=DEBUG
```

## Cost Considerations

- Bedrock models are charged per token (input and output)
- Different models have different pricing tiers
- Monitor usage in the AWS Billing console
- Consider using smaller models for development/testing

## Security Best Practices

1. **Use IAM Roles** when possible instead of access keys
2. **Rotate credentials** regularly
3. **Use least privilege** permissions
4. **Monitor usage** for unexpected activity
5. **Enable CloudTrail** for audit logging

## Support

For issues specific to:
- **AWS Bedrock**: Check AWS documentation and support
- **Application Integration**: Create an issue in the project repository
- **Model Behavior**: Refer to the model provider's documentation
