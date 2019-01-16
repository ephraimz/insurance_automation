import re
import time
import uuid
from urllib.parse import parse_qs
from urllib.parse import urlencode
from urllib.parse import urljoin
from zipfile import ZipFile

import requests

from bs4 import BeautifulSoup
from requests.utils import cookiejar_from_dict

from invoice_automation.common.utils import deep_get


SITE_URL = 'https://www.harel-group.co.il/'

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

HTTP_PROXY_URL = ('https://www.harel-group.co.il/_layouts/15/HarelWebSite/'
                  'HarelReports/ApplicationPages/HTTP_Proxy_Script.aspx')

MY_POLICY_PDF_URL = ('https://www.harel-group.co.il/personal-info/my-harel/'
                     'Pages/personal-info/my-policy-pdf.aspx')

CREATE_POLICY_PDF_URL_1 = ('https://apps.harel-group.co.il/CreatePolicyPDF/'
                         'jsp/createPdf')

CREATE_POLICY_PDF_URL_2 = ('https://apps.harel-group.co.il/CreatePolicyPDF/'
                           'jsp/PolicyPDF.jsp')

SHOW_PDF_URL = 'https://www.hrl.co.il/showpdf/jsp/showpdf'

HEALTH_GO_TO_POLICY_DOCUMENT_URL = ('https://apps.harel-group.co.il/'
                                    'apps.customer-health-info/api/'
                                    'go-to-policy-document/')

HEALTH_POLICIES_URL = ('https://apps.harel-group.co.il/'
                       'apps.customer-health-info/api/policies')

GET_POLICY_DOCUMENT_URL = ('https://apps.harel-group.co.il/'
                           'apps.policy-document/api/get-policy-document')

TIME_BETWEEN_QSID_AND_SID = 5000

COPY_POLICY_TOPIC_IDS = (10, 30, 99)

DIMUT_WEB_DOCS_LOGIN_URL = 'https://www.hrl.co.il/DimutWebDocs/jsp/login.jsp'

DIMUT_WEB_DOCUMENTS_URL = ('https://www.hrl.co.il/DimutWebDocs/jsp/'
                           'docListTable.jsp')

DIMUT_WEB_SHOW_FILE_URL = ('https://www.hrl.co.il/DimutWebDocs/jsp/'
                           'showFile')

MAX_PERIODIC_REPORTS_DOCUMENTS_TO_DOWNLOAD = 4

ticket_re = re.compile(r'ticket=(\w+)')

