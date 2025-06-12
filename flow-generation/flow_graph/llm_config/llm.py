import os
import boto3
import configparser
from langchain_aws.chat_models import ChatBedrock
from langchain_core.messages import HumanMessage
from botocore.config import Config

os.environ["AWS_SHARED_CREDENTIALS_FILE"] = '~/.aws/credentials'
os.environ["AWS_PROFILE"] = '536697239187-/AI-DEVELOPER'

config = configparser.ConfigParser()
config.read(os.path.expanduser('~/.aws/credentials'))

profile = '536697239187-/AI-DEVELOPER'

if profile in config:
    os.environ['AWS_ACCESS_KEY_ID'] = config[profile]['aws_access_key_id']
    os.environ['AWS_SECRET_ACCESS_KEY'] = config[profile]['aws_secret_access_key']
    if 'aws_session_token' in config[profile]:
        os.environ['AWS_SESSION_TOKEN'] = config[profile]['aws_session_token']

region_name = 'us-east-1'
session = boto3.Session(
    aws_access_key_id=os.environ['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=os.environ['AWS_SECRET_ACCESS_KEY'],
    aws_session_token=os.environ['AWS_SESSION_TOKEN'],
    region_name='us-east-1'
)

config = Config(
    read_timeout = 300, 
    retries = {
        'max_attempts' : 3
    }
)

bedrock_runtime = boto3.client("bedrock-runtime", region_name=region_name, config=config)

llm = ChatBedrock(
    model_id="arn:aws:bedrock:us-east-1:536697239187:inference-profile/us.anthropic.claude-3-7-sonnet-20250219-v1:0",
    client=bedrock_runtime,
    provider="anthropic",
    model_kwargs={
        "max_tokens": 64000,
        "anthropic_version": "bedrock-2023-05-31",
        "temperature": 0
    }
)

def invoke_llm(prompt):
    
    print("-----------LLM CALLED-----------")
    llm_prompt = HumanMessage(content=prompt)
    response = llm.invoke([prompt])
    return response.content