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

    def add_file_to_zipfile(self, zipfile, url, filename):
        r = self.session.get(url)
        if r.status_code != 200:
            return False
        zipfile.writestr(filename, r.content)
        return True

    def finalize_zipfile(self, zipfile):
        """
        If there are no files in the zipfile, adds a text
        file informing the user that no documents were
        downloaded.
        """
        if not zipfile.namelist():
            zipfile.writestr(
                'no_documents_downloaded.txt',
                'No documents were downloaded.\n',
            )