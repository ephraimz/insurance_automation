class InvoiceAutomationResource:
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
