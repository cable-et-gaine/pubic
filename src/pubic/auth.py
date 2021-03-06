# coding: utf-8
import base64
import requests
import urllib.parse
import random
import string
import logging

from getpass import getpass

from pubic import cache


HUBIC_API_ENDPOINT = "https://api.hubic.com/"


def generate_random_string(length=16):
    return ''.join(random.choice(string.ascii_letters) for i in range(length))


def get_client_id_and_secret(client_id_file='', client_secret_file=''):
    with open(client_id_file) as f:
        logging.debug(f"Found a client ID file: {client_id_file}")
        client_id = f.readline().rstrip('\n')
        logging.debug(f"Using client ID: {client_id}")

    with open(client_secret_file) as f:
        logging.debug(f"Found a client secret file: {client_secret_file}")
        client_secret = f.readline().rstrip('\n')
        logging.debug(f"Using client secret: {'*' * len(client_secret)}")

    return client_id, client_secret


def request_token(client_id, redirect_uri):
    logging.info("1. Authorization Code Request")

    # scope = "usage.r,account.r,getAllLinks.r,credentials.r,sponsorCode.r,activate.w,sponsored.r,links.drw"
    scope = "account.r,credentials.r"
    response_type = "code"
    random_string = generate_random_string()
    request_token_url = "{}oauth/auth/?client_id={}&redirect_uri={}&scope={}&response_type={}&state={}".format(
        HUBIC_API_ENDPOINT,
        client_id,
        redirect_uri,
        scope,
        response_type,
        random_string
    )

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    logging.debug(request_token_url)
    response = requests.get(request_token_url, headers=headers)
    logging.debug(response.status_code)

    logging.debug(response.headers.get("location", "Cannot get response location header."))
    logging.debug("Parsing response HTML to get oauth code...")

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(response.content, 'html.parser')

    try:
        oauth_number = soup.find_all("input", {"name": "oauth"})[0]["value"]
        logging.debug(f"oauth_number: {oauth_number}")
    except:
        import pdb
        pdb.set_trace()

    return oauth_number, scope


def login(oauth_number, scope, user_login_file='', user_password_file=''):
    logging.info("2. Login & Consent")
    try:
        with open('user_login.txt') as f:
            user_login = f.readline().rstrip('\n')
            logging.debug(user_login)
            user_login = urllib.parse.quote(user_login, safe="")
    except:
        user_login = input("login: ")

    try:
        with open('user_password.txt') as f:
            user_password = f.readline().rstrip('\n')
            logging.debug("*" * len(user_password))
            user_password = urllib.parse.quote(user_password, safe="")
    except:
        user_password = getpass("password: ")
        
    data = f"oauth={oauth_number}&action=accepted&{'&'.join([x.replace('.', '=') for x in scope.split(',')])}&login={user_login}&user_pwd={user_password}"

    oauth_url = "https://api.hubic.com/oauth/auth/"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    logging.debug("Sending login request...")
    logging.debug(oauth_url)
    logging.debug(headers)
    logging.debug(data)
    response = requests.post(oauth_url, headers=headers, data=data)
    logging.debug(response.status_code)
    logging.debug(response.url)
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(response.url).query)
    logging.debug(qs)

    # This first GET request can sometimes goes into error state. User can refuse to give you access, or your scope can be malformed. When this kind of error happened, our login application will redirect user to your application with two parameters in the URL : error, and error_description. You can find a full description of all different errors :
    # HTTP 	error 	error_description
    # 400 	invalid_request 	missing arguments
    # 400 	invalid_request 	please verify redirect uri
    # 400 	unsupported_response_type 	response type must be set to code or token
    # 400 	invalid_scope 	please verify scope
    # 401 	unauthorized_client 	please verify credentials
    # 500 	server_error 	please retry

    # Expected response
    # response = https://api.hubic.com/sandbox/code=1575816242S8EV4vCZJ8...ROQphF0vJD&scope=account.r&state=SomeRandomString_Y1sO...DTt"
    # Code 	1575816242S8EV4vCZJ8...ROQphF0vJD
    # Scope 	account.r
    # State 	RandomString_Y1sO...DTt

    return qs


def request_access_token(qs, client_id, client_secret, redirect_uri):
    logging.info("3. Access Token Request")

    # Convert creds to base64
    # api_hubic_1366206728U6fa...K6SMkMmnU4lQUcnRy5E26
    # Base64 : YXBpX2h1YmlHhvdf...415VNGxRVWNuUnk1RTI2
    creds_b64 = base64.b64encode(f"{client_id}:{client_secret}".encode())
    logging.debug(f"creds_b64: {creds_b64}")

    # And create a POST request
    # API Hubic only support application/x-www-form-urlencoded, so do not try to send application/json data in your POST request
    # You don't have to redirect user to this URL. Just use Javascript, for example, to make an HTTP POST request.

    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }

    headers.update(
        {
            "Authorization": f"Basic {creds_b64.decode()}"
        }
    )

    data = f"code={qs['code'][0]}&redirect_uri={redirect_uri}&grant_type=authorization_code"
    response = requests.post(
        "https://api.hubic.com/oauth/token/",
        headers=headers,
        data=data)

    # When making your POST request to exchange your request code for an access token, something wrong can happen. Instead of an access token, you can receive a JSON formated response with error and error_description parameters. You need to handle those errors.
    # HTTP 	error 	error_description
    # 400 	invalid_request 	missing parameters
    # 400 	invalid_request 	grant type must be set to authorization_code
    # 400 	invalid_request 	please verify redirect uri
    # 400 	invalid_request 	invalid code
    # 400 	invalid_request 	expired code
    # 401 	unauthorized_client 	please verify credentials
    # 500 	server_error 	please retry

    logging.debug(response.status_code)
    r_data = response.json()
    logging.debug(r_data)

    access_token = r_data["access_token"]
    refresh_token = r_data["refresh_token"]
    logging.debug(f"access_token: {access_token}")

    # Get Json response
    # access_token 	z41k9n2LZ3rV...L6ZuOJs0oa1gQ7VVx
    # expires_in 	21600
    # refresh_token 	Kdn3eKevmp7...zaZQVnohj9AmiXMmz
    # token_type 	Bearer

    return access_token, refresh_token


