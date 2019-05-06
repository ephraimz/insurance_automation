import time
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from ..base import InsuranceAutomationResource


BASE_URL = 'https://myinfo.fnx.co.il'
REGISTRATION_BASE_URL = BASE_URL+'/fnx/MyZone/Registration/Registration'
INSURANCE_BASE_URL = BASE_URL+'/fnx/MyZone/Insurance'

REGISTRATION_URL = REGISTRATION_BASE_URL
CHECK_VALIDATE_USER_URL = REGISTRATION_BASE_URL+'/CheckValidateUser'
OTP_URL = REGISTRATION_BASE_URL+'/Otp'
DO_LOGIN_URL = REGISTRATION_BASE_URL+'/DoLogin'

ARCHIVES_URL = INSURANCE_BASE_URL+'/Archives'
HOME_PAGE_URL = INSURANCE_BASE_URL+'/HomePage'
POLICY_DOCS_URL = INSURANCE_BASE_URL+'/RequestDocuments/RequestPolicyAjax'
DOCUMENTS_URL = INSURANCE_BASE_URL+'/RequestDocuments/GetLatestDocumentStatus'
DOWNLOAD_DOCUMENT_URL = INSURANCE_BASE_URL+'/Risk/OpenDocument/'

POLICY_DOWNLOAD_RETRY_NUMBER = 25
POLICY_DOWNLOAD_RETRY_INTERVAL = 1.2

EXCLUDED_REPORTS_TABS = ['דיוור כללי']


class Phoenix(InsuranceAutomationResource):
    def authenticate(self, user_id, phone):
        self.session = requests.Session()

        r = self.session.get(REGISTRATION_URL)
        soup = BeautifulSoup(r.text, 'html.parser')
        token = self.get_request_verification_token(soup)

        payload = {
            '__RequestVerificationToken': token,
            'SelectedIdentityType': '0',
            'UserIdentity': user_id,
            'CommissionedId': '',
            'SelectedOTPIdentificationType': '0',
            'UserNumberPhone': '{}-{}'.format(phone[:3], phone[3:]),
            'UserNumberEmail': '',
            'Consent': 'on',
            'X-Requested-With': 'XMLHttpRequest',
        }

        r = self.session.post(
            CHECK_VALIDATE_USER_URL,
            data=payload,
        )
        response_data = r.json()

        if response_data != 'UserValid':
            return {'logged_in': False}

        r = self.session.get(OTP_URL)
        soup = BeautifulSoup(r.text, 'html.parser')
        self.data['token'] = self.get_request_verification_token(soup)

        return {'logged_in': True}

    def confirm_authentication(self, code):
        payload = {
            '__RequestVerificationToken': self.data['token'],
            'SecretCode': code,
        }

        r = self.session.post(
            DO_LOGIN_URL,
            data=payload,
            allow_redirects=False,
        )

        if '.ASPXAUTH' not in self.session.cookies:
            return False

        redirect = r.headers['Location']

        r = self.session.get(BASE_URL+redirect)

        return True

    def get_policies(self, url, name):
        r = self.session.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')

        policies_table = soup.find('table', {'role': 'presentation'})

        if not policies_table:
            return []

        rows = policies_table.find_all('tr')[1:]

        policies = []

        for row in rows:
            number = row.a.contents[0]
            onclick_value = row.find_all('td')[-1].find('a')['onclick']
            params = [
                s.strip(' \'"')
                for s in onclick_value.split('(')[1][0:-1].split(',')
            ]

            policies.append({
                'policyId': number,
                'lob': params[1],
                'fromAda': params[2] != 'False',
                'serviceType': params[3],
                'policyExpired': params[4] != 'False',
                'url': url,
                'hebrew_type': name,
            })

        return policies

    def download_copy_policy_document(self, zipfile, document_id, policy):
        qs = urlencode({
            'docId': document_id,
            'serviceType': policy['serviceType'],
            'fileName': '{}.pdf'.format(policy['policyId']),
            'expired': policy['policyExpired'],
        })
        url = '{}{}?{}'.format(
            DOWNLOAD_DOCUMENT_URL,
            policy['policyId'],
            qs,
        )
        filename = 'מסמכי פוליסה/{} - {}.pdf'.format(
            policy['hebrew_type'],
            policy['policyId'],
        )
        self.add_file_to_zipfile(zipfile, url, filename)

    def download_copy_policy_documents(self, zipfile):
        r = self.session.get(HOME_PAGE_URL)

        soup = BeautifulSoup(r.content, 'html.parser')

        policies_div = soup.find('div', class_='myPolicies')

        policies = []
        for a in policies_div.find_all('a'):
            policies += self.get_policies(a['href'], a.text.strip())

        skipped_policies = []

        for policy in policies:
            params = {
                'policyId': policy['policyId'],
                'lob': policy['lob'],
                'fromAda': policy['fromAda'],
                'policyExpired': policy['policyExpired'],
                '_': self.get_current_time(),
            }
            r = self.session.get(
                POLICY_DOCS_URL,
                params=params,
            )
            data = r.json()
            if data['Success']:
                for i in range(POLICY_DOWNLOAD_RETRY_NUMBER):
                    r = self.session.get(
                        DOCUMENTS_URL,
                        params={
                            'policyId': policy['policyId'],
                            '&_': self.get_current_time(),
                        },
                    )
                    data = r.json()
                    if data['Status'] == 2:
                        break
                    else:
                        time.sleep(POLICY_DOWNLOAD_RETRY_INTERVAL)

                if data['Status'] != 2:
                    skipped_policies.append('{} - {}'.format(
                        policy['hebrew_type'],
                        policy['policyId'],
                    ))
                    continue

                if data['Success']:
                    self.download_copy_policy_document(
                        zipfile,
                        data['DocumentId'],
                        policy,
                    )

        if skipped_policies:
            zipfile.writestr(
                'skipped_policies.txt',
                '{}\n'.format('\n'.join(skipped_policies)),
            )

    def download_periodic_reports(self, zipfile):
        r = self.session.get(ARCHIVES_URL, allow_redirects=False)

        soup = BeautifulSoup(r.content, 'html.parser')

        tabs = soup.find_all('div', {'class': 'ArchiveTab'})

        for tab in tabs:
            text = tab.find('a').text.strip()
            if text in EXCLUDED_REPORTS_TABS:
                continue
            url = tab.find('a').attrs['href']
            r = self.session.get(BASE_URL+url)
            soup = BeautifulSoup(r.content, 'html.parser')
            div = soup.find('div', {'class': 'ArchiveDocDisplay'})
            if div:
                for a in div.find_all('a'):
                    href = a.attrs['href']
                    url = BASE_URL+href
                    filename = 'דוחות/{}/{}.pdf'.format(text, a.text.strip())
                    self.add_file_to_zipfile(zipfile, url, filename)

    def download_all(self, zipfile):
        self.download_copy_policy_documents(zipfile)
        self.download_periodic_reports(zipfile)
