import datetime
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

TIME_BETWEEN_QSID_AND_SID = 5000

COPY_POLICY_TOPIC_IDS = (10,)

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

    def get_dashboard_metadata(self, report_id, filter_params):
        current_time = self.get_current_time()
        r = self.session.get(HTTP_PROXY_URL, params={
            'Action': 'GetDashboardMetaData',
            'UID': report_id,
            'FilterParams': filter_params,
            'Sid': current_time,
            'QSID': current_time - TIME_BETWEEN_QSID_AND_SID,
        })
        r.raise_for_status()
        return r.text

    def get_policy_document_xml(self, metadata):
        metadata_soup = BeautifulSoup(metadata, 'lxml-xml')
        export_soup = BeautifulSoup('<App/>', 'lxml-xml')

        dashboard = metadata_soup.Dashboard

        export_soup.App['Name'] = dashboard.get('ReportName') or 'Dashboard'

        containers = dashboard.select('Layouts > Layout > Region > Container')

        dashboard_items = export_soup.new_tag('DashboardItems')

        for container in containers:
            if container.get('DisplayAsPopup'):
                continue

            cells = container.find_all('Cell', recursive=False)

            for cell in cells:
                module_id = cell.get('ModuleId')

                if not module_id:
                    continue

                dashboard_item = dashboard.find('DashboardItem', Id=module_id)

                if not dashboard_item:
                    continue

                if dashboard_item.find('PublishSettings', DisablePublish='1'):
                    continue

                dashboard_items.append(dashboard_item)

        export_soup.App.append(dashboard_items)
        export_soup.App.append(metadata_soup.find('DataCache'))
        export_soup.App.append(dashboard.DashboardDataSources)
        export_soup.App['ColorTheme'] = dashboard['ColorTheme']
        export_soup.App['Date'] = datetime.date.today().strftime('%d/%m/%Y')

    def download_policy_documents(self):
        ticket = self.get_ticket(selected_app='client-view')
        self.request_client_view(ticket)
        policies = self.get_policies(ticket)
        for policy in policies:
            report_id = self.get_report_id(policy)
            filter_params = 'policySubjectId|{}'.format(
                policy['policySubjectId']
            )
            metadata = self.get_dashboard_metadata(report_id, filter_params)

    def download_copy_policy_document_10(self, zipfile, policy):
        policy_id = policy['policySubjectId']
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
        filename = 'copy_policy/{}.pdf'.format(policy_id)
        self.add_file_to_zipfile(zipfile, url, filename)

    def download_copy_policy_document_30(self, zipfile, policy):
        ticket = self.get_ticket('lobby_health')
        r = self.session.get(HEALTH_GO_TO_POLICY_DOCUMENT_URL, params={
            ticket: ticket,
            policyNumber: policy['policySubjectId'],
            topicId: policy['topicId'],
            ctime: self.get_current_time(),
        })

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

            if not policy_id or policy_id == '0' or policy_id in policy_ids:
                continue

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
