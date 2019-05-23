import re

from urllib.parse import urljoin

import requests

from bs4 import BeautifulSoup
from user_agent import generate_user_agent

from insurance_automation.common.utils import deep_get
from ..base import InsuranceAutomationResource


AUTH_URL = (
    'https://www.555.co.il/webapp/api/client/OTPLogin/'
    'authenticateClientByIdAndPhoneNr'
)

AUTH_CONFIRM_URL = (
    'https://www.555.co.il/webapp/api/client/OTPLogin/'
    'isTempPasswordOk'
)

PERSONAL_AREA_URL = (
    'https://www.555.co.il/site/online/personalArea.html'
)

HOMEPAGE_URL = (
    'https://www.555.co.il/site/online/HomePage.html'
)

DOCUMENTS_LIST_URL = (
    'https://www.555.co.il/site/online/HomePage.html?'
    'wicket:interface=privateClientZone:1:viewPanel:'
    'wtk-internal-border:ClientZoneHeader:linkContainer:'
    'documents::ILinkListener::'
)

document_re = re.compile(
    'DocumentsForClient\.html\?wicket:interface=privateClientZone:'
    '\d+:viewPanel:selectDocTypePanel:selectDocTypePanel:inner:'
    'sentLettersPanel:documentsListContainer:documentsList:\d+:'
    'inner:nameLink::IBehaviorListener:0:'
)

document_download_re = re.compile(
    'DocumentsForClient\.html\?wicket:interface=privateClientZone:'
    '\d+:plugins:items:\d+:item:dialogs:items:\d+:item:item:item:'
    'singleDocPanel:embeddedImage:docViewerForm:downloadLink::'
    'ILinkListener::'
)


class BituachYashir(InsuranceAutomationResource):
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

    def request_personal_area(self):
        r = self.session.get(PERSONAL_AREA_URL)
        return r.url.startswith(HOMEPAGE_URL)

    def get_documents_list(self):
        r = self.session.get(DOCUMENTS_LIST_URL)
        soup = BeautifulSoup(r.text, 'html.parser')
        tbody = soup.find('div', class_='documentsList').tbody
        documents = []
        for tr in tbody.find_all('tr'):
            m = document_re.search(tr.a['onclick'])
            if m:
                url = m.group(0)
                name = tr.a.span.string
                documents.append({
                    'url': url,
                    'name': name,
                })
        return documents

    def download_document(self, d, document):
        r = self.session.get(urljoin(HOMEPAGE_URL, document['url']))
        download_url = document_download_re.search(r.text).group(0)
        url = urljoin(HOMEPAGE_URL, download_url)
        filename = '{}.pdf'.format(document['name'])
        self.add_file_to_dict(d, url, filename)
