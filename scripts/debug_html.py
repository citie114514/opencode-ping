import requests
from bs4 import BeautifulSoup

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
})

resp = session.get('https://www.itdog.cn/ping/github.citie.dpdns.org', timeout=30)
soup = BeautifulSoup(resp.text, 'lxml')

# Check tables
tables = soup.find_all('table')
print(f'Found {len(tables)} tables')
for i, t in enumerate(tables):
    table_id = t.get('id')
    table_class = t.get('class')
    rows = t.find_all('tr')
    node_rows = t.find_all('tr', class_='node_tr')
    print(f'Table {i}: id={table_id}, rows={len(rows)}, node_tr={len(node_rows)}')

# Check for script tags with data
scripts = soup.find_all('script')
for script in scripts:
    text = script.string or ''
    if 'check_node_num' in text or 'node_tr' in text:
        print(f'\nFound script with node data:')
        print(text[:500])
        break

# Try to get the actual content
table = soup.find('table', {'id': 'simpletable'})
if table:
    rows = table.find_all('tr', class_='node_tr')
    print(f'\nFound {len(rows)} node rows in simpletable')
    if rows:
        # Print first row structure
        first_row = rows[0]
        cells = first_row.find_all('td')
        print(f'First row cells: {len(cells)}')
        for i, cell in enumerate(cells[:6]):
            print(f'  Cell {i}: {cell.get_text(strip=True)[:50]}')
else:
    print('\nNo simpletable found')
