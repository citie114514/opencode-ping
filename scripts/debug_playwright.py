from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.set_default_timeout(90000)
    
    # Go to main page first
    page.goto('https://www.itdog.cn/ping/')
    page.wait_for_timeout(3000)
    
    # Fill in the host
    page.fill('#host', 'github.citie.dpdns.org')
    page.wait_for_timeout(1000)
    
    # Click the test button (use index)
    buttons = page.query_selector_all('button')
    for btn in buttons:
        text = btn.inner_text()
        if '单次' in text or '测试' in text:
            btn.click()
            break
    
    page.wait_for_timeout(15000)
    
    # Check current URL
    print(f'Current URL: {page.url}')
    
    # Check node count
    expected = page.evaluate('() => window.check_node_num || 0')
    actual_rows = page.query_selector_all('tr.node_tr')
    
    print(f'Expected: {expected}, Actual rows: {len(actual_rows)}')
    
    # Get first few nodes
    for i, row in enumerate(actual_rows[:5]):
        cells = row.query_selector_all('td')
        if cells:
            loc = cells[0].inner_text().strip()
            lat = cells[3].inner_text().strip()
            print(f'Node {i}: {loc} -> {lat}')
    
    browser.close()
