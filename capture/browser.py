from playwright.sync_api import Page, sync_playwright

def launch_browser():
    pw = sync_playwright().start()
    browser = pw.chromium.launch(
        headless=False,
        args=["--disabled-infobars", "--start-maximized"]
    )
    context = browser.new_context(
        viewport=None,  # Use actual window size
        record_video_dir="output/runs"
    )
    # Set navigation timeout on the context
    context.set_default_navigation_timeout(60000)  # 60 seconds
    context.set_default_timeout(60000)  # 60 seconds for all operations
    page = context.new_page()
    return pw, browser, context, page