periodic_reports_session_id_re = re.compile(r'sessionid=\'([\w.]+)\'')
periodic_reports_csrf_token_re = re.compile(r'csrftoken = \'(\w+)\'')


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

        if response_data['Status'] == 0:
            return {'logged_in': True}

        user_input_error = deep_get(response_data, 'Details.UserInputError')

        if user_input_error:
            return {'logged_in': False, 'error': user_input_error}

        process_error = deep_get(response_data, 'Details.ProcessError')

        return {'logged_in': False, 'error': process_error}

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

    def add_file_to_zipfile(self, zipfile, url, filename):
        r = self.session.get(url)
        if r.status_code != 200:
            return False
        zipfile.writestr(filename, r.content)
        return True

    def get_ticket(self, selected_app):
        r = self.session.post(GET_APPLICATION_URL, {
            'selectedApp': selected_app,
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
        policies = []
        for l in r.json()['topicsList'].values():
            policies += l
        return policies

    def get_report_id(self, policy):
        url = urljoin(SITE_URL, policy['url'])
        r = self.session.get(url)
        soup = BeautifulSoup(r.text, 'html.parser')
        el = soup.find('div', class_='portal-body').div
        report_id = el['data-reportid'].strip('!')
        return report_id

    def get_my_policy_pdf_url(self, policy_id):
        referer = '{}?{}'.format(MY_POLICY_PDF_URL, urlencode(
            {'POLICY_ID': policy_id}
        ))
        r = self.session.post(GET_APPLICATION_URL, data={
            'selectedApp': 'my-policy-pdf',
            'ContainerId': 'application_container_{}'.format(uuid.uuid4()),
        }, headers={'Referer': referer})
        app_url = r.json()['returnObject']['AppUrl']
        ticket = parse_qs(app_url)['ticket'][0]
        r = self.session.post(CREATE_POLICY_PDF_URL_1, data={
            'ticket': ticket,
        })
        r = self.session.get(CREATE_POLICY_PDF_URL_2)
        ticket = ticket_re.search(r.text).group(1)
        url = '{}?{}'.format(SHOW_PDF_URL, urlencode({'ticket': ticket}))
        return url

    def download_copy_policy_document_10(self, zipfile, policy):
        policy_id = policy['policySubjectId']
        url = self.get_my_policy_pdf_url(policy_id)
        filename = 'copy_policy/{}.pdf'.format(policy_id)
        self.add_file_to_zipfile(zipfile, url, filename)

    def download_copy_policy_document_30(self, zipfile, policy):
        policy_id = policy['policySubjectId']
        topic_id = policy['topicId']
        ticket = self.get_ticket('lobby_health')
        r = self.session.get(HEALTH_POLICIES_URL, params={
            'ticket': ticket,
            'ctime': self.get_current_time(),
        })
        r = self.session.get(HEALTH_GO_TO_POLICY_DOCUMENT_URL, params={
            'ticket': ticket,
            'policyNumber': policy_id,
            'topicId': topic_id,
            'ctime': self.get_current_time(),
        })
        ticket = r.text
        url = '{}?{}'.format(
            GET_POLICY_DOCUMENT_URL,
            urlencode({
                'ticket': ticket,
                'ctime': self.get_current_time()
            }),
        )
        filename = 'copy_policy/{}.pdf'.format(policy_id)
        r = self.session.get(url)
        self.add_file_to_zipfile(zipfile, url, filename)

    def download_copy_policy_document_99(self, zipfile, policy):
        if policy['xtopicId'] != 20:
            return
        report_id = self.get_report_id(policy)
        current_time = self.get_current_time()
        r = self.session.post(HTTP_PROXY_URL, params={
            'Action': 'ExecSQL',
            'Sid': current_time,
            'QSID': current_time - TIME_BETWEEN_QSID_AND_SID,
        }, data=(
            '<Query KEY="622" R="{report_id}" D="1" DataSource="52">'
            '<Parameters>'
            '<Parameter U="HCUN" V="-999"/>'
            '<Parameter U="_REPORTID" V="{report_id}"/>'
            '</Parameters>'
            '</Query>'
        ).format(report_id=report_id))
        soup = BeautifulSoup(r.text, 'lxml-xml')
        policy_id = soup.Row['POLISA']
        url = self.get_my_policy_pdf_url(policy_id)
        filename = 'copy_policy/{}.pdf'.format(policy_id)
        self.add_file_to_zipfile(zipfile, url, filename)

    def download_copy_policy_documents(self, zipfile):
        ticket = self.get_ticket(selected_app='client-view')
        self.request_client_view(ticket)
        policies = self.get_policies(ticket)

        policy_ids = []

        for policy in policies:
            topic_id = policy['topicId']

            if topic_id not in COPY_POLICY_TOPIC_IDS:
                continue

            policy_id = policy['policySubjectId']

            # policySubjectId is None for mortgage (99),
            # but we check for repeats for other policies
            if policy_id and policy_id in policy_ids:
                continue
            else:
                policy_ids.append(policy_id)

            method_name = 'download_copy_policy_document_{}'.format(topic_id)
            getattr(self, method_name)(zipfile, policy)

    def get_periodic_reports_params(self):
        ticket = self.get_ticket(selected_app='quarter-reports')
        r = self.session.get(DIMUT_WEB_DOCS_LOGIN_URL, params={
            'h': '0',
            'i': '1',
            'd': '1',
            'applicationID': 'quarter-reports',
            'flowGuid': str(uuid.uuid4()),
            'RedirectUrl': '/',
            'ticket': ticket,
        })
        session_id = periodic_reports_session_id_re.search(r.text).group(1)
        csrf_token = periodic_reports_csrf_token_re.search(r.text).group(1)
        return {
            'session_id': session_id,
            'csrf_token': csrf_token,
        }

    def download_periodic_reports(self, zipfile):
        params = self.get_periodic_reports_params()
        r = self.session.post(DIMUT_WEB_DOCUMENTS_URL, data={
            'sessionid': params['session_id'],
            'csrfkey': params['csrf_token'],
        })
        documents_count = len(r.json()['data']['lines'])
        documents_to_download = min(
            MAX_PERIODIC_REPORTS_DOCUMENTS_TO_DOWNLOAD,
            documents_count,
        )
        for i in range(documents_to_download):
            url = '{}?docId={}&csrfkey={}'.format(
                DIMUT_WEB_SHOW_FILE_URL,
                i,
                params['csrf_token'],
            )
            filename = 'periodic_reports/{}.pdf'.format(i)
            self.add_file_to_zipfile(zipfile, url, filename)

    def download_all(self):
        zipfile = ZipFile('documents.zip', 'w')
        self.download_copy_policy_documents(zipfile)
        self.download_periodic_reports(zipfile)
        zipfile.close()
