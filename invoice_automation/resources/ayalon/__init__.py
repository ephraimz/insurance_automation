import requests

from bs4 import BeautifulSoup


AUTH_URL = ('https://clientportfolio.ayalon-ins.co.il/'
            'ClientPortfolio/Account/Login')

AUTH_CONFIRM_URL = ('https://clientportfolio.ayalon-ins.co.il/'
                    'ClientPortfolio/Account/VerifyPhoneNumber')


class Ayalon:
    def get_request_verification_token(self, response):
        soup = BeautifulSoup(response.text, 'html.parser')
        token = soup.find('input', attrs={
            'name': '__RequestVerificationToken'
        })['value']
        return token

    def authenticate(self, user_id, phone):
        self.session = requests.Session()

        r = self.session.get(AUTH_URL)
        token = self.get_request_verification_token(r)

        r = self.session.post(AUTH_URL, data={
            '__RequestVerificationToken': token,
            'PassportId': user_id,
            'PhoneNumber': phone[3:],
            'MobileAreaCode': phone[:3],
            'g-recaptcha-response': '',
        })

        soup = BeautifulSoup(r.text, 'html.parser')

        if soup.find(id='sadesismahadpeamit'):
            return {
                'logged_in': True,
                'token': self.get_request_verification_token(r),
            }

        return {'logged_in': False}

    def confirm_authentication(self, token, user_id, phone, code):
        r = self.session.post(AUTH_CONFIRM_URL, data={
            '__RequestVerificationToken': token,
            'PhoneToValidate': phone,
            'EmailToValidate': '',
            'PassportId': user_id,
            'IsKosherPhone': False,
            'Action': '',
            'Code': code,
            'g-recaptcha-response': '',
            'button': 'validate',
        }, allow_redirects=False)
        return r.status_code == 302
