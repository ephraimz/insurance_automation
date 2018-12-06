import datetime
import time
import uuid
from urllib.parse import parse_qs
from urllib.parse import urljoin

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

TIME_BETWEEN_QSID_AND_SID = 5000


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
            'selectedApp': 'client-view',
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
        ticket = self.get_ticket()
        self.request_client_view(ticket)
        policies = self.get_policies(ticket)
        for policy in policies:
            report_id = self.get_report_id(policy)
            filter_params = 'policySubjectId|{}'.format(
                policy['policySubjectId']
            )
            metadata = self.get_dashboard_metadata(report_id, filter_params)
