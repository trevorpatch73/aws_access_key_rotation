import json
import boto3
import requests

REPOSITORY_NAME = str('Github')

iam = boto3.client('iam')
secretsmanager = boto3.client('secretsmanager')

def lambda_handler(event, context):
    
    # EXTRACT A LIST OF IAM_USERS:SERVICE INTO A JSON OBJECT
    IAM_USERS_DICT = iam.list_users(MaxItems=100)
    IAM_USERS_CONVERT = json.dumps(IAM_USERS_DICT, indent = 4, default=str)
    IAM_USERS_JSON = json.loads(IAM_USERS_CONVERT)
    
    # ITERATE OVER THE LIST OF USERS
    IAM_USER_LIST = IAM_USERS_JSON["Users"]
    USER_INDEX = 0
    for USER in IAM_USER_LIST:
        USERNAME = IAM_USER_LIST[USER_INDEX]["UserName"]
        
        # EXTRACT THE ACCESS_KEY USED BY THE IAM_USER:SERVICE
        USER_ACCESS_KEYS = iam.list_access_keys(UserName=USERNAME)
        for KEY in USER_ACCESS_KEYS['AccessKeyMetadata']:
            
            # DEACTIVATE THE EXISTING KEY
            if KEY['Status'] == 'Active':
                iam.delete_access_key(AccessKeyId=KEY['AccessKeyId'],UserName=KEY['UserName'])
            
            # CREATE A NEW ACCESS KEY & SECRET KEY
            CREATE_ACCESS_KEY = iam.create_access_key(UserName=USERNAME)
            
            # UPDATE SECRETS MANAGER KEY STORE FOR IAM_USER:SERVICE
            GET_SECRETS = secretsmanager.get_secret_value(SecretId=USERNAME)
            SECRETS_JSON = json.loads(GET_SECRETS['SecretString'])
            SECRETS_JSON['AccessKeyId'] = CREATE_ACCESS_KEY['AccessKey']['AccessKeyId']
            SECRETS_JSON['SecretAccessKey'] = CREATE_ACCESS_KEY['AccessKey']['SecretAccessKey']
            SECRETS_STRING = json.dumps(SECRETS_JSON)
            secretsmanager.update_secret(SecretId=USERNAME,SecretString=SECRETS_STRING)
            
            # DETERMINE SERVICE USE-CASE
            SECRETS_LIST = secretsmanager.list_secrets(
                MaxResults=100,
                Filters=[
                    {
                        'Key': 'name',
                        'Values': [USERNAME]
                    },
                ],
                SortOrder='asc'
            )
        
            for SECRET in SECRETS_LIST['SecretList']:
                TAG_LIST = SECRET['Tags']
                for EACH_TAG in TAG_LIST:
                    
                    # DEFINE INSTRUCTIONS FOR EACH SERVICE
                    if EACH_TAG['Key'] == 'SERVICE':
                        
                        # GITHUB SERVICE: UPDATE PRIVATE REPOSITORY ACTION SECRETS
                        if EACH_TAG['Value'] == 'GITHUB':
                            
                            GET_SECRETS = secretsmanager.get_secret_value(SecretId=USERNAME)
                            SECRETS_JSON = json.loads(GET_SECRETS['SecretString'])
                            
                            GITHUB_TOKEN = SECRETS_JSON['OAuthToken']
                            AWS_ACCESS_KEY_ID = SECRETS_JSON['AccessKeyId']
                            AWS_SECRET_ACCESS_KEY = SECRETS_JSON['SecretAccessKey']
                            GITHUB_TARGET = SECRETS_JSON['ServiceTarget']
                            
                            GITHUB_HEADERS = {
                                'Authorization': 'Bearer ' + GITHUB_TOKEN,
                                'Accept': 'application/vnd.github+json'
                            }
                            
                            GITHUB_KEY_URL = ('https://api.github.com/repos/' + GITHUB_TARGET + '/actions/secrets/public-key') 
                            
                            GIHUB_KEY_REQUEST = requests.get(GITHUB_KEY_URL, headers=GITHUB_HEADERS)
                            GITHUB_KEY_RESPONSE = GIHUB_KEY_REQUEST.json()
                            
                            REPOSITORY_KEY_ID = GITHUB_KEY_RESPONSE["key_id"]
                            
                            GITHUB_ACCESS_KEY_URL = ('https://api.github.com/repos/' + GITHUB_TARGET + '/actions/secrets/AWS_ACCESS_KEY_ID')
                            
                            ACCESS_KEY_PAYLOAD_STR = '{"encrypted_value":"' + AWS_ACCESS_KEY_ID + '","key_id":"' + REPOSITORY_KEY_ID + '"}'
                            ACCESS_KEY_PAYLOAD = json.loads(ACCESS_KEY_PAYLOAD_STR)
                            
                            GITHUB_ACCESS_KEY_REQUEST = requests.put(GITHUB_ACCESS_KEY_URL, json=ACCESS_KEY_PAYLOAD, headers=GITHUB_HEADERS)
                            
                            GITHUB_SECRET_KEY_URL = ('https://api.github.com/repos/' + GITHUB_TARGET + '/actions/secrets/AWS_SECRET_ACCESS_KEY')
                            
                            SECRET_KEY_PAYLOAD_STR = '{"encrypted_value":"' + AWS_SECRET_ACCESS_KEY + '","key_id":"' + REPOSITORY_KEY_ID + '"}'
                            SECRET_KEY_PAYLOAD = json.loads(SECRET_KEY_PAYLOAD_STR)
                            
                            GITHUB_SECRET_KEY_REQUEST = requests.put(GITHUB_SECRET_KEY_URL, json=SECRET_KEY_PAYLOAD, headers=GITHUB_HEADERS)  

        USER_INDEX += 1
    
    return print ('Lambda has successfully rotated access keys.')
