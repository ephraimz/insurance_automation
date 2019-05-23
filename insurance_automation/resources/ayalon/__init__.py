import re

import requests

from bs4 import BeautifulSoup

from ..base import InsuranceAutomationResource


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


class Ayalon(InsuranceAutomationResource):
    def authenticate(self, user_id, phone):
        self.session = requests.Session()

        r = self.session.get(AUTH_URL)
        soup = BeautifulSoup(r.text, 'html.parser')
        token = self.get_request_verification_token(soup)

        r = self.session.post(AUTH_URL, data={
            '__RequestVerificationToken': token,
            'PassportId': user_id,
            'PhoneNumber': phone[3:],
            'MobileAreaCode': phone[:3],
            'g-recaptcha-response': '',
        })

        soup = BeautifulSoup(r.text, 'html.parser')

        if soup.find(id='sadesismahadpeamit'):
            self.data.update({
                'user_id': user_id,
                'phone': phone,
                'token': self.get_request_verification_token(soup),
            })

            return {'logged_in': True}

        return {'logged_in': False}

    def confirm_authentication(self, code):
        r = self.session.post(AUTH_CONFIRM_URL, data={
            '__RequestVerificationToken': self.data['token'],
            'PhoneToValidate': self.data['phone'],
            'EmailToValidate': '',
            'PassportId': self.data['user_id'],
            'IsKosherPhone': False,
            'Action': '',
            'Code': code,
            'g-recaptcha-response': '',
            'button': 'validate',
        }, allow_redirects=False)
        return r.status_code == 302

    def get_document_download_url(self, document):
        return ''.join([
            DOCUMENT_DOWNLOAD_URL,
            document['DownloadGuid'],
        ])

    def get_filename(self, document):
        return '{} {} {}.pdf'.format(
            document['DocDate'].replace('/', '.'),
            document['DocName'].replace('/', '.'),
            document_guid_re.match(document['DocGuid']).group(1),
        )

    def get_latest_periodic_report(self, documents):
        for document in documents:
            if document['DocName'] == 'דוח תקופתי למבוטח':
                return document

    def download_periodic_report(self, d, documents):
        document = self.get_latest_periodic_report(documents)

        if not document:
            return False

        url = self.get_document_download_url(document)
        filename = self.get_filename(document)
        self.add_file_to_dict(d, url, filename)

        return True

    def get_policies(self, documents):
        return [
            document for document
            in documents
            if document['DirectoryDesc'] == 'פוליסות'
        ]

    def download_policies(self, d, documents):
        documents = self.get_policies(documents)

        if not documents:
            return False

        for document in documents:
            url = self.get_document_download_url(document)
            filename = 'פוליסות/{}'.format(
                self.get_filename(document)
            )
            self.add_file_to_dict(d, url, filename)

        return True

    def download_all(self):
        r = self.session.get(DOCUMENTS_CONTAINER_COMPONENT_URL)

        token = documents_token_re.search(r.text).group(1)

        headers = {'Authorization': 'Bearer {}'.format(token)}

        r = self.session.get(ALL_DOCUMENTS_URL, headers=headers)

        documents = r.json()['Data']

        d = {}

        self.download_periodic_report(d, documents)
        self.download_policies(d, documents)

        return d
