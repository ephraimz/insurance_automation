import re

import requests

from bs4 import BeautifulSoup

from ..base import InvoiceAutomationResource


AUTH_URL = ('https://clientportfolio.ayalon-ins.co.il/'
            'ClientPortfolio/Account/Login')

AUTH_CONFIRM_URL = ('https://clientportfolio.ayalon-ins.co.il/'
                    'ClientPortfolio/Account/VerifyPhoneNumber')

DOCUMENTS_CONTAINER_COMPONENT_URL = (
    'https://clientportfolio.ayalon-ins.co.il/'
    'ClientPortfolio/documentsContainerComponent'
)

ALL_DOCUMENTS_URL = ('https://clientportfolio.ayalon-ins.co.il/'
                    'ClientPortfolioService/api/allDocuments')

DOCUMENT_DOWNLOAD_URL = ('https://clientportfolio.ayalon-ins.co.il/'
                         'ClientPortfolioService/api/downloadFile/documents/')

documents_token_re = re.compile(r'token = "([a-zA-Z0-9_-]+)"')
document_guid_re = re.compile(r'{([0-9A-Z-]+)}')


class Ayalon(InvoiceAutomationResource):
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

    def get_filename(self, document):
        return '{}/{} {} {}.pdf'.format(
            document['DirectoryDesc'],
            document['DocDate'].replace('/', '.'),
            document['DocName'],
            document_guid_re.match(document['DocGuid']).group(1),
        )

    def download_documents(self, zipfile):
        r = self.session.get(DOCUMENTS_CONTAINER_COMPONENT_URL)

        token = documents_token_re.search(r.text).group(1)

        headers = {'Authorization': 'Bearer {}'.format(token)}

        r = self.session.get(ALL_DOCUMENTS_URL, headers=headers)

        for document in r.json()['Data']:
            url = ''.join([DOCUMENT_DOWNLOAD_URL, document['DownloadGuid']])
            filename = self.get_filename(document)
            self.add_file_to_zipfile(zipfile, url, filename)
