import os
import boto3
import configparser
from langchain_aws.chat_models import ChatBedrock
from langchain_core.messages import HumanMessage
import dotenv
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

bedrock_runtime = boto3.client(
    "bedrock-runtime", 
    region_name=region_name, 
    config=config
)

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


# prompt = "who is the ceo of google"

# message = HumanMessage(content=prompt)

# response = llm.invoke([message])

# print(response.content)


dir = "generated-codes_claude3.7"

hotstar_api_documentation = "API-Documentations/Hotstar.txt"
ctv_api_documentation = "API-Documentations/CTV.txt"
yle_api_documentation = "API-Documentations/YLE.txt"

with open(f"{yle_api_documentation}", "r") as f:
    yle_file = f.read()

# print(ctv_file)

dotenv.load_dotenv()

hotstar_user_token = os.getenv('X-HS-USERTOKEN')
hotstar_device_id = os.getenv('X-HS-DEVICE-ID')

# prompt = f"""

#     Provided an API documentation, you need to generate a crawler code in python,
#     which can crawl this website and get all its APIs\n

#     IMPORTANT: 
#         1. Dont write anything extra except the python code in the response\n
#         2. Save the resulting jsons in "../results_claude3.7/hotstar" directory\n
#         3. Provided below the necessary x-hs-usertoken and x-hs-device-id\n

#         User Token = {hotstar_user_token}\n
#         Device Id = {hotstar_device_id}\n

#     Documentation Below\n

#     {hotstar_file}

# """

prompt = f"""

    Provided an API documentation, you need to generate a crawler code in python,
    which can crawl this website and get all its APIs\n

    IMPORTANT: 
        1. Dont write anything extra except the python code in the response\n
        2. Save the resulting jsons in "../results_claude3.7/yle" directory\n

    Documentation Below\n

    {yle_file}

"""

# print(hotstar_device_id)
message = HumanMessage(content=prompt)

response = llm.invoke([message])

with open(f"{dir}/yle.py", "w") as f:
    f.write(response.content)
# print(response.content)

print("SUCCESS")