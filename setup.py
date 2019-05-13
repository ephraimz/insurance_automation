import setuptools


with open('README.md', 'r') as f:
    long_description = f.read()


setuptools.setup(
    name='insurance-automation',
    version='0.1.0',
    description='Insurance Automation',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://ezsave.visualstudio.com/insurance_automation',
    packages=setuptools.find_packages(),
    install_requires=[
        'beautifulsoup4==4.6.3',
        'lxml==4.2.5',
        'requests==2.20.1',
        'user-agent==0.1.9',
        'WeasyPrint==47',
    ],
)
