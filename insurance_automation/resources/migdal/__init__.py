import json
from urllib.parse import urlencode

import requests

from insurance_automation.common.utils import has_all_needed_keys
from ..base import InsuranceAutomationResource



BASE_URL = 'https://www.migdal.co.il'

SESSION_GENARETOR_URL = BASE_URL + '/Handlers/SessionGenaretor.ashx'
USER_LOGIN_URL = BASE_URL + '/Handlers/UserLogin.ashx'
REPORTS_HANDLER_URL = BASE_URL + '/Handlers/Reports/ReportsHandler.ashx'
IMAGE_DOCUMENT_URL = BASE_URL + '/Handlers/ImageDocument.ashx'
POLICY_RIKUZ_URL = (
    BASE_URL + '/handlers/rikuzextended/RikuzExtendedHandler.ashx'
)
POLICIES_LIST_URL = (
    BASE_URL + '/handlers/newmyaccount/policiesListHandler.ashx'
)
POLICIES_DOCUMENT_URL = (
    BASE_URL + '/handlers/OrderDocuments/orderdocumentshandler.ashx'
)
MIGDAL_EVENT_URL = BASE_URL + '/handlers/newmyaccount/eventsHandler.ashx'

MIGDAL_EVENT_REFERER = BASE_URL + '/He/MyAccount/Pages/Rikuzextended.aspx'

RELEVANT_REPORTS = ('דוח רבעוני', 'דוח שנתי מקוצר', 'דוח שנתי')


def get_image_document_url(doc_id):
    return '{}?action=1&docId={}'.format(IMAGE_DOCUMENT_URL, doc_id)


def get_policy_list(response_data_value):
    for k, v in response_data_value.items():
        if 'list' in k:
            return v
    return None


def get_migdal_event_payload(policies):
    needed_keys = ('policyType', 'PolicyNumber', 'sugPolicy')

    for policy in policies:
        if has_all_needed_keys(policy, needed_keys):
            payload = {
                'action': '1',
                'policyType': policy['policyType'],
                'policyNumber': policy['PolicyNumber'],
                'sugKeren': policy.get('sugKeren', 0),
                'sugPolicy': policy['sugPolicy'],
            }
            return payload

    return None


def is_relevant_report(report):
    for report_type in RELEVANT_REPORTS:
        if report_type in report['HebrewDocType']:
            return report_type
    return None


class Migdal(InsuranceAutomationResource):
    def authenticate(self, user_id):
        self.session = requests.Session()

        response = self.session.get(SESSION_GENARETOR_URL)

        params = {'type': 'UserLoginReq'}
        payload = {
            'data': json.dumps({
                'idNumber': user_id,
                'cellPhone': '',
                'currentStep': '1',
                'loginOption': '1',
            }, separators=(',', ':')),
        }

        response = self.session.post(
            USER_LOGIN_URL,
            data=payload,
            params=params,
        )
        response_data = response.json()
        otp_send_to = response_data.get('OTPSendTo')

        return {'logged_in': bool(otp_send_to)}

    def confirm_authentication(self, code):
        response = self.session.get(USER_LOGIN_URL, params={
            'type': 'UserLoginReq',
            'data': json.dumps({
                'currentStep': '2',
                'otp': code
            }, separators=(',', ':')),
        })

        response_data = response.json()
        redirect_to = response_data.get('RedirectTo')

        return bool(redirect_to)

    def get_policies(self):
        response = self.session.get(
            POLICY_RIKUZ_URL,
            params={'action': 'rikuz'},
        )
        response_data = response.json()

        policies = []

        for k, v in response_data.items():
            if not v or k in ('isMdpOrCrm', 'currentUser', 'dProducts'):
                continue
            l = get_policy_list(v)
            if l:
                policies += l

        payload = get_migdal_event_payload(policies)

        if payload:
            response = self.session.post(
                MIGDAL_EVENT_URL,
                data=payload,
                headers={
                    'Referer': MIGDAL_EVENT_REFERER
                },
            )

        response = self.session.get(
            POLICIES_LIST_URL,
            params={'isSite': '1'},
        )
        response_data = response.json()

        policies = [
            {
                'PolicyName': policy['text'],
                'PolicyValue': policy['value'],
                'PolicyNumber': policy['value'].split('|', 1)[0],
            }
            for policy in response_data
        ]

        return policies

    def download_copy_policy_documents(self, zipfile):
        policies = self.get_policies()

        relevant_documents = []

        for policy in policies:
            response = self.session.get(
                POLICIES_DOCUMENT_URL,
                params={
                    'action': 'Get',
                    'p': policy['PolicyNumber'],
                    'ip': '0',
                },
            )
            response_data = response.json()
            documents = response_data.get('documents')

            if documents:
                relevant_documents += response_data['documents']

        for relevant_document in relevant_documents:
            url = get_image_document_url(relevant_document['DocId'])
            filename = 'מסמכי פוליסה/{}/{}.pdf'.format(
                relevant_document['PolicyNo'],
                relevant_document['DocTypeName'],
            )
            self.add_file_to_zipfile(zipfile, url, filename)

    def download_periodic_reports(self, zipfile):
        response = self.session.get(
            REPORTS_HANDLER_URL,
            params={'action': '1'},
        )
        reports = response.json()

        reports = reports['Data']
        relevant_reports = {}
        for report in reports[::-1]:
            report_type = is_relevant_report(report)
            if report_type and not report_type in relevant_reports:
                relevant_reports[report_type] = report
            if len(relevant_reports) == len(RELEVANT_REPORTS):
                break

        for report_name, report_dict in relevant_reports.items():
            url = get_image_document_url(report_dict['DocId'])
            filename = 'דוחות שנתיים/{} {}.pdf'.format(
                report_dict['DocDate'].replace('/', '.'),
                report_name,
            )
            self.add_file_to_zipfile(zipfile, url, filename)

    def download_all(self, zipfile):
        self.download_copy_policy_documents(zipfile)
        self.download_periodic_reports(zipfile)
