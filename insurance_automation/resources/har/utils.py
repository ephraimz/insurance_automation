from bs4 import BeautifulSoup


def parse_tables(soup):
    data = []
    for table in soup.find_all('table'):
        if not table.thead:
            continue

        headers = [element.string for element in table.thead.find_all('th')]
        rows = table.tbody.find_all('tr')

        for row in rows:
            result = {
                header: cell.string
                for header, cell in zip(
                    headers,
                    row.find_all('td')
                )
            }
            data.append(result)

    return data


def find_column_position(table, column_name):
    if not table.thead:
        return None

    for i, element in enumerate(table.thead.find_all('th')):
        if element.string == column_name:
            return i

    return None


def format_tables(soup):
    for table in soup.find_all('table'):
        index = find_column_position(table, 'מספר פוליסה')
        if not index:
            continue
        rows = table.find('tbody').find_all('tr')
        for row in rows:
            cell = row.find_all('td')[index]
            cell.string = cell.string.lstrip('0')


def create_table(soup, data, headers, colour):
    table = soup.new_tag(
        'table',
        border=1,
        style='border-spacing:0;page-break-after:always;'
    )

    thead = soup.new_tag('thead')
    table.append(thead)

    tbody = soup.new_tag('tbody')
    table.append(tbody)

    headers_tr = soup.new_tag('tr')
    thead.append(headers_tr)

    for header in headers:
        th = soup.new_tag(
            'th',
            style='padding:10px;background-color:{}'.format(colour)
        )
        th.string = header
        headers_tr.append(th)

    for row in data:
        tr = soup.new_tag('tr')
        tbody.append(tr)

        for cell in row:
            td = soup.new_tag('td', style='padding:8px')
            td.string = cell
            tr.append(td)

    return table


def get_har_soup(response):
    soup = BeautifulSoup(response.content, 'html.parser')

    soup.body.find('script').decompose()
    soup.head.find('link').decompose()

    data = parse_tables(soup)
    format_tables(soup)

    span = soup.new_tag('span')
    span.string = 'חישובים'
    p = soup.new_tag('p', style='font-weight:bold')
    p.append(span)

    soup.body.div.append(p)

    sum_without_car_insurance = sum(
        float(value['פרמיה בש"ח']) if value['סוג פרמיה'] == 'חודשית'
        else (float(value['פרמיה בש"ח']) / 12)
        for value in data if value['ענף ראשי'] != 'ביטוח רכב'
    )

    table = create_table(
        soup,
        [['{:0.2f}'.format(sum_without_car_insurance)]],
        ['תשלום חודשי ביטוח ללא ביטוח רכב'],
        '#fba4ec'
    )

    soup.body.div.append(table)

    return soup