def get_effective_storage_credentials(api_access_token):
    logging.info("Requesting storage credentials to the API")

    # You can store those data, and make your first call on hubic API ! Just ask the correct url and method according to your needs, and pass your access_token in the HTTP Authorization header, with the keyword Bearer
    """
    GET https://api.hubic.com/1.0/account HTTP/1.1
    Authorization: Bearer z41k9n2LZ3rV...L6ZuOJs0oa1gQ7VVx
    """
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Bearer {api_access_token}"
    }
    logging.debug(f"headers: {headers}")

    # response = requests.get(
    #     "https://api.hubic.com/1.0/account",
    #     headers=headers)

    # logging.debug(response.status_code)
    # logging.debug(response.json())

    logging.debug(f"headers: {headers}")

    response = requests.get(
        "https://api.hubic.com/1.0/account/credentials",
        headers=headers)

    logging.debug(response.status_code)
    if response.status_code == 200:
        logging.debug(response.json())

    # Extract Sotrage API credentials
    # expected_creds = {
    #     "token":"gA...S0Et-RaG...bAvr-GwpIrt...MRXGWPK-cTq1T...NjnCtznSc22N_90...Uj_cfM...mEr_OVsK2H...UJm-0...s-PbExi1R7m...uktDw",
    #     "endpoint":"https://lb1949.hubic.ovh.net/v1/AUTH_b61efe...98a614",
    #     "expires":"2019-12-14T22:52:45+01:00"
    # }
    storage_access_token = response.json()["token"]
    storage_endpoint = response.json()["endpoint"]

    # When you call API, you can miss your call, or an error can occured. You need to handle all of those errors.
    # HTTP 	error 	error_description
    # 400 	invalid_request 	missing arguments
    # 400 	insufficient_scope 	this scope is insufficient
    # 401 	invalid_token 	not found
    # 401 	invalid_token 	expired
    # 403 	invalid_token 	revoked
    # 403 	invalid_token 	deleted

    # Expected response
    # email 	<youremail@example.com>
    # creationDate 	2013-06-22T20:19:42+02:00
    # status 	ok
    # firstname 	John
    # lastname 	Doe

    return storage_access_token, storage_endpoint


def refresh_token():
    # But after a delimited time (21600 milliseconds), you will need to refresh your token ...

    # Refreshing an access token looks like getting a new one, but some parameter's values change.
    # First, you need to authenticate your application, with Authorization: Basic header or passing your credentials (client_id, client_secret) in POST data. Remember, we only support application/x-www-form-urlencoded POST data.
    """
    POST https://api.hubic.com/oauth/token/ HTTP/1.1
    Authorization: Basic YXBpX2h1YmljXz...bW5VNGxRVWNuUnk1RTI2
    refresh_token=Kdn3eKevmp...zaZQVnohj9AmiXMmz
    &grant_type=refresh_token
    """

    #Response
    # access_token 	c7rKS3VCMVFr...Nb5iPGdTKHRW05
    # expires_in 	21600
    # token_type 	Bearer


def get_api_credentials(use_cache=True):
    if use_cache:
        api_creds = cache.load_api_credentials()
        if api_creds:
            return api_creds

    logging.info(f"No cached API credentials available. Proceeding to oauth2 authentication...")

    redirect_uri = urllib.parse.quote(HUBIC_API_ENDPOINT, safe="")

    # 0. Register app and get cient ID and secret
    client_id, client_secret = get_client_id_and_secret('client_id.txt', 'client_secret.txt')

    # 1. Request token
    oauth_number, scope = request_token(client_id, redirect_uri)

    # 2. Login & Consent
    qs = login(oauth_number, scope)

    # 3. Access token
    access_token, refresh_token = request_access_token(qs, client_id, client_secret, redirect_uri)

    cache.save_api_credentials(access_token, refresh_token)
    return access_token, refresh_token


def get_storage_credentials(use_cache=True):
    if use_cache:
        storage_creds = cache.load_storage_credentials()
        if storage_creds:
            return storage_creds

    logging.info(f"No cached storage credentials available.")
    api_creds = get_api_credentials(use_cache)
    storage_access_token, storage_endpoint = get_effective_storage_credentials(api_creds[0])
    cache.save_storage_credentials(storage_access_token, storage_endpoint)
    return storage_access_token, storage_endpoint

    # 10. Refesh token
    # if access_token.has_expired():
    #     access_token = refresh_token(refresh_token)
