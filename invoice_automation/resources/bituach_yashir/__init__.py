import re

import requests

from bs4 import BeautifulSoup
from user_agent import generate_user_agent

from invoice_automation.common.utils import deep_get
from ..base import InvoiceAutomationResource


AUTH_URL = (
    'https://www.555.co.il/webapp/api/client/OTPLogin/'
    'authenticateClientByIdAndPhoneNr'
)

AUTH_CONFIRM_URL = (
    'https://www.555.co.il/webapp/api/client/OTPLogin/'
    'isTempPasswordOk'
)


class BituachYashir(InvoiceAutomationResource):
    def authenticate(self, user_id, phone):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = generate_user_agent(
            device_type='desktop'
        )

        r = self.session.post(AUTH_URL, json={
            'clientId': user_id,
            'phone': phone[3:],
            'prePhone': phone[:3],
            'sendType': '0',
        })

        r.raise_for_status()

        key = deep_get(r.json(), 'data.message.key')

        if key == 'otp.login.tempPassWasSent':
            return {'logged_in': True}

        return {'logged_in': False}

    def confirm_authentication(self, code):
        r = self.session.post(AUTH_CONFIRM_URL, json={
            'tempPassword': code,
            'service': None,
            'action': None,
        })

        r.raise_for_status()

        key = deep_get(r.json(), 'data.message.key')

        return key == 'login.success'
