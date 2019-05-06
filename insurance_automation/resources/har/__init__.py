import os

from urllib.parse import parse_qs
from urllib.parse import urlparse

import requests
import weasyprint
from bs4 import BeautifulSoup

from ..base import InsuranceAutomationResource

from .utils import get_har_soup


ROOT_URL = 'https://harb.cma.gov.il'
HOME_URL = ROOT_URL + '/Home/'
CHECK_CAPTCHA_URL = ROOT_URL + '/Captcha/CheckCaptcha/'
SAVE_USER_DETAILS_URL = ROOT_URL + '/Home/SaveUserDetails/'
PRINTER_URL = ROOT_URL + '/Exports/ExportToPrinter'
EXCEL_URL = ROOT_URL + '/Exports/ExportToExcel'
RESULTS_URL = ROOT_URL + '/Results'

CSS_FILE_PATH = os.path.join(os.path.dirname(__file__), 'har_pdf.css')


class Har(InsuranceAutomationResource):
    def get_captcha(self):
        self.session = requests.Session()

        response = self.session.get(HOME_URL)
        soup = BeautifulSoup(response.content, 'html.parser')

        captcha_img = soup.find('img', {
            'id': 'LocateBeneficiariesCaptcha_CaptchaImage',
        })

        response = self.session.get(ROOT_URL + captcha_img['src'])

        pr = urlparse(captcha_img['src'])

        instance_id = parse_qs(pr.query)['t'][0]

        self.data['instance_id'] = instance_id

        return response.content

    def send_captcha_response(self, response):
        params = {
            'CaptchaId': 'LocateBeneficiariesCaptcha',
            'InstanceId': self.data['instance_id'],
            'UserInput': response,
        }

        res = self.session.get(CHECK_CAPTCHA_URL, params=params)

        return res.text == 'true'

    def send_user_info(self, user_info):
        passport_issued = 'true' if user_info['passport_issued'] else 'false'
        exit_country = 'true' if user_info['exit_country'] else 'false'

        payload = {
            'MainData': {
                'UserId': user_info['user_id'],
                'Day': user_info['issue_day'],
                'Month': user_info['issue_month'],
                'Year': user_info['issue_year'],
            },
            'DeceasedData': {
                'UserId': None,
                'Day': None,
                'Month': None,
                'Year': None,
            },
            'IsPassportOutInLast': passport_issued,
            'IsCuntryOutInLast': exit_country,
        }

        r = self.session.post(SAVE_USER_DETAILS_URL, json=payload)

        if r.status_code == 200:
            return {'success': True}

        return {'success': False, 'error': r.text}

    def download_all(self, zipfile):
        self.session.get(RESULTS_URL, params={'id': '-1'})

        printer_response = self.session.get(PRINTER_URL)
        excel_response = self.session.get(EXCEL_URL)

        soup = get_har_soup(printer_response)

        weasyprint_html = weasyprint.HTML(string=str(soup))
        weasyprint_css = weasyprint.CSS(filename=CSS_FILE_PATH)
        pdf = weasyprint_html.write_pdf(stylesheets=[weasyprint_css])

        zipfile.writestr('har.pdf', pdf)
        zipfile.writestr('har.xlsx', excel_response.content)
