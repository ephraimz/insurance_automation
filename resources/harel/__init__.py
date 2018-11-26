import requests

from bs4 import BeautifulSoup
from requests.utils import cookiejar_from_dict


VALIDATE_USER_URL = ('https://www.harel-group.co.il/_vti_bin/webapi/'
                     'CustomersAuthentication/PostAuthenticate/ValidateUser')
AUTH_COOKIE_NAME = 'ASP.NET_SessionId'


class Harel:
    def authenticate(self, user_id, phone):
        self.session = requests.Session()
        r = self.session.post(VALIDATE_USER_URL, data={
            "UserId": user_id,
            "FullPhone": phone,
        })

    @property
    def session_id(self):
        return self.session.cookies[AUTH_COOKIE_NAME]

    @session_id.setter
    def session_id(self, value):
        self.session = requests.Session()
        self.session.cookies = cookiejar_from_dict({AUTH_COOKIE_NAME: value})
