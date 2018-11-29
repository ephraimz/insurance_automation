import time
import uuid
from urllib.parse import parse_qs

import requests

from bs4 import BeautifulSoup
from requests.utils import cookiejar_from_dict


AUTH_URL = ('https://www.harel-group.co.il/_vti_bin/webapi/'
            'CustomersAuthentication/PostAuthenticate/ValidateUser')
AUTH_CONFIRM_URL = ('https://www.harel-group.co.il/_vti_bin/webapi/'
                    'CustomersAuthentication/PostAuthenticate/ValidateOTP')
AUTH_COOKIE_NAME = 'ASP.NET_SessionId'

GET_APPLICATION_URL = ('https://www.harel-group.co.il/_vti_bin/webapi/'
                       'Application/GetApplication/')

CLIENT_VIEW_URL = ('https://apps.harel-group.co.il/apps.client-view/'
                   'client-view/')

CUSTOMER_PRODUCTS_URL = ('https://apps.harel-group.co.il/apps.client-view/'
                         'client-view/customer-products')


class Harel:
    def get_current_time(self):
        return int(time.time()*1000)

    def authenticate(self, user_id, phone):
        self.session = requests.Session()
        r = self.session.post(AUTH_URL, data={
            'UserId': user_id,
            'FullPhone': phone,
        })
        response_data = r.json()
        return response_data['Status'] == 0

    def confirm_authentication(self, code):
        r = self.session.post(AUTH_CONFIRM_URL, data={
            'OTP': code,
            'captchaResponse': None
        })
        response_data = r.json()
        return response_data['Status'] == 0

    @property
    def session_id(self):
        return self.session.cookies[AUTH_COOKIE_NAME]

    @session_id.setter
    def session_id(self, value):
        self.session = requests.Session()
        self.session.cookies = cookiejar_from_dict({AUTH_COOKIE_NAME: value})

    def download_file(self, url, filename):
        r = self.session.get(url, stream=True)
        if r.status_code != 200:
            return False
        with open(filename, 'wb') as f:
            for chunk in r:
                f.write(chunk)
        return True

    def get_ticket(self):
        r = self.session.post(GET_APPLICATION_URL, {
            "selectedApp": "client-view",
        })
        app_url = r.json()['returnObject']['AppUrl']
        return parse_qs(app_url)['ticket'][0]

    def request_client_view(self, ticket):
        r = self.session.get(CLIENT_VIEW_URL, params={
            'h': '0',
            'i': '1',
            'd': '1',
            'applicationID': 'client-view',
            'flowGuid': str(uuid.uuid4()),
            'RedirectUrl': '/',
            'ticket': ticket,
        })
        return r.status_code == 200

    def get_policies(self, ticket):
        r = self.session.get(CUSTOMER_PRODUCTS_URL, params={
            'ctime': self.get_current_time(),
            'ticket': ticket,
        })
        return r.json()['topicsList']
