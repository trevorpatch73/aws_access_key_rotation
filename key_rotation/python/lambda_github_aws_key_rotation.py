import json
import boto3
import requests

REPOSITORY_NAME = str("INSERT_GITHUB_REPOSITORY_NAME")

iam = boto3.client('iam')
secretsmanager = boto3.client('secretsmanager')

def lambda_handler(event, context):
    
    USERNAME = REPOSITORY_NAME

    # EXTRACT THE ACCESS_KEY USED BY THE IAM ROLE
    USER_ACCESS_KEYS = iam.list_access_keys(UserName=USERNAME)
    for KEY in USER_ACCESS_KEYS['AccessKeyMetadata']:

        # DEACTIVATE THE EXISTING KEYS
        if KEY['Status'] == 'Active':
            iam.delete_access_key(AccessKeyId=KEY['AccessKeyId'],UserName=KEY['UserName'])
        
        # CREATE A NEW ACCESS KEY & SECRET KEY
        CREATE_ACCESS_KEY = iam.create_access_key(UserName=USERNAME)

        # UPDATE SECRETS MANAGER KEY STORE FOR IAM_USER:SERVICE
        GET_SECRETS = secretsmanager.get_secret_value(SecretId=USERNAME)
        SECRETS_JSON = json.loads(GET_SECRETS['SecretString'])
        SECRETS_JSON['AWS_ACCESS_KEY_ID'] = CREATE_ACCESS_KEY['AccessKey']['AccessKeyId']
        SECRETS_JSON['AWS_SECRET_ACCESS_KEY'] = CREATE_ACCESS_KEY['AccessKey']['SecretAccessKey']
        SECRETS_STRING = json.dumps(SECRETS_JSON)

        # EXECUTE ACTIONS TO SECRETS MANAGER
        secretsmanager.update_secret(SecretId=USERNAME,SecretString=SECRETS_STRING)

        # GET ALL UPDATED SECRETS FROM SECRETS MANAGER FOR PERSISTANCE
        GET_SECRETS = secretsmanager.get_secret_value(SecretId=USERNAME)
        SECRETS_JSON = json.loads(GET_SECRETS['SecretString'])

        # MAP SECRETS TO VARIABLES FOR USE IN HTTP CALLS
        AWS_ACCESS_KEY_ID = SECRETS_JSON['AWS_ACCESS_KEY_ID']
        AWS_SECRET_ACCESS_KEY = SECRETS_JSON['AWS_SECRET_ACCESS_KEY']
        GITHUB_TOKEN = SECRETS_JSON['GITHUB_TOKEN']
        GITHUB_TARGET = SECRETS_JSON['GITHUB_ORG_REPOSITORY']

        # SET THE HEADERS ON THE HTTP CALLS TO THE GITHUB REST API
        GITHUB_HEADERS = {
            'Authorization': 'Bearer ' + GITHUB_TOKEN,
            'Accept': 'application/vnd.github+json'
        }
        
        # GET THE DB KEY ID FOR THE GITHUB REPOSITORY BEING UPDATED
        GITHUB_KEY_URL = ('https://api.github.com/repos/' + GITHUB_TARGET + '/actions/secrets/public-key') 
        
        GIHUB_KEY_REQUEST = requests.get(GITHUB_KEY_URL, headers=GITHUB_HEADERS)
        GITHUB_KEY_RESPONSE = GIHUB_KEY_REQUEST.json()
        
        REPOSITORY_KEY_ID = GITHUB_KEY_RESPONSE["key_id"]

        # UPDATE THE AWS_ACCESS_KEY_ID IN THE GITHUB REPOSITORY                
        GITHUB_ACCESS_KEY_URL = ('https://api.github.com/repos/' + GITHUB_TARGET + '/actions/secrets/AWS_ACCESS_KEY_ID')
        
        ACCESS_KEY_PAYLOAD_STR = '{"encrypted_value":"' + AWS_ACCESS_KEY_ID + '","key_id":"' + REPOSITORY_KEY_ID + '"}'
        ACCESS_KEY_PAYLOAD = json.loads(ACCESS_KEY_PAYLOAD_STR)
        
        GITHUB_ACCESS_KEY_REQUEST = requests.put(GITHUB_ACCESS_KEY_URL, json=ACCESS_KEY_PAYLOAD, headers=GITHUB_HEADERS)

        # UPDATE THE AWS_SECRET_KEY IN THE GITHUB REPOSITORY                
        GITHUB_SECRET_KEY_URL = ('https://api.github.com/repos/' + GITHUB_TARGET + '/actions/secrets/AWS_SECRET_ACCESS_KEY')
        
        SECRET_KEY_PAYLOAD_STR = '{"encrypted_value":"' + AWS_SECRET_ACCESS_KEY + '","key_id":"' + REPOSITORY_KEY_ID + '"}'
        SECRET_KEY_PAYLOAD = json.loads(SECRET_KEY_PAYLOAD_STR)
        
        GITHUB_SECRET_KEY_REQUEST = requests.put(GITHUB_SECRET_KEY_URL, json=SECRET_KEY_PAYLOAD, headers=GITHUB_HEADERS)    

    return print ('Lambda has successfully rotated access keys.')