import time


class InsuranceAutomationResource:
    def __init__(self):
        self.data = {}

    def get_current_time(self):
        return int(time.time()*1000)

    def get_request_verification_token(self, soup):
        token = soup.find('input', attrs={
            'name': '__RequestVerificationToken'
        })['value']
        return token

    def add_file_to_dict(self, d, url, filename):
        r = self.session.get(url)
        if r.status_code != 200:
            return False
        d[filename] = r.content
        return True
