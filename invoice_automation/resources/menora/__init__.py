import datetime
from urllib.parse import urlencode

import requests
from bs4 import BeautifulSoup

from ..base import InvoiceAutomationResource
from .utils import change_url

BASE_URL = 'https://www.menoramivt.co.il'

PORTAL_URL = BASE_URL + '/wps/portal/'


class Menora(InvoiceAutomationResource):
    def authenticate(self, user_id, phone):
        self.session = requests.Session()

        response = self.session.get(PORTAL_URL)

        soup = BeautifulSoup(response.content, 'html.parser')

        auth_url = BASE_URL + soup.select_one(
            'div[id*=cellPhonePrefixStore_ns_]'
        ).attrs['url'].replace(
            'DojoCellphonePrefixServlet',
            'MnGetOneTimePasswordServlet'
        )

        form = soup.find('form', {'method': 'POST'})

        self.data['auth_confirm_url'] = BASE_URL + form.attrs['action']

        response = self.session.post(
            auth_url,
            params={
                'idNumber': user_id,
                'telephonePrefix': '972',
                'telephoneNumber': phone,
            },
        )

        response_data = response.json()

        if response_data['items'][0]['errorCode']:
            return {'logged_in': False}

        self.data.update({
            'user_id': user_id,
            'phone': phone,
        })

        return {'logged_in': True}

    def confirm_authentication(self, code):
        params = {
            'MnHomePageLoginPortletUserid': 'OTP{:015d}'.format(
                int(self.data['user_id'])
            ),
            'MnHomePageLoginPortletPassword': code,
            'MnHomePageLoginPortletOtpPhonePrefix': self.data['phone'][:3],
            'MnHomePageLoginPortletOtpTelephone': self.data['phone'][3:],
            'MnHomePageLoginPortletFormSubmit': 'Submit',
        }

        response = self.session.post(
            self.data['auth_confirm_url'],
            params=params,
            allow_redirects=False,
        )

        if 'LtpaToken2' not in self.session.cookies:
            return False

        redirect_url = response.headers['Location']

        response = self.session.get(redirect_url)

        soup = BeautifulSoup(response.content, 'html.parser')

        a = soup.find('a', {'id': 'myreports'})

        self.data['my_reports_url'] = BASE_URL + a.attrs['href']

        return True

    def get_periodic_reports(self, get_reports_url):
        now = datetime.datetime.now()

        payload = {
            'reportType': '1',
            'rawPeriods': '{},{}'.format(now.year, now.year-2),
            'periodType': 'Y',
        }

        response = self.session.post(
            BASE_URL + get_reports_url,
            data=payload,
        )

        response_data = response.json()
        items = response_data['items']

        return items

    def download_periodic_reports(self, zipfile):
        response = self.session.get(self.data['my_reports_url'])

        soup = BeautifulSoup(response.content, 'html.parser')

        year_store_url = soup.select_one(
            "div[id*='yearStore_ns']"
        ).attrs['url']

        get_reports_url = change_url(
            year_store_url,
            'DojoGetReportsListServlets'
        )

        reports = self.get_periodic_reports(get_reports_url)

        get_report_file_url = change_url(
            year_store_url,
            'DojoGetReportFile'
        )

        for report in reports:
            url = '{}{}?{}'.format(
                BASE_URL,
                get_report_file_url,
                urlencode({'fileSequence': report['Link']}),
            )
            filename = 'דוחות שנתיים/{}/{}/{}-{}.pdf'.format(
                report['Period'],
                report['Domain'],
                report['Name'],
                report['id'],
            )
            self.add_file_to_zipfile(zipfile, url, filename)

    def download_all(self, zipfile):
        self.download_periodic_reports(zipfile)
