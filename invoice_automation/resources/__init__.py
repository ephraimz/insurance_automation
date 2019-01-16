class InvoiceAutomationResource:
    def add_file_to_zipfile(self, zipfile, url, filename):
        r = self.session.get(url)
        if r.status_code != 200:
            return False
        zipfile.writestr(filename, r.content)
        return True